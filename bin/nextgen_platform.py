#!/usr/bin/env python3
"""
Data-driven Platform Adapter for NextGen Plasma Bigscreen.

Separates hardware/environment discovery from runtime policy using pure Python 3 stdlib:
- Sanitization helpers (strip usernames/$HOME, serial numbers, MAC addresses, UUIDs)
- GPU & video decode adapter (Intel iHD vs legacy i965, AMD, NVIDIA, unknown)
- Display & mode policy engine (independently testable from kscreen-doctor)
- Strictly read-only HDMI audio inspection via WirePlumber (wpctl)
- Normalized remote action vocabulary, data-driven remote profiles, and HDMI-CEC classifier
"""

from __future__ import annotations

import copy
import json
import logging
import os
import pwd
import re
import shutil
import subprocess
from typing import Any, Callable

LOGGER = logging.getLogger("nextgen-platform")

# ---------------------------------------------------------------------------
# Sanitization helpers
# ---------------------------------------------------------------------------

_MAC_RE = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b")
_UUID_RE = re.compile(
    r"\b[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\b"
)
_HOME_PATH_RE = re.compile(r"(?:/var)?/home/[A-Za-z0-9._-]+")
_SERIAL_KV_RE = re.compile(
    r"(\b(?:serial(?:[\s_-]*number)?|uniq|edid_serial|machine[_-]?id)\s*[:=]\s*)([^\s,;\"']+)",
    re.IGNORECASE,
)

_SENSITIVE_KEY_EXACT = {
    "serial",
    "serial_number",
    "serialnumber",
    "edid_serial",
    "uniq",
    "mac",
    "mac_address",
    "macaddress",
    "uuid",
    "machine_id",
    "machineid",
}

_SENSITIVE_KEY_SUBSTRINGS = (
    "serial",
    "mac_addr",
    "machine_id",
)


def _detect_current_user_and_home(
    home_dir: str | None = None, username: str | None = None
) -> tuple[str, str]:
    resolved_home = home_dir if home_dir is not None else os.path.expanduser("~")
    resolved_user = username
    if resolved_user is None:
        resolved_user = os.environ.get("USER") or ""
        if not resolved_user:
            try:
                resolved_user = pwd.getpwuid(os.getuid()).pw_name
            except Exception:
                resolved_user = ""
    if not resolved_user and resolved_home:
        base = os.path.basename(resolved_home.rstrip("/"))
        if base and base not in {"root", "home", "Users"}:
            resolved_user = base
    return resolved_home, resolved_user


def sanitize_text(
    text: str,
    home_dir: str | None = None,
    username: str | None = None,
) -> str:
    """Redact $HOME paths, usernames, serial fields, MAC addresses, and UUIDs from text."""
    if not text:
        return text
    resolved_home, resolved_user = _detect_current_user_and_home(home_dir, username)
    out = str(text)

    if resolved_home and resolved_home not in {"/", "$HOME"}:
        trimmed = resolved_home.rstrip("/")
        if trimmed:
            out = out.replace(trimmed, "$HOME")
            try:
                real_home = os.path.realpath(trimmed).rstrip("/")
                if real_home and real_home != trimmed and real_home != "/":
                    out = out.replace(real_home, "$HOME")
            except OSError:
                pass

    out = _HOME_PATH_RE.sub("$HOME", out)
    out = _UUID_RE.sub("<REDACTED_UUID>", out)
    out = _MAC_RE.sub("<REDACTED_MAC>", out)
    out = _SERIAL_KV_RE.sub(r"\1<REDACTED_SERIAL>", out)

    if resolved_user and len(resolved_user) >= 3 and resolved_user.lower() not in {
        "root",
        "user",
        "bin",
        "sys",
        "adm",
    }:
        user_re = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(resolved_user)}(?![A-Za-z0-9_])")
        out = user_re.sub("<USER>", out)

    return out


def _is_sensitive_key(key: str) -> str | None:
    low = key.strip().lower()
    if low in _SENSITIVE_KEY_EXACT:
        if "mac" in low:
            return "<REDACTED_MAC>"
        if "uuid" in low or "machine" in low:
            return "<REDACTED_UUID>"
        return "<REDACTED_SERIAL>"
    for sub in _SENSITIVE_KEY_SUBSTRINGS:
        if sub in low:
            if "mac" in low:
                return "<REDACTED_MAC>"
            if "machine" in low:
                return "<REDACTED_UUID>"
            return "<REDACTED_SERIAL>"
    return None


def sanitize_dict(
    obj: Any,
    home_dir: str | None = None,
    username: str | None = None,
) -> Any:
    """Recursively sanitize dicts/lists/strings to strip sensitive local/hardware identifiers."""
    if isinstance(obj, dict):
        cleaned: dict[Any, Any] = {}
        for k, v in obj.items():
            key_str = str(k)
            redaction = _is_sensitive_key(key_str)
            if redaction is not None and v not in (None, "", False):
                cleaned[k] = redaction
            else:
                cleaned[k] = sanitize_dict(v, home_dir=home_dir, username=username)
        return cleaned
    if isinstance(obj, list):
        return [sanitize_dict(item, home_dir=home_dir, username=username) for item in obj]
    if isinstance(obj, tuple):
        return [sanitize_dict(item, home_dir=home_dir, username=username) for item in obj]
    if isinstance(obj, str):
        return sanitize_text(obj, home_dir=home_dir, username=username)
    return obj


# ---------------------------------------------------------------------------
# GPU & Video Decode Adapter
# ---------------------------------------------------------------------------

_LEGACY_INTEL_RENDERER_HINTS = (
    "i965",
    "crocus",
    "haswell",
    "ivybridge",
    "ivy bridge",
    "sandybridge",
    "sandy bridge",
    "ironlake",
    "gma ",
    "gen4",
    "gen5",
    "gen6",
    "gen7",
    "hd graphics 2000",
    "hd graphics 2500",
    "hd graphics 3000",
    "hd graphics 4000",
    "hd graphics 4200",
    "hd graphics 4400",
    "hd graphics 4600",
    "hd graphics 5000",
    "iris graphics 5100",
    "iris pro graphics 5200",
)

# Representative Intel Gen4-Gen7 PCI device ID prefixes (Ironlake/SandyBridge/IvyBridge/Haswell/BayTrail)
_LEGACY_INTEL_PCI_DEVICE_PREFIXES = (
    "0042",
    "0046",
    "0102",
    "0106",
    "010a",
    "0112",
    "0116",
    "0122",
    "0126",
    "0152",
    "0156",
    "015a",
    "0162",
    "0166",
    "016a",
    "0402",
    "0406",
    "040a",
    "0412",
    "0416",
    "041a",
    "041e",
    "0422",
    "0426",
    "0a02",
    "0a06",
    "0a16",
    "0a1e",
    "0a22",
    "0a26",
    "0a2e",
    "0d12",
    "0d16",
    "0d22",
    "0d26",
    "0f30",
    "0f31",
    "0f32",
    "0f33",
)


def _normalize_hex_id(val: str | None) -> str:
    if not val:
        return ""
    s = str(val).strip().lower()
    if s.startswith("0x"):
        s = s[2:]
    return s.zfill(4) if s else ""


def classify_gpu_vendor(
    pci_vendor_id: str | None = None,
    driver_name: str | None = None,
    renderer_name: str | None = None,
    pci_device_id: str | None = None,
) -> dict[str, Any]:
    """
    Classify GPU vendor, decode stack, render stack, and DRM/Wayland caveats.

    Separates kernel driver, decode API (VA-API/VDPAU/NVDEC), render stack, and DRM/display notes.
    """
    vendor_hex = _normalize_hex_id(pci_vendor_id)
    device_hex = _normalize_hex_id(pci_device_id)
    drv = str(driver_name or "").strip().lower()
    rend = str(renderer_name or "").strip()
    rend_low = rend.lower()

    # Intel
    if vendor_hex == "8086" or drv in {"i915", "xe"} or "intel" in rend_low:
        is_legacy = False
        if drv != "xe":
            if any(hint in rend_low for hint in _LEGACY_INTEL_RENDERER_HINTS):
                is_legacy = True
            elif device_hex in _LEGACY_INTEL_PCI_DEVICE_PREFIXES:
                is_legacy = True
        if is_legacy:
            return {
                "vendor": "intel",
                "profile": "intel-i965",
                "kernel_driver": drv or "i915",
                "vaapi_driver": "i965",
                "decode_apis": ["VA-API (i965 legacy)"],
                "render_stack": "Mesa (crocus/i965)",
                "drm_notes": (
                    "Legacy Intel Gen4-Gen7 GPU: use LIBVA_DRIVER_NAME=i965; "
                    "4K HEVC/VP9/AV1 hardware decode is not available on Gen7 and earlier."
                ),
            }
        render_stack = "Mesa (xe/iris/anv)" if drv == "xe" else "Mesa (iris/anv)"
        return {
            "vendor": "intel",
            "profile": "intel-ihd",
            "kernel_driver": drv or "i915",
            "vaapi_driver": "iHD",
            "decode_apis": ["VA-API (iHD)"],
            "render_stack": render_stack,
            "drm_notes": (
                "Intel Gen8+ GPU: supports Wayland KMS and VA-API via intel-media-driver (iHD)."
            ),
        }

    # AMD
    if (
        vendor_hex == "1002"
        or drv in {"amdgpu", "radeon"}
        or any(tok in rend_low for tok in ("amd", "radeon", "radeonsi", "navi", "vega", "renoir", "phoenix"))
    ):
        is_legacy_radeon = drv == "radeon" or "r600" in rend_low
        return {
            "vendor": "amd",
            "profile": "amd-r600" if is_legacy_radeon else "amd-radeonsi",
            "kernel_driver": drv or "amdgpu",
            "vaapi_driver": "r600" if is_legacy_radeon else "radeonsi",
            "decode_apis": ["VA-API (Mesa radeonsi)", "VDPAU"] if not is_legacy_radeon else ["VA-API (Mesa r600)", "VDPAU"],
            "render_stack": "Mesa (r600)" if is_legacy_radeon else "Mesa (radeonsi/radv)",
            "drm_notes": (
                "AMD GPU: Mesa auto-selects VA-API driver; do not force Intel LIBVA_DRIVER_NAME. "
                "Supports Wayland KMS; HDMI 2.1 4K@120/FRL may require DP-to-HDMI adapter on Linux."
            ),
        }

    # NVIDIA
    if (
        vendor_hex == "10de"
        or drv in {"nvidia", "nvidia-drm", "nvidia-open", "nouveau"}
        or any(tok in rend_low for tok in ("nvidia", "geforce", "quadro", "rtx", "gtx", "nouveau", "nvk"))
    ):
        if drv == "nouveau" or "nouveau" in rend_low or "nvk" in rend_low:
            return {
                "vendor": "nvidia",
                "profile": "nvidia-nouveau",
                "kernel_driver": drv or "nouveau",
                "vaapi_driver": "nouveau",
                "decode_apis": ["VA-API (nouveau limited)", "VDPAU (nouveau limited)"],
                "render_stack": "Mesa (nouveau/nvk)",
                "drm_notes": (
                    "NVIDIA Nouveau open-source driver: limited hardware video decode and "
                    "Wayland performance caveats; do not force Intel LIBVA_DRIVER_NAME."
                ),
            }
        is_open_kmd = drv == "nvidia-open" or "open" in rend_low
        return {
            "vendor": "nvidia",
            "profile": "nvidia-open" if is_open_kmd else "nvidia-proprietary",
            "kernel_driver": drv or "nvidia",
            "vaapi_driver": None,
            "decode_apis": ["NVDEC", "VDPAU"],
            "render_stack": "NVIDIA Proprietary (EGL/GLX/Vulkan)",
            "drm_notes": (
                "NVIDIA GPU uses NVDEC/VDPAU rather than native VA-API (VA-API requires optional "
                "nvidia-vaapi-driver shim). Wayland requires nvidia-drm.modeset=1 and explicit sync "
                "support; do not force Intel LIBVA_DRIVER_NAME."
            ),
        }

    return {
        "vendor": "unknown",
        "profile": "unknown",
        "kernel_driver": drv or "unknown",
        "vaapi_driver": None,
        "decode_apis": [],
        "render_stack": rend or "unknown",
        "drm_notes": "Unrecognized GPU vendor; leaving VA-API and render environment untouched.",
    }


def recommended_vaapi_env(gpu_info: dict[str, Any] | list[dict[str, Any]] | None) -> dict[str, str]:
    """
    Return recommended VA-API environment overrides.

    Sets LIBVA_DRIVER_NAME ONLY for Intel GPUs (`iHD` for intel-ihd, `i965` for intel-i965).
    NEVER forces Intel env vars onto AMD, NVIDIA, or unknown GPUs.
    """
    if not gpu_info:
        return {}
    if isinstance(gpu_info, list):
        if not gpu_info:
            return {}
        # If multiple GPUs exist and include a non-Intel discrete GPU alongside Intel,
        # avoid blindly forcing Intel LIBVA_DRIVER_NAME globally unless all GPUs are Intel.
        vendors = {str(g.get("vendor") or "").lower() for g in gpu_info if isinstance(g, dict)}
        if vendors - {"intel"}:
            return {}
        primary = gpu_info[0]
    elif isinstance(gpu_info, dict):
        primary = gpu_info
    else:
        return {}

    profile = str(primary.get("profile") or "").strip().lower()
    if profile == "intel-ihd":
        return {"LIBVA_DRIVER_NAME": "iHD"}
    if profile == "intel-i965":
        return {"LIBVA_DRIVER_NAME": "i965"}
    return {}


def _run_cmd_safe(cmd: list[str], timeout: float = 3.0) -> tuple[int, str, str]:
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return res.returncode, res.stdout or "", res.stderr or ""
    except (OSError, subprocess.SubprocessError) as exc:
        return -1, "", str(exc)


def _probe_vainfo(vainfo_runner: Callable[[], tuple[int, str, str]] | None = None) -> dict[str, Any]:
    if vainfo_runner is not None:
        rc, out, err = vainfo_runner()
    else:
        exe = shutil.which("vainfo")
        if not exe:
            return {"available": False, "driver": None, "profiles_count": 0, "note": "vainfo not installed"}
        rc, out, err = _run_cmd_safe([exe], timeout=4.0)

    combined = f"{out}\n{err}"
    driver_match = re.search(r"Driver version:\s*(.+)", combined)
    profiles = re.findall(r"^\s*VAProfile[A-Za-z0-9_]+\s*:", combined, re.MULTILINE)
    return {
        "available": rc == 0 and bool(profiles),
        "driver": driver_match.group(1).strip() if driver_match else None,
        "profiles_count": len(profiles),
    }


def _probe_nvidia_smi(
    nvidia_smi_runner: Callable[[], tuple[int, str, str]] | None = None,
) -> dict[str, Any]:
    if nvidia_smi_runner is not None:
        rc, out, err = nvidia_smi_runner()
    else:
        exe = shutil.which("nvidia-smi")
        if not exe:
            return {"available": False, "gpus": [], "note": "nvidia-smi not installed"}
        rc, out, err = _run_cmd_safe(
            [exe, "--query-gpu=name,driver_version", "--format=csv,noheader"],
            timeout=3.0,
        )
    if rc != 0 or not out.strip():
        return {"available": False, "gpus": [], "note": err.strip() or "nvidia-smi unavailable"}
    gpus = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if parts and parts[0]:
            gpus.append(
                {
                    "name": parts[0],
                    "driver_version": parts[1] if len(parts) > 1 else "",
                }
            )
    return {"available": bool(gpus), "gpus": gpus}


def detect_gpus(
    sys_pci_root: str = "/sys/bus/pci/devices",
    vainfo_runner: Callable[[], tuple[int, str, str]] | None = None,
    nvidia_smi_runner: Callable[[], tuple[int, str, str]] | None = None,
) -> list[dict[str, Any]]:
    """
    Discover PCI display controllers and classify kernel driver, decode API, and render stack.
    Strictly read-only and fully testable via injected sysfs root and command runners.
    """
    gpus: list[dict[str, Any]] = []
    if not os.path.isdir(sys_pci_root):
        return gpus

    vaapi_probe = _probe_vainfo(vainfo_runner=vainfo_runner)
    nvidia_probe: dict[str, Any] | None = None

    for slot in sorted(os.listdir(sys_pci_root)):
        dev_dir = os.path.join(sys_pci_root, slot)
        class_path = os.path.join(dev_dir, "class")
        if not os.path.isfile(class_path):
            continue
        try:
            with open(class_path, "r", encoding="utf-8") as fh:
                pci_class = fh.read().strip().lower()
        except OSError:
            continue
        # PCI base class 0x03 = Display controller (VGA 0x0300, 3D 0x0302, Display 0x0380)
        if not pci_class.startswith("0x03"):
            continue

        vendor_id = ""
        device_id = ""
        kernel_driver = ""
        try:
            with open(os.path.join(dev_dir, "vendor"), "r", encoding="utf-8") as fh:
                vendor_id = fh.read().strip().lower()
        except OSError:
            pass
        try:
            with open(os.path.join(dev_dir, "device"), "r", encoding="utf-8") as fh:
                device_id = fh.read().strip().lower()
        except OSError:
            pass
        driver_link = os.path.join(dev_dir, "driver")
        if os.path.islink(driver_link):
            try:
                kernel_driver = os.path.basename(os.readlink(driver_link))
            except OSError:
                pass
        elif os.path.isfile(driver_link):
            try:
                with open(driver_link, "r", encoding="utf-8") as fh:
                    kernel_driver = fh.read().strip()
            except OSError:
                pass

        renderer_hint = vaapi_probe.get("driver") or ""
        if _normalize_hex_id(vendor_id) == "10de":
            if nvidia_probe is None:
                nvidia_probe = _probe_nvidia_smi(nvidia_smi_runner=nvidia_smi_runner)
            if nvidia_probe.get("gpus"):
                renderer_hint = nvidia_probe["gpus"][0].get("name") or renderer_hint

        classified = classify_gpu_vendor(
            pci_vendor_id=vendor_id,
            driver_name=kernel_driver,
            renderer_name=renderer_hint,
            pci_device_id=device_id,
        )
        entry: dict[str, Any] = {
            "pci_slot": slot,
            "pci_vendor_id": vendor_id,
            "pci_device_id": device_id,
            "pci_class": pci_class,
            "vendor": classified["vendor"],
            "profile": classified["profile"],
            "kernel_driver": kernel_driver or classified["kernel_driver"],
            "decode_apis": classified["decode_apis"],
            "vaapi_driver": classified["vaapi_driver"],
            "recommended_vaapi_env": recommended_vaapi_env(classified),
            "render_stack": classified["render_stack"],
            "drm_notes": classified["drm_notes"],
            "vaapi_probe": vaapi_probe,
        }
        if classified["vendor"] == "nvidia" and nvidia_probe is not None:
            entry["nvidia_probe"] = nvidia_probe
        gpus.append(entry)

    return gpus


# ---------------------------------------------------------------------------
# Display & Mode Policy Engine (independently testable from kscreen-doctor)
# ---------------------------------------------------------------------------


def select_display_output(
    outputs: list[dict[str, Any]],
    configured_output: str = "auto",
) -> dict[str, Any]:
    """
    Resolve configured or auto-selected display output from parsed kscreen outputs list.

    Never crashes on missing/disconnected outputs; returns structured status + fallback info.
    """
    req = str(configured_output or "auto").strip()
    output_list = [o for o in (outputs or []) if isinstance(o, dict)]
    connected = [o for o in output_list if bool(o.get("connected", True))]

    def _auto_pick(candidates: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str]:
        if not candidates:
            return None, "no_connected_outputs"
        enabled = [o for o in candidates if bool(o.get("enabled", True))]
        pool = enabled if enabled else candidates
        # Prefer explicit primary or priority==1
        for out in pool:
            if out.get("primary") is True or out.get("priority") == 1:
                return out, "auto_primary_enabled" if enabled else "auto_primary_connected"
        # Otherwise prefer first enabled with a currentModeId, else first in pool
        for out in pool:
            if str(out.get("currentModeId") or "").strip():
                return out, "auto_connected_enabled" if enabled else "auto_connected"
        return pool[0], "auto_connected_enabled" if enabled else "auto_connected"

    if req and req.lower() != "auto":
        exact = None
        for out in output_list:
            if str(out.get("name") or "") == req:
                exact = out
                break
        if exact is not None and bool(exact.get("connected", True)):
            return {
                "ok": True,
                "output": exact,
                "output_name": str(exact.get("name") or req),
                "requested_output": req,
                "selection_reason": "configured_exact",
                "fallback": False,
                "error": None,
            }
        # Configured output missing or disconnected -> fall back gracefully to a connected output
        fb_out, _fb_reason = _auto_pick(connected)
        if fb_out is not None:
            return {
                "ok": True,
                "output": fb_out,
                "output_name": str(fb_out.get("name") or ""),
                "requested_output": req,
                "selection_reason": "configured_disconnected_fallback",
                "fallback": True,
                "error": None,
            }
        return {
            "ok": False,
            "output": None,
            "output_name": req,
            "requested_output": req,
            "selection_reason": "no_connected_outputs",
            "fallback": False,
            "error": f"Configured output {req!r} is unavailable and no connected outputs were found",
        }

    picked, reason = _auto_pick(connected)
    if picked is not None:
        return {
            "ok": True,
            "output": picked,
            "output_name": str(picked.get("name") or ""),
            "requested_output": "auto",
            "selection_reason": reason,
            "fallback": False,
            "error": None,
        }
    return {
        "ok": False,
        "output": None,
        "output_name": None,
        "requested_output": "auto",
        "selection_reason": "no_connected_outputs",
        "fallback": False,
        "error": "No connected display outputs found",
    }


def _numeric_mode_id(mode: dict[str, Any]) -> int:
    try:
        return int(str(mode.get("id", "")))
    except ValueError:
        return 999999


def _mode_dims(mode: dict[str, Any]) -> tuple[int, int, float]:
    size = mode.get("size") or {}
    try:
        w = int(size.get("width", 0))
        h = int(size.get("height", 0))
    except (TypeError, ValueError):
        w, h = 0, 0
    try:
        hz = float(mode.get("refreshRate", 0.0))
    except (TypeError, ValueError):
        hz = 0.0
    return w, h, hz


def _detect_output_capabilities(output_obj: dict[str, Any], modes: list[dict[str, Any]]) -> dict[str, Any]:
    max_w = 0
    max_h = 0
    max_hz = 0.0
    has_4k_60 = False
    has_4k_120 = False
    for m in modes:
        w, h, hz = _mode_dims(m)
        if (w * h) > (max_w * max_h):
            max_w, max_h = w, h
        if hz > max_hz:
            max_hz = hz
        if w >= 3840 and h >= 2160:
            if hz >= 59.0:
                has_4k_60 = True
            if hz >= 119.0:
                has_4k_120 = True

    # Never assume HDR or VRR unless explicitly advertised in output_obj
    hdr_advertised = bool(
        output_obj.get("hdr") is True
        or output_obj.get("hdrCapable") is True
        or (isinstance(output_obj.get("capabilities"), dict) and output_obj["capabilities"].get("hdr") is True)
    )
    vrr_advertised = bool(
        output_obj.get("vrrPolicy") not in (None, "", "never", 0)
        or output_obj.get("vrrCapable") is True
        or (isinstance(output_obj.get("capabilities"), dict) and output_obj["capabilities"].get("vrr") is True)
    )
    return {
        "max_resolution": f"{max_w}x{max_h}" if max_w and max_h else None,
        "max_refresh_rate": round(max_hz, 2) if max_hz else None,
        "supports_4k": max_w >= 3840 and max_h >= 2160,
        "supports_4k_60": has_4k_60,
        "supports_4k_120": has_4k_120,
        "hdr_advertised": hdr_advertised,
        "vrr_advertised": vrr_advertised,
    }


def select_modes_for_output(
    output_obj: dict[str, Any],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    """
    Select best UI (1080p/fallback) and Movie/4K modes for a single kscreen output.

    - Returns `mode_4k = None` on 1080p-only displays (never raises).
    - Supports 4K@60, 4K@30, high-refresh 1080p/1440p, and empty mode lists during suspend/resume.
    - Never assumes 4K/120, HDR, or VRR unless explicitly advertised.
    """
    modes = [m for m in (output_obj.get("modes") or []) if isinstance(m, dict)]
    preferred_ids = {str(x) for x in (output_obj.get("preferredModes") or [])}
    current_id = str(output_obj.get("currentModeId") or "")
    current_mode = None
    for m in modes:
        if str(m.get("id", "")) == current_id:
            current_mode = m
            break

    m4k_cfg = cfg.get("mode_4k") or {"width": 3840, "height": 2160, "refresh_rate": 30.0}
    m1080_cfg = cfg.get("mode_1080p") or {"width": 1920, "height": 1080, "refresh_rate": 60.0}

    target_4k_w = int(m4k_cfg.get("width", 3840))
    target_4k_h = int(m4k_cfg.get("height", 2160))
    raw_4k_hz = m4k_cfg.get("refresh_rate", 30.0)
    auto_4k_hz = raw_4k_hz is None or str(raw_4k_hz).strip().lower() == "auto"
    target_4k_hz = 0.0 if auto_4k_hz else float(raw_4k_hz)

    target_ui_w = int(m1080_cfg.get("width", 1920))
    target_ui_h = int(m1080_cfg.get("height", 1080))
    raw_ui_hz = m1080_cfg.get("refresh_rate", 60.0)
    auto_ui_hz = raw_ui_hz is None or str(raw_ui_hz).strip().lower() == "auto"
    target_ui_hz = 0.0 if auto_ui_hz else float(raw_ui_hz)

    best_4k: dict[str, Any] | None = None
    best_4k_score: tuple[Any, ...] | None = None
    best_ui: dict[str, Any] | None = None
    best_ui_score: tuple[Any, ...] | None = None

    for m in modes:
        w, h, hz = _mode_dims(m)
        mid = str(m.get("id", ""))
        num_id = _numeric_mode_id(m)
        is_pref = mid in preferred_ids

        if w == target_4k_w and h == target_4k_h:
            if auto_4k_hz:
                score_4k: tuple[Any, ...] = (0 if is_pref else 1, -round(hz, 4), num_id)
            else:
                # Prefer an EDID-preferred 4K mode if its refresh rate meets/exceeds target
                # (e.g., 4K@60 preferred TV when config has legacy 30.0 default), otherwise closest Hz.
                pref_ok = 0 if (is_pref and hz >= target_4k_hz - 0.15) else 1
                score_4k = (pref_ok, round(abs(hz - target_4k_hz), 4), 0 if is_pref else 1, num_id)
            if best_4k_score is None or score_4k < best_4k_score:
                best_4k_score = score_4k
                best_4k = m

        if w == target_ui_w and h == target_ui_h:
            if auto_ui_hz:
                score_ui: tuple[Any, ...] = (-round(hz, 4), 0 if is_pref else 1, num_id)
            else:
                score_ui = (round(abs(hz - target_ui_hz), 4), num_id)
            if best_ui_score is None or score_ui < best_ui_score:
                best_ui_score = score_ui
                best_ui = m

    mode_1080p_fallback = False
    if best_ui is None and modes:
        # Display does not advertise 1920x1080 (e.g. 1440p-only or 720p-only):
        # gracefully select best available UI mode without crashing.
        mode_1080p_fallback = True
        if current_mode is not None:
            best_ui = current_mode
        else:
            fallback_candidates = []
            for m in modes:
                w, h, hz = _mode_dims(m)
                mid = str(m.get("id", ""))
                fallback_candidates.append(
                    (
                        0 if mid in preferred_ids else 1,
                        abs(h - target_ui_h),
                        -round(hz, 4),
                        _numeric_mode_id(m),
                        m,
                    )
                )
            fallback_candidates.sort(key=lambda t: t[:4])
            best_ui = fallback_candidates[0][4]

    return {
        "current_mode_id": current_id,
        "current_mode": current_mode,
        "mode_4k": best_4k,
        "mode_1080p": best_ui,
        "mode_1080p_fallback": mode_1080p_fallback,
        "advertised_modes_count": len(modes),
        "capabilities": _detect_output_capabilities(output_obj, modes),
    }


def resolve_safe_target_mode(
    kscreen_info: dict[str, Any],
    requested_target: str,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    """
    Resolve a requested target ('4k' or '1080p') safely against advertised modes.

    If the requested mode is unavailable (e.g. requesting '4k' on a 1080p-only display),
    gracefully falls back to the best available UI/current mode with `fallback=True`
    and `reason="mode_unavailable_fallback"`. Never crash-loops or black-screens.
    """
    if requested_target not in {"4k", "1080p"}:
        raise ValueError(f"Unknown target mode: {requested_target!r}")

    if not kscreen_info or kscreen_info.get("available") is False:
        return {
            "ok": False,
            "requested_target": requested_target,
            "resolved_target": None,
            "mode": None,
            "fallback": True,
            "reason": "display_unavailable",
            "error": str((kscreen_info or {}).get("error") or "Display output unavailable"),
        }

    if not bool(kscreen_info.get("connected", True)) or not bool(kscreen_info.get("enabled", True)):
        return {
            "ok": False,
            "requested_target": requested_target,
            "resolved_target": None,
            "mode": None,
            "fallback": True,
            "reason": "display_unavailable",
            "error": (
                f"Display {kscreen_info.get('output') or 'unknown'} is not connected/enabled "
                f"(connected={kscreen_info.get('connected')}, enabled={kscreen_info.get('enabled')})"
            ),
        }

    mode_4k = kscreen_info.get("mode_4k")
    mode_1080p = kscreen_info.get("mode_1080p")
    current_mode = kscreen_info.get("current_mode")

    if requested_target == "4k":
        if mode_4k is not None:
            return {
                "ok": True,
                "requested_target": "4k",
                "resolved_target": "4k",
                "mode": mode_4k,
                "fallback": False,
                "reason": "exact_match",
                "error": None,
            }
        fallback_mode = mode_1080p or current_mode
        if fallback_mode is not None:
            return {
                "ok": True,
                "requested_target": "4k",
                "resolved_target": "1080p" if mode_1080p is not None else "current",
                "mode": fallback_mode,
                "fallback": True,
                "reason": "mode_unavailable_fallback",
                "error": None,
            }
        return {
            "ok": False,
            "requested_target": "4k",
            "resolved_target": None,
            "mode": None,
            "fallback": True,
            "reason": "display_unavailable",
            "error": "No advertised display modes available",
        }

    # requested_target == "1080p"
    if mode_1080p is not None:
        is_fb = bool(kscreen_info.get("mode_1080p_fallback", False))
        return {
            "ok": True,
            "requested_target": "1080p",
            "resolved_target": "1080p",
            "mode": mode_1080p,
            "fallback": is_fb,
            "reason": "mode_unavailable_fallback" if is_fb else "exact_match",
            "error": None,
        }
    if current_mode is not None:
        return {
            "ok": True,
            "requested_target": "1080p",
            "resolved_target": "current",
            "mode": current_mode,
            "fallback": True,
            "reason": "mode_unavailable_fallback",
            "error": None,
        }
    return {
        "ok": False,
        "requested_target": "1080p",
        "resolved_target": None,
        "mode": None,
        "fallback": True,
        "reason": "display_unavailable",
        "error": "No advertised display modes available",
    }


# ---------------------------------------------------------------------------
# Audio Diagnostic Helper (strictly read-only)
# ---------------------------------------------------------------------------

_WPCTL_SINK_RE = re.compile(
    r"^\s*([*])?\s*(\d+)\.\s+(.+?)(?:\s+\[([^\]]+)\])?\s*$"
)


def inspect_hdmi_audio(
    wpctl_runner: Callable[[], tuple[int, str, str]] | None = None,
) -> dict[str, Any]:
    """
    Strictly read-only summary of PipeWire/WirePlumber HDMI audio sinks.

    Reports unavailable honestly if `wpctl` is missing; never claims automatic
    HDMI audio routing or modifies PipeWire state.
    """
    if wpctl_runner is not None:
        rc, out, err = wpctl_runner()
    else:
        exe = shutil.which("wpctl")
        if not exe:
            return {
                "available": False,
                "tool": "wpctl",
                "hdmi_sinks": [],
                "all_sinks_count": 0,
                "default_sink": None,
                "auto_configured": False,
                "note": (
                    "wpctl not found; HDMI audio status unavailable. "
                    "Automatic HDMI audio configuration is not performed."
                ),
            }
        rc, out, err = _run_cmd_safe([exe, "status"], timeout=3.0)

    if rc != 0:
        return {
            "available": False,
            "tool": "wpctl",
            "hdmi_sinks": [],
            "all_sinks_count": 0,
            "default_sink": None,
            "auto_configured": False,
            "error": sanitize_text(err.strip() or f"wpctl exited with code {rc}"),
            "note": (
                "wpctl status failed; HDMI audio status unavailable. "
                "Automatic HDMI audio configuration is not performed."
            ),
        }

    in_audio = False
    in_sinks = False
    all_sinks: list[dict[str, Any]] = []
    hdmi_sinks: list[dict[str, Any]] = []
    default_sink: dict[str, Any] | None = None

    for raw_line in out.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        # Detect top-level section transitions (Audio, Video, Settings)
        if not raw_line.startswith((" ", "\t", "│", "├", "└")):
            in_audio = stripped.startswith("Audio")
            in_sinks = False
            continue
        if not in_audio:
            continue

        clean = re.sub(r"^[│├└─\s]+", "", raw_line).strip()
        if clean.startswith("Sinks:"):
            in_sinks = True
            continue
        if clean.endswith(":") and not clean.startswith("Sinks:"):
            in_sinks = False
            continue
        if not in_sinks:
            continue

        match = _WPCTL_SINK_RE.match(clean)
        if not match:
            continue
        is_default = bool(match.group(1))
        sink_id = int(match.group(2))
        sink_name = sanitize_text(match.group(3).strip())
        vol_info = sanitize_text((match.group(4) or "").strip())
        sink_obj = {
            "id": sink_id,
            "name": sink_name,
            "default": is_default,
            "state": vol_info,
        }
        all_sinks.append(sink_obj)
        if is_default:
            default_sink = sink_obj
        low_name = sink_name.lower()
        if any(tok in low_name for tok in ("hdmi", "displayport", "digital stereo (hdmi", "dp-")):
            hdmi_sinks.append(sink_obj)

    return {
        "available": True,
        "tool": "wpctl",
        "hdmi_sinks": hdmi_sinks,
        "all_sinks_count": len(all_sinks),
        "default_sink": default_sink,
        "auto_configured": False,
        "note": (
            "Read-only PipeWire/WirePlumber inspection; HDMI audio routing is not "
            "automatically modified."
        ),
    }


# ---------------------------------------------------------------------------
# Remote & HDMI-CEC Adapter Model
# ---------------------------------------------------------------------------

NORMALIZED_ACTIONS: tuple[str, ...] = (
    "up",
    "down",
    "left",
    "right",
    "select",
    "back",
    "home",
    "menu",
    "play_pause",
    "volume_up",
    "volume_down",
    "mute",
    "power",
    "search",
    "long_press",
)

# Linux <linux/input-event-codes.h> constants shared with tv-remote-keymap.py
KEY_ESC = 1
KEY_ENTER = 28
KEY_KPENTER = 96
KEY_POWER = 116
KEY_COMPOSE = 127
KEY_MENU = 139
KEY_SLEEP = 142
KEY_EXIT = 174
KEY_SEARCH = 217
KEY_SELECT = 353
KEY_VOICECOMMAND = 582
KEY_ASSISTANT = 583

XINGWEI_SCANCODE_MAP: dict[int, tuple[int, int, str]] = {
    # Interface 2: USB HID Keyboard (Usage Page 0x07)
    0x070058: (KEY_ENTER, KEY_KPENTER, "HID Keyboard Keypad Enter -> KEY_ENTER"),
    0x070066: (KEY_POWER, KEY_POWER, "HID Keyboard Power -> KEY_POWER"),
    0x0700F8: (KEY_POWER, KEY_SLEEP, "HID Keyboard Sleep -> KEY_POWER (DPMS Toggle)"),
    # Interface 3: USB HID Consumer Control (Usage Page 0x0c)
    0x0C0041: (KEY_ENTER, KEY_SELECT, "HID Consumer Menu Pick (OK) -> KEY_ENTER"),
    0x0C0040: (KEY_COMPOSE, KEY_MENU, "HID Consumer Menu -> KEY_COMPOSE (Qt::Key_Menu)"),
    0x0C0094: (KEY_ESC, KEY_EXIT, "HID Consumer Quit -> KEY_ESC"),
    0x0C0204: (KEY_ESC, KEY_EXIT, "HID Consumer AC Exit -> KEY_ESC"),
    0x0C00CF: (KEY_SEARCH, KEY_VOICECOMMAND, "HID Consumer Voice Command -> KEY_SEARCH"),
    0x0C01CB: (KEY_SEARCH, KEY_ASSISTANT, "HID Consumer Assistant -> KEY_SEARCH"),
    0x0C0030: (KEY_POWER, KEY_POWER, "HID Consumer Power -> KEY_POWER"),
    0x0C0032: (KEY_POWER, KEY_SLEEP, "HID Consumer Sleep -> KEY_POWER (DPMS Toggle)"),
    0x0C0034: (KEY_POWER, KEY_SLEEP, "HID Consumer Sleep Mode -> KEY_POWER (DPMS Toggle)"),
    # Interface 3: USB HID System Control (Usage Page 0x01)
    0x010081: (KEY_POWER, KEY_POWER, "HID System Power Down -> KEY_POWER"),
    0x010082: (KEY_POWER, KEY_SLEEP, "HID System Sleep -> KEY_POWER (DPMS Toggle)"),
}

REMOTE_PROFILES: dict[str, dict[str, Any]] = {
    "xingwei_24g": {
        "name": "xingwei_24g",
        "display_name": "XING WEI 2.4G USB Remote (620a:0407)",
        "transport": "usb_hid_rf",
        "match": {"vendor": "620a", "product": "0407"},
        "requires_evdev_remap": True,
        "scancode_map": dict(XINGWEI_SCANCODE_MAP),
        "supported_actions": [
            "up",
            "down",
            "left",
            "right",
            "select",
            "back",
            "home",
            "menu",
            "play_pause",
            "volume_up",
            "volume_down",
            "mute",
            "power",
            "search",
        ],
        "optional_unavailable_actions": ["long_press"],
        "notes": (
            "Remaps >255 XKB-dropped Consumer Control scancodes and unifies Sleep/Power "
            "scancodes to KEY_POWER via user-space EVIOCSKEYCODE_V2."
        ),
    },
    "generic_keyboard": {
        "name": "generic_keyboard",
        "display_name": "Generic HID Keyboard / Media Remote",
        "transport": "usb_hid_keyboard",
        "match": {"capabilities": ["keyboard"]},
        "requires_evdev_remap": False,
        "scancode_map": {},
        "supported_actions": [
            "up",
            "down",
            "left",
            "right",
            "select",
            "back",
            "home",
            "menu",
            "play_pause",
            "volume_up",
            "volume_down",
            "mute",
            "power",
            "search",
        ],
        "optional_unavailable_actions": ["long_press"],
        "notes": "Standard HID keyboard/media keys work out of the box without scancode remapping.",
    },
    "generic_usb_rf": {
        "name": "generic_usb_rf",
        "display_name": "Generic USB RF / Air-Mouse Remote",
        "transport": "usb_hid_rf",
        "match": {"capabilities": ["consumer_control"]},
        "requires_evdev_remap": False,
        "scancode_map": {},
        "supported_actions": [
            "up",
            "down",
            "left",
            "right",
            "select",
            "back",
            "home",
            "menu",
            "play_pause",
            "volume_up",
            "volume_down",
            "mute",
            "power",
        ],
        "optional_unavailable_actions": ["search", "long_press"],
        "notes": (
            "Consumer-control USB RF/air-mouse template. Add vendor/product and scancode_map "
            "overrides in ~/.config/nextgen-plasmabigscreen/remote-profiles.json if needed."
        ),
    },
    "bluetooth_gamepad": {
        "name": "bluetooth_gamepad",
        "display_name": "Bluetooth / SDL Gamepad Controller",
        "transport": "bluetooth_sdl_gamepad",
        "match": {"capabilities": ["gamepad"]},
        "requires_evdev_remap": False,
        "scancode_map": {},
        "supported_actions": [
            "up",
            "down",
            "left",
            "right",
            "select",
            "back",
            "home",
            "menu",
        ],
        "optional_unavailable_actions": [
            "play_pause",
            "volume_up",
            "volume_down",
            "mute",
            "power",
            "search",
            "long_press",
        ],
        "auto_suppress_input": True,
        "notes": (
            "Managed by plasma-bigscreen-inputhandler (SDL); keep AutoSuppressInput=true "
            "to prevent double-input inside Steam and fullscreen games."
        ),
    },
    "hdmi_cec_native": {
        "name": "hdmi_cec_native",
        "display_name": "Native HDMI-CEC TV Remote",
        "transport": "hdmi_cec",
        "match": {"cec_adapter_type": "native_hdmi_cec"},
        "requires_evdev_remap": False,
        "scancode_map": {},
        "supported_actions": [
            "up",
            "down",
            "left",
            "right",
            "select",
            "back",
            "home",
            "menu",
            "play_pause",
        ],
        "optional_unavailable_actions": [
            "volume_up",
            "volume_down",
            "mute",
            "power",
            "search",
            "long_press",
        ],
        "notes": (
            "Active when a genuine physical HDMI/USB CEC adapter is detected. "
            "Volume and power are typically handled directly by the TV/AVR."
        ),
    },
}

DEFAULT_USER_REMOTE_PROFILES_PATH = os.path.join(
    os.path.expanduser("~"),
    ".config",
    "nextgen-plasmabigscreen",
    "remote-profiles.json",
)


def _parse_scancode_map(raw_map: Any) -> dict[int, tuple[int, int, str]]:
    parsed: dict[int, tuple[int, int, str]] = {}
    if not isinstance(raw_map, dict):
        return parsed
    for raw_sc, spec in raw_map.items():
        try:
            sc = int(str(raw_sc), 0)
        except (TypeError, ValueError):
            continue
        if isinstance(spec, (list, tuple)) and len(spec) >= 2:
            target_kc = int(spec[0])
            default_kc = int(spec[1])
            desc = str(spec[2]) if len(spec) >= 3 else f"0x{sc:06x} -> {target_kc}"
            parsed[sc] = (target_kc, default_kc, desc)
        elif isinstance(spec, dict) and "target_keycode" in spec:
            target_kc = int(spec["target_keycode"])
            default_kc = int(spec.get("default_keycode", target_kc))
            desc = str(spec.get("description") or f"0x{sc:06x} -> {target_kc}")
            parsed[sc] = (target_kc, default_kc, desc)
    return parsed


def load_remote_profiles(
    user_config_path: str | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Load built-in remote profiles merged with optional user JSON overrides from
    ~/.config/nextgen-plasmabigscreen/remote-profiles.json.
    """
    profiles = copy.deepcopy(REMOTE_PROFILES)
    path = user_config_path if user_config_path is not None else DEFAULT_USER_REMOTE_PROFILES_PATH
    if not path or not os.path.isfile(path):
        return profiles

    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except Exception as exc:
        LOGGER.warning("Failed loading user remote profiles from %s: %s", path, exc)
        return profiles

    if not isinstance(raw, dict):
        return profiles
    user_entries = raw.get("profiles") if isinstance(raw.get("profiles"), dict) else raw

    for name, entry in user_entries.items():
        if not isinstance(entry, dict):
            continue
        prof_name = str(entry.get("name") or name).strip()
        if not prof_name:
            continue
        base = copy.deepcopy(profiles.get(prof_name, {}))
        base["name"] = prof_name
        base.setdefault("display_name", prof_name)
        base.setdefault("transport", "usb_hid_rf")
        base.setdefault("match", {})
        base.setdefault("scancode_map", {})
        base.setdefault("supported_actions", [])
        base.setdefault("notes", "")

        for key in ("display_name", "transport", "notes", "auto_suppress_input"):
            if key in entry:
                base[key] = entry[key]

        if isinstance(entry.get("match"), dict):
            merged_match = dict(base.get("match") or {})
            for mk, mv in entry["match"].items():
                if mk in {"vendor", "product"} and mv is not None:
                    merged_match[mk] = _normalize_hex_id(str(mv))
                else:
                    merged_match[mk] = mv
            base["match"] = merged_match

        if "scancode_map" in entry:
            parsed_sc = _parse_scancode_map(entry["scancode_map"])
            merged_sc = dict(base.get("scancode_map") or {})
            merged_sc.update(parsed_sc)
            base["scancode_map"] = merged_sc

        if "requires_evdev_remap" in entry:
            base["requires_evdev_remap"] = bool(entry["requires_evdev_remap"])
        else:
            base["requires_evdev_remap"] = bool(base.get("scancode_map"))

        if isinstance(entry.get("supported_actions"), list):
            base["supported_actions"] = [
                str(a) for a in entry["supported_actions"] if str(a) in NORMALIZED_ACTIONS
            ]
        supported_set = set(base.get("supported_actions") or [])
        base["optional_unavailable_actions"] = [
            a for a in NORMALIZED_ACTIONS if a not in supported_set
        ]

        profiles[prof_name] = base

    return profiles


def evaluate_profile_action_coverage(profile: dict[str, Any]) -> dict[str, Any]:
    """
    Evaluate normalized remote action coverage for a profile.

    Unavailable buttons are explicitly marked optional (`optional_unavailable`), never failures.
    """
    supported_set = {
        str(a) for a in (profile.get("supported_actions") or []) if str(a) in NORMALIZED_ACTIONS
    }
    supported = [a for a in NORMALIZED_ACTIONS if a in supported_set]
    optional_unavailable = [a for a in NORMALIZED_ACTIONS if a not in supported_set]
    actions = {
        action: {
            "supported": action in supported_set,
            "optional": action not in supported_set,
            "status": "supported" if action in supported_set else "optional_unavailable",
        }
        for action in NORMALIZED_ACTIONS
    }
    return {
        "profile": str(profile.get("name") or "unknown"),
        "supported": supported,
        "optional_unavailable": optional_unavailable,
        "actions": actions,
        "has_errors": False,
    }


def classify_cec_adapter(cec_ctl_output: str | None) -> dict[str, Any]:
    """
    Classify `cec-ctl` output into:
    - "none": no CEC adapter / empty output
    - "dp_aux_tunnel": DisplayPort AUX tunnel (`cec-DP-*` / `drm_dp_cec`)
    - "native_hdmi_cec": genuine physical HDMI/USB CEC adapter with Logical Address or RC capability
    - "unsupported_or_unallocated": non-DP adapter with no valid physical/logical CEC allocation
    """
    if not cec_ctl_output or not str(cec_ctl_output).strip():
        return {
            "adapter_type": "none",
            "adapter_name": None,
            "driver_name": None,
            "allocated": False,
            "should_clear_on_apply": False,
            "note": "No CEC adapter detected.",
        }

    text = str(cec_ctl_output)
    low = text.lower()

    drv_match = re.search(r"Driver Name\s*:\s*(.+)", text, re.IGNORECASE)
    adp_match = re.search(r"Adapter Name\s*:\s*(.+)", text, re.IGNORECASE)
    phys_match = re.search(r"Physical Address\s*:\s*([0-9a-fA-F\.]+)", text, re.IGNORECASE)

    driver_name = drv_match.group(1).strip() if drv_match else None
    adapter_name = adp_match.group(1).strip() if adp_match else None
    phys_addr = phys_match.group(1).strip().lower() if phys_match else None

    not_allocated = "logical address          : not allocated" in low or bool(
        re.search(r"logical address\s*:\s*not allocated", low)
    )
    has_logical_addr = (
        bool(re.search(r"logical address\s*:\s*\d+", low))
        or ("logical address" in low and not not_allocated)
    )
    allocated = has_logical_addr and not not_allocated

    is_dp_tunnel = (
        "cec-dp-" in low
        or (driver_name is not None and "drm_dp_cec" in driver_name.lower())
        or (
            adapter_name is not None
            and bool(re.match(r"^(?:cec-)?dp-\d+", adapter_name.strip(), re.IGNORECASE))
        )
    )
    if is_dp_tunnel:
        return {
            "adapter_type": "dp_aux_tunnel",
            "adapter_name": adapter_name,
            "driver_name": driver_name,
            "physical_address": phys_addr,
            "allocated": allocated,
            "should_clear_on_apply": True,
            "note": (
                "DisplayPort AUX CEC tunnel detected (cec-DP-*). Clear logical address on "
                "--apply/--watch only when allocated to avoid DP-AUX TX timeout contention."
            ),
        }

    has_valid_phys = bool(phys_addr and phys_addr != "f.f.f.f")
    has_rc_capability = any(
        tok in low
        for tok in (
            "remote control",
            "allow rc passthrough",
            "playback device",
            "primary device type",
        )
    )

    if allocated or (has_valid_phys and has_rc_capability):
        return {
            "adapter_type": "native_hdmi_cec",
            "adapter_name": adapter_name,
            "driver_name": driver_name,
            "physical_address": phys_addr,
            "allocated": allocated,
            "should_clear_on_apply": False,
            "note": (
                "Genuine physical HDMI/USB CEC adapter detected. Never cleared by "
                "tv-remote-keymap.py so native TV remote control remains functional."
            ),
        }

    return {
        "adapter_type": "unsupported_or_unallocated",
        "adapter_name": adapter_name,
        "driver_name": driver_name,
        "physical_address": phys_addr,
        "allocated": False,
        "should_clear_on_apply": False,
        "note": (
            "Non-DP CEC adapter present but unallocated or lacking valid physical address / "
            "remote control capability; left untouched."
        ),
    }

#!/usr/bin/env python3
"""
User-space evdev scancode-to-keycode remapper & remote input diagnostics for NextGen Plasma Bigscreen.

Supports data-driven remote profiles (built-in XING WEI 2.4G 620a:0407, generic HID keyboard,
generic USB RF, Bluetooth/SDL gamepad, native HDMI-CEC, plus user JSON overrides in
~/.config/nextgen-plasmabigscreen/remote-profiles.json).

Uses the Linux EVIOCSKEYCODE_V2 ioctl via least-privilege uaccess ACL permissions (no root/sudo
or /usr mutations required on atomic Linux distros). Strictly read-only in --status and --diagnose.
"""

from __future__ import annotations

import argparse
import errno
import fcntl
import glob
import json
import os
import shutil
import struct
import subprocess
import sys
import time
from typing import Any, Callable

_BIN_DIR = os.path.dirname(os.path.abspath(__file__))
if _BIN_DIR not in sys.path:
    sys.path.insert(0, _BIN_DIR)

import nextgen_platform  # noqa: E402

VENDOR_ID = "620a"
PRODUCT_ID = "0407"
CEC_DEV = "/dev/cec0"
CEC_OSD_NAME = "Bigscreen TV"

EVIOCGKEYCODE_V2 = 0x80284504
EVIOCSKEYCODE_V2 = 0x40284504

# Keycodes from <linux/input-event-codes.h>
KEY_ESC = nextgen_platform.KEY_ESC
KEY_ENTER = nextgen_platform.KEY_ENTER
KEY_KPENTER = nextgen_platform.KEY_KPENTER
KEY_POWER = nextgen_platform.KEY_POWER
KEY_COMPOSE = nextgen_platform.KEY_COMPOSE
KEY_MENU = nextgen_platform.KEY_MENU
KEY_SLEEP = nextgen_platform.KEY_SLEEP
KEY_EXIT = nextgen_platform.KEY_EXIT
KEY_SEARCH = nextgen_platform.KEY_SEARCH
KEY_SELECT = nextgen_platform.KEY_SELECT
KEY_VOICECOMMAND = nextgen_platform.KEY_VOICECOMMAND
KEY_ASSISTANT = nextgen_platform.KEY_ASSISTANT

# Backward-compatible default scancode map (XING WEI 2.4G 620a:0407)
SCANCODE_MAP: dict[int, tuple[int, int, str]] = dict(nextgen_platform.XINGWEI_SCANCODE_MAP)

UACCESS_REMEDIATION_HINT = (
    "Permission denied on /dev/input/event* (EACCES). Ensure your desktop session is active "
    "on a local graphical seat so systemd-logind grants least-privilege uaccess ACLs "
    "(check `loginctl session-status` and `getfacl /dev/input/event*`). Do not use chmod 777."
)


def _default_cec_runner(args: list[str]) -> tuple[int, str, str]:
    exe = shutil.which("cec-ctl") or "/usr/bin/cec-ctl"
    try:
        res = subprocess.run(
            [exe, *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return res.returncode, res.stdout or "", res.stderr or ""
    except OSError as exc:
        return -1, "", str(exc)


def inspect_cec_adapter(
    cec_dev: str = CEC_DEV,
    cec_ctl_runner: Callable[[list[str]], tuple[int, str, str]] | None = None,
    device_exists_fn: Callable[[str], bool] = os.path.exists,
) -> dict[str, Any]:
    """
    Strictly read-only CEC adapter inspection.
    NEVER calls `cec-ctl --clear` or mutates CEC logical address state.
    """
    if not device_exists_fn(cec_dev):
        info = nextgen_platform.classify_cec_adapter(None)
        info["device"] = cec_dev
        info["present"] = False
        return info

    runner = cec_ctl_runner if cec_ctl_runner is not None else _default_cec_runner
    rc, out, err = runner(["-d", cec_dev])
    if rc != 0 and not out.strip():
        info = nextgen_platform.classify_cec_adapter(None)
        info["device"] = cec_dev
        info["present"] = True
        info["error"] = nextgen_platform.sanitize_text(err.strip() or f"cec-ctl exited {rc}")
        return info

    info = nextgen_platform.classify_cec_adapter(out)
    info["device"] = cec_dev
    info["present"] = True
    return info


def configure_cec(
    verbose: bool = True,
    cec_dev: str = CEC_DEV,
    cec_ctl_runner: Callable[[list[str]], tuple[int, str, str]] | None = None,
    device_exists_fn: Callable[[str], bool] = os.path.exists,
) -> dict[str, Any]:
    """
    Clear logical address ONLY on DisplayPort AUX CEC tunnels (`dp_aux_tunnel`) when allocated.
    NEVER clears genuine native HDMI-CEC adapters (`native_hdmi_cec`).
    """
    info = inspect_cec_adapter(
        cec_dev=cec_dev,
        cec_ctl_runner=cec_ctl_runner,
        device_exists_fn=device_exists_fn,
    )
    info["cleared"] = False
    if not info.get("present"):
        if verbose:
            print(f"{cec_dev}: not present")
        return info

    adapter_type = info.get("adapter_type")
    if adapter_type == "dp_aux_tunnel":
        if info.get("allocated"):
            runner = cec_ctl_runner if cec_ctl_runner is not None else _default_cec_runner
            rc, _out, err = runner(["-d", cec_dev, "--clear"])
            info["cleared"] = rc == 0
            if rc != 0:
                info["clear_error"] = nextgen_platform.sanitize_text(err.strip())
            if verbose:
                print(
                    f"{cec_dev}: cleared logical address on DP-AUX tunnel ({info.get('adapter_name') or 'cec-DP'}) "
                    "to prevent AUX channel contention"
                )
        elif verbose:
            print(f"{cec_dev}: DP-AUX tunnel idle (unallocated)")
        return info

    if adapter_type == "native_hdmi_cec":
        if verbose:
            print(
                f"{cec_dev}: native HDMI-CEC adapter ({info.get('adapter_name') or 'native'}) detected; "
                "leaving intact"
            )
        return info

    if verbose:
        print(f"{cec_dev}: {adapter_type} (left untouched)")
    return info


def _read_sysfs_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def _infer_device_capabilities(name: str, sys_event_path: str) -> list[str]:
    """Infer coarse device capability tags without reading serial/uniq identifiers."""
    caps: list[str] = []
    low = name.lower()
    if any(tok in low for tok in ("gamepad", "controller", "xbox", "dualshock", "dualsense", "8bitdo", "joystick")):
        caps.append("gamepad")
    if any(tok in low for tok in ("consumer control", "remote", "air mouse", "media")):
        caps.append("consumer_control")
    if any(tok in low for tok in ("keyboard", "kbd")):
        caps.append("keyboard")
    if not caps:
        # Check evdev key capability bitmask presence in sysfs if available
        key_cap = _read_sysfs_text(os.path.join(sys_event_path, "device", "capabilities", "key"))
        if key_cap and key_cap != "0":
            caps.append("keyboard")
    return caps


def audit_device_permissions(
    dev_node: str,
    access_fn: Callable[[str, int], bool] = os.access,
) -> dict[str, Any]:
    """Strictly read-only permission check for /dev/input/event* nodes."""
    can_read = bool(access_fn(dev_node, os.R_OK))
    can_write = bool(access_fn(dev_node, os.W_OK))
    result: dict[str, Any] = {
        "readable": can_read,
        "writable": can_write,
        "status": "ok" if (can_read and can_write) else ("read_only" if can_read else "permission_denied"),
    }
    if not (can_read and can_write):
        result["remediation_hint"] = UACCESS_REMEDIATION_HINT
    return result


def discover_input_devices(
    sys_input_root: str = "/sys/class/input",
    dev_input_root: str = "/dev/input",
    access_fn: Callable[[str, int], bool] = os.access,
) -> list[dict[str, Any]]:
    """
    Enumerate /dev/input/event* devices reading ONLY name and vendor:product.
    Explicitly NEVER reads `uniq`, serial numbers, MAC addresses, or phys strings.
    """
    devices: list[dict[str, Any]] = []
    pattern = os.path.join(sys_input_root, "event*")
    for sys_path in sorted(glob.glob(pattern)):
        ev_name = os.path.basename(sys_path)
        vendor = _read_sysfs_text(os.path.join(sys_path, "device", "id", "vendor")).lower()
        product = _read_sysfs_text(os.path.join(sys_path, "device", "id", "product")).lower()
        raw_name = _read_sysfs_text(os.path.join(sys_path, "device", "name"))
        dev_node = os.path.join(dev_input_root, ev_name)
        exists = os.path.exists(dev_node)
        perms = (
            audit_device_permissions(dev_node, access_fn=access_fn)
            if exists
            else {"readable": False, "writable": False, "status": "missing"}
        )
        devices.append(
            {
                "event": ev_name,
                "dev_node": dev_node,
                "exists": exists,
                "name": nextgen_platform.sanitize_text(raw_name or ev_name),
                "vendor": vendor,
                "product": product,
                "vendor_product": f"{vendor}:{product}" if (vendor or product) else "",
                "capabilities": _infer_device_capabilities(raw_name, sys_path),
                "permissions": perms,
            }
        )
    return devices


def match_profiles_for_devices(
    devices: list[dict[str, Any]],
    profiles: dict[str, dict[str, Any]],
    cec_info: dict[str, Any] | None = None,
    forced_profile: str | None = None,
) -> list[dict[str, Any]]:
    """Match connected input devices (and native CEC if present) to remote profiles."""
    if forced_profile:
        prof = profiles.get(forced_profile)
        if not prof:
            return []
        match = prof.get("match") or {}
        want_v = str(match.get("vendor") or "").lower()
        want_p = str(match.get("product") or "").lower()
        matched_devs = []
        for dev in devices:
            if not dev.get("exists"):
                continue
            if want_v and want_p:
                if dev["vendor"] == want_v and dev["product"] == want_p:
                    matched_devs.append(dev)
            else:
                matched_devs.append(dev)
        return [{"profile": prof, "devices": matched_devs, "forced": True}]

    matches: list[dict[str, Any]] = []
    matched_dev_nodes: set[str] = set()

    # 1. Exact vendor:product matches first (highest specificity, e.g. xingwei_24g or user custom profile)
    for prof in profiles.values():
        match = prof.get("match") or {}
        want_v = str(match.get("vendor") or "").lower()
        want_p = str(match.get("product") or "").lower()
        if not (want_v and want_p):
            continue
        devs = [
            d
            for d in devices
            if d.get("exists") and d["vendor"] == want_v and d["product"] == want_p
        ]
        if devs:
            for d in devs:
                matched_dev_nodes.add(d["dev_node"])
            matches.append({"profile": prof, "devices": devs, "forced": False})

    # 2. Native HDMI-CEC match if detected
    if cec_info and cec_info.get("adapter_type") == "native_hdmi_cec":
        for prof in profiles.values():
            if (prof.get("match") or {}).get("cec_adapter_type") == "native_hdmi_cec":
                matches.append({"profile": prof, "devices": [], "forced": False, "cec_matched": True})
                break

    # 3. Capability-based matches for remaining unmatched devices (gamepad, consumer_control, keyboard)
    remaining = [d for d in devices if d.get("exists") and d["dev_node"] not in matched_dev_nodes]
    for cap_key in ("gamepad", "consumer_control", "keyboard"):
        for prof in profiles.values():
            caps = (prof.get("match") or {}).get("capabilities") or []
            if cap_key not in caps:
                continue
            cap_devs = [
                d
                for d in remaining
                if cap_key in (d.get("capabilities") or []) and d["dev_node"] not in matched_dev_nodes
            ]
            if cap_devs:
                for d in cap_devs:
                    matched_dev_nodes.add(d["dev_node"])
                matches.append({"profile": prof, "devices": cap_devs, "forced": False})
                break

    return matches


def find_remote_event_devices(
    vendor_id: str = VENDOR_ID,
    product_id: str = PRODUCT_ID,
    sys_input_root: str = "/sys/class/input",
    dev_input_root: str = "/dev/input",
) -> list[str]:
    """Return sorted list of /dev/input/event* paths belonging to vendor_id:product_id."""
    want_v = vendor_id.lower()
    want_p = product_id.lower()
    matched = []
    for sys_path in sorted(glob.glob(os.path.join(sys_input_root, "event*"))):
        ev_name = os.path.basename(sys_path)
        vendor = _read_sysfs_text(os.path.join(sys_path, "device", "id", "vendor")).lower()
        product = _read_sysfs_text(os.path.join(sys_path, "device", "id", "product")).lower()
        if vendor == want_v and product == want_p:
            dev_node = os.path.join(dev_input_root, ev_name)
            if os.path.exists(dev_node):
                matched.append(dev_node)
    return matched


def get_keycode(fd: int, scancode: int) -> int | None:
    """Query current keycode for a 32-bit HID scancode, or None if not present on this device."""
    buf = bytearray(struct.pack("BBHI", 0, 4, 0, 0) + struct.pack("<I", scancode) + b"\x00" * 28)
    try:
        fcntl.ioctl(fd, EVIOCGKEYCODE_V2, buf, True)
    except OSError:
        return None
    _, _, _, keycode = struct.unpack("BBHI", buf[:8])
    return keycode


def set_keycode(fd: int, scancode: int, keycode: int) -> None:
    """Set keycode for a 32-bit HID scancode using EVIOCSKEYCODE_V2."""
    buf = bytearray(struct.pack("BBHI", 0, 4, 0, keycode) + struct.pack("<I", scancode) + b"\x00" * 28)
    fcntl.ioctl(fd, EVIOCSKEYCODE_V2, buf, True)


def _format_open_error(dev: str, exc: OSError) -> str:
    if exc.errno in (errno.EACCES, errno.EPERM):
        return f"{dev}: permission denied (EACCES). {UACCESS_REMEDIATION_HINT}"
    return f"{dev}: cannot open ({exc})"


def apply_mappings(
    reset: bool = False,
    verbose: bool = True,
    profile_name: str | None = None,
    profiles_config_path: str | None = None,
    sys_input_root: str = "/sys/class/input",
    dev_input_root: str = "/dev/input",
    cec_dev: str = CEC_DEV,
    cec_ctl_runner: Callable[[list[str]], tuple[int, str, str]] | None = None,
    open_fn: Callable[[str, int], int] = os.open,
    close_fn: Callable[[int], None] = os.close,
    get_keycode_fn: Callable[[int, int], int | None] = get_keycode,
    set_keycode_fn: Callable[[int, int, int], None] = set_keycode,
) -> int:
    """Apply (or reset) evdev scancode remappings for matched remote profile(s)."""
    if not reset:
        configure_cec(verbose=verbose, cec_dev=cec_dev, cec_ctl_runner=cec_ctl_runner)

    profiles = nextgen_platform.load_remote_profiles(user_config_path=profiles_config_path)
    devices = discover_input_devices(sys_input_root=sys_input_root, dev_input_root=dev_input_root)
    matched = match_profiles_for_devices(devices, profiles, forced_profile=profile_name)

    remap_targets: list[tuple[dict[str, Any], list[dict[str, Any]]]] = [
        (m["profile"], m["devices"])
        for m in matched
        if m["profile"].get("scancode_map")
    ]
    if not remap_targets:
        if verbose:
            target_label = profile_name or f"{VENDOR_ID}:{PRODUCT_ID}"
            print(f"No remappable event devices found for {target_label}")
        return 0

    updated_count = 0
    for prof, prof_devices in remap_targets:
        scancode_map = prof.get("scancode_map") or {}
        for dev_info in prof_devices:
            dev = dev_info["dev_node"]
            try:
                fd = open_fn(dev, os.O_RDWR)
            except OSError as exc:
                if verbose:
                    print(_format_open_error(dev, exc))
                continue
            try:
                for scancode, (target_kc, default_kc, desc) in scancode_map.items():
                    current_kc = get_keycode_fn(fd, scancode)
                    if current_kc is None:
                        continue
                    desired_kc = default_kc if reset else target_kc
                    if current_kc != desired_kc:
                        set_keycode_fn(fd, scancode, desired_kc)
                        updated_count += 1
                        if verbose:
                            print(f"{dev}: 0x{scancode:06x} {current_kc} -> {desired_kc} ({desc})")
                    elif verbose:
                        print(f"{dev}: 0x{scancode:06x} == {current_kc} ({desc})")
            finally:
                close_fn(fd)
    return updated_count


def print_status(
    profile_name: str | None = None,
    profiles_config_path: str | None = None,
    sys_input_root: str = "/sys/class/input",
    dev_input_root: str = "/dev/input",
    cec_dev: str = CEC_DEV,
    cec_ctl_runner: Callable[[list[str]], tuple[int, str, str]] | None = None,
    open_fn: Callable[[str, int], int] = os.open,
    close_fn: Callable[[int], None] = os.close,
    get_keycode_fn: Callable[[int, int], int | None] = get_keycode,
) -> int:
    """
    Strictly read-only status inspection.
    NEVER calls `cec-ctl --clear` and NEVER calls `EVIOCSKEYCODE_V2`.
    """
    cec_info = inspect_cec_adapter(cec_dev=cec_dev, cec_ctl_runner=cec_ctl_runner)
    print(f"{cec_dev}: {cec_info.get('adapter_type')} (allocated={cec_info.get('allocated')})")

    profiles = nextgen_platform.load_remote_profiles(user_config_path=profiles_config_path)
    devices = discover_input_devices(sys_input_root=sys_input_root, dev_input_root=dev_input_root)
    matched = match_profiles_for_devices(devices, profiles, cec_info=cec_info, forced_profile=profile_name)

    remap_targets = [
        (m["profile"], m["devices"])
        for m in matched
        if m["profile"].get("scancode_map") and m["devices"]
    ]
    if not remap_targets:
        target_label = profile_name or f"{VENDOR_ID}:{PRODUCT_ID}"
        print(f"No event devices found for {target_label}")
        return 1

    for prof, prof_devices in remap_targets:
        scancode_map = prof.get("scancode_map") or {}
        print(f"Profile: {prof.get('name')} ({prof.get('display_name')})")
        for dev_info in prof_devices:
            dev = dev_info["dev_node"]
            try:
                fd = open_fn(dev, os.O_RDONLY)
            except OSError as exc:
                print(_format_open_error(dev, exc))
                continue
            try:
                for scancode, (target_kc, default_kc, desc) in scancode_map.items():
                    current_kc = get_keycode_fn(fd, scancode)
                    if current_kc is not None:
                        state = "OK" if current_kc == target_kc else f"MISMATCH (expected {target_kc})"
                        print(
                            f"{dev}: 0x{scancode:06x} -> keycode {current_kc:3d} "
                            f"(default {default_kc:3d}) [{state}] {desc}"
                        )
            finally:
                close_fn(fd)
    return 0


def build_diagnose_report(
    profile_name: str | None = None,
    profiles_config_path: str | None = None,
    sys_input_root: str = "/sys/class/input",
    dev_input_root: str = "/dev/input",
    cec_dev: str = CEC_DEV,
    cec_ctl_runner: Callable[[list[str]], tuple[int, str, str]] | None = None,
    access_fn: Callable[[str, int], bool] = os.access,
    device_exists_fn: Callable[[str], bool] = os.path.exists,
) -> dict[str, Any]:
    """
    Build a strictly read-only, sanitized input & CEC diagnostic report.

    Reports detected input devices (name + vendor:product ONLY — NO serials/MACs/uniq),
    matched remote profile(s), normalized action coverage (optional missing buttons are
    explicitly marked optional, never errors), /dev/input/event* permission audit, and
    CEC adapter classification.
    """
    profiles = nextgen_platform.load_remote_profiles(user_config_path=profiles_config_path)
    cec_info = inspect_cec_adapter(
        cec_dev=cec_dev,
        cec_ctl_runner=cec_ctl_runner,
        device_exists_fn=device_exists_fn,
    )
    devices = discover_input_devices(
        sys_input_root=sys_input_root,
        dev_input_root=dev_input_root,
        access_fn=access_fn,
    )
    matched = match_profiles_for_devices(
        devices,
        profiles,
        cec_info=cec_info,
        forced_profile=profile_name,
    )

    matched_summaries = []
    for item in matched:
        prof = item["profile"]
        coverage = nextgen_platform.evaluate_profile_action_coverage(prof)
        matched_summaries.append(
            {
                "profile": prof["name"],
                "display_name": prof.get("display_name", prof["name"]),
                "transport": prof.get("transport", ""),
                "requires_evdev_remap": bool(prof.get("requires_evdev_remap", False)),
                "auto_suppress_input": prof.get("auto_suppress_input"),
                "notes": prof.get("notes", ""),
                "devices": [d["dev_node"] for d in item["devices"]],
                "action_coverage": coverage,
            }
        )

    denied_devices = [
        d["dev_node"]
        for d in devices
        if d.get("exists") and d["permissions"]["status"] == "permission_denied"
    ]
    read_only_devices = [
        d["dev_node"]
        for d in devices
        if d.get("exists") and d["permissions"]["status"] == "read_only"
    ]

    report = {
        "read_only": True,
        "available_profiles": sorted(profiles.keys()),
        "devices": [
            {
                "event": d["event"],
                "dev_node": d["dev_node"],
                "name": d["name"],
                "vendor_product": d["vendor_product"],
                "capabilities": d["capabilities"],
                "permissions": d["permissions"],
            }
            for d in devices
        ],
        "matched_profiles": matched_summaries,
        "permission_audit": {
            "total_event_devices": len(devices),
            "permission_denied_count": len(denied_devices),
            "read_only_count": len(read_only_devices),
            "permission_denied_devices": denied_devices,
            "read_only_devices": read_only_devices,
            "remediation_hint": UACCESS_REMEDIATION_HINT if (denied_devices or read_only_devices) else None,
        },
        "cec": cec_info,
    }
    return nextgen_platform.sanitize_dict(report)


def format_diagnose_text(report: dict[str, Any]) -> str:
    cec = report.get("cec") or {}
    perm = report.get("permission_audit") or {}
    lines = [
        "=== Remote Input & CEC Diagnostics (Read-Only) ===",
        f"CEC Adapter: {cec.get('adapter_type', 'none')} "
        f"(device={cec.get('device', CEC_DEV)}, name={cec.get('adapter_name') or 'n/a'}, "
        f"allocated={cec.get('allocated', False)})",
        f"  Note: {cec.get('note', '')}",
        f"Input Devices ({perm.get('total_event_devices', 0)} found, "
        f"{perm.get('permission_denied_count', 0)} EACCES, {perm.get('read_only_count', 0)} read-only):",
    ]
    for dev in report.get("devices") or []:
        p = dev.get("permissions") or {}
        lines.append(
            f"  - {dev['dev_node']}: {dev['name']} [{dev['vendor_product'] or 'n/a'}] "
            f"perms={p.get('status')} (r={p.get('readable')}, w={p.get('writable')})"
        )
    if perm.get("remediation_hint"):
        lines.append(f"  Permission Hint: {perm['remediation_hint']}")

    matched = report.get("matched_profiles") or []
    lines.append(f"Matched Profiles ({len(matched)}):")
    if not matched:
        lines.append("  - none")
    for mp in matched:
        cov = mp.get("action_coverage") or {}
        lines.append(
            f"  - {mp['profile']} ({mp['display_name']}) | transport={mp['transport']} | "
            f"remap={mp['requires_evdev_remap']}"
        )
        lines.append(f"    Supported actions: {', '.join(cov.get('supported') or []) or 'none'}")
        lines.append(
            f"    Optional unavailable actions (not errors): "
            f"{', '.join(cov.get('optional_unavailable') or []) or 'none'}"
        )
        if mp.get("notes"):
            lines.append(f"    Notes: {mp['notes']}")
    return "\n".join(lines)


def watch_hotplug(
    profile_name: str | None = None,
    profiles_config_path: str | None = None,
) -> None:
    apply_mappings(
        reset=False,
        verbose=True,
        profile_name=profile_name,
        profiles_config_path=profiles_config_path,
    )
    sys.stdout.flush()
    proc = subprocess.Popen(
        ["udevadm", "monitor", "--udev", "--subsystem-match=input"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            if (" add " in line or " change " in line) and "/event" in line:
                time.sleep(0.25)
                apply_mappings(
                    reset=False,
                    verbose=True,
                    profile_name=profile_name,
                    profiles_config_path=profiles_config_path,
                )
                sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="tv-remote-keymap.py",
        description="User-space evdev remote scancode remapper and read-only input/CEC diagnostics.",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--apply", action="store_true", help="Apply remote scancode mappings (default)")
    mode_group.add_argument("--reset", action="store_true", help="Reset remapped scancodes back to defaults")
    mode_group.add_argument("--status", action="store_true", help="Strictly read-only mapping & CEC status")
    mode_group.add_argument("--watch", action="store_true", help="Watch input hotplug events and re-apply")
    mode_group.add_argument(
        "--diagnose",
        action="store_true",
        help="Strictly read-only sanitized input, permission, profile, and CEC diagnostic report",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON (for --diagnose)")
    parser.add_argument("--profile", default=None, help="Explicit remote profile name to target")
    parser.add_argument(
        "--profiles-config",
        default=None,
        help="Optional path to user remote-profiles.json override file",
    )

    args = parser.parse_args(argv)

    if args.diagnose:
        report = build_diagnose_report(
            profile_name=args.profile,
            profiles_config_path=args.profiles_config,
        )
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(format_diagnose_text(report))
        return 0
    if args.reset:
        apply_mappings(
            reset=True,
            verbose=True,
            profile_name=args.profile,
            profiles_config_path=args.profiles_config,
        )
        return 0
    if args.status:
        return print_status(
            profile_name=args.profile,
            profiles_config_path=args.profiles_config,
        )
    if args.watch:
        watch_hotplug(
            profile_name=args.profile,
            profiles_config_path=args.profiles_config,
        )
        return 0

    apply_mappings(
        reset=False,
        verbose=True,
        profile_name=args.profile,
        profiles_config_path=args.profiles_config,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Transactional, ownership-tracked manifest helper for NextGen Plasma Bigscreen.

Manages user-space installs, upgrades, repairs, INI-safe Flatpak override patching,
read-only GPU VA-API auto-detection, and exact rollbacks without external dependencies.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
STATE_REL_DIR = Path(".local/state/nextgen-plasmabigscreen")
MANIFEST_FILENAME = "manifest.json"
FLATPAK_OVERRIDES_REL_DIR = Path(".local/share/flatpak/overrides")

VALID_GPU_PROFILES = ("auto", "intel-ihd", "intel-i965", "amd", "nvidia", "none")

# Pre-Gen8 Intel PCI device ID prefixes (Gen2-Gen7 use i965 rather than iHD).
LEGACY_INTEL_PREFIXES = (
    "0x004",
    "0x010",
    "0x011",
    "0x012",
    "0x015",
    "0x016",
    "0x040",
    "0x041",
    "0x042",
    "0x0a0",
    "0x0a1",
    "0x0a2",
    "0x0c0",
    "0x0c1",
    "0x0c2",
    "0x0d0",
    "0x0d1",
    "0x0d2",
    "0x0f3",
    "0x25",
    "0x27",
    "0x29",
    "0x2a",
    "0x2e",
    "0x35",
)

# Directories owned exclusively by NextGen whose empty subdirs may be pruned on rollback.
SAFE_PRUNE_ROOTS = (
    Path(".local/share/tv-display-mode"),
    Path("Applications/streaming_scripts"),
    Path(".config/tv-display-mode"),
)

SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")


def utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_timestamp_slug() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def resolve_home(home_override: str | None = None) -> Path:
    raw = home_override or os.environ.get("HOME") or os.path.expanduser("~")
    return Path(raw).resolve()


def state_dir_for(home: Path) -> Path:
    return home / STATE_REL_DIR


def manifest_path_for(home: Path) -> Path:
    return state_dir_for(home) / MANIFEST_FILENAME


def _resolve_parent_keeping_leaf(path: Path) -> Path:
    """Resolve symlinks in the deepest existing parent directory without dereferencing the leaf."""
    norm = Path(os.path.normpath(str(path)))
    parent = norm.parent
    tail_parts: list[str] = [norm.name] if norm.name else []
    while not parent.exists() and parent != parent.parent:
        tail_parts.append(parent.name)
        parent = parent.parent
    resolved_parent = parent.resolve()
    result = resolved_parent
    for part in reversed(tail_parts):
        result = result / part
    return Path(os.path.normpath(str(result)))


def normalize_rel_path(home: Path, dst: str) -> tuple[str, Path]:
    """Return (posix_rel_path, resolved_abs_path) and reject paths escaping $HOME."""
    p = Path(dst)
    if not p.is_absolute():
        p = home / p
    # Canonicalize symlinked prefixes (e.g. OSTree /home -> /var/home) without dereferencing leaf symlinks.
    abs_p = _resolve_parent_keeping_leaf(p)
    try:
        rel = abs_p.relative_to(home)
    except ValueError as exc:
        raise ValueError(f"Refusing path outside HOME ({home}): {dst}") from exc
    rel_posix = rel.as_posix()
    if not rel_posix or rel_posix == "." or rel_posix.startswith(".."):
        raise ValueError(f"Invalid destination path inside HOME: {dst}")
    return rel_posix, abs_p


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_dir(root: Path) -> str:
    """Deterministic SHA-256 over a directory tree's relative paths, links, and contents."""
    h = hashlib.sha256()
    root_str = str(root)
    entries: list[tuple[str, str, Path]] = []
    for dirpath, dirnames, filenames in os.walk(root_str, followlinks=False):
        dirnames.sort()
        filenames.sort()
        rel_dir = Path(dirpath).relative_to(root).as_posix()
        if rel_dir != ".":
            entries.append(("D", rel_dir, Path(dirpath)))
        for name in filenames:
            full = Path(dirpath) / name
            rel = full.relative_to(root).as_posix()
            kind = "L" if full.is_symlink() else "F"
            entries.append((kind, rel, full))
    entries.sort(key=lambda item: (item[1], item[0]))
    for kind, rel, full in entries:
        h.update(f"{kind}:{rel}\0".encode("utf-8"))
        if kind == "L":
            h.update(os.readlink(full).encode("utf-8") + b"\0")
        elif kind == "F":
            h.update(sha256_file(full).encode("ascii") + b"\0")
    return h.hexdigest()


def atomic_write_bytes(dst: Path, data: bytes, mode: int = 0o644) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(dst.parent), prefix=f".{dst.name}.nextgen-tmp-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, dst)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def atomic_write_json(dst: Path, payload: dict[str, Any]) -> None:
    encoded = (json.dumps(payload, indent=2, sort_keys=False) + "\n").encode("utf-8")
    atomic_write_bytes(dst, encoded, mode=0o644)


def load_manifest(home: Path) -> dict[str, Any] | None:
    mpath = manifest_path_for(home)
    if not mpath.exists():
        return None
    with mpath.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Corrupt manifest at {mpath}: expected JSON object")
    data.setdefault("schema_version", SCHEMA_VERSION)
    data.setdefault("entries", {})
    data.setdefault("flatpak_overrides", {})
    data.setdefault("flatpak_override_meta", {})
    return data


def save_manifest(home: Path, manifest: dict[str, Any], dry_run: bool) -> None:
    if dry_run:
        return
    atomic_write_json(manifest_path_for(home), manifest)


def choose_backup_subdir(home: Path) -> str:
    base = utc_timestamp_slug()
    backups_root = state_dir_for(home) / "backups"
    candidate = f"backups/{base}"
    idx = 1
    while (backups_root / candidate.split("/", 1)[1]).exists():
        candidate = f"backups/{base}-{idx}"
        idx += 1
    return candidate


def backup_existing_path(home: Path, manifest: dict[str, Any], rel_posix: str, src: Path, dry_run: bool) -> str:
    """Copy an existing file/dir into backups/<timestamp>/<rel_posix> and return its state-relative path."""
    backup_subdir = manifest.get("current_backup_dir") or choose_backup_subdir(home)
    manifest["current_backup_dir"] = backup_subdir
    state_root = state_dir_for(home)
    rel_backup = Path(backup_subdir) / rel_posix
    full_backup = state_root / rel_backup

    # Avoid overwriting an earlier backup in the same run.
    if full_backup.exists() or full_backup.is_symlink():
        idx = 1
        while True:
            alt = Path(f"{rel_backup.as_posix()}.{idx}")
            if not (state_root / alt).exists() and not (state_root / alt).is_symlink():
                rel_backup = alt
                full_backup = state_root / rel_backup
                break
            idx += 1

    if dry_run:
        return rel_backup.as_posix()

    full_backup.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir() and not src.is_symlink():
        shutil.copytree(src, full_backup, symlinks=True)
    elif src.is_symlink():
        os.symlink(os.readlink(src), full_backup)
    else:
        shutil.copy2(src, full_backup)
    return rel_backup.as_posix()


def ensure_active_manifest(home: Path, gpu_profile: str = "none", dry_run: bool = False) -> dict[str, Any]:
    existing = load_manifest(home)
    if existing is not None and existing.get("status") != "rolled_back":
        existing.setdefault("current_backup_dir", choose_backup_subdir(home))
        return existing
    now = utc_now_iso()
    return {
        "schema_version": SCHEMA_VERSION,
        "install_id": f"{utc_timestamp_slug()}-{secrets.token_hex(4)}",
        "status": "in_progress",
        "started_at": now,
        "completed_at": None,
        "gpu_profile": gpu_profile,
        "current_backup_dir": choose_backup_subdir(home),
        "entries": {},
        "flatpak_overrides": {},
        "flatpak_override_meta": {},
    }


def parse_mode(mode_str: str) -> int:
    return int(mode_str, 8)


# ---------------------------------------------------------------------------
# Line-preserving INI parser/editor for Flatpak override files (GKeyFile)
# ---------------------------------------------------------------------------


class FlatpakIni:
    """Line-preserving, case-sensitive, interpolation-free INI editor for Flatpak overrides."""

    def __init__(self, text: str = "") -> None:
        self.lines: list[str] = text.splitlines() if text else []

    def _locate(self, target_section: str, target_key: str) -> tuple[int | None, int | None, int | None]:
        """Return (section_header_idx, section_end_idx, key_line_idx)."""
        current_section: str | None = None
        sec_start: int | None = None
        sec_end: int | None = None
        key_idx: int | None = None

        for idx, line in enumerate(self.lines):
            m = SECTION_RE.match(line)
            if m:
                if current_section == target_section and sec_end is None:
                    sec_end = idx
                current_section = m.group(1).strip()
                if current_section == target_section and sec_start is None:
                    sec_start = idx
                continue
            if current_section == target_section:
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or stripped.startswith(";"):
                    continue
                if "=" in line:
                    k, _ = line.split("=", 1)
                    if k.strip() == target_key:
                        key_idx = idx

        if sec_start is not None and sec_end is None:
            sec_end = len(self.lines)
        return sec_start, sec_end, key_idx

    def get(self, section: str, key: str) -> tuple[bool, str | None]:
        _, _, key_idx = self._locate(section, key)
        if key_idx is None:
            return False, None
        _, val = self.lines[key_idx].split("=", 1)
        return True, val

    def set(self, section: str, key: str, value: str) -> None:
        sec_start, sec_end, key_idx = self._locate(section, key)
        new_line = f"{key}={value}"
        if key_idx is not None:
            self.lines[key_idx] = new_line
            return
        if sec_start is not None and sec_end is not None:
            insert_at = sec_end
            while insert_at > sec_start + 1 and not self.lines[insert_at - 1].strip():
                insert_at -= 1
            self.lines.insert(insert_at, new_line)
            return
        if self.lines and self.lines[-1].strip():
            self.lines.append("")
        self.lines.append(f"[{section}]")
        self.lines.append(new_line)

    def delete(self, section: str, key: str) -> bool:
        sec_start, sec_end, key_idx = self._locate(section, key)
        if key_idx is None:
            return False
        del self.lines[key_idx]
        # Re-check if section now has zero key=value entries (and no comments).
        sec_start, sec_end, _ = self._locate(section, key)
        if sec_start is not None and sec_end is not None:
            body = self.lines[sec_start + 1 : sec_end]
            has_content = any(
                ln.strip() and not ln.strip().startswith("#") and "=" in ln for ln in body
            )
            has_comments = any(ln.strip().startswith("#") for ln in body)
            if not has_content and not has_comments:
                # Remove section header and any trailing blank lines belonging to it.
                del self.lines[sec_start:sec_end]
                # Collapse double blank lines or leading/trailing blank lines.
                self._trim_blank_lines()
        return True

    def _trim_blank_lines(self) -> None:
        cleaned: list[str] = []
        for ln in self.lines:
            if not ln.strip() and (not cleaned or not cleaned[-1].strip()):
                continue
            cleaned.append(ln)
        while cleaned and not cleaned[-1].strip():
            cleaned.pop()
        self.lines = cleaned

    def has_any_keys(self) -> bool:
        current_section: str | None = None
        for line in self.lines:
            m = SECTION_RE.match(line)
            if m:
                current_section = m.group(1).strip()
                continue
            stripped = line.strip()
            if current_section is not None and stripped and not stripped.startswith("#") and "=" in line:
                return True
        return False

    def render(self) -> str:
        self._trim_blank_lines()
        if not self.lines:
            return ""
        return "\n".join(self.lines) + "\n"


# ---------------------------------------------------------------------------
# GPU auto-detection (read-only)
# ---------------------------------------------------------------------------


def detect_gpu_profile(
    gpu_override: str = "auto",
    sysfs_pci_dir: str = "/sys/bus/pci/devices",
) -> dict[str, Any]:
    mode = (gpu_override or "auto").strip().lower()
    if mode not in VALID_GPU_PROFILES:
        raise ValueError(f"Invalid --gpu profile '{gpu_override}'. Expected one of: {', '.join(VALID_GPU_PROFILES)}")

    if mode != "auto":
        if mode == "intel-ihd":
            return {
                "profile": "intel-ihd",
                "vaapi_driver": "iHD",
                "install_intel_vaapi_conf": True,
                "vendors": [],
                "reason": "explicit --gpu intel-ihd override",
            }
        if mode == "intel-i965":
            return {
                "profile": "intel-i965",
                "vaapi_driver": "i965",
                "install_intel_vaapi_conf": False,
                "vendors": [],
                "reason": "explicit --gpu intel-i965 override",
            }
        return {
            "profile": mode,
            "vaapi_driver": "",
            "install_intel_vaapi_conf": False,
            "vendors": [],
            "reason": f"explicit --gpu {mode} override",
        }

    vendors: set[str] = set()
    intel_devices: list[str] = []
    pci_root = Path(sysfs_pci_dir)

    if pci_root.is_dir():
        try:
            dev_entries = sorted(pci_root.iterdir())
        except OSError:
            dev_entries = []
        for dev in dev_entries:
            class_file = dev / "class"
            vendor_file = dev / "vendor"
            device_file = dev / "device"
            try:
                pci_class = class_file.read_text(encoding="utf-8").strip().lower()
                if not pci_class.startswith("0x03"):
                    continue
                vendor = vendor_file.read_text(encoding="utf-8").strip().lower()
                vendors.add(vendor)
                if vendor == "0x8086" and device_file.exists():
                    intel_devices.append(device_file.read_text(encoding="utf-8").strip().lower())
            except OSError:
                continue

    sorted_vendors = sorted(vendors)

    if vendors == {"0x8086"}:
        # Intel-only system: distinguish Gen8+ (iHD) vs pre-Gen8 (i965).
        is_legacy_only = bool(intel_devices) and all(
            any(dev_id.startswith(pref) for pref in LEGACY_INTEL_PREFIXES) for dev_id in intel_devices
        )
        if is_legacy_only:
            return {
                "profile": "intel-i965",
                "vaapi_driver": "i965",
                "install_intel_vaapi_conf": False,
                "vendors": sorted_vendors,
                "reason": f"detected pre-Gen8 Intel GPU ({', '.join(intel_devices)})",
            }
        return {
            "profile": "intel-ihd",
            "vaapi_driver": "iHD",
            "install_intel_vaapi_conf": True,
            "vendors": sorted_vendors,
            "reason": "detected Intel Gen8+ GPU (0x8086)",
        }

    if "0x1002" in vendors and "0x8086" not in vendors and "0x10de" not in vendors:
        return {
            "profile": "amd",
            "vaapi_driver": "",
            "install_intel_vaapi_conf": False,
            "vendors": sorted_vendors,
            "reason": "detected AMD GPU (0x1002); Mesa radeonsi auto-selects VA-API",
        }

    if "0x10de" in vendors and "0x8086" not in vendors and "0x1002" not in vendors:
        return {
            "profile": "nvidia",
            "vaapi_driver": "",
            "install_intel_vaapi_conf": False,
            "vendors": sorted_vendors,
            "reason": "detected NVIDIA GPU (0x10de); skipping Intel VA-API override",
        }

    if len(vendors) > 1:
        return {
            "profile": "none",
            "vaapi_driver": "",
            "install_intel_vaapi_conf": False,
            "vendors": sorted_vendors,
            "reason": f"detected multi-GPU system ({', '.join(sorted_vendors)}); not forcing LIBVA_DRIVER_NAME",
        }

    return {
        "profile": "none",
        "vaapi_driver": "",
        "install_intel_vaapi_conf": False,
        "vendors": sorted_vendors,
        "reason": "no Intel Gen8+ GPU detected; leaving LIBVA_DRIVER_NAME unset",
    }


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_begin(args: argparse.Namespace) -> int:
    home = resolve_home(args.home)
    dry_run = args.dry_run
    existing = load_manifest(home)
    now = utc_now_iso()
    new_install_id = f"{utc_timestamp_slug()}-{secrets.token_hex(4)}"
    backup_subdir = choose_backup_subdir(home)

    if existing is None or existing.get("status") == "rolled_back":
        manifest: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "install_id": new_install_id,
            "status": "in_progress",
            "started_at": now,
            "completed_at": None,
            "gpu_profile": args.gpu_profile,
            "current_backup_dir": backup_subdir,
            "entries": {},
            "flatpak_overrides": {},
            "flatpak_override_meta": {},
        }
        action = "Starting fresh transactional install"
    else:
        prev_status = existing.get("status")
        prev_id = existing.get("install_id", "unknown")
        if prev_status == "in_progress":
            action = f"Recovering interrupted install ({prev_id})"
        else:
            action = f"Upgrading existing install ({prev_id})"
        manifest = existing
        manifest["schema_version"] = SCHEMA_VERSION
        manifest["install_id"] = new_install_id
        manifest["status"] = "in_progress"
        manifest["started_at"] = now
        manifest["completed_at"] = None
        manifest["gpu_profile"] = args.gpu_profile
        manifest["current_backup_dir"] = backup_subdir

    if dry_run:
        print(f"[dry-run] {action} (install_id={new_install_id}, gpu_profile={args.gpu_profile})")
        return 0

    save_manifest(home, manifest, dry_run=False)
    print(f"{action} (install_id={new_install_id}, gpu_profile={args.gpu_profile})")
    return 0


def _install_bytes(
    home: Path,
    rel_posix: str,
    dst: Path,
    payload: bytes,
    mode_str: str,
    preserve_user_edits: bool,
    keep_existing: bool,
    force: bool,
    repair: bool,
    dry_run: bool,
    label: str,
) -> int:
    manifest = ensure_active_manifest(home, dry_run=dry_run)
    entries: dict[str, Any] = manifest["entries"]
    mode = parse_mode(mode_str)
    new_sha = sha256_bytes(payload)
    now = utc_now_iso()
    exists = dst.exists() or dst.is_symlink()

    if rel_posix in entries:
        entry = entries[rel_posix]
        ownership = entry.get("ownership", "nextgen_created")
        prev_sha = entry.get("installed_sha256")

        if ownership == "user_preserved" and exists and not force:
            if dry_run:
                print(f"[dry-run] keep pre-existing user file {dst} (pass --force to overwrite)")
            else:
                print(f"Keeping existing {dst} (pass --force to overwrite)")
            return 0

        if exists and dst.is_file():
            cur_sha = sha256_file(dst)
            user_edited = prev_sha is not None and cur_sha != prev_sha
            if user_edited and preserve_user_edits and not force and not repair:
                msg = (
                    f"Preserving user-edited config {dst} "
                    f"(differs from last installed version; pass --force to overwrite after backup)"
                )
                print(f"[dry-run] {msg}" if dry_run else msg)
                return 0

            if cur_sha == new_sha and (stat.S_IMODE(dst.stat().st_mode) == mode):
                if dry_run:
                    print(f"[dry-run] up-to-date {dst}")
                else:
                    entry["updated_at"] = now
                    entry["preserve_user_edits"] = preserve_user_edits
                    save_manifest(home, manifest, dry_run=False)
                return 0

            if ownership == "user_preserved" and force:
                bpath = backup_existing_path(home, manifest, rel_posix, dst, dry_run)
                if dry_run:
                    print(f"[dry-run] backup {dst} -> {state_dir_for(home) / bpath}")
                    print(f"[dry-run] {label} -> {dst} (mode {mode_str})")
                    return 0
                atomic_write_bytes(dst, payload, mode=mode)
                entry["ownership"] = "user_modified"
                entry["backup_path"] = bpath
                entry["installed_sha256"] = new_sha
                entry["mode"] = mode_str
                entry["preserve_user_edits"] = preserve_user_edits
                entry["updated_at"] = now
                save_manifest(home, manifest, dry_run=False)
                print(f"Backed up {dst} -> {state_dir_for(home) / bpath} and updated")
                return 0

            if user_edited:
                bpath = backup_existing_path(home, manifest, rel_posix, dst, dry_run)
                if dry_run:
                    print(f"[dry-run] backup edited {dst} -> {state_dir_for(home) / bpath}")
                    print(f"[dry-run] {label} -> {dst} (mode {mode_str})")
                    return 0
                atomic_write_bytes(dst, payload, mode=mode)
                entry.setdefault("extra_backups", []).append(bpath)
                entry["installed_sha256"] = new_sha
                entry["mode"] = mode_str
                entry["preserve_user_edits"] = preserve_user_edits
                entry["updated_at"] = now
                save_manifest(home, manifest, dry_run=False)
                print(f"Backed up user-edited {dst} -> {state_dir_for(home) / bpath} and installed update")
                return 0

        # Tracked entry, either missing on disk (repair/recreate) or clean upgrade.
        if dry_run:
            verb = "restore missing" if not exists else "update"
            print(f"[dry-run] {verb} {dst} ({label}, mode {mode_str})")
            return 0
        if dst.is_dir() and not dst.is_symlink():
            shutil.rmtree(dst)
        atomic_write_bytes(dst, payload, mode=mode)
        entry["type"] = "file"
        entry["installed_sha256"] = new_sha
        entry["mode"] = mode_str
        entry["preserve_user_edits"] = preserve_user_edits
        entry["updated_at"] = now
        save_manifest(home, manifest, dry_run=False)
        return 0

    # Not yet tracked in manifest.
    if exists:
        if keep_existing and not force:
            cur_sha = sha256_file(dst) if dst.is_file() else None
            if dry_run:
                print(f"[dry-run] keep pre-existing user file {dst} (pass --force to overwrite)")
                return 0
            entries[rel_posix] = {
                "type": "file",
                "ownership": "user_preserved",
                "installed_sha256": cur_sha,
                "mode": mode_str,
                "backup_path": None,
                "preserve_user_edits": True,
                "updated_at": now,
            }
            save_manifest(home, manifest, dry_run=False)
            print(f"Keeping existing {dst} (pass --force to overwrite)")
            return 0

        bpath = backup_existing_path(home, manifest, rel_posix, dst, dry_run)
        if dry_run:
            print(f"[dry-run] backup pre-existing {dst} -> {state_dir_for(home) / bpath}")
            print(f"[dry-run] {label} -> {dst} (mode {mode_str})")
            return 0
        if dst.is_dir() and not dst.is_symlink():
            shutil.rmtree(dst)
        atomic_write_bytes(dst, payload, mode=mode)
        entries[rel_posix] = {
            "type": "file",
            "ownership": "user_modified",
            "installed_sha256": new_sha,
            "mode": mode_str,
            "backup_path": bpath,
            "preserve_user_edits": preserve_user_edits,
            "updated_at": now,
        }
        save_manifest(home, manifest, dry_run=False)
        print(f"Backed up pre-existing {dst} -> {state_dir_for(home) / bpath}")
        return 0

    # Brand new NextGen-created file.
    if dry_run:
        print(f"[dry-run] {label} -> {dst} (mode {mode_str})")
        return 0
    atomic_write_bytes(dst, payload, mode=mode)
    entries[rel_posix] = {
        "type": "file",
        "ownership": "nextgen_created",
        "installed_sha256": new_sha,
        "mode": mode_str,
        "backup_path": None,
        "preserve_user_edits": preserve_user_edits,
        "updated_at": now,
    }
    save_manifest(home, manifest, dry_run=False)
    return 0


def cmd_install_file(args: argparse.Namespace) -> int:
    home = resolve_home(args.home)
    rel_posix, dst = normalize_rel_path(home, args.dst)
    src = Path(args.src)
    payload = src.read_bytes()
    return _install_bytes(
        home=home,
        rel_posix=rel_posix,
        dst=dst,
        payload=payload,
        mode_str=args.mode,
        preserve_user_edits=args.preserve_user_edits,
        keep_existing=args.keep_existing,
        force=args.force,
        repair=args.repair,
        dry_run=args.dry_run,
        label=f"install {src}",
    )


def resolve_steam_exec(
    home: Path,
    *,
    bazzite_steam: Path = Path("/usr/bin/bazzite-steam"),
    usr_steam: Path = Path("/usr/bin/steam"),
    system_flatpak_app: Path = Path("/var/lib/flatpak/app/com.valvesoftware.Steam"),
    which_fn=shutil.which,
) -> str:
    """Resolve the Steam launcher command across Bazzite, native distros, and Flatpak."""
    if bazzite_steam.exists() and os.access(bazzite_steam, os.X_OK):
        return str(bazzite_steam)
    if usr_steam.exists() and os.access(usr_steam, os.X_OK):
        return str(usr_steam)
    found_steam = which_fn("steam") if which_fn else None
    if found_steam:
        return str(found_steam)
    if (home / ".local/share/flatpak/app/com.valvesoftware.Steam").exists() or system_flatpak_app.exists():
        return "/usr/bin/flatpak run com.valvesoftware.Steam"
    return "steam"


def resolve_haruna_desktop_path(
    home: Path,
    logical_home: str,
    *,
    system_flatpak_desktop: Path = Path("/var/lib/flatpak/exports/share/applications/org.kde.haruna.desktop"),
    native_desktop: Path = Path("/usr/share/applications/org.kde.haruna.desktop"),
) -> str:
    """Resolve org.kde.haruna.desktop across user Flatpak, system Flatpak, and native packages."""
    user_rel = ".local/share/flatpak/exports/share/applications/org.kde.haruna.desktop"
    if (home / user_rel).exists():
        return f"{logical_home}/{user_rel}"
    if system_flatpak_desktop.exists():
        return str(system_flatpak_desktop)
    if native_desktop.exists():
        return str(native_desktop)
    return "/var/lib/flatpak/exports/share/applications/org.kde.haruna.desktop"


def cmd_install_template(args: argparse.Namespace) -> int:
    home = resolve_home(args.home)
    logical_home = os.path.normpath(args.home or os.environ.get("HOME") or str(home))
    rel_posix, dst = normalize_rel_path(home, args.dst)
    src = Path(args.src)
    text = src.read_text(encoding="utf-8").replace("@HOME@", logical_home)
    if "@STEAM_EXEC@" in text:
        text = text.replace("@STEAM_EXEC@", resolve_steam_exec(home))
    if "@HARUNA_DESKTOP_PATH@" in text:
        text = text.replace("@HARUNA_DESKTOP_PATH@", resolve_haruna_desktop_path(home, logical_home))
    rendered = text.encode("utf-8")
    return _install_bytes(
        home=home,
        rel_posix=rel_posix,
        dst=dst,
        payload=rendered,
        mode_str=args.mode,
        preserve_user_edits=args.preserve_user_edits,
        keep_existing=args.keep_existing,
        force=args.force,
        repair=args.repair,
        dry_run=args.dry_run,
        label=f"render(@HOME@={logical_home}) {src}",
    )


def _atomic_replace_dir(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp_new = dst.parent / f".{dst.name}.nextgen-new-{os.getpid()}-{secrets.token_hex(4)}"
    tmp_old = dst.parent / f".{dst.name}.nextgen-old-{os.getpid()}-{secrets.token_hex(4)}"
    try:
        shutil.copytree(src, tmp_new, symlinks=True)
        had_dst = dst.exists() or dst.is_symlink()
        if had_dst:
            os.rename(dst, tmp_old)
        try:
            os.rename(tmp_new, dst)
        except BaseException:
            if had_dst and tmp_old.exists():
                os.rename(tmp_old, dst)
            raise
        if had_dst:
            if tmp_old.is_dir() and not tmp_old.is_symlink():
                shutil.rmtree(tmp_old)
            else:
                tmp_old.unlink(missing_ok=True)
    except BaseException:
        if tmp_new.exists():
            shutil.rmtree(tmp_new, ignore_errors=True)
        raise


def cmd_install_dir(args: argparse.Namespace) -> int:
    home = resolve_home(args.home)
    rel_posix, dst = normalize_rel_path(home, args.dst)
    src = Path(args.src)
    if not src.is_dir():
        raise FileNotFoundError(f"Source directory not found: {src}")

    dry_run = args.dry_run
    manifest = ensure_active_manifest(home, dry_run=dry_run)
    entries: dict[str, Any] = manifest["entries"]
    new_sha = sha256_dir(src)
    now = utc_now_iso()
    exists = dst.exists() or dst.is_symlink()

    if rel_posix in entries:
        entry = entries[rel_posix]
        if exists and dst.is_dir() and not dst.is_symlink():
            cur_sha = sha256_dir(dst)
            if cur_sha == new_sha:
                if dry_run:
                    print(f"[dry-run] directory up-to-date {dst}")
                else:
                    entry["updated_at"] = now
                    save_manifest(home, manifest, dry_run=False)
                return 0
            prev_sha = entry.get("installed_sha256")
            if prev_sha is not None and cur_sha != prev_sha:
                bpath = backup_existing_path(home, manifest, rel_posix, dst, dry_run)
                if dry_run:
                    print(f"[dry-run] backup modified dir {dst} -> {state_dir_for(home) / bpath}")
                else:
                    entry.setdefault("extra_backups", []).append(bpath)
                    print(f"Backed up modified dir {dst} -> {state_dir_for(home) / bpath}")

        if dry_run:
            print(f"[dry-run] sync dir {src} -> {dst}")
            return 0
        _atomic_replace_dir(src, dst)
        entry["type"] = "dir"
        entry["installed_sha256"] = new_sha
        entry["updated_at"] = now
        save_manifest(home, manifest, dry_run=False)
        return 0

    # Not yet tracked in manifest.
    if exists:
        bpath = backup_existing_path(home, manifest, rel_posix, dst, dry_run)
        if dry_run:
            print(f"[dry-run] backup pre-existing dir {dst} -> {state_dir_for(home) / bpath}")
            print(f"[dry-run] sync dir {src} -> {dst}")
            return 0
        _atomic_replace_dir(src, dst)
        entries[rel_posix] = {
            "type": "dir",
            "ownership": "user_modified",
            "installed_sha256": new_sha,
            "backup_path": bpath,
            "preserve_user_edits": False,
            "updated_at": now,
        }
        save_manifest(home, manifest, dry_run=False)
        print(f"Backed up pre-existing dir {dst} -> {state_dir_for(home) / bpath}")
        return 0

    if dry_run:
        print(f"[dry-run] sync dir {src} -> {dst}")
        return 0
    _atomic_replace_dir(src, dst)
    entries[rel_posix] = {
        "type": "dir",
        "ownership": "nextgen_created",
        "installed_sha256": new_sha,
        "backup_path": None,
        "preserve_user_edits": False,
        "updated_at": now,
    }
    save_manifest(home, manifest, dry_run=False)
    return 0


def _parse_set_spec(spec: str) -> tuple[str, str, str]:
    if ":" not in spec:
        raise ValueError(f"Invalid --set spec (expected Section:Key=Value): {spec}")
    section, rest = spec.split(":", 1)
    if "=" not in rest:
        raise ValueError(f"Invalid --set spec (expected Section:Key=Value): {spec}")
    key, value = rest.split("=", 1)
    return section.strip(), key.strip(), value


def _parse_unset_spec(spec: str) -> tuple[str, str]:
    if ":" not in spec:
        raise ValueError(f"Invalid --unset spec (expected Section:Key): {spec}")
    section, key = spec.split(":", 1)
    return section.strip(), key.strip()


def cmd_patch_flatpak_override(args: argparse.Namespace) -> int:
    home = resolve_home(args.home)
    app_id = args.app_id.strip()
    if not app_id or "/" in app_id or "\\" in app_id or app_id in (".", ".."):
        raise ValueError(f"Invalid Flatpak app ID: {app_id}")

    sets = [_parse_set_spec(s) for s in (args.set_kv or [])]
    unsets = [_parse_unset_spec(u) for u in (args.unset_k or [])]
    if not sets and not unsets:
        return 0

    dry_run = args.dry_run
    manifest = ensure_active_manifest(home, dry_run=dry_run)
    overrides_map: dict[str, list[dict[str, Any]]] = manifest["flatpak_overrides"]
    meta_map: dict[str, dict[str, Any]] = manifest["flatpak_override_meta"]

    override_rel = (FLATPAK_OVERRIDES_REL_DIR / app_id).as_posix()
    override_path = home / FLATPAK_OVERRIDES_REL_DIR / app_id
    exists = override_path.exists()

    # If only unsetting and this app has no tracked NextGen keys, do nothing.
    if not sets and app_id not in overrides_map:
        return 0

    existing_text = override_path.read_text(encoding="utf-8") if exists else ""
    ini = FlatpakIni(existing_text)

    if app_id not in meta_map:
        if exists:
            bpath = backup_existing_path(home, manifest, override_rel, override_path, dry_run)
            meta = {"ownership": "user_modified", "backup_path": bpath}
            if dry_run:
                print(f"[dry-run] backup pre-existing Flatpak override {override_path} -> {state_dir_for(home) / bpath}")
        else:
            meta = {"ownership": "nextgen_created", "backup_path": None}
    else:
        meta = meta_map[app_id]

    records: list[dict[str, Any]] = list(overrides_map.get(app_id, []))

    def find_record(sec: str, k: str) -> dict[str, Any] | None:
        for r in records:
            if r["section"] == sec and r["key"] == k:
                return r
        return None

    for section, key, value in sets:
        rec = find_record(section, key)
        if rec is None:
            prev_present, prev_val = ini.get(section, key)
            records.append(
                {
                    "section": section,
                    "key": key,
                    "previous_present": prev_present,
                    "previous_value": prev_val,
                    "managed_value": value,
                }
            )
        else:
            # Keep original previous_present / previous_value across upgrades!
            rec["managed_value"] = value
        ini.set(section, key, value)
        if dry_run:
            print(f"[dry-run] flatpak override {app_id}: set [{section}] {key}={value}")

    for section, key in unsets:
        rec = find_record(section, key)
        if rec is None:
            continue
        if rec["previous_present"]:
            ini.set(section, key, rec["previous_value"])
            if dry_run:
                print(f"[dry-run] flatpak override {app_id}: restore [{section}] {key}={rec['previous_value']}")
        else:
            cur_present, cur_val = ini.get(section, key)
            if cur_present and cur_val == rec["managed_value"]:
                ini.delete(section, key)
                if dry_run:
                    print(f"[dry-run] flatpak override {app_id}: remove NextGen key [{section}] {key}")
        records = [r for r in records if not (r["section"] == section and r["key"] == key)]

    if dry_run:
        return 0

    rendered = ini.render()
    if ini.has_any_keys():
        atomic_write_bytes(override_path, rendered.encode("utf-8"), mode=0o644)
        if records:
            overrides_map[app_id] = records
            meta_map[app_id] = meta
        else:
            overrides_map.pop(app_id, None)
            meta_map.pop(app_id, None)
    else:
        if meta.get("ownership") == "nextgen_created" and override_path.exists():
            override_path.unlink()
        overrides_map.pop(app_id, None)
        meta_map.pop(app_id, None)

    save_manifest(home, manifest, dry_run=False)
    return 0


def cmd_commit(args: argparse.Namespace) -> int:
    home = resolve_home(args.home)
    if args.dry_run:
        print("[dry-run] commit manifest (status=complete)")
        return 0
    manifest = load_manifest(home)
    if manifest is None:
        raise RuntimeError("No active manifest to commit")
    manifest["status"] = "complete"
    manifest["completed_at"] = utc_now_iso()
    save_manifest(home, manifest, dry_run=False)
    print(f"Manifest committed (install_id={manifest['install_id']}, status=complete)")
    return 0


def _prune_safe_empty_dirs(home: Path, path: Path) -> None:
    """Prune empty parent dirs ONLY when strictly inside SAFE_PRUNE_ROOTS."""
    safe_abs_roots = [(home / r).resolve() for r in SAFE_PRUNE_ROOTS]
    cur = path.parent
    while True:
        try:
            cur_resolved = cur.resolve()
        except OSError:
            break
        allowed = any(
            cur_resolved == root or root in cur_resolved.parents for root in safe_abs_roots
        )
        if not allowed:
            break
        try:
            cur.rmdir()
        except OSError:
            break
        cur = cur.parent


def cmd_rollback(args: argparse.Namespace) -> int:
    home = resolve_home(args.home)
    dry_run = args.dry_run
    manifest = load_manifest(home)

    if manifest is None:
        print("No NextGen manifest found; nothing tracked to roll back.")
        return 0

    if manifest.get("status") == "rolled_back" and not manifest.get("entries") and not manifest.get("flatpak_overrides"):
        print("NextGen installation is already rolled back; nothing to do.")
        return 0

    state_root = state_dir_for(home)
    overrides_map: dict[str, list[dict[str, Any]]] = manifest.get("flatpak_overrides", {})
    meta_map: dict[str, dict[str, Any]] = manifest.get("flatpak_override_meta", {})

    # 1. Revert Flatpak override keys cleanly without touching unrelated keys/apps.
    for app_id, records in list(overrides_map.items()):
        override_path = home / FLATPAK_OVERRIDES_REL_DIR / app_id
        meta = meta_map.get(app_id, {})
        if not override_path.exists():
            continue
        ini = FlatpakIni(override_path.read_text(encoding="utf-8"))
        for rec in records:
            sec = rec["section"]
            key = rec["key"]
            if rec.get("previous_present"):
                if dry_run:
                    print(f"[dry-run] restore Flatpak override {app_id}: [{sec}] {key}={rec['previous_value']}")
                else:
                    ini.set(sec, key, rec["previous_value"])
            else:
                cur_present, cur_val = ini.get(sec, key)
                if cur_present:
                    if cur_val == rec.get("managed_value"):
                        if dry_run:
                            print(f"[dry-run] remove NextGen Flatpak key {app_id}: [{sec}] {key}")
                        else:
                            ini.delete(sec, key)
                    else:
                        msg = (
                            f"Preserving user-modified Flatpak override key {app_id} "
                            f"[{sec}] {key}={cur_val}"
                        )
                        print(f"[dry-run] {msg}" if dry_run else msg)

        if dry_run:
            continue

        if ini.has_any_keys():
            atomic_write_bytes(override_path, ini.render().encode("utf-8"), mode=0o644)
        else:
            if meta.get("ownership") == "nextgen_created":
                override_path.unlink(missing_ok=True)
            else:
                bpath = meta.get("backup_path")
                if bpath and (state_root / bpath).exists():
                    atomic_write_bytes(override_path, (state_root / bpath).read_bytes(), mode=0o644)
                else:
                    atomic_write_bytes(override_path, ini.render().encode("utf-8"), mode=0o644)

    # 2. Revert tracked files and directories.
    entries: dict[str, Any] = manifest.get("entries", {})
    for rel_posix, entry in list(entries.items()):
        _, dst = normalize_rel_path(home, rel_posix)
        ownership = entry.get("ownership", "nextgen_created")
        etype = entry.get("type", "file")
        backup_rel = entry.get("backup_path")

        if ownership == "user_preserved":
            msg = f"Leaving pre-existing user file untouched: {dst}"
            print(f"[dry-run] {msg}" if dry_run else msg)
            continue

        if ownership == "user_modified":
            if backup_rel and (state_root / backup_rel).exists():
                backup_full = state_root / backup_rel
                if dry_run:
                    print(f"[dry-run] restore {dst} from {backup_full}")
                    continue
                if backup_full.is_dir() and not backup_full.is_symlink():
                    _atomic_replace_dir(backup_full, dst)
                elif backup_full.is_symlink():
                    if dst.exists() or dst.is_symlink():
                        if dst.is_dir() and not dst.is_symlink():
                            shutil.rmtree(dst)
                        else:
                            dst.unlink()
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    os.symlink(os.readlink(backup_full), dst)
                else:
                    if dst.is_dir() and not dst.is_symlink():
                        shutil.rmtree(dst)
                    mode = stat.S_IMODE(backup_full.stat().st_mode)
                    atomic_write_bytes(dst, backup_full.read_bytes(), mode=mode)
                print(f"Restored pre-existing {dst} from {backup_full}")
            else:
                msg = f"Warning: backup missing for user-modified {dst}; leaving current file intact"
                print(f"[dry-run] {msg}" if dry_run else msg)
            continue

        # ownership == "nextgen_created"
        if not (dst.exists() or dst.is_symlink()):
            continue
        if dry_run:
            print(f"[dry-run] remove NextGen-created {etype} {dst}")
            continue
        if dst.is_dir() and not dst.is_symlink():
            shutil.rmtree(dst)
        else:
            dst.unlink(missing_ok=True)
        _prune_safe_empty_dirs(home, dst)

    if dry_run:
        print("[dry-run] mark manifest status=rolled_back")
        return 0

    manifest["status"] = "rolled_back"
    manifest["rolled_back_at"] = utc_now_iso()
    manifest["entries"] = {}
    manifest["flatpak_overrides"] = {}
    manifest["flatpak_override_meta"] = {}
    save_manifest(home, manifest, dry_run=False)
    print("Manifest rollback complete (status=rolled_back).")
    return 0


def cmd_legacy_clean_flatpak(args: argparse.Namespace) -> int:
    """Conservatively strip only known NextGen keys from Flatpak overrides when no manifest exists."""
    home = resolve_home(args.home)
    dry_run = args.dry_run
    shim_path = str(home / ".var/app/com.stremio.Stremio/data/stremio-mpv-shim.so")
    apps = [
        "rocks.shy.VacuumTube",
        "org.jellyfin.JellyfinDesktop",
        "com.stremio.Stremio",
        "org.kde.haruna",
        "org.mozilla.firefox",
    ]
    for app_id in apps:
        ov = home / FLATPAK_OVERRIDES_REL_DIR / app_id
        if not ov.exists():
            continue
        ini = FlatpakIni(ov.read_text(encoding="utf-8"))
        changed = False
        present, val = ini.get("Environment", "LIBVA_DRIVER_NAME")
        if present and val == "iHD":
            if dry_run:
                print(f"[dry-run] legacy clean {ov}: remove [Environment] LIBVA_DRIVER_NAME=iHD")
            else:
                ini.delete("Environment", "LIBVA_DRIVER_NAME")
            changed = True
        if app_id == "com.stremio.Stremio":
            p_ld, v_ld = ini.get("Environment", "LD_PRELOAD")
            if p_ld and v_ld is not None and ("stremio-mpv-shim.so" in v_ld or v_ld == shim_path):
                if dry_run:
                    print(f"[dry-run] legacy clean {ov}: remove [Environment] LD_PRELOAD={v_ld}")
                else:
                    ini.delete("Environment", "LD_PRELOAD")
                changed = True
        if changed and not dry_run:
            if ini.has_any_keys():
                atomic_write_bytes(ov, ini.render().encode("utf-8"), mode=0o644)
            else:
                ov.unlink(missing_ok=True)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    home = resolve_home(args.home)
    manifest = load_manifest(home)
    if manifest is None:
        info = {"installed": False, "status": "not_installed"}
        if args.json:
            print(json.dumps(info, indent=2))
        else:
            print("Status: not_installed (no manifest found)")
        return 0

    missing: list[str] = []
    drifted: list[str] = []
    for rel_posix, entry in manifest.get("entries", {}).items():
        _, dst = normalize_rel_path(home, rel_posix)
        if not (dst.exists() or dst.is_symlink()):
            missing.append(rel_posix)
            continue
        expected = entry.get("installed_sha256")
        if expected is None:
            continue
        actual = sha256_dir(dst) if entry.get("type") == "dir" else sha256_file(dst)
        if actual != expected:
            drifted.append(rel_posix)

    info = {
        "installed": manifest.get("status") != "rolled_back",
        "schema_version": manifest.get("schema_version"),
        "install_id": manifest.get("install_id"),
        "status": manifest.get("status"),
        "gpu_profile": manifest.get("gpu_profile"),
        "started_at": manifest.get("started_at"),
        "completed_at": manifest.get("completed_at"),
        "entry_count": len(manifest.get("entries", {})),
        "flatpak_override_count": len(manifest.get("flatpak_overrides", {})),
        "missing": missing,
        "drifted": drifted,
    }
    if args.json:
        print(json.dumps(info, indent=2))
    else:
        print(f"Status: {info['status']} (install_id={info['install_id']}, gpu_profile={info['gpu_profile']})")
        print(f"Tracked entries: {info['entry_count']}, Flatpak overrides: {info['flatpak_override_count']}")
        if missing:
            print(f"Missing ({len(missing)}): {', '.join(missing)}")
        if drifted:
            print(f"Modified since install ({len(drifted)}): {', '.join(drifted)}")
    return 0


def cmd_detect_gpu(args: argparse.Namespace) -> int:
    res = detect_gpu_profile(gpu_override=args.gpu, sysfs_pci_dir=args.sysfs_pci_dir)
    if args.json:
        print(json.dumps(res, indent=2))
    elif args.shell:
        print(f"GPU_PROFILE={res['profile']}")
        print(f"VAAPI_DRIVER={res['vaapi_driver']}")
        print(f"INSTALL_INTEL_VAAPI_CONF={1 if res['install_intel_vaapi_conf'] else 0}")
    else:
        driver_desc = res["vaapi_driver"] or "(auto/unset)"
        print(f"GPU profile: {res['profile']} | LIBVA_DRIVER_NAME: {driver_desc} | {res['reason']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--dry-run", "-n", action="store_true", default=argparse.SUPPRESS, help="Preview actions without filesystem writes")
    common.add_argument("--home", default=argparse.SUPPRESS, help="Override target HOME directory")

    parser = argparse.ArgumentParser(
        prog="nextgen-manifest.py",
        description="Transactional user-space manifest and rollback helper for NextGen Plasma Bigscreen.",
        parents=[common],
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_begin = sub.add_parser("begin", parents=[common], help="Start or resume an install transaction")
    p_begin.add_argument("--gpu-profile", default="none")
    p_begin.add_argument("--repair", action="store_true")
    p_begin.set_defaults(func=cmd_begin)

    p_file = sub.add_parser("install-file", parents=[common], help="Atomically install and track a file")
    p_file.add_argument("--src", required=True)
    p_file.add_argument("--dst", required=True)
    p_file.add_argument("--mode", default="0644")
    p_file.add_argument("--preserve-user-edits", action="store_true")
    p_file.add_argument("--keep-existing", action="store_true")
    p_file.add_argument("--force", action="store_true")
    p_file.add_argument("--repair", action="store_true")
    p_file.set_defaults(func=cmd_install_file)

    p_tpl = sub.add_parser("install-template", parents=[common], help="Render @HOME@ template and track it")
    p_tpl.add_argument("--src", required=True)
    p_tpl.add_argument("--dst", required=True)
    p_tpl.add_argument("--mode", default="0644")
    p_tpl.add_argument("--preserve-user-edits", action="store_true")
    p_tpl.add_argument("--keep-existing", action="store_true")
    p_tpl.add_argument("--force", action="store_true")
    p_tpl.add_argument("--repair", action="store_true")
    p_tpl.set_defaults(func=cmd_install_template)

    p_dir = sub.add_parser("install-dir", parents=[common], help="Atomically install and track a directory")
    p_dir.add_argument("--src", required=True)
    p_dir.add_argument("--dst", required=True)
    p_dir.set_defaults(func=cmd_install_dir)

    p_fp = sub.add_parser("patch-flatpak-override", parents=[common], help="INI-safe Flatpak override patching")
    p_fp.add_argument("--app-id", required=True)
    p_fp.add_argument("--set", dest="set_kv", action="append", default=[], help="Section:Key=Value")
    p_fp.add_argument("--unset", dest="unset_k", action="append", default=[], help="Section:Key")
    p_fp.set_defaults(func=cmd_patch_flatpak_override)

    p_commit = sub.add_parser("commit", parents=[common], help="Mark active install transaction complete")
    p_commit.set_defaults(func=cmd_commit)

    p_rb = sub.add_parser("rollback", parents=[common], help="Revert tracked files and Flatpak overrides")
    p_rb.set_defaults(func=cmd_rollback)

    p_leg = sub.add_parser("legacy-clean-flatpak", parents=[common], help="Conservatively clean legacy Flatpak overrides")
    p_leg.set_defaults(func=cmd_legacy_clean_flatpak)

    p_st = sub.add_parser("status", parents=[common], help="Show manifest status and drift")
    p_st.add_argument("--json", action="store_true")
    p_st.set_defaults(func=cmd_status)

    p_gpu = sub.add_parser("detect-gpu", parents=[common], help="Read-only GPU VA-API profile detection")
    p_gpu.add_argument("--gpu", default="auto")
    p_gpu.add_argument("--sysfs-pci-dir", default="/sys/bus/pci/devices")
    p_gpu.add_argument("--json", action="store_true")
    p_gpu.add_argument("--shell", action="store_true")
    p_gpu.set_defaults(func=cmd_detect_gpu)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "dry_run"):
        args.dry_run = False
    if not hasattr(args, "home"):
        args.home = None
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"nextgen-manifest error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

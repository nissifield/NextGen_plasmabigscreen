#!/usr/bin/env python3
"""Automated safety test suite for NextGen Plasma Bigscreen installer and rollback.

Verifies transactional manifest tracking, dry-run zero-mutation guarantees,
GPU-aware VA-API override selection, INI-safe Flatpak override patching,
pre-existing user config & plasmoid backup/restoration, interrupted-install
recovery (--repair and rollback), missing C compiler fallback, and idempotent
re-installs and rollbacks.

Test Harness Limitations:
- Runs exclusively against isolated temporary directories via fake ``HOME`` and
  passes ``--skip-services`` so live host ``systemctl --user``, KWin DBus
  (``qdbus6``), ``steamosctl``, evdev/CEC devices, and real ``/home`` are never
  touched.
- GPU auto-detection is tested against synthetic PCI sysfs fixtures as well as
  explicit ``--gpu`` overrides rather than live hardware registers.
- Does not verify runtime Plasma Bigscreen shell rendering or Flatpak sandbox
  execution; those require manual validation on a KDE Plasma 6 host.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "install.sh"
ROLLBACK_SH = REPO_ROOT / "rollback-tv-setup.sh"
MANIFEST_PY = REPO_ROOT / "bin" / "nextgen-manifest.py"


def load_manifest_module():
    loader = importlib.machinery.SourceFileLoader("nextgen_manifest", str(MANIFEST_PY))
    spec = importlib.util.spec_from_loader("nextgen_manifest", loader)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


manifest_mod = load_manifest_module()


def snapshot_tree(root: Path) -> dict[str, bytes | str]:
    """Capture a complete snapshot of all files, symlinks, and empty dirs under root."""
    snap: dict[str, bytes | str] = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        filenames.sort()
        cur = Path(dirpath)
        rel_dir = cur.relative_to(root).as_posix()
        if rel_dir != "." and not dirnames and not filenames:
            snap[f"DIR:{rel_dir}"] = ""
        for name in filenames:
            p = cur / name
            rel = p.relative_to(root).as_posix()
            if p.is_symlink():
                snap[f"LINK:{rel}"] = os.readlink(p)
            else:
                snap[f"FILE:{rel}"] = p.read_bytes()
    return snap


class TestInstallerSafety(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="nextgen-installer-test-")
        self.home = Path(self._tmp.name) / "home"
        self.home.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _base_env(self, path_override: str | None = None) -> dict[str, str]:
        env = os.environ.copy()
        env["HOME"] = str(self.home)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        if path_override is not None:
            env["PATH"] = path_override
        return env

    def _run_install(self, *args: str, path_override: str | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(INSTALL_SH), "--skip-services", *args],
            cwd=str(REPO_ROOT),
            env=self._base_env(path_override=path_override),
            capture_output=True,
            text=True,
            check=False,
        )

    def _run_rollback(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(ROLLBACK_SH), "--skip-services", *args],
            cwd=str(REPO_ROOT),
            env=self._base_env(),
            capture_output=True,
            text=True,
            check=False,
        )

    def _manifest_path(self) -> Path:
        return self.home / ".local/state/nextgen-plasmabigscreen/manifest.json"

    def _read_manifest(self) -> dict:
        return json.loads(self._manifest_path().read_text(encoding="utf-8"))

    # (a) --dry-run on fresh fake $HOME creates ZERO files/directories
    def test_a_dry_run_creates_zero_files(self) -> None:
        res = self._run_install("--dry-run", "--gpu", "intel-ihd", "--with-hardware-presets")
        self.assertEqual(res.returncode, 0, msg=res.stderr + "\n" + res.stdout)
        self.assertEqual(list(self.home.iterdir()), [], msg=f"Dry-run created entries: {list(self.home.rglob('*'))}")
        self.assertIn("[dry-run]", res.stdout)

    # (b) Fresh install (--gpu intel-ihd) creates manifest, installs binaries/configs/plasmoid, VA-API, Stremio shim
    def test_b_fresh_install_intel_ihd(self) -> None:
        res = self._run_install("--gpu", "intel-ihd", "--with-hardware-presets")
        self.assertEqual(res.returncode, 0, msg=res.stderr + "\n" + res.stdout)

        manifest = self._read_manifest()
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["status"], "complete")
        self.assertEqual(manifest["gpu_profile"], "intel-ihd")
        self.assertIsNotNone(manifest["completed_at"])

        # Core binaries & helpers
        self.assertTrue((self.home / ".local/bin/tv-display-mode").is_file())
        self.assertTrue((self.home / ".local/bin/nextgen-manifest.py").is_file())
        self.assertTrue((self.home / "rollback-tv-setup.sh").is_file())
        self.assertTrue((self.home / ".config/tv-display-mode/config.json").is_file())
        self.assertTrue((self.home / ".local/share/plasma/plasmoids/org.kde.bigscreen.homescreen").is_dir())
        self.assertTrue((self.home / ".config/environment.d/90-intel-vaapi.conf").is_file())

        # Flatpak overrides have LIBVA_DRIVER_NAME=iHD
        for app_id in (
            "com.stremio.Stremio",
            "org.jellyfin.JellyfinDesktop",
            "org.kde.haruna",
            "org.mozilla.firefox",
            "rocks.shy.VacuumTube",
        ):
            ov = self.home / ".local/share/flatpak/overrides" / app_id
            self.assertTrue(ov.is_file(), msg=f"Missing override for {app_id}")
            text = ov.read_text(encoding="utf-8")
            self.assertIn("LIBVA_DRIVER_NAME=iHD", text, msg=f"{app_id} missing iHD:\n{text}")

        # Stremio shim compiled and LD_PRELOAD set (assuming gcc/cc exists in test environment)
        if shutil.which("gcc") or shutil.which("cc"):
            shim = self.home / ".var/app/com.stremio.Stremio/data/stremio-mpv-shim.so"
            self.assertTrue(shim.is_file())
            stremio_ov = (self.home / ".local/share/flatpak/overrides/com.stremio.Stremio").read_text(encoding="utf-8")
            self.assertIn(f"LD_PRELOAD={shim}", stremio_ov)

    # (c) Non-Intel GPU (--gpu amd and --gpu nvidia) never sets LIBVA_DRIVER_NAME=iHD or 90-intel-vaapi.conf
    def test_c_non_intel_gpu_skips_intel_vaapi(self) -> None:
        for gpu in ("amd", "nvidia"):
            with self.subTest(gpu=gpu):
                # Use a fresh sub-home per GPU profile
                sub_home = Path(self._tmp.name) / f"home-{gpu}"
                sub_home.mkdir(parents=True, exist_ok=True)
                self.home = sub_home

                res = self._run_install("--gpu", gpu, "--with-hardware-presets")
                self.assertEqual(res.returncode, 0, msg=res.stderr + "\n" + res.stdout)

                manifest = self._read_manifest()
                self.assertEqual(manifest["status"], "complete")
                self.assertEqual(manifest["gpu_profile"], gpu)

                # 90-intel-vaapi.conf MUST NOT exist
                self.assertFalse((self.home / ".config/environment.d/90-intel-vaapi.conf").exists())

                # No Flatpak override may contain LIBVA_DRIVER_NAME=iHD
                ov_dir = self.home / ".local/share/flatpak/overrides"
                if ov_dir.is_dir():
                    for ov in ov_dir.iterdir():
                        text = ov.read_text(encoding="utf-8")
                        self.assertNotIn("LIBVA_DRIVER_NAME=iHD", text, msg=f"{ov.name} got iHD on {gpu}!")

                # Unneeded overrides (Jellyfin/Haruna) are not created when no keys apply
                self.assertFalse((ov_dir / "org.jellyfin.JellyfinDesktop").exists())
                self.assertFalse((ov_dir / "org.kde.haruna").exists())

                # Firefox and VacuumTube still get their non-VA-API keys
                ff_text = (ov_dir / "org.mozilla.firefox").read_text(encoding="utf-8")
                self.assertIn("org.kde.plasma.browser.integration=talk", ff_text)
                vt_text = (ov_dir / "rocks.shy.VacuumTube").read_text(encoding="utf-8")
                self.assertIn("sockets=!fallback-x11;wayland;!x11;", vt_text)

    # Extra unit verification of sysfs PCI GPU auto-detection
    def test_c_sysfs_gpu_auto_detection(self) -> None:
        pci_root = Path(self._tmp.name) / "sysfs-pci"

        def make_sysfs(case_name: str, devices: list[tuple[str, str, str]]) -> Path:
            root = pci_root / case_name
            for idx, (pci_class, vendor, device) in enumerate(devices):
                dev_dir = root / f"0000:00:0{idx}.0"
                dev_dir.mkdir(parents=True, exist_ok=True)
                (dev_dir / "class").write_text(pci_class + "\n", encoding="utf-8")
                (dev_dir / "vendor").write_text(vendor + "\n", encoding="utf-8")
                (dev_dir / "device").write_text(device + "\n", encoding="utf-8")
            return root

        intel_gen12 = make_sysfs("intel", [("0x030000", "0x8086", "0x9a49")])
        amd_only = make_sysfs("amd", [("0x030000", "0x1002", "0x744c")])
        nvidia_only = make_sysfs("nvidia", [("0x030000", "0x10de", "0x2684")])
        hybrid = make_sysfs("hybrid", [("0x030000", "0x8086", "0x9a49"), ("0x030200", "0x10de", "0x25a0")])

        self.assertEqual(manifest_mod.detect_gpu_profile("auto", str(intel_gen12))["vaapi_driver"], "iHD")
        self.assertEqual(manifest_mod.detect_gpu_profile("auto", str(amd_only))["profile"], "amd")
        self.assertEqual(manifest_mod.detect_gpu_profile("auto", str(amd_only))["vaapi_driver"], "")
        self.assertEqual(manifest_mod.detect_gpu_profile("auto", str(nvidia_only))["profile"], "nvidia")
        self.assertEqual(manifest_mod.detect_gpu_profile("auto", str(nvidia_only))["vaapi_driver"], "")
        self.assertEqual(manifest_mod.detect_gpu_profile("auto", str(hybrid))["vaapi_driver"], "")

    # (d) Pre-existing user configs, custom plasmoid, and unrelated Flatpak overrides survive install -> upgrade -> uninstall
    def test_d_preexisting_user_state_survives_install_upgrade_uninstall(self) -> None:
        # Seed pre-existing user files
        powerdevil = self.home / ".config/powerdevilrc"
        kwinrules = self.home / ".config/kwinrulesrc"
        tv_cfg = self.home / ".config/tv-display-mode/config.json"
        custom_plasmoid_file = self.home / ".local/share/plasma/plasmoids/org.kde.bigscreen.homescreen/custom.qml"
        ff_ov = self.home / ".local/share/flatpak/overrides/org.mozilla.firefox"
        other_ov = self.home / ".local/share/flatpak/overrides/org.example.App"

        for p in (powerdevil, kwinrules, tv_cfg, custom_plasmoid_file, ff_ov, other_ov):
            p.parent.mkdir(parents=True, exist_ok=True)

        orig_powerdevil = "[AC][SuspendAndShutdown]\nPowerButtonAction=8\n# User custom power config\n"
        orig_kwinrules = "[General]\ncount=1\n[1]\nDescription=User Custom Rule\n"
        orig_tv_cfg = json.dumps({"output": "HDMI-A-1", "poll_interval_sec": 7}, indent=2) + "\n"
        orig_plasmoid_qml = "// User's bespoke custom homescreen QML\n"
        orig_ff_ov = (
            "[Session Bus Policy]\n"
            "org.kde.plasma.browser.integration=talk\n"
            "\n"
            "[Environment]\n"
            "FOO=bar\n"
        )
        orig_other_ov = "[Context]\nfilesystems=home;\n\n[Environment]\nMY_APP_FLAG=true\n"

        powerdevil.write_text(orig_powerdevil, encoding="utf-8")
        kwinrules.write_text(orig_kwinrules, encoding="utf-8")
        tv_cfg.write_text(orig_tv_cfg, encoding="utf-8")
        custom_plasmoid_file.write_text(orig_plasmoid_qml, encoding="utf-8")
        ff_ov.write_text(orig_ff_ov, encoding="utf-8")
        other_ov.write_text(orig_other_ov, encoding="utf-8")

        # 1. Install
        r1 = self._run_install("--gpu", "intel-ihd", "--with-hardware-presets")
        self.assertEqual(r1.returncode, 0, msg=r1.stderr + "\n" + r1.stdout)

        # Pre-existing tv-display-mode/config.json must stay untouched during install
        self.assertEqual(tv_cfg.read_text(encoding="utf-8"), orig_tv_cfg)

        # Firefox override preserves FOO=bar and browser integration while adding iHD
        ff_after_install = ff_ov.read_text(encoding="utf-8")
        self.assertIn("org.kde.plasma.browser.integration=talk", ff_after_install)
        self.assertIn("FOO=bar", ff_after_install)
        self.assertIn("LIBVA_DRIVER_NAME=iHD", ff_after_install)

        # Unrelated app override completely untouched
        self.assertEqual(other_ov.read_text(encoding="utf-8"), orig_other_ov)

        # 2. Upgrade (second install)
        r2 = self._run_install("--gpu", "intel-ihd", "--with-hardware-presets")
        self.assertEqual(r2.returncode, 0, msg=r2.stderr + "\n" + r2.stdout)
        self.assertEqual(tv_cfg.read_text(encoding="utf-8"), orig_tv_cfg)
        self.assertEqual(other_ov.read_text(encoding="utf-8"), orig_other_ov)

        # 3. Uninstall / Rollback
        rb = self._run_rollback()
        self.assertEqual(rb.returncode, 0, msg=rb.stderr + "\n" + rb.stdout)

        # Every single pre-existing user asset must be restored intact!
        self.assertEqual(powerdevil.read_text(encoding="utf-8"), orig_powerdevil)
        self.assertEqual(kwinrules.read_text(encoding="utf-8"), orig_kwinrules)
        self.assertEqual(tv_cfg.read_text(encoding="utf-8"), orig_tv_cfg)
        self.assertTrue(custom_plasmoid_file.is_file())
        self.assertEqual(custom_plasmoid_file.read_text(encoding="utf-8"), orig_plasmoid_qml)
        self.assertEqual(other_ov.read_text(encoding="utf-8"), orig_other_ov)

        ff_after_rb = ff_ov.read_text(encoding="utf-8")
        self.assertIn("org.kde.plasma.browser.integration=talk", ff_after_rb)
        self.assertIn("FOO=bar", ff_after_rb)
        self.assertNotIn("LIBVA_DRIVER_NAME=iHD", ff_after_rb)

        # NextGen-created files must be gone
        self.assertFalse((self.home / ".local/bin/tv-display-mode").exists())
        self.assertFalse((self.home / ".config/environment.d/90-intel-vaapi.conf").exists())
        self.assertFalse((self.home / ".local/share/flatpak/overrides/org.jellyfin.JellyfinDesktop").exists())

    # (e) Repeated install / upgrade is idempotent and preserves user edits to config.json
    def test_e_upgrade_idempotent_and_preserves_user_edits(self) -> None:
        r1 = self._run_install("--gpu", "intel-ihd")
        self.assertEqual(r1.returncode, 0, msg=r1.stderr + "\n" + r1.stdout)

        # User edits NextGen-created config.json after install
        tv_cfg = self.home / ".config/tv-display-mode/config.json"
        edited_cfg = json.loads(tv_cfg.read_text(encoding="utf-8"))
        edited_cfg["output"] = "HDMI-A-2"
        edited_cfg["poll_interval_sec"] = 9
        edited_text = json.dumps(edited_cfg, indent=2) + "\n"
        tv_cfg.write_text(edited_text, encoding="utf-8")

        # Upgrade without --force MUST preserve the user's edits
        r2 = self._run_install("--gpu", "intel-ihd")
        self.assertEqual(r2.returncode, 0, msg=r2.stderr + "\n" + r2.stdout)
        self.assertEqual(tv_cfg.read_text(encoding="utf-8"), edited_text)
        self.assertIn("Preserving user-edited config", r2.stdout)

        # Upgrade with --force overwrites AFTER backing up the user's edited version
        r3 = self._run_install("--gpu", "intel-ihd", "--force")
        self.assertEqual(r3.returncode, 0, msg=r3.stderr + "\n" + r3.stdout)
        self.assertNotEqual(tv_cfg.read_text(encoding="utf-8"), edited_text)
        manifest = self._read_manifest()
        extra_backups = manifest["entries"][".config/tv-display-mode/config.json"].get("extra_backups", [])
        self.assertTrue(extra_backups, msg="Expected backup of user-edited config.json before --force overwrite")
        backup_file = self.home / ".local/state/nextgen-plasmabigscreen" / extra_backups[-1]
        self.assertEqual(backup_file.read_text(encoding="utf-8"), edited_text)

    # (f) Interrupted install simulation recovers cleanly via --repair AND via rollback-tv-setup.sh
    def test_f_interrupted_install_recovery_and_rollback(self) -> None:
        # Subtest 1: Recover via --repair
        with self.subTest(mode="repair"):
            sub_home = Path(self._tmp.name) / "home-interrupted-repair"
            sub_home.mkdir(parents=True, exist_ok=True)
            self.home = sub_home

            # Simulate an interrupted install: partial manifest (status=in_progress) + 1 pre-existing backup + 1 partial file
            state_dir = self.home / ".local/state/nextgen-plasmabigscreen"
            backup_file = state_dir / "backups/20261122T000000Z/.config/powerdevilrc"
            backup_file.parent.mkdir(parents=True, exist_ok=True)
            backup_file.write_text("[AC]\nUserOriginal=1\n", encoding="utf-8")

            partial_bin = self.home / ".local/bin/tv-display-mode"
            partial_bin.parent.mkdir(parents=True, exist_ok=True)
            partial_bin.write_text("corrupted-partial", encoding="utf-8")

            partial_manifest = {
                "schema_version": 1,
                "install_id": "interrupted-001",
                "status": "in_progress",
                "started_at": "2026-11-22T00:00:00Z",
                "completed_at": None,
                "gpu_profile": "intel-ihd",
                "entries": {
                    ".local/bin/tv-display-mode": {
                        "type": "file",
                        "ownership": "nextgen_created",
                        "installed_sha256": "deadbeef",
                        "mode": "0755",
                        "backup_path": None,
                        "preserve_user_edits": False,
                    },
                    ".config/powerdevilrc": {
                        "type": "file",
                        "ownership": "user_modified",
                        "installed_sha256": "deadbeef",
                        "mode": "0644",
                        "backup_path": "backups/20261122T000000Z/.config/powerdevilrc",
                        "preserve_user_edits": False,
                    },
                },
                "flatpak_overrides": {},
                "flatpak_override_meta": {},
            }
            (state_dir / "manifest.json").write_text(json.dumps(partial_manifest, indent=2), encoding="utf-8")

            res = self._run_install("--repair", "--gpu", "intel-ihd", "--with-hardware-presets")
            self.assertEqual(res.returncode, 0, msg=res.stderr + "\n" + res.stdout)
            self.assertIn("Recovering interrupted install", res.stdout)

            manifest = self._read_manifest()
            self.assertEqual(manifest["status"], "complete")
            # Original pre-NextGen backup path for powerdevilrc MUST be preserved!
            self.assertEqual(
                manifest["entries"][".config/powerdevilrc"]["backup_path"],
                "backups/20261122T000000Z/.config/powerdevilrc",
            )
            # Corrupted binary must be reconciled to repo version
            self.assertEqual(
                partial_bin.read_bytes(),
                (REPO_ROOT / "bin/tv-display-mode").read_bytes(),
            )

        # Subtest 2: Clean rollback of an interrupted install
        with self.subTest(mode="rollback"):
            sub_home = Path(self._tmp.name) / "home-interrupted-rollback"
            sub_home.mkdir(parents=True, exist_ok=True)
            self.home = sub_home

            state_dir = self.home / ".local/state/nextgen-plasmabigscreen"
            backup_file = state_dir / "backups/20261122T000000Z/.config/powerdevilrc"
            backup_file.parent.mkdir(parents=True, exist_ok=True)
            backup_file.write_text("[AC]\nUserOriginal=1\n", encoding="utf-8")

            powerdevil = self.home / ".config/powerdevilrc"
            powerdevil.parent.mkdir(parents=True, exist_ok=True)
            powerdevil.write_text("[AC]\nNextGenPartial=1\n", encoding="utf-8")

            partial_bin = self.home / ".local/bin/tv-display-mode"
            partial_bin.parent.mkdir(parents=True, exist_ok=True)
            partial_bin.write_text("partial-script", encoding="utf-8")

            partial_manifest = {
                "schema_version": 1,
                "install_id": "interrupted-002",
                "status": "in_progress",
                "started_at": "2026-11-22T00:00:00Z",
                "completed_at": None,
                "gpu_profile": "amd",
                "entries": {
                    ".local/bin/tv-display-mode": {
                        "type": "file",
                        "ownership": "nextgen_created",
                        "installed_sha256": "deadbeef",
                        "mode": "0755",
                        "backup_path": None,
                    },
                    ".config/powerdevilrc": {
                        "type": "file",
                        "ownership": "user_modified",
                        "installed_sha256": "deadbeef",
                        "mode": "0644",
                        "backup_path": "backups/20261122T000000Z/.config/powerdevilrc",
                    },
                },
                "flatpak_overrides": {},
                "flatpak_override_meta": {},
            }
            (state_dir / "manifest.json").write_text(json.dumps(partial_manifest, indent=2), encoding="utf-8")

            rb = self._run_rollback()
            self.assertEqual(rb.returncode, 0, msg=rb.stderr + "\n" + rb.stdout)
            self.assertFalse(partial_bin.exists())
            self.assertEqual(powerdevil.read_text(encoding="utf-8"), "[AC]\nUserOriginal=1\n")
            self.assertEqual(self._read_manifest()["status"], "rolled_back")

    # (g) rollback --dry-run makes zero modifications; rollback restores & deletes; running rollback twice is idempotent
    def test_g_rollback_dry_run_and_idempotency(self) -> None:
        r_inst = self._run_install("--gpu", "intel-ihd", "--with-hardware-presets")
        self.assertEqual(r_inst.returncode, 0, msg=r_inst.stderr + "\n" + r_inst.stdout)

        before_dry = snapshot_tree(self.home)
        rb_dry = self._run_rollback("--dry-run")
        self.assertEqual(rb_dry.returncode, 0, msg=rb_dry.stderr + "\n" + rb_dry.stdout)
        self.assertIn("[dry-run]", rb_dry.stdout)
        self.assertEqual(snapshot_tree(self.home), before_dry, msg="rollback --dry-run modified HOME!")

        rb1 = self._run_rollback()
        self.assertEqual(rb1.returncode, 0, msg=rb1.stderr + "\n" + rb1.stdout)
        self.assertEqual(self._read_manifest()["status"], "rolled_back")
        self.assertFalse((self.home / ".local/bin/tv-display-mode").exists())

        # Second rollback must succeed cleanly (exit 0, idempotent)
        rb2 = self._run_rollback()
        self.assertEqual(rb2.returncode, 0, msg=rb2.stderr + "\n" + rb2.stdout)
        self.assertIn("already rolled back", rb2.stdout.lower())

    # (h) Missing C compiler skips Stremio shim cleanly and does NOT write a broken LD_PRELOAD override
    def test_h_missing_c_compiler_skips_ld_preload(self) -> None:
        # Build a clean PATH containing bash, python3, and core utilities, but NO gcc or cc.
        clean_bin = Path(self._tmp.name) / "no-cc-bin"
        clean_bin.mkdir(parents=True, exist_ok=True)
        for tool in ("bash", "python3", "basename", "dirname", "mktemp", "rm", "mkdir", "cp", "chmod", "env"):
            found = shutil.which(tool)
            if found:
                os.symlink(found, clean_bin / tool)

        res = self._run_install("--gpu", "amd", path_override=str(clean_bin))
        self.assertEqual(res.returncode, 0, msg=res.stderr + "\n" + res.stdout)
        self.assertIn("gcc/cc not found", res.stdout)

        shim = self.home / ".var/app/com.stremio.Stremio/data/stremio-mpv-shim.so"
        self.assertFalse(shim.exists())

        stremio_ov = self.home / ".local/share/flatpak/overrides/com.stremio.Stremio"
        if stremio_ov.exists():
            self.assertNotIn("LD_PRELOAD", stremio_ov.read_text(encoding="utf-8"))

    # (i) Legacy rollback (no manifest.json) conservatively strips NextGen keys and is idempotent
    def test_i_legacy_rollback_preserves_unrelated_overrides_and_is_idempotent(self) -> None:
        # Create a legacy install footprint without manifest.json
        legacy_bin = self.home / ".local/bin/tv-display-mode"
        legacy_bin.parent.mkdir(parents=True, exist_ok=True)
        legacy_bin.write_text("#!/bin/sh\necho legacy\n", encoding="utf-8")

        ff_ov = self.home / ".local/share/flatpak/overrides/org.mozilla.firefox"
        ff_ov.parent.mkdir(parents=True, exist_ok=True)
        ff_ov.write_text(
            "[Session Bus Policy]\n"
            "org.kde.plasma.browser.integration=talk\n"
            "\n"
            "[Environment]\n"
            "FOO=bar\n"
            "LIBVA_DRIVER_NAME=iHD\n",
            encoding="utf-8",
        )

        unrelated_cfg = self.home / ".config/tv-display-mode/config.json"
        unrelated_cfg.parent.mkdir(parents=True, exist_ok=True)
        unrelated_cfg.write_text('{"output": "HDMI-A-1"}\n', encoding="utf-8")

        # Dry-run makes zero changes
        before = snapshot_tree(self.home)
        r_dry = self._run_rollback("--dry-run")
        self.assertEqual(r_dry.returncode, 0, msg=r_dry.stderr + "\n" + r_dry.stdout)
        self.assertEqual(snapshot_tree(self.home), before)

        # First legacy rollback
        r1 = self._run_rollback()
        self.assertEqual(r1.returncode, 0, msg=r1.stderr + "\n" + r1.stdout)
        self.assertFalse(legacy_bin.exists())
        self.assertTrue(unrelated_cfg.is_file())

        ff_after = ff_ov.read_text(encoding="utf-8")
        self.assertIn("org.kde.plasma.browser.integration=talk", ff_after)
        self.assertIn("FOO=bar", ff_after)
        self.assertNotIn("LIBVA_DRIVER_NAME=iHD", ff_after)

        # Second legacy rollback is idempotent
        r2 = self._run_rollback()
        self.assertEqual(r2.returncode, 0, msg=r2.stderr + "\n" + r2.stdout)

    # (j) Symlinked HOME (e.g. OSTree /home -> var/home on Bazzite/Kinoite) works cleanly
    def test_j_symlinked_ostree_home_dry_run_install_and_rollback(self) -> None:
        real_home = Path(self._tmp.name) / "ostree-root" / "var" / "home" / "tester"
        real_home.mkdir(parents=True, exist_ok=True)
        link_root = Path(self._tmp.name) / "ostree-root" / "home"
        os.symlink(Path(self._tmp.name) / "ostree-root" / "var" / "home", link_root)
        logical_home = link_root / "tester"

        self.home = logical_home

        # --dry-run must succeed and write nothing
        r_dry = self._run_install("--dry-run", "--gpu", "intel-ihd")
        self.assertEqual(r_dry.returncode, 0, msg=r_dry.stderr + "\n" + r_dry.stdout)
        self.assertEqual(snapshot_tree(real_home), {})

        # Real install + rollback through symlinked HOME must succeed
        r_inst = self._run_install("--gpu", "intel-ihd")
        self.assertEqual(r_inst.returncode, 0, msg=r_inst.stderr + "\n" + r_inst.stdout)
        self.assertTrue((real_home / ".local/bin/tv-display-mode").is_file())
        self.assertEqual(self._read_manifest()["status"], "complete")

        # Rendered templates should use logical HOME path consistently
        swap_desktop = (real_home / ".local/share/applications/plasma-bigscreen-swap.desktop").read_text(
            encoding="utf-8"
        )
        self.assertIn(str(logical_home), swap_desktop)

        r_rb = self._run_rollback()
        self.assertEqual(r_rb.returncode, 0, msg=r_rb.stderr + "\n" + r_rb.stdout)
        self.assertFalse((real_home / ".local/bin/tv-display-mode").exists())
        self.assertEqual(self._read_manifest()["status"], "rolled_back")

    # (k) Distro- and architecture-agnostic launchers and template placeholders
    def test_k_distro_and_arch_agnostic_launchers_and_templates(self) -> None:
        # Create a user-local Flatpak Haruna desktop entry to verify @HARUNA_DESKTOP_PATH@ prefers it
        user_haruna = self.home / ".local/share/flatpak/exports/share/applications/org.kde.haruna.desktop"
        user_haruna.parent.mkdir(parents=True, exist_ok=True)
        user_haruna.write_text("[Desktop Entry]\nName=Haruna\n", encoding="utf-8")

        res = self._run_install("--gpu", "amd")
        self.assertEqual(res.returncode, 0, msg=res.stderr + "\n" + res.stdout)

        # Installed Flatpak desktop files must not hardcode --arch=x86_64
        for desktop_name in (
            "com.stremio.Stremio.desktop",
            "org.jellyfin.JellyfinDesktop.desktop",
            "rocks.shy.VacuumTube.desktop",
        ):
            desktop_text = (self.home / ".local/share/applications" / desktop_name).read_text(encoding="utf-8")
            self.assertNotIn("--arch=x86_64", desktop_text, msg=f"{desktop_name} still hardcodes --arch=x86_64")

        # steam-bigpicture.desktop must render @STEAM_EXEC@ cleanly
        steam_desktop = (self.home / ".local/share/applications/steam-bigpicture.desktop").read_text(encoding="utf-8")
        self.assertNotIn("@STEAM_EXEC@", steam_desktop)
        expected_steam = manifest_mod.resolve_steam_exec(self.home)
        self.assertIn(f"Exec={expected_steam} steam://open/bigpicture", steam_desktop)

        # bigscreen-favs must render @HARUNA_DESKTOP_PATH@ and @HOME@ cleanly
        favs_text = (self.home / ".config/bigscreen-favs").read_text(encoding="utf-8")
        self.assertNotIn("@HARUNA_DESKTOP_PATH@", favs_text)
        self.assertNotIn("@HOME@", favs_text)
        self.assertIn(f"desktopPath={user_haruna}", favs_text)
        self.assertIn(f"entryPath={user_haruna}", favs_text)

        # Verify all resolution branches of resolve_steam_exec and resolve_haruna_desktop_path
        fake_root = Path(self._tmp.name) / "fake-host"
        fake_bazzite = fake_root / "usr/bin/bazzite-steam"
        fake_usr_steam = fake_root / "usr/bin/steam"
        fake_sys_fp_steam = fake_root / "var/lib/flatpak/app/com.valvesoftware.Steam"
        fake_home = fake_root / "home/tester"
        fake_home.mkdir(parents=True, exist_ok=True)
        missing = fake_root / "does-not-exist"

        # Fallback -> "steam"
        self.assertEqual(
            manifest_mod.resolve_steam_exec(
                fake_home,
                bazzite_steam=missing,
                usr_steam=missing,
                system_flatpak_app=missing,
                which_fn=lambda _cmd: None,
            ),
            "steam",
        )
        # Flatpak Steam (user or system)
        fake_sys_fp_steam.mkdir(parents=True, exist_ok=True)
        self.assertEqual(
            manifest_mod.resolve_steam_exec(
                fake_home,
                bazzite_steam=missing,
                usr_steam=missing,
                system_flatpak_app=fake_sys_fp_steam,
                which_fn=lambda _cmd: None,
            ),
            "/usr/bin/flatpak run com.valvesoftware.Steam",
        )
        # Native /usr/bin/steam
        fake_usr_steam.parent.mkdir(parents=True, exist_ok=True)
        fake_usr_steam.write_text("#!/bin/sh\n", encoding="utf-8")
        fake_usr_steam.chmod(0o755)
        self.assertEqual(
            manifest_mod.resolve_steam_exec(
                fake_home,
                bazzite_steam=missing,
                usr_steam=fake_usr_steam,
                system_flatpak_app=fake_sys_fp_steam,
                which_fn=lambda _cmd: None,
            ),
            str(fake_usr_steam),
        )
        # Bazzite /usr/bin/bazzite-steam takes highest precedence
        fake_bazzite.write_text("#!/bin/sh\n", encoding="utf-8")
        fake_bazzite.chmod(0o755)
        self.assertEqual(
            manifest_mod.resolve_steam_exec(
                fake_home,
                bazzite_steam=fake_bazzite,
                usr_steam=fake_usr_steam,
                system_flatpak_app=fake_sys_fp_steam,
                which_fn=lambda _cmd: "/alt/steam",
            ),
            str(fake_bazzite),
        )

        # Haruna desktop path resolution order
        fake_sys_haruna = fake_root / "var/lib/flatpak/exports/share/applications/org.kde.haruna.desktop"
        fake_native_haruna = fake_root / "usr/share/applications/org.kde.haruna.desktop"
        # Fallback
        self.assertEqual(
            manifest_mod.resolve_haruna_desktop_path(
                fake_home,
                str(fake_home),
                system_flatpak_desktop=missing,
                native_desktop=missing,
            ),
            "/var/lib/flatpak/exports/share/applications/org.kde.haruna.desktop",
        )
        # Native distro package
        fake_native_haruna.parent.mkdir(parents=True, exist_ok=True)
        fake_native_haruna.write_text("[Desktop Entry]\n", encoding="utf-8")
        self.assertEqual(
            manifest_mod.resolve_haruna_desktop_path(
                fake_home,
                str(fake_home),
                system_flatpak_desktop=missing,
                native_desktop=fake_native_haruna,
            ),
            str(fake_native_haruna),
        )
        # System Flatpak
        fake_sys_haruna.parent.mkdir(parents=True, exist_ok=True)
        fake_sys_haruna.write_text("[Desktop Entry]\n", encoding="utf-8")
        self.assertEqual(
            manifest_mod.resolve_haruna_desktop_path(
                fake_home,
                str(fake_home),
                system_flatpak_desktop=fake_sys_haruna,
                native_desktop=fake_native_haruna,
            ),
            str(fake_sys_haruna),
        )

    # (l) PR #19 rollback & retire-file safety: no ytdl-format in stremio/mpv.conf, clean upgrade retirement
    def test_l_retire_pr19_mpv_configs_and_preserve_user_edits(self) -> None:
        # 1. stremio/mpv.conf must not use Lua/yt-dlp-dependent options unsupported by Stremio's libmpv
        stremio_mpv_src = (REPO_ROOT / "stremio/mpv.conf").read_text(encoding="utf-8")
        self.assertNotIn("ytdl-format", stremio_mpv_src)
        self.assertIn("hwdec=auto-safe", stremio_mpv_src)
        self.assertIn("hwdec-codecs=all", stremio_mpv_src)

        pr19_content = (
            "hwdec=auto-safe\n"
            "hwdec-codecs=all\n"
            "# Prefer hardware-accelerated VP9/HEVC/H.264 over software-decoded AV1 on remote streams\n"
            "ytdl-format=bestvideo[vcodec!^=av01]+bestaudio/best\n"
        )
        pr19_bytes = pr19_content.encode("utf-8")
        pr19_sha = manifest_mod.sha256_bytes(pr19_bytes)

        # 2. Subtest A: Upgrade from PR #19 state cleanly retires unedited nextgen_created files & restores Stremio mpv.conf
        with self.subTest(case="retire_unedited_pr19_files"):
            sub_home = Path(self._tmp.name) / "home-retire-unedited"
            sub_home.mkdir(parents=True, exist_ok=True)
            self.home = sub_home

            r1 = self._run_install("--gpu", "intel-ihd")
            self.assertEqual(r1.returncode, 0, msg=r1.stderr + "\n" + r1.stdout)

            # Simulate PR #19 deployment state on disk and in manifest
            stremio_mpv = self.home / ".var/app/com.stremio.Stremio/config/mpv/mpv.conf"
            jellyfin_mpv = self.home / ".var/app/org.jellyfin.JellyfinDesktop/data/jellyfin-desktop/mpv.conf"
            host_mpv = self.home / ".config/mpv/mpv.conf"
            for p in (stremio_mpv, jellyfin_mpv, host_mpv):
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(pr19_bytes)

            manifest = self._read_manifest()
            manifest["entries"][".var/app/com.stremio.Stremio/config/mpv/mpv.conf"]["installed_sha256"] = pr19_sha
            for rel in (
                ".var/app/org.jellyfin.JellyfinDesktop/data/jellyfin-desktop/mpv.conf",
                ".config/mpv/mpv.conf",
            ):
                manifest["entries"][rel] = {
                    "type": "file",
                    "ownership": "nextgen_created",
                    "installed_sha256": pr19_sha,
                    "mode": "0644",
                    "backup_path": None,
                    "preserve_user_edits": True,
                    "updated_at": "2026-11-27T10:49:37Z",
                }
            self._manifest_path().write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            # --dry-run must leave HOME completely untouched
            before_dry = snapshot_tree(self.home)
            r_dry = self._run_install("--dry-run", "--gpu", "intel-ihd")
            self.assertEqual(r_dry.returncode, 0, msg=r_dry.stderr + "\n" + r_dry.stdout)
            self.assertEqual(snapshot_tree(self.home), before_dry)
            self.assertIn("[dry-run] retire NextGen-created file", r_dry.stdout)

            # Real upgrade removes the two retired files, cleans manifest entries, and downgrades Stremio mpv.conf
            r_up = self._run_install("--gpu", "intel-ihd")
            self.assertEqual(r_up.returncode, 0, msg=r_up.stderr + "\n" + r_up.stdout)
            self.assertFalse(jellyfin_mpv.exists())
            self.assertFalse(host_mpv.exists())
            self.assertEqual(stremio_mpv.read_text(encoding="utf-8"), stremio_mpv_src)

            updated_manifest = self._read_manifest()
            self.assertNotIn(".var/app/org.jellyfin.JellyfinDesktop/data/jellyfin-desktop/mpv.conf", updated_manifest["entries"])
            self.assertNotIn(".config/mpv/mpv.conf", updated_manifest["entries"])

        # 3. Subtest B: Pre-existing untracked OR user-edited ~/.config/mpv/mpv.conf is NEVER deleted
        with self.subTest(case="preserve_untracked_and_user_edited"):
            sub_home = Path(self._tmp.name) / "home-retire-preserve"
            sub_home.mkdir(parents=True, exist_ok=True)
            self.home = sub_home

            host_mpv = self.home / ".config/mpv/mpv.conf"
            host_mpv.parent.mkdir(parents=True, exist_ok=True)
            user_custom = "# User's own mpv config\nvo=gpu-next\n"
            host_mpv.write_text(user_custom, encoding="utf-8")

            r1 = self._run_install("--gpu", "amd")
            self.assertEqual(r1.returncode, 0, msg=r1.stderr + "\n" + r1.stdout)
            self.assertEqual(host_mpv.read_text(encoding="utf-8"), user_custom)
            self.assertNotIn(".config/mpv/mpv.conf", self._read_manifest()["entries"])

            # Now simulate a tracked nextgen_created file that the user subsequently edited
            manifest = self._read_manifest()
            manifest["entries"][".config/mpv/mpv.conf"] = {
                "type": "file",
                "ownership": "nextgen_created",
                "installed_sha256": pr19_sha,
                "mode": "0644",
                "backup_path": None,
                "preserve_user_edits": True,
                "updated_at": "2026-11-27T10:49:37Z",
            }
            self._manifest_path().write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            r2 = self._run_install("--gpu", "amd")
            self.assertEqual(r2.returncode, 0, msg=r2.stderr + "\n" + r2.stdout)
            self.assertEqual(host_mpv.read_text(encoding="utf-8"), user_custom)
            self.assertIn("Preserving user-edited retired config", r2.stdout)
            self.assertNotIn(".config/mpv/mpv.conf", self._read_manifest()["entries"])

        # 4. Subtest C: Retired user_modified file restores its original pre-install backup
        with self.subTest(case="restore_user_modified_backup"):
            sub_home = Path(self._tmp.name) / "home-retire-restore-backup"
            sub_home.mkdir(parents=True, exist_ok=True)
            self.home = sub_home

            r1 = self._run_install("--gpu", "amd")
            self.assertEqual(r1.returncode, 0, msg=r1.stderr + "\n" + r1.stdout)

            host_mpv = self.home / ".config/mpv/mpv.conf"
            host_mpv.parent.mkdir(parents=True, exist_ok=True)
            host_mpv.write_bytes(pr19_bytes)

            orig_content = "# Original pre-NextGen user mpv.conf\nprofile=high-quality\n"
            state_dir = self.home / ".local/state/nextgen-plasmabigscreen"
            backup_rel = "backups/20261127T000000Z/.config/mpv/mpv.conf"
            backup_file = state_dir / backup_rel
            backup_file.parent.mkdir(parents=True, exist_ok=True)
            backup_file.write_text(orig_content, encoding="utf-8")

            manifest = self._read_manifest()
            manifest["entries"][".config/mpv/mpv.conf"] = {
                "type": "file",
                "ownership": "user_modified",
                "installed_sha256": pr19_sha,
                "mode": "0644",
                "backup_path": backup_rel,
                "preserve_user_edits": True,
                "updated_at": "2026-11-27T10:49:37Z",
            }
            self._manifest_path().write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            r2 = self._run_install("--gpu", "amd")
            self.assertEqual(r2.returncode, 0, msg=r2.stderr + "\n" + r2.stdout)
            self.assertEqual(host_mpv.read_text(encoding="utf-8"), orig_content)
            self.assertNotIn(".config/mpv/mpv.conf", self._read_manifest()["entries"])


if __name__ == "__main__":
    unittest.main()

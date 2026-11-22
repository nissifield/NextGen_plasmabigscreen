#!/usr/bin/env python3
"""
Simulated unit tests for nextgen_platform, tv-display-mode, and tv-movie-mode-toggle.

Covers:
- GPU classification & VA-API env recommendations (Intel iHD, Intel legacy i965, AMD, NVIDIA, unknown)
- Display & mode resolution (1080p-only, 4K@30, 4K@60, high-refresh 1440p/1080p, multi-monitor,
  unplug/replug, suspend/resume, missing kscreen-doctor binary, unsupported mode fallback)
- Configurable steam_priority=False (no compulsory 1080p cap when disabled)
- tv-display-mode status read-only guarantee (calls GetStatus, NEVER EvaluateNow)
- tv-display-mode diagnose read-only sanitized report
- tv-movie-mode-toggle dynamic feedback formatting
- Read-only HDMI audio inspection via wpctl
- Sanitization redacting usernames, $HOME, serial numbers, MACs, and UUIDs
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

BIN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin"))
if BIN_DIR not in sys.path:
    sys.path.insert(0, BIN_DIR)

import nextgen_platform  # noqa: E402


def _load_script_module(mod_name: str, filename: str):
    path = os.path.join(BIN_DIR, filename)
    loader = importlib.machinery.SourceFileLoader(mod_name, path)
    spec = importlib.util.spec_from_loader(mod_name, loader)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


tv_display_mode = _load_script_module("tv_display_mode_plat", "tv-display-mode")
tv_movie_toggle = _load_script_module("tv_movie_mode_toggle_plat", "tv-movie-mode-toggle")


def _kscreen_doc(outputs: list[dict]) -> str:
    return json.dumps({"outputs": outputs})


TV_1080P_ONLY = _kscreen_doc(
    [
        {
            "name": "HDMI-A-1",
            "enabled": True,
            "connected": True,
            "primary": True,
            "currentModeId": "1",
            "preferredModes": ["1"],
            "modes": [
                {"id": "1", "name": "1920x1080@60", "refreshRate": 60.0, "size": {"width": 1920, "height": 1080}},
                {"id": "2", "name": "1920x1080@50", "refreshRate": 50.0, "size": {"width": 1920, "height": 1080}},
                {"id": "3", "name": "1280x720@60", "refreshRate": 60.0, "size": {"width": 1280, "height": 720}},
            ],
        }
    ]
)

TV_4K30_DP1 = _kscreen_doc(
    [
        {
            "name": "DP-1",
            "enabled": True,
            "connected": True,
            "primary": True,
            "currentModeId": "12",
            "preferredModes": ["1"],
            "modes": [
                {"id": "1", "name": "3840x2160@30", "refreshRate": 30.0, "size": {"width": 3840, "height": 2160}},
                {"id": "12", "name": "1920x1080@60", "refreshRate": 60.0, "size": {"width": 1920, "height": 1080}},
            ],
        }
    ]
)

TV_4K60_HDMI = _kscreen_doc(
    [
        {
            "name": "HDMI-A-1",
            "enabled": True,
            "connected": True,
            "primary": True,
            "currentModeId": "2",
            "preferredModes": ["1"],
            "modes": [
                {"id": "1", "name": "3840x2160@60", "refreshRate": 60.0, "size": {"width": 3840, "height": 2160}},
                {"id": "2", "name": "1920x1080@60", "refreshRate": 60.0, "size": {"width": 1920, "height": 1080}},
                {"id": "3", "name": "3840x2160@30", "refreshRate": 30.0, "size": {"width": 3840, "height": 2160}},
            ],
        }
    ]
)

MONITOR_HIGH_REFRESH_1440P_1080P = _kscreen_doc(
    [
        {
            "name": "DP-2",
            "enabled": True,
            "connected": True,
            "primary": True,
            "currentModeId": "1",
            "preferredModes": ["1"],
            "vrrPolicy": "automatic",
            "modes": [
                {"id": "1", "name": "2560x1440@144", "refreshRate": 144.0, "size": {"width": 2560, "height": 1440}},
                {"id": "2", "name": "1920x1080@120", "refreshRate": 120.0, "size": {"width": 1920, "height": 1080}},
                {"id": "3", "name": "1920x1080@60", "refreshRate": 60.0, "size": {"width": 1920, "height": 1080}},
            ],
        }
    ]
)

MULTI_MONITOR = _kscreen_doc(
    [
        {
            "name": "eDP-1",
            "enabled": True,
            "connected": True,
            "priority": 2,
            "currentModeId": "1",
            "preferredModes": ["1"],
            "modes": [
                {"id": "1", "name": "1920x1080@60", "refreshRate": 60.0, "size": {"width": 1920, "height": 1080}},
            ],
        },
        {
            "name": "HDMI-A-1",
            "enabled": True,
            "connected": True,
            "priority": 1,
            "currentModeId": "2",
            "preferredModes": ["1"],
            "modes": [
                {"id": "1", "name": "3840x2160@60", "refreshRate": 60.0, "size": {"width": 3840, "height": 2160}},
                {"id": "2", "name": "1920x1080@60", "refreshRate": 60.0, "size": {"width": 1920, "height": 1080}},
            ],
        },
    ]
)


class TestSanitization(unittest.TestCase):
    def test_sanitize_text_redacts_home_user_serial_mac_uuid(self) -> None:
        raw = (
            "User alice at /home/alice/.config/tv-display-mode "
            "and /var/home/bob/data "
            "MAC=aa:bb:cc:dd:ee:ff "
            "UUID=12345678-1234-5678-9abc-def012345678 "
            "serial_number=SN-99887766 uniq=usb-12345"
        )
        cleaned = nextgen_platform.sanitize_text(raw, home_dir="/home/alice", username="alice")
        self.assertNotIn("/home/alice", cleaned)
        self.assertNotIn("/var/home/bob", cleaned)
        self.assertNotIn("alice", cleaned)
        self.assertNotIn("aa:bb:cc:dd:ee:ff", cleaned)
        self.assertNotIn("12345678-1234-5678-9abc-def012345678", cleaned)
        self.assertNotIn("SN-99887766", cleaned)
        self.assertNotIn("usb-12345", cleaned)
        self.assertIn("$HOME", cleaned)
        self.assertIn("<REDACTED_MAC>", cleaned)
        self.assertIn("<REDACTED_UUID>", cleaned)
        self.assertIn("<REDACTED_SERIAL>", cleaned)

    def test_sanitize_dict_recursively_strips_sensitive_keys_and_values(self) -> None:
        payload = {
            "path": "/home/alice/.config/app.json",
            "serial": "ABC123456789",
            "mac_address": "00:11:22:33:44:55",
            "uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "uniq": "AA:BB:CC:DD:EE:FF",
            "nested": [
                {"edid_serial": "987654", "note": "Owned by alice at /home/alice"},
            ],
        }
        cleaned = nextgen_platform.sanitize_dict(payload, home_dir="/home/alice", username="alice")
        self.assertEqual(cleaned["path"], "$HOME/.config/app.json")
        self.assertEqual(cleaned["serial"], "<REDACTED_SERIAL>")
        self.assertEqual(cleaned["mac_address"], "<REDACTED_MAC>")
        self.assertEqual(cleaned["uuid"], "<REDACTED_UUID>")
        self.assertEqual(cleaned["uniq"], "<REDACTED_SERIAL>")
        self.assertEqual(cleaned["nested"][0]["edid_serial"], "<REDACTED_SERIAL>")
        self.assertNotIn("alice", cleaned["nested"][0]["note"])


class TestGpuAdapter(unittest.TestCase):
    def test_classify_intel_ihd_and_legacy_i965(self) -> None:
        ihd = nextgen_platform.classify_gpu_vendor("0x8086", "i915", "Intel iHD driver - Alder Lake-N")
        self.assertEqual(ihd["vendor"], "intel")
        self.assertEqual(ihd["profile"], "intel-ihd")
        self.assertEqual(nextgen_platform.recommended_vaapi_env(ihd), {"LIBVA_DRIVER_NAME": "iHD"})

        xe = nextgen_platform.classify_gpu_vendor("0x8086", "xe", "Intel Arc")
        self.assertEqual(xe["profile"], "intel-ihd")
        self.assertEqual(nextgen_platform.recommended_vaapi_env(xe), {"LIBVA_DRIVER_NAME": "iHD"})

        i965_by_renderer = nextgen_platform.classify_gpu_vendor(
            "0x8086", "i915", "Mesa Intel(R) HD Graphics 4600 (HSW GT2) Haswell"
        )
        self.assertEqual(i965_by_renderer["vendor"], "intel")
        self.assertEqual(i965_by_renderer["profile"], "intel-i965")
        self.assertEqual(
            nextgen_platform.recommended_vaapi_env(i965_by_renderer),
            {"LIBVA_DRIVER_NAME": "i965"},
        )

        i965_by_pci = nextgen_platform.classify_gpu_vendor("0x8086", "i915", "", pci_device_id="0x0412")
        self.assertEqual(i965_by_pci["profile"], "intel-i965")
        self.assertEqual(nextgen_platform.recommended_vaapi_env(i965_by_pci), {"LIBVA_DRIVER_NAME": "i965"})

    def test_classify_amd_nvidia_unknown_never_force_intel_vaapi(self) -> None:
        amd = nextgen_platform.classify_gpu_vendor("0x1002", "amdgpu", "AMD Radeon RX 7800 XT (radeonsi)")
        self.assertEqual(amd["vendor"], "amd")
        self.assertEqual(amd["profile"], "amd-radeonsi")
        self.assertEqual(nextgen_platform.recommended_vaapi_env(amd), {})

        nv_prop = nextgen_platform.classify_gpu_vendor("0x10de", "nvidia", "NVIDIA GeForce RTX 4070")
        self.assertEqual(nv_prop["vendor"], "nvidia")
        self.assertEqual(nv_prop["profile"], "nvidia-proprietary")
        self.assertIn("NVDEC", nv_prop["decode_apis"])
        self.assertIn("Wayland", nv_prop["drm_notes"])
        self.assertEqual(nextgen_platform.recommended_vaapi_env(nv_prop), {})

        nv_open = nextgen_platform.classify_gpu_vendor("0x10de", "nvidia-open", "NVIDIA GeForce RTX 4060")
        self.assertEqual(nv_open["profile"], "nvidia-open")
        self.assertEqual(nextgen_platform.recommended_vaapi_env(nv_open), {})

        nv_nouveau = nextgen_platform.classify_gpu_vendor("0x10de", "nouveau", "NV176")
        self.assertEqual(nv_nouveau["profile"], "nvidia-nouveau")
        self.assertEqual(nextgen_platform.recommended_vaapi_env(nv_nouveau), {})

        unknown = nextgen_platform.classify_gpu_vendor("0x1234", "bochs-drm", "llvmpipe")
        self.assertEqual(unknown["vendor"], "unknown")
        self.assertEqual(nextgen_platform.recommended_vaapi_env(unknown), {})

        # Hybrid Intel + NVIDIA system should NOT globally force Intel LIBVA_DRIVER_NAME
        self.assertEqual(nextgen_platform.recommended_vaapi_env([ihd_gpu := nextgen_platform.classify_gpu_vendor("0x8086", "i915", ""), nv_prop]), {})
        self.assertEqual(nextgen_platform.recommended_vaapi_env([ihd_gpu]), {"LIBVA_DRIVER_NAME": "iHD"})

    def test_detect_gpus_from_simulated_sysfs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Non-display device (network 0x020000) should be ignored
            net_dir = os.path.join(tmp, "0000:00:1f.6")
            os.makedirs(net_dir)
            with open(os.path.join(net_dir, "class"), "w", encoding="utf-8") as fh:
                fh.write("0x020000\n")

            # AMD GPU (VGA 0x030000)
            gpu_dir = os.path.join(tmp, "0000:03:00.0")
            os.makedirs(gpu_dir)
            with open(os.path.join(gpu_dir, "class"), "w", encoding="utf-8") as fh:
                fh.write("0x030000\n")
            with open(os.path.join(gpu_dir, "vendor"), "w", encoding="utf-8") as fh:
                fh.write("0x1002\n")
            with open(os.path.join(gpu_dir, "device"), "w", encoding="utf-8") as fh:
                fh.write("0x747e\n")
            with open(os.path.join(gpu_dir, "driver"), "w", encoding="utf-8") as fh:
                fh.write("amdgpu\n")

            gpus = nextgen_platform.detect_gpus(
                sys_pci_root=tmp,
                vainfo_runner=lambda: (
                    0,
                    "vainfo: Driver version: Mesa Gallium driver 24.2 for AMD Radeon\n"
                    "      VAProfileHEVCMain               : VAEntrypointVLD\n",
                    "",
                ),
            )
            self.assertEqual(len(gpus), 1)
            self.assertEqual(gpus[0]["vendor"], "amd")
            self.assertEqual(gpus[0]["kernel_driver"], "amdgpu")
            self.assertEqual(gpus[0]["recommended_vaapi_env"], {})
            self.assertTrue(gpus[0]["vaapi_probe"]["available"])
            self.assertEqual(gpus[0]["vaapi_probe"]["profiles_count"], 1)


class TestDisplayPolicyAndResilience(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = json.loads(json.dumps(tv_display_mode.DEFAULT_CONFIG))

    def test_1080p_only_tv_graceful_fallback_no_crash(self) -> None:
        cfg = dict(self.cfg, output="auto")
        info = tv_display_mode.parse_kscreen_json(TV_1080P_ONLY, "auto", cfg)
        self.assertTrue(info["available"])
        self.assertEqual(info["output"], "HDMI-A-1")
        self.assertIsNone(info["mode_4k"])
        self.assertEqual(info["mode_1080p"]["id"], "1")
        self.assertFalse(info["capabilities"]["supports_4k"])
        self.assertFalse(info["capabilities"]["hdr_advertised"])
        self.assertFalse(info["capabilities"]["vrr_advertised"])

        resolved = nextgen_platform.resolve_safe_target_mode(info, "4k", cfg)
        self.assertTrue(resolved["ok"])
        self.assertTrue(resolved["fallback"])
        self.assertEqual(resolved["reason"], "mode_unavailable_fallback")
        self.assertEqual(resolved["resolved_target"], "1080p")

        applied = tv_display_mode.apply_display_mode("4k", cfg, dry_run=True, kscreen_info=info)
        self.assertFalse(applied["changed"])
        self.assertTrue(applied["fallback"])
        self.assertEqual(applied["reason"], "mode_unavailable_fallback")
        self.assertEqual(applied["resolved_target"], "1080p")

    def test_4k60_tv_and_4k30_tv_resolution(self) -> None:
        cfg_auto = dict(self.cfg, output="auto")
        info_60 = tv_display_mode.parse_kscreen_json(TV_4K60_HDMI, "auto", cfg_auto)
        self.assertEqual(info_60["output"], "HDMI-A-1")
        self.assertEqual(info_60["mode_4k"]["id"], "1")
        self.assertEqual(info_60["mode_4k"]["refreshRate"], 60.0)
        self.assertTrue(info_60["capabilities"]["supports_4k_60"])
        self.assertFalse(info_60["capabilities"]["supports_4k_120"])

        applied_60 = tv_display_mode.apply_display_mode("4k", cfg_auto, dry_run=True, kscreen_info=info_60)
        self.assertTrue(applied_60["changed"])
        self.assertFalse(applied_60["fallback"])
        self.assertEqual(applied_60["refresh_rate"], 60.0)
        self.assertIn("output.HDMI-A-1.mode.1", applied_60["command"])

        # 4K@30 TV even if user asks for 60Hz cleanly falls back to advertised 4K@30
        cfg_want_60 = json.loads(json.dumps(self.cfg))
        cfg_want_60["mode_4k"]["refresh_rate"] = 60.0
        info_30 = tv_display_mode.parse_kscreen_json(TV_4K30_DP1, "DP-1", cfg_want_60)
        self.assertEqual(info_30["mode_4k"]["id"], "1")
        self.assertEqual(info_30["mode_4k"]["refreshRate"], 30.0)

    def test_high_refresh_display_and_multi_monitor_auto_selection(self) -> None:
        cfg_hi = json.loads(json.dumps(self.cfg))
        cfg_hi["output"] = "auto"
        cfg_hi["mode_1080p"]["refresh_rate"] = "auto"
        info_hi = tv_display_mode.parse_kscreen_json(MONITOR_HIGH_REFRESH_1440P_1080P, "auto", cfg_hi)
        self.assertEqual(info_hi["output"], "DP-2")
        self.assertEqual(info_hi["mode_1080p"]["id"], "2")
        self.assertEqual(info_hi["mode_1080p"]["refreshRate"], 120.0)
        self.assertTrue(info_hi["capabilities"]["vrr_advertised"])

        info_multi = tv_display_mode.parse_kscreen_json(MULTI_MONITOR, "auto", dict(self.cfg, output="auto"))
        self.assertEqual(info_multi["output"], "HDMI-A-1")
        self.assertEqual(info_multi["selection_reason"], "auto_primary_enabled")

    def test_unplug_replug_and_suspend_resume_no_crash_loop(self) -> None:
        cfg = dict(self.cfg, output="DP-1")

        # 1. Unplug: empty outputs list
        unplugged = tv_display_mode.parse_kscreen_json(_kscreen_doc([]), "DP-1", cfg)
        self.assertFalse(unplugged["available"])
        res_unplugged = tv_display_mode.apply_display_mode("4k", cfg, dry_run=True, kscreen_info=unplugged)
        self.assertFalse(res_unplugged["changed"])
        self.assertEqual(res_unplugged["reason"], "display_unavailable")

        # 2. Suspend/resume: output present but enabled=False and modes=[]
        suspended_json = _kscreen_doc(
            [{"name": "DP-1", "enabled": False, "connected": True, "currentModeId": "", "modes": []}]
        )
        suspended = tv_display_mode.parse_kscreen_json(suspended_json, "DP-1", cfg)
        self.assertFalse(suspended["available"])
        res_suspended = tv_display_mode.apply_display_mode("1080p", cfg, dry_run=True, kscreen_info=suspended)
        self.assertFalse(res_suspended["changed"])
        self.assertEqual(res_suspended["reason"], "display_unavailable")

        # 3. Replug / wake: DP-1 returns with full modes
        replugged = tv_display_mode.parse_kscreen_json(TV_4K30_DP1, "DP-1", cfg)
        self.assertTrue(replugged["available"])
        res_replugged = tv_display_mode.apply_display_mode("4k", cfg, dry_run=True, kscreen_info=replugged)
        self.assertTrue(res_replugged["changed"])
        self.assertEqual(res_replugged["mode_id"], "1")

    def test_missing_kscreen_doctor_binary_handled_gracefully(self) -> None:
        cfg = dict(self.cfg, output="auto")
        info = tv_display_mode.query_kscreen("auto", cfg, kscreen_bin="/nonexistent/kscreen-doctor-missing")
        self.assertFalse(info["available"])
        self.assertIn("not found", info["error"])

        applied = tv_display_mode.apply_display_mode(
            "4k",
            cfg,
            dry_run=False,
            kscreen_bin="/nonexistent/kscreen-doctor-missing",
        )
        self.assertFalse(applied["changed"])
        self.assertEqual(applied["reason"], "display_unavailable")
        self.assertIn("not found", applied["error"])

    def test_configurable_steam_priority_opt_out(self) -> None:
        steam_kwin = {
            "active": {
                "resourceClass": "steamwebhelper",
                "desktopFileName": "steam",
                "caption": "Steam Big Picture Mode",
                "pid": 4069,
                "fullScreen": True,
                "minimized": False,
            },
            "windows": [],
        }
        no_ancestry = lambda _p: []

        # Default steam_priority=True forces 1080p even on manual 4k
        dec_default = tv_display_mode.decide_target_mode(steam_kwin, [], "4k", self.cfg, no_ancestry)
        self.assertEqual(dec_default["target"], "1080p")
        self.assertEqual(dec_default["reason"], "steam_priority")

        # Opting out (steam_priority=False) allows capable 4K/60 hardware to keep manual 4k in Steam
        cfg_opt_out = dict(self.cfg, steam_priority=False)
        dec_opt_out = tv_display_mode.decide_target_mode(steam_kwin, [], "4k", cfg_opt_out, no_ancestry)
        self.assertEqual(dec_opt_out["target"], "4k")
        self.assertEqual(dec_opt_out["reason"], "manual_override_4k")

        # Custom steam_target_mode="4k"
        cfg_steam_4k = dict(self.cfg, steam_priority=True, steam_target_mode="4k")
        dec_steam_4k = tv_display_mode.decide_target_mode(steam_kwin, [], "auto", cfg_steam_4k, no_ancestry)
        self.assertEqual(dec_steam_4k["target"], "4k")
        self.assertEqual(dec_steam_4k["reason"], "steam_priority")


class TestStatusReadOnlyAndDiagnose(unittest.TestCase):
    def test_status_subcommand_calls_getstatus_never_evaluatenow(self) -> None:
        fake_status = json.dumps(
            {
                "daemon_running": True,
                "manual_mode": "auto",
                "display": {"output": "HDMI-A-1", "current_mode_name": "1920x1080@60", "current_mode_id": "2"},
                "decision": {"target": "1080p", "reason": "auto_default_1080p", "detail": "ok"},
                "playbacks": [],
            }
        )
        calls: list[str] = []

        def fake_call_daemon(method: str, *args):
            calls.append(method)
            return fake_status

        buf = io.StringIO()
        with mock.patch.object(tv_display_mode, "_call_daemon", side_effect=fake_call_daemon), mock.patch.object(
            tv_display_mode, "apply_session_env", return_value={}
        ), mock.patch("sys.stdout", buf):
            rc = tv_display_mode.main(["status", "--json"])

        self.assertEqual(rc, 0)
        self.assertEqual(calls, ["GetStatus"])
        self.assertNotIn("EvaluateNow", calls)
        parsed = json.loads(buf.getvalue())
        self.assertEqual(parsed["display"]["output"], "HDMI-A-1")

    def test_diagnose_payload_is_read_only_and_sanitized(self) -> None:
        cfg = dict(tv_display_mode.DEFAULT_CONFIG, output="auto")
        wpctl_out = (
            "Audio\n"
            " ├─ Devices:\n"
            " ├─ Sinks:\n"
            " │  *   42. Built-in Audio Digital Stereo (HDMI) [vol: 0.80]\n"
            " │      43. Analog Stereo [vol: 0.50]\n"
            " └─ Sources:\n"
        )
        report = tv_display_mode.build_diagnose_payload(
            cfg,
            kscreen_raw=TV_4K60_HDMI,
            sys_pci_root="/nonexistent/pci",
            wpctl_runner=lambda: (0, wpctl_out, ""),
        )
        self.assertTrue(report["read_only"])
        self.assertEqual(report["display_policy"]["selected"]["output"], "HDMI-A-1")
        self.assertTrue(report["hdmi_audio"]["available"])
        self.assertFalse(report["hdmi_audio"]["auto_configured"])
        self.assertEqual(len(report["hdmi_audio"]["hdmi_sinks"]), 1)
        self.assertIn("$HOME", report["config"]["config_path"])

        # Missing wpctl reports unavailable honestly
        missing_audio = nextgen_platform.inspect_hdmi_audio(wpctl_runner=lambda: (-1, "", "No such file"))
        self.assertFalse(missing_audio["available"])
        self.assertFalse(missing_audio["auto_configured"])


class TestMovieModeToggleFeedback(unittest.TestCase):
    def test_dynamic_feedback_4k60_4k30_fallback_steam_and_minimal(self) -> None:
        # 4K @ 60Hz on HDMI-A-1
        osd, title, sub = tv_movie_toggle.format_feedback(
            {
                "manual_mode": "4k",
                "decision": {"target": "4k", "reason": "manual_override_4k"},
                "applied": {
                    "output": "HDMI-A-1",
                    "resolved_target": "4k",
                    "size": {"width": 3840, "height": 2160},
                    "refresh_rate": 60.0,
                    "fallback": False,
                    "reason": "exact_match",
                },
            }
        )
        self.assertEqual(osd, "Movie Mode: 4K @ 60Hz")
        self.assertEqual(title, "Movie Mode")
        self.assertEqual(sub, "HDMI-A-1 switched to 3840x2160 @ 60Hz")

        # 4K @ 30Hz on DP-1
        osd30, _, sub30 = tv_movie_toggle.format_feedback(
            {
                "manual_mode": "4k",
                "decision": {"target": "4k", "reason": "manual_override_4k"},
                "display": {
                    "output": "DP-1",
                    "size": {"width": 3840, "height": 2160},
                    "refresh_rate": 30.0,
                },
            }
        )
        self.assertEqual(osd30, "Movie Mode: 4K @ 30Hz")
        self.assertEqual(sub30, "DP-1 switched to 3840x2160 @ 30Hz")

        # 1080p-only display fallback when 4k requested
        osd_fb, title_fb, sub_fb = tv_movie_toggle.format_feedback(
            {
                "manual_mode": "4k",
                "decision": {"target": "4k", "reason": "manual_override_4k"},
                "applied": {
                    "output": "HDMI-A-1",
                    "resolved_target": "1080p",
                    "size": {"width": 1920, "height": 1080},
                    "refresh_rate": 60.0,
                    "fallback": True,
                    "reason": "mode_unavailable_fallback",
                },
            }
        )
        self.assertIn("4K Unavailable", osd_fb)
        self.assertEqual(title_fb, "4K Mode Unavailable")
        self.assertIn("HDMI-A-1 stays at 1920x1080 @ 60Hz", sub_fb)

        # Steam priority
        osd_st, title_st, sub_st = tv_movie_toggle.format_feedback(
            {
                "manual_mode": "4k",
                "decision": {"target": "1080p", "reason": "steam_priority"},
                "applied": {
                    "output": "HDMI-A-2",
                    "resolved_target": "1080p",
                    "size": {"width": 1920, "height": 1080},
                    "refresh_rate": 120.0,
                },
            }
        )
        self.assertIn("Steam Priority", osd_st)
        self.assertEqual(title_st, "1080p Mode (Steam Priority)")
        self.assertIn("HDMI-A-2 stays at 1920x1080 @ 120Hz", sub_st)

        # Minimal payload without mode dimensions/Hz still falls back cleanly without hardcoding DP-1 or 30Hz
        osd_min, _, sub_min = tv_movie_toggle.format_feedback(
            {"decision": {"target": "4k", "reason": "manual_override_4k"}}
        )
        self.assertEqual(osd_min, "Movie Mode: 4K")
        self.assertNotIn("DP-1", sub_min)
        self.assertNotIn("30Hz", sub_min)


if __name__ == "__main__":
    unittest.main(verbosity=2)

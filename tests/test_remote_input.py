#!/usr/bin/env python3
"""
Unit tests for normalized remote input model, profile loading, HDMI-CEC safety,
read-only status/diagnose guarantees, and EACCES permission diagnostics.
"""

from __future__ import annotations

import errno
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


def _load_remote_keymap():
    path = os.path.join(BIN_DIR, "tv-remote-keymap.py")
    loader = importlib.machinery.SourceFileLoader("tv_remote_keymap_mod", path)
    spec = importlib.util.spec_from_loader("tv_remote_keymap_mod", loader)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


remote_mod = _load_remote_keymap()


SAMPLE_CEC_DP_ALLOCATED = """\
Driver Info:
        Driver Name                : drm_dp_cec
        Adapter Name               : cec-DP-1
        Capabilities               : 0x0000011e
                Logical Addresses
                Transmit
                Passthrough
                Remote Control Support
        Physical Address           : f.f.f.f
        Logical Address            : 4 (Playback Device 1)
"""

SAMPLE_CEC_DP_UNALLOCATED = """\
Driver Info:
        Driver Name                : drm_dp_cec
        Adapter Name               : cec-DP-1
        Physical Address           : f.f.f.f
        Logical Address          : Not Allocated
"""

SAMPLE_CEC_NATIVE_HDMI = """\
Driver Info:
        Driver Name                : pulse8-cec
        Adapter Name               : cec-pulse8
        Capabilities               : 0x0000003f
                Physical Address
                Logical Addresses
                Transmit
                Passthrough
                Remote Control Support
        Physical Address           : 1.0.0.0
        Logical Address            : 4 (Playback Device 1)
                Primary Device Type    : Playback
"""

SAMPLE_CEC_UNSUPPORTED = """\
Driver Info:
        Driver Name                : vivid
        Adapter Name               : vivid-000-cec
        Physical Address           : f.f.f.f
        Logical Address          : Not Allocated
"""


def _create_fake_input_tree(base_dir: str, devices: list[dict]) -> tuple[str, str]:
    sys_root = os.path.join(base_dir, "sys_input")
    dev_root = os.path.join(base_dir, "dev_input")
    os.makedirs(sys_root, exist_ok=True)
    os.makedirs(dev_root, exist_ok=True)

    for dev in devices:
        ev = dev["event"]
        ev_dir = os.path.join(sys_root, ev, "device", "id")
        os.makedirs(ev_dir, exist_ok=True)
        with open(os.path.join(ev_dir, "vendor"), "w", encoding="utf-8") as fh:
            fh.write(dev.get("vendor", "") + "\n")
        with open(os.path.join(ev_dir, "product"), "w", encoding="utf-8") as fh:
            fh.write(dev.get("product", "") + "\n")
        with open(os.path.join(sys_root, ev, "device", "name"), "w", encoding="utf-8") as fh:
            fh.write(dev.get("name", ev) + "\n")
        if "uniq" in dev:
            # Plant a sensitive uniq/MAC/serial file to prove diagnose NEVER reads or leaks it
            with open(os.path.join(sys_root, ev, "device", "uniq"), "w", encoding="utf-8") as fh:
                fh.write(dev["uniq"] + "\n")
        if "key_cap" in dev:
            cap_dir = os.path.join(sys_root, ev, "device", "capabilities")
            os.makedirs(cap_dir, exist_ok=True)
            with open(os.path.join(cap_dir, "key"), "w", encoding="utf-8") as fh:
                fh.write(dev["key_cap"] + "\n")
        dev_node = os.path.join(dev_root, ev)
        with open(dev_node, "w", encoding="utf-8") as fh:
            fh.write("")

    return sys_root, dev_root


class TestRemoteProfilesAndActionModel(unittest.TestCase):
    def test_normalized_actions_and_optional_missing_buttons_not_errors(self) -> None:
        expected = {
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
        }
        self.assertEqual(set(nextgen_platform.NORMALIZED_ACTIONS), expected)

        profiles = nextgen_platform.load_remote_profiles(user_config_path="/nonexistent/remote-profiles.json")
        for required_prof in (
            "xingwei_24g",
            "generic_keyboard",
            "generic_usb_rf",
            "bluetooth_gamepad",
            "hdmi_cec_native",
        ):
            self.assertIn(required_prof, profiles)
            cov = nextgen_platform.evaluate_profile_action_coverage(profiles[required_prof])
            self.assertFalse(cov["has_errors"])
            for opt_act in cov["optional_unavailable"]:
                self.assertTrue(cov["actions"][opt_act]["optional"])
                self.assertEqual(cov["actions"][opt_act]["status"], "optional_unavailable")

        # Bluetooth gamepad explicitly notes AutoSuppressInput anti-double-input behavior
        gp = profiles["bluetooth_gamepad"]
        self.assertTrue(gp.get("auto_suppress_input"))
        self.assertIn("AutoSuppressInput", gp.get("notes", ""))

        # Built-in xingwei_24g matches existing 620a:0407 scancode map
        xw = profiles["xingwei_24g"]
        self.assertEqual(xw["match"]["vendor"], "620a")
        self.assertEqual(xw["match"]["product"], "0407")
        self.assertEqual(xw["scancode_map"][0x0C0041][0], nextgen_platform.KEY_ENTER)

    def test_custom_user_json_profile_loading_and_matching(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = os.path.join(tmp, "remote-profiles.json")
            user_cfg = {
                "profiles": {
                    "my_custom_rf": {
                        "display_name": "Living Room RF Remote",
                        "transport": "usb_hid_rf",
                        "match": {"vendor": "0x1234", "product": "0xabcd"},
                        "scancode_map": {
                            "0x0c0041": [28, 353, "OK -> KEY_ENTER"],
                        },
                        "supported_actions": ["up", "down", "left", "right", "select", "back"],
                    }
                }
            }
            with open(cfg_path, "w", encoding="utf-8") as fh:
                json.dump(user_cfg, fh)

            profiles = nextgen_platform.load_remote_profiles(user_config_path=cfg_path)
            self.assertIn("my_custom_rf", profiles)
            self.assertIn("xingwei_24g", profiles)
            self.assertEqual(profiles["my_custom_rf"]["match"]["vendor"], "1234")
            self.assertEqual(profiles["my_custom_rf"]["match"]["product"], "abcd")
            self.assertEqual(profiles["my_custom_rf"]["scancode_map"][0x0C0041][0], 28)

            sys_root, dev_root = _create_fake_input_tree(
                tmp,
                [
                    {
                        "event": "event5",
                        "vendor": "1234",
                        "product": "abcd",
                        "name": "Living Room RF Consumer Control",
                    }
                ],
            )
            devices = remote_mod.discover_input_devices(sys_input_root=sys_root, dev_input_root=dev_root)
            matched = remote_mod.match_profiles_for_devices(devices, profiles)
            self.assertEqual(len(matched), 1)
            self.assertEqual(matched[0]["profile"]["name"], "my_custom_rf")
            self.assertEqual(len(matched[0]["devices"]), 1)


class TestCecClassificationAndSafety(unittest.TestCase):
    def test_classify_cec_adapter_all_categories(self) -> None:
        self.assertEqual(nextgen_platform.classify_cec_adapter(None)["adapter_type"], "none")
        self.assertEqual(nextgen_platform.classify_cec_adapter("")["adapter_type"], "none")

        dp = nextgen_platform.classify_cec_adapter(SAMPLE_CEC_DP_ALLOCATED)
        self.assertEqual(dp["adapter_type"], "dp_aux_tunnel")
        self.assertTrue(dp["allocated"])
        self.assertTrue(dp["should_clear_on_apply"])

        dp_idle = nextgen_platform.classify_cec_adapter(SAMPLE_CEC_DP_UNALLOCATED)
        self.assertEqual(dp_idle["adapter_type"], "dp_aux_tunnel")
        self.assertFalse(dp_idle["allocated"])

        # Modern i915 kernels may report Adapter Name: DP-1 without the "cec-" prefix
        dp_short = nextgen_platform.classify_cec_adapter(
            "Driver Info:\n\tDriver Name : i915\n\tAdapter Name : DP-1\n\tLogical Address : 4 (Playback Device 1)\n"
        )
        self.assertEqual(dp_short["adapter_type"], "dp_aux_tunnel")
        self.assertTrue(dp_short["allocated"])
        self.assertTrue(dp_short["should_clear_on_apply"])

        native = nextgen_platform.classify_cec_adapter(SAMPLE_CEC_NATIVE_HDMI)
        self.assertEqual(native["adapter_type"], "native_hdmi_cec")
        self.assertTrue(native["allocated"])
        self.assertFalse(native["should_clear_on_apply"])

        unsup = nextgen_platform.classify_cec_adapter(SAMPLE_CEC_UNSUPPORTED)
        self.assertEqual(unsup["adapter_type"], "unsupported_or_unallocated")
        self.assertFalse(unsup["should_clear_on_apply"])

    def test_apply_clears_only_dp_aux_tunnel_and_never_native_hdmi_cec(self) -> None:
        dp_calls: list[list[str]] = []

        def dp_runner(args: list[str]) -> tuple[int, str, str]:
            dp_calls.append(list(args))
            if "--clear" in args:
                return 0, "", ""
            return 0, SAMPLE_CEC_DP_ALLOCATED, ""

        res_dp = remote_mod.configure_cec(
            verbose=False,
            cec_dev="/dev/cec0",
            cec_ctl_runner=dp_runner,
            device_exists_fn=lambda _p: True,
        )
        self.assertTrue(res_dp["cleared"])
        self.assertEqual(dp_calls, [["-d", "/dev/cec0"], ["-d", "/dev/cec0", "--clear"]])

        native_calls: list[list[str]] = []

        def native_runner(args: list[str]) -> tuple[int, str, str]:
            native_calls.append(list(args))
            return 0, SAMPLE_CEC_NATIVE_HDMI, ""

        res_native = remote_mod.configure_cec(
            verbose=False,
            cec_dev="/dev/cec0",
            cec_ctl_runner=native_runner,
            device_exists_fn=lambda _p: True,
        )
        self.assertFalse(res_native["cleared"])
        self.assertEqual(native_calls, [["-d", "/dev/cec0"]])
        self.assertFalse(any("--clear" in c for c in native_calls))


class TestReadOnlyAndPermissions(unittest.TestCase):
    def test_status_and_diagnose_are_strictly_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sys_root, dev_root = _create_fake_input_tree(
                tmp,
                [
                    {
                        "event": "event3",
                        "vendor": "620a",
                        "product": "0407",
                        "name": "XING WEI Consumer Control",
                        "uniq": "AA:BB:CC:DD:EE:FF",
                    }
                ],
            )
            cec_calls: list[list[str]] = []

            def dp_runner(args: list[str]) -> tuple[int, str, str]:
                cec_calls.append(list(args))
                return 0, SAMPLE_CEC_DP_ALLOCATED, ""

            set_called = []

            def forbidden_set(*_args, **_kwargs):
                set_called.append(True)
                raise AssertionError("EVIOCSKEYCODE_V2 must NEVER be called in read-only mode")

            with mock.patch.object(remote_mod, "set_keycode", side_effect=forbidden_set), mock.patch(
                "sys.stdout", io.StringIO()
            ):
                rc = remote_mod.print_status(
                    sys_input_root=sys_root,
                    dev_input_root=dev_root,
                    cec_ctl_runner=dp_runner,
                    open_fn=lambda _p, flags: (
                        self.assertEqual(flags, os.O_RDONLY) or 42
                    ),
                    close_fn=lambda _fd: None,
                    get_keycode_fn=lambda _fd, sc: 28 if sc == 0x0C0041 else None,
                )
            self.assertEqual(rc, 0)
            self.assertEqual(set_called, [])
            self.assertFalse(any("--clear" in c for c in cec_calls))

            # Diagnose must also be strictly read-only and never leak uniq/MAC
            cec_calls.clear()
            report = remote_mod.build_diagnose_report(
                sys_input_root=sys_root,
                dev_input_root=dev_root,
                cec_ctl_runner=dp_runner,
                device_exists_fn=lambda _p: True,
                access_fn=lambda _p, _m: True,
            )
            self.assertTrue(report["read_only"])
            self.assertFalse(any("--clear" in c for c in cec_calls))
            serialized = json.dumps(report)
            self.assertNotIn("AA:BB:CC:DD:EE:FF", serialized)
            self.assertEqual(report["cec"]["adapter_type"], "dp_aux_tunnel")
            self.assertEqual(report["matched_profiles"][0]["profile"], "xingwei_24g")
            self.assertFalse(report["matched_profiles"][0]["action_coverage"]["has_errors"])

    def test_eacces_permission_denied_reports_clear_diagnostic_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sys_root, dev_root = _create_fake_input_tree(
                tmp,
                [
                    {
                        "event": "event7",
                        "vendor": "620a",
                        "product": "0407",
                        "name": "XING WEI Keyboard",
                    }
                ],
            )

            # 1. --diagnose permission audit detects EACCES and provides least-privilege uaccess hint
            report = remote_mod.build_diagnose_report(
                sys_input_root=sys_root,
                dev_input_root=dev_root,
                device_exists_fn=lambda _p: False,
                access_fn=lambda _p, _m: False,
            )
            audit = report["permission_audit"]
            self.assertEqual(audit["permission_denied_count"], 1)
            self.assertIn("uaccess", audit["remediation_hint"].lower())
            self.assertNotIn("chmod 777", audit["remediation_hint"].lower().replace("do not use chmod 777", ""))

            # 2. --apply handles EACCES gracefully with user-readable message (no unhandled traceback)
            buf = io.StringIO()

            def deny_open(_path: str, _flags: int) -> int:
                raise PermissionError(errno.EACCES, "Permission denied")

            with mock.patch("sys.stdout", buf):
                updated = remote_mod.apply_mappings(
                    reset=False,
                    verbose=True,
                    sys_input_root=sys_root,
                    dev_input_root=dev_root,
                    cec_dev="/nonexistent/cec0",
                    open_fn=deny_open,
                )
            self.assertEqual(updated, 0)
            output = buf.getvalue()
            self.assertIn("EACCES", output)
            self.assertIn("uaccess", output.lower())

            # 3. --status also reports EACCES + uaccess hint when ALL nodes fail
            buf_status = io.StringIO()
            with mock.patch("sys.stdout", buf_status):
                rc = remote_mod.print_status(
                    sys_input_root=sys_root,
                    dev_input_root=dev_root,
                    cec_dev="/nonexistent/cec0",
                    open_fn=deny_open,
                )
            self.assertEqual(rc, 1)
            status_out = buf_status.getvalue()
            self.assertIn("EACCES", status_out)
            self.assertIn("uaccess", status_out.lower())

    def test_composite_usb_skips_non_key_and_silences_sibling_eacces_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sys_root, dev_root = _create_fake_input_tree(
                tmp,
                [
                    {
                        "event": "event7",
                        "vendor": "620a",
                        "product": "0407",
                        "name": "XING WEI Keyboard",
                        "key_cap": "1000000000007 ff9f207ac14057ff",
                    },
                    {
                        "event": "event8",
                        "vendor": "620a",
                        "product": "0407",
                        "name": "XING WEI Mouse",
                        "key_cap": "70000 0 0 0 0",  # mouse buttons (has key bits) but lacks uaccess ACL
                    },
                    {
                        "event": "event9",
                        "vendor": "620a",
                        "product": "0407",
                        "name": "XING WEI Consumer Control",
                        "key_cap": "300ff 0 0 483ffff17aff32d",
                    },
                    {
                        "event": "event11",
                        "vendor": "620a",
                        "product": "0407",
                        "name": "XING WEI Raw HID",
                        "key_cap": "0",  # zero key capabilities -> filtered out completely
                    },
                ],
            )

            # 1. find_remote_event_devices filters out capabilities/key == "0" (event11)
            found = remote_mod.find_remote_event_devices(
                sys_input_root=sys_root,
                dev_input_root=dev_root,
            )
            self.assertIn(os.path.join(dev_root, "event7"), found)
            self.assertIn(os.path.join(dev_root, "event9"), found)
            self.assertNotIn(os.path.join(dev_root, "event11"), found)

            opened_paths: list[str] = []

            def mixed_open(path: str, _flags: int) -> int:
                opened_paths.append(os.path.basename(path))
                if path.endswith("event8"):
                    raise PermissionError(errno.EACCES, "Permission denied")
                return 100

            # 2. apply_mappings: event7 & event9 succeed, event11 is never opened,
            #    and event8 sibling EACCES is silenced by default (no scary EACCES noise!)
            buf_apply = io.StringIO()
            with mock.patch("sys.stdout", buf_apply):
                updated = remote_mod.apply_mappings(
                    reset=False,
                    verbose=True,
                    show_sibling_errors=False,
                    sys_input_root=sys_root,
                    dev_input_root=dev_root,
                    cec_dev="/nonexistent/cec0",
                    open_fn=mixed_open,
                    close_fn=lambda _fd: None,
                    get_keycode_fn=lambda _fd, sc: 353 if sc == 0x0C0041 else None,
                    set_keycode_fn=lambda _fd, _sc, _kc: None,
                )
            self.assertEqual(updated, 2)
            self.assertNotIn("event11", opened_paths)
            apply_out = buf_apply.getvalue()
            self.assertNotIn("EACCES", apply_out)
            self.assertNotIn("permission denied", apply_out.lower())

            # 3. With show_sibling_errors=True (--verbose), sibling skip notice IS shown
            buf_verbose = io.StringIO()
            with mock.patch("sys.stdout", buf_verbose):
                remote_mod.apply_mappings(
                    reset=False,
                    verbose=True,
                    show_sibling_errors=True,
                    sys_input_root=sys_root,
                    dev_input_root=dev_root,
                    cec_dev="/nonexistent/cec0",
                    open_fn=mixed_open,
                    close_fn=lambda _fd: None,
                    get_keycode_fn=lambda _fd, sc: 28 if sc == 0x0C0041 else None,
                    set_keycode_fn=lambda _fd, _sc, _kc: None,
                )
            self.assertIn("event8", buf_verbose.getvalue())

            # 4. print_status: sibling EACCES silenced by default when event7/event9 open cleanly
            buf_st = io.StringIO()
            with mock.patch("sys.stdout", buf_st):
                rc = remote_mod.print_status(
                    sys_input_root=sys_root,
                    dev_input_root=dev_root,
                    cec_dev="/nonexistent/cec0",
                    open_fn=mixed_open,
                    close_fn=lambda _fd: None,
                    get_keycode_fn=lambda _fd, sc: 28 if sc == 0x0C0041 else None,
                )
            self.assertEqual(rc, 0)
            st_out = buf_st.getvalue()
            self.assertNotIn("EACCES", st_out)
            self.assertNotIn("permission denied", st_out.lower())
            self.assertIn("event7", st_out)
            self.assertIn("event9", st_out)

            # 5. --diagnose STILL surfaces EACCES on event8 in permission_audit
            report = remote_mod.build_diagnose_report(
                sys_input_root=sys_root,
                dev_input_root=dev_root,
                device_exists_fn=lambda _p: False,
                access_fn=lambda p, _m: not p.endswith("event8"),
            )
            self.assertEqual(report["permission_audit"]["permission_denied_count"], 1)
            self.assertIn(os.path.join(dev_root, "event8"), report["permission_audit"]["permission_denied_devices"])
            self.assertIn("uaccess", report["permission_audit"]["remediation_hint"].lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)

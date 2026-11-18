#!/usr/bin/env python3
"""
User-space evdev scancode-to-keycode remapper for the XING WEI 2.4G USB Remote (620a:0407).

Uses the Linux EVIOCSKEYCODE_V2 ioctl via uaccess ACL permissions (no root/sudo or /usr
mutations required on atomic Bazzite) to fix:
1. Navigation keys on Consumer Control (0x0c) & Keyboard (0x07):
   - 0x0c0041 (Menu Pick / Center OK): KEY_SELECT (353 > 255, dropped by XKB) -> KEY_ENTER (28)
   - 0x0c0040 (Consumer Menu): KEY_MENU (139 -> XF86MenuKB) -> KEY_COMPOSE (127 -> Qt::Key_Menu)
   - 0x0c0094 & 0x0c0204 (Consumer Exit): KEY_EXIT (174) -> KEY_ESC (1)
   - 0x0c00cf & 0x0c01cb (Voice/Assistant): 582/583 (> 255, dropped by XKB) -> KEY_SEARCH (217)
   - 0x070058 (Keypad Enter): KEY_KPENTER (96) -> KEY_ENTER (28)
2. Power/Sleep keys across Keyboard (0x07), Consumer (0x0c), and System Control (0x01):
   - Unifies Sleep scancodes (0x0700f8, 0x0c0032, 0x0c0034, 0x010082: KEY_SLEEP 142) to
     KEY_POWER (116) so PowerDevil's PowerButtonAction=128 (ToggleScreenOnOff) handles all
     power/standby button presses instead of triggering system shutdown or suspend.
"""

import fcntl
import glob
import os
import struct
import subprocess
import sys
import time

VENDOR_ID = "620a"
PRODUCT_ID = "0407"
CEC_DEV = "/dev/cec0"
CEC_OSD_NAME = "Bigscreen TV"


def configure_cec(verbose=True):
    """Ensure /dev/cec0 does not block or hammer DisplayPort AUX when connected via a passive-CEC DP-to-HDMI adapter."""
    if not os.path.exists(CEC_DEV):
        if verbose:
            print(f"{CEC_DEV}: not present")
        return False
    try:
        res = subprocess.run(
            ["/usr/bin/cec-ctl", "-d", CEC_DEV],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        out = res.stdout or ""
    except OSError as exc:
        if verbose:
            print(f"{CEC_DEV}: cec-ctl query failed ({exc})")
        return False

    # On DP-1 (Active DP 1.2-to-HDMI 2.0 adapter), cec-DP-1 tunnels over DP-AUX without physical HDMI Pin 13 ACK.
    # Leave /dev/cec0 unconfigured (--clear) so kernel/libcec do not hammer DP-AUX with 2.1s TX timeouts.
    if "cec-DP-" in out:
        if "Logical Address          : Not Allocated" not in out:
            subprocess.run(
                ["/usr/bin/cec-ctl", "-d", CEC_DEV, "--clear"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if verbose:
                print(f"{CEC_DEV}: cleared logical address on DP-AUX tunnel (cec-DP) to prevent AUX channel contention")
        elif verbose:
            print(f"{CEC_DEV}: DP-AUX tunnel idle (unallocated)")
        return True
    return True

EVIOCGKEYCODE_V2 = 0x80284504
EVIOCSKEYCODE_V2 = 0x40284504

# Keycodes from <linux/input-event-codes.h>
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

# Target remappings: scancode -> (target_keycode, default_keycode, description)
SCANCODE_MAP = {
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


def find_remote_event_devices():
    """Return sorted list of /dev/input/event* paths belonging to 620a:0407."""
    matched = []
    for sys_path in sorted(glob.glob("/sys/class/input/event*")):
        ev_name = os.path.basename(sys_path)
        vendor_file = os.path.join(sys_path, "device", "id", "vendor")
        product_file = os.path.join(sys_path, "device", "id", "product")
        try:
            with open(vendor_file, "r", encoding="utf-8") as vf:
                vendor = vf.read().strip().lower()
            with open(product_file, "r", encoding="utf-8") as pf:
                product = pf.read().strip().lower()
        except OSError:
            continue
        if vendor == VENDOR_ID and product == PRODUCT_ID:
            dev_node = f"/dev/input/{ev_name}"
            if os.path.exists(dev_node):
                matched.append(dev_node)
    return matched


def get_keycode(fd, scancode):
    """Query current keycode for a 32-bit HID scancode, or None if not present on this device."""
    buf = bytearray(struct.pack("BBHI", 0, 4, 0, 0) + struct.pack("<I", scancode) + b"\x00" * 28)
    try:
        fcntl.ioctl(fd, EVIOCGKEYCODE_V2, buf, True)
    except OSError:
        return None
    _, _, _, keycode = struct.unpack("BBHI", buf[:8])
    return keycode


def set_keycode(fd, scancode, keycode):
    """Set keycode for a 32-bit HID scancode using EVIOCSKEYCODE_V2."""
    buf = bytearray(struct.pack("BBHI", 0, 4, 0, keycode) + struct.pack("<I", scancode) + b"\x00" * 28)
    fcntl.ioctl(fd, EVIOCSKEYCODE_V2, buf, True)


def apply_mappings(reset=False, verbose=True):
    if not reset:
        configure_cec(verbose=verbose)
    devices = find_remote_event_devices()
    if not devices:
        if verbose:
            print(f"No event devices found for {VENDOR_ID}:{PRODUCT_ID}")
        return 0

    updated_count = 0
    for dev in devices:
        try:
            fd = os.open(dev, os.O_RDWR)
        except OSError as exc:
            if verbose:
                print(f"Skipping {dev} ({exc})")
            continue
        try:
            for scancode, (target_kc, default_kc, desc) in SCANCODE_MAP.items():
                current_kc = get_keycode(fd, scancode)
                if current_kc is None:
                    continue
                desired_kc = default_kc if reset else target_kc
                if current_kc != desired_kc:
                    set_keycode(fd, scancode, desired_kc)
                    updated_count += 1
                    if verbose:
                        print(f"{dev}: 0x{scancode:06x} {current_kc} -> {desired_kc} ({desc})")
                elif verbose:
                    print(f"{dev}: 0x{scancode:06x} == {current_kc} ({desc})")
        finally:
            os.close(fd)
    return updated_count


def print_status():
    configure_cec(verbose=True)
    devices = find_remote_event_devices()
    if not devices:
        print(f"No event devices found for {VENDOR_ID}:{PRODUCT_ID}")
        return 1
    for dev in devices:
        try:
            fd = os.open(dev, os.O_RDONLY)
        except OSError as exc:
            print(f"{dev}: cannot open ({exc})")
            continue
        try:
            for scancode, (target_kc, default_kc, desc) in SCANCODE_MAP.items():
                current_kc = get_keycode(fd, scancode)
                if current_kc is not None:
                    state = "OK" if current_kc == target_kc else f"MISMATCH (expected {target_kc})"
                    print(f"{dev}: 0x{scancode:06x} -> keycode {current_kc:3d} (default {default_kc:3d}) [{state}] {desc}")
        finally:
            os.close(fd)
    return 0


def watch_hotplug():
    apply_mappings(reset=False, verbose=True)
    sys.stdout.flush()
    proc = subprocess.Popen(
        ["udevadm", "monitor", "--udev", "--subsystem-match=input"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        for line in proc.stdout:
            if (" add " in line or " change " in line) and "/event" in line:
                time.sleep(0.25)
                apply_mappings(reset=False, verbose=True)
                sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--apply"
    if mode == "--reset":
        apply_mappings(reset=True, verbose=True)
    elif mode == "--status":
        sys.exit(print_status())
    elif mode == "--watch":
        watch_hotplug()
    else:
        apply_mappings(reset=False, verbose=True)


if __name__ == "__main__":
    main()

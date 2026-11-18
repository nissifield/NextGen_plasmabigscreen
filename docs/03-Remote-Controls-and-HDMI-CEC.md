# 03 — Remote Controls, Game Controllers, and HDMI-CEC

## 1. 2.4G USB Remote Keymap Service (`bin/tv-remote-keymap.py`)

Many aftermarket 2.4G wireless TV air-mouse remotes (tested with **XING WEI 2.4G USB Remote `620a:0407`**) send Linux HID keycodes above `255` (dropped by Wayland/XKB) or sleep/exit codes (`KEY_SELECT` 353, `KEY_MENU` 139, `KEY_EXIT` 174, `KEY_SLEEP` 142, `KEY_VOICECOMMAND` 582).

`tv-remote-keymap.py` runs as a user systemd service (`tv-remote-keymap.service`) using `uaccess` ACL permissions and `EVIOCSKEYCODE_V2` ioctls on USB hotplug (`udevadm monitor`) with zero root privileges:

- `0x0c0041` (`KEY_SELECT` 353) & `0x070058` (`KEY_KPENTER` 96) -> `KEY_ENTER` (28)
- `0x0c0040` (`KEY_MENU` 139) -> `KEY_COMPOSE` (127 / `Qt::Key_Menu`)
- `0x0c0094` & `0x0c0204` (`KEY_EXIT` 174) -> `KEY_ESC` (1)
- `0x0c00cf` & `0x0c01cb` (Voice/Assistant 582/583) -> `KEY_SEARCH` (217)
- `0x0700f8`, `0x0c0032`, `0x0c0034`, `0x010082` (`KEY_SLEEP`) -> `KEY_POWER` (116)

Pair this with `configs/powerdevilrc` (`PowerButtonAction=128`, `LockBeforeTurnOffDisplay=false`) so pressing the remote Power button toggles screen DPMS rather than suspending/shutting down the HTPC.

> **Using a different USB remote?** Inspect its vendor/product IDs with `lsusb` and update `VENDOR_ID` / `PRODUCT_ID` in `~/.local/bin/tv-remote-keymap.py`.

---

## 2. Game Controllers & Passive DP-to-HDMI CEC Isolation (`plasma-bigscreen-inputhandler.service`)

`plasma-bigscreen-inputhandler` translates SDL3 game controller inputs into Plasma Bigscreen Wayland navigation events:

- **`AutoSuppressInput=true` (`configs/plasma-bigscreen-inputhandlerrc`):** Automatically suppresses Plasma Bigscreen's virtual D-pad injection whenever a fullscreen/focused client handles controller input itself (Steam Big Picture, Stremio with `gamepadSupport`, native games). This prevents double D-pad presses while still keeping gamepad control on the Bigscreen Homescreen.
- **Tunneled `/dev/cec0` Mitigation:** When connected through an active DisplayPort-to-HDMI adapter whose kernel driver registers a `cec-DP-*` tunnel without physical HDMI pin 13 ACKs, leaving CEC polling enabled causes repeated 2.1-second DP-AUX timeouts and sluggish input. To eliminate contention completely:
  - `tv-remote-keymap.py`'s `configure_cec()` runs `cec-ctl -d /dev/cec0 --clear` on `cec-DP-*` tunnels.
  - `configs/plasma-bigscreen-inputhandlerrc` sets `CecEnabled=false` and `ClaimActiveSource=false`.
  - `systemd/user/plasma-bigscreen-inputhandler.service` isolates `/dev/cec0` inside the unit using `bwrap --dev-bind / / --dev-bind /dev/null /dev/cec0`.

If you use a real native HDMI-CEC adapter (such as a Pulse-Eight USB-CEC adapter) instead of a tunneled `cec-DP-*` adapter, you can re-enable `CecEnabled=true` and drop the `bwrap` bind override.

---

## 3. Optional WirePlumber HDMI Audio Priority (`configs/wireplumber/90-tv-hdmi-audio.conf.example`)

If your USB TV remote exposes a built-in microphone/audio card that occasionally steals default audio routing at boot or resume, install the WirePlumber rule with `./install.sh --with-hardware-presets` (and adjust the ALSA `node.name` regex to match `wpctl status` on your machine).

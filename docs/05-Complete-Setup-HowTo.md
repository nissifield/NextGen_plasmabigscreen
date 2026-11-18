# 05 — Complete Setup How-To Guide

This guide walks you through installing, adapting, and verifying **NextGen Plasma Bigscreen** on your own Linux living-room HTPC—from checking your hardware capabilities to customizing display timings, GPU acceleration, remotes, and streaming apps.

---

## 1. Prerequisites

### Supported System
- **OS:** Atomic/immutable Fedora Kinoite / Bazzite (`bazzite-deck` or KDE spin) or any standard **KDE Plasma 6 Wayland** distribution.
- **Session:** Logged into KDE Plasma Wayland (`XDG_SESSION_TYPE=wayland`). Everything installs into `$HOME` with **no `sudo` required** and no `/usr` edits.
- **Core CLI Tools:**
  - `python3`, `gcc`, `git`, `bash`, `kscreen-doctor`, `busctl` / `qdbus`, `systemctl --user`, `desktop-file-validate`
  - Optional: `vainfo` (verify VA-API), `cec-ctl` (clear tunneled `cec-DP-*` adapters), `udevadm` (remote hotplug), `ffprobe` (optional video probing)

### Recommended Flatpak Streaming Apps
Install the living-room apps you want from Flathub (or via `ujust get-media-app` on Bazzite):
```bash
flatpak install flathub \
  rocks.shy.VacuumTube \
  com.stremio.Stremio \
  org.jellyfin.JellyfinDesktop \
  org.kde.haruna
```

---

## 2. Inspect Your Hardware First

Before installing, gather four details about your machine so you know what (if anything) to adjust afterward.

### A. Find Your TV Output Connector & Supported Modes
Run inside your active KDE Wayland session:
```bash
kscreen-doctor -o
```
Look for the connected output name (for example `DP-1`, `HDMI-A-1`, or `HDMI-A-2`) and check which modes are listed:
- **HDMI 2.0 / native HDMI 2.0+ or active DP-to-HDMI 2.0 adapter:** You will typically see `3840x2160@60.00` (or `59.94`).
- **Passive DP-to-HDMI / HDMI 1.4 link (340 MHz TMDS cap):** `3840x2160` will top out at `30.00` Hz, while `1920x1080` runs at `60.00` Hz.

### B. Check Your GPU & VA-API Hardware Decode Driver
```bash
lspci -k | grep -A3 -iE 'vga|display|3d'
vainfo
```
- **Intel Gen 9.5+ (Coffee Lake / UHD 630, Iris Xe, Arc):** Uses `iHD` (`intel-media-driver`). Keep `LIBVA_DRIVER_NAME=iHD` and VacuumTube's `--use-vulkan=disabled`.
- **AMD Radeon (AMDGPU):** Uses `radeonsi` (`mesa-va-drivers`). After installing, remove `LIBVA_DRIVER_NAME=iHD` from Flatpak overrides and `~/.config/environment.d/90-intel-vaapi.conf`.
- **NVIDIA:** Uses proprietary NVDEC / `nvidia-vaapi-driver` rather than Intel `iHD`.

### C. Check Your USB Remote & CEC Devices
```bash
lsusb
ls -la /dev/cec* 2>/dev/null || true
```
- Note your 2.4 GHz USB remote's `Vendor:Product` ID (e.g., `620a:0407`) if it differs from the default in `bin/tv-remote-keymap.py`.
- If you see `/dev/cec0` over a DisplayPort-to-HDMI adapter (`cec-DP-*`), keep the CEC mitigation enabled (`CecEnabled=false` + `tv-remote-keymap.service` `--clear`). If you use a real USB-CEC adapter (e.g., Pulse-Eight), you can re-enable `CecEnabled=true`.

### D. Check HDMI Audio Sink Name (Optional)
```bash
wpctl status
```
If a USB remote mic/audio device occasionally steals default audio output, note your TV HDMI sink's `node.name` via `pw-dump` for `90-tv-hdmi-audio.conf`.

---

## 3. Clone, Preview, and Install

```bash
git clone https://github.com/nissifield/NextGen_plasmabigscreen.git
cd NextGen_plasmabigscreen

# Review options and preview every target path without modifying $HOME:
./install.sh --help
./install.sh --dry-run
```

Run the installer:
```bash
# Core install (Bigscreen QML plasmoid, tv-display-mode, Movie Mode toggle,
# Stremio libmpv shim, remote keymap, systemd user units, desktop files):
./install.sh
```
Or include the optional hardware presets (`90-intel-vaapi.conf`, WirePlumber HDMI audio rule, Gamescope mode pins, PowerDevil DPMS button behavior, screen-locker off):
```bash
./install.sh --with-hardware-presets
```

> **Note on shell helpers:** `configs/bashrc.d/tv-display-mode.sh` installs to `~/.bashrc.d/tv-display-mode.sh`. Ensure your `~/.bashrc` sources `~/.bashrc.d/*.sh` (standard on Fedora/Bazzite), or `source ~/.bashrc.d/tv-display-mode.sh` directly.

---

## 4. Customize for Your Setup

### A. Display Connector, Refresh Rate & Policy (`~/.config/tv-display-mode/config.json`)
Open `~/.config/tv-display-mode/config.json`:
```json
{
  "output": "DP-1",
  "mode_4k": {
    "width": 3840,
    "height": 2160,
    "refresh_rate": 30.0
  },
  "mode_1080p": {
    "width": 1920,
    "height": 1080,
    "refresh_rate": 60.0
  },
  "auto_4k_video_switch": false,
  "auto_pause_background_media": true
}
```
- **Different cable/port?** Change `"output"` from `"DP-1"` to match `kscreen-doctor -o` (e.g., `"HDMI-A-1"`).
- **Have HDMI 2.0 / 4K@60Hz?** Change `"mode_4k.refresh_rate"` to `60.0`.
- **Want automatic 4K switching on >1080p video?** Set `"auto_4k_video_switch": true` (by default it is `false`, so desktop/navigation stays at `1080p @ 60Hz` and you toggle **Movie Mode** from the Bigscreen favorite tile or `tv-movie`).
- **Android TV-style background pause:** `"auto_pause_background_media": true` pauses playing background media apps when returning to Bigscreen Home or switching apps.

Apply config changes:
```bash
systemctl --user restart tv-display-mode.service
~/.local/bin/tv-display-mode status
```

### B. Customizing Your USB Remote (`~/.local/bin/tv-remote-keymap.py`)
If your 2.4 GHz USB remote has a different `VENDOR_ID` / `PRODUCT_ID`:
1. Find the IDs with `lsusb` and inspect scancodes with `evtest` (if installed) or `/sys/class/input/`.
2. Update `VENDOR_ID`, `PRODUCT_ID`, and `SCANCODE_MAP` in `~/.local/bin/tv-remote-keymap.py`.
3. Restart the user service:
   ```bash
   systemctl --user restart tv-remote-keymap.service
   ```

### C. Stremio Controller Navigation (Option A)
To use an Xbox/PlayStation/8BitDo controller inside Stremio without double inputs from Plasma Bigscreen:
1. Ensure `~/.config/plasma-bigscreen-inputhandlerrc` has `AutoSuppressInput=true` (installed by default).
2. In Stremio, open **Settings → General** and enable **Gamepad Support** (press `Ctrl+G` inside Stremio to view its built-in Gamepad Guide).
3. Restart Stremio if it was already open.

---

## 5. Launch Plasma Bigscreen & Verify

Switch your active Plasma Wayland session into the customized Plasma Bigscreen UI:
```bash
~/.local/bin/tv-session-switch.sh bigscreen
```

Run a quick health check:
```bash
# 1. Display switcher & auto-pause daemon:
~/.local/bin/tv-display-mode status

# 2. KWin Wayland window-tracker script:
busctl --user call org.kde.KWin /Scripting org.kde.kwin.Scripting isScriptLoaded s tv-display-mode

# 3. Movie Mode toggle test (switches 4K <-> 1080p and shows OSD + toast):
~/.local/bin/tv-movie-mode-toggle
# Run again to switch back to 1080p @ 60Hz (or run `~/.local/bin/tv-display-mode auto`)

# 4. Stremio libmpv VA-API shim override:
flatpak override --user --show com.stremio.Stremio
```

---

## 6. Updating or Rolling Back

- **Pulling future repo updates:**
  ```bash
  git pull --ff-only
  ./install.sh
  systemctl --user restart tv-display-mode.service tv-remote-keymap.service plasma-bigscreen-inputhandler.service
  ```
- **Cleanly reverting everything to stock KDE Plasma Desktop:**
  ```bash
  ./rollback-tv-setup.sh
  ```
  See [04 — Operations and Rollback Runbook](04-Operations-and-Rollback-Runbook.md) for detailed troubleshooting commands.

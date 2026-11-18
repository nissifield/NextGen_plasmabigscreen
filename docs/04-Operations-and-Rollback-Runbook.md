# 04 — Operations and Rollback Runbook

## 1. Routine Health & Status Checks

### Check Display Mode & Auto-Pause Daemon
```bash
systemctl --user status tv-display-mode.service
~/.local/bin/tv-display-mode status
```
Expected status:
- `Daemon: running`
- `Auto 4K Video: disabled (Steam 1080p auto-switch active)`
- `Auto Pause Bg: enabled`
- Output connector matching `kscreen-doctor -o` (`1920x1080@60` by default)

### Check KWin Wayland Script Registration
```bash
busctl --user call org.kde.KWin /Scripting org.kde.kwin.Scripting isScriptLoaded s tv-display-mode
```
Expected: `b true`

### Check Plasma Bigscreen Shell & Input Handler
```bash
~/.local/bin/tv-session-switch.sh status
systemctl --user status plasma-bigscreen-inputhandler.service
systemctl --user status tv-remote-keymap.service
```

### Check Stremio libmpv Preload Shim
```bash
flatpak override --user --show com.stremio.Stremio
```
Expected: `LD_PRELOAD=$HOME/.var/app/com.stremio.Stremio/data/stremio-mpv-shim.so` and `LIBVA_DRIVER_NAME=iHD`.

---

## 2. Manual Display & Session Commands

| Command | Action |
| :--- | :--- |
| `~/.local/bin/tv-movie-mode-toggle` | Toggle `4K @ 30Hz` (Movie Mode) <-> `1080p @ 60Hz` with OSD + toast banner |
| `~/.local/bin/tv-display-mode toggle` | Same toggle via CLI (`movie`, `4k`, `1080p`, `auto`, `status`) |
| `~/.local/bin/tv-session-switch.sh bigscreen` | Switch live into Plasma Bigscreen UI |
| `~/.local/bin/tv-session-switch.sh desktop` | Switch live back to standard KDE Plasma Desktop |
| `~/tv-display-mode.sh retrain` | Force DPMS + mode retrain on HDMI/DP link |

Shell helpers installed into `~/.bashrc.d/tv-display-mode.sh` also expose `tv-movie`, `tv-toggle`, `tv-4k`, `tv-1080p`, `tv-auto`, and `tv-status`.

---

## 3. Running Tests

From the repository root:
```bash
python3 -m py_compile bin/tv-display-mode tests/test_tv_display_mode.py
python3 tests/test_tv_display_mode.py
bash -n install.sh rollback-tv-setup.sh bin/tv-session-switch.sh bin/tv-display-mode.sh configs/bashrc.d/tv-display-mode.sh
gcc -shared -fPIC -O2 stremio/stremio_mpv_shim.c -o /tmp/stremio-mpv-shim-test.so -ldl && rm -f /tmp/stremio-mpv-shim-test.so
```

---

## 4. Full User-Space Rollback

Run `./rollback-tv-setup.sh` from the repository root (no `sudo` required):
```bash
./rollback-tv-setup.sh
```
This disables user services (`tv-display-mode`, `tv-remote-keymap`, `plasma-bigscreen-inputhandler`), unloads the KWin script, removes user-space plasmoid/Flatpak/desktop overrides, restores stock KDE Plasma Desktop shell, and resets remote scancode mappings.

# 02 — Streaming Apps Guide

NextGen Plasma Bigscreen configures 10-foot living-room Flatpak media apps with VA-API hardware video decoding, fullscreen defaults, and controller/remote navigation.

---

## 1. YouTube TV — VacuumTube (`rocks.shy.VacuumTube`)

**VacuumTube** wraps the official YouTube Leanback TV interface (`https://www.youtube.com/tv`) in Electron with built-in adblocking, SponsorBlock, Return YouTube Dislike, and gamepad/remote navigation.

- **Wayland & Intel VA-API Flags (`~/.var/app/rocks.shy.VacuumTube/config/VacuumTube/flags.txt`):**
  - Uses Ozone Wayland and disables Vulkan (`--use-vulkan=disabled`) to prevent VA-API `vkAllocateMemory` failures on older Intel GPUs while preserving smooth 4K hardware playback.
- **Flatpak Override (`~/.local/share/flatpak/overrides/rocks.shy.VacuumTube`):**
  - `sockets=!fallback-x11;wayland;!x11;` and `LIBVA_DRIVER_NAME=iHD`.
- **Navigation:** Arrow keys / D-Pad scrub & browse; `Enter`/`OK` plays/pauses; `Escape`/`Backspace` goes back.

---

## 2. Stremio (`com.stremio.Stremio`)

**Stremio** runs in Flatpak with an embedded `libmpv` video backend. By default, embedded `libmpv` ignores `mpv.conf` and disables hardware decoding on some Linux systems.

- **Libmpv Hardware Decode Preload Shim (`stremio/stremio_mpv_shim.c`):**
  - Compiled during `install.sh` to `~/.var/app/com.stremio.Stremio/data/stremio-mpv-shim.so` and loaded via `LD_PRELOAD` in `~/.local/share/flatpak/overrides/com.stremio.Stremio`.
  - Forces `config=yes`, `hwdec=auto-safe`, and `hwdec-codecs=all` before `mpv_initialize`, enabling VA-API hardware acceleration via `~/.var/app/com.stremio.Stremio/config/mpv/mpv.conf`.
- **Fullscreen & Gamepad Support:**
  - `kwin/tv-display-mode.js` and `configs/kwinrulesrc` ensure Stremio opens fullscreen by default.
  - Enable `gamepadSupport` in Stremio UI settings when navigating with an Xbox/PlayStation controller alongside `AutoSuppressInput=true`.

---

## 3. Jellyfin Desktop (`org.jellyfin.JellyfinDesktop`)

- **Launcher (`desktop/org.jellyfin.JellyfinDesktop.desktop`):** Passes `--fullscreen --tv` so Jellyfin opens directly in 10-foot TV mode.
- **Flatpak Override:** Sets `LIBVA_DRIVER_NAME=iHD` for Intel VA-API playback.
- **Optional mpv Lua Hook (`mpv/tv-display-mode.lua`):** Writes playback resolution JSON metadata into `$HOME/.var/app/org.jellyfin.JellyfinDesktop/data/jellyfin-desktop/tv-display-mode/` when `auto_4k_video_switch` is enabled.

---

## 4. Haruna (`org.kde.haruna`)

- Pre-configured (`~/.var/app/org.kde.haruna/config/haruna/haruna.conf`) with `UseHardwareDecoding=true` and `HardwareDecoding=vaapi`, plus `LIBVA_DRIVER_NAME=iHD`.

---

## 5. Adding Streaming Services via `ujust get-media-app` (`~/.local/bin/steamos-add-to-steam`)

On KDE Plasma 6, `/usr/bin/kmimetypefinder` reports shell wrappers in `~/Applications/streaming_scripts/` as `text/x-shellscript`, which stock `/usr/bin/steamos-add-to-steam` previously rejected (`Unsupported file type`).

`bin/steamos-add-to-steam` installs to `~/.local/bin/steamos-add-to-steam` (earlier in `$PATH` than `/usr/bin`) and accepts `text/x-shellscript`, `application/x-shellscript`, and `text/x-python` executables cleanly.

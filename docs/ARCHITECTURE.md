# Architecture & Subsystem Boundaries

NextGen Plasma Bigscreen is structured as a **user-space-first (`$HOME`)** living-room TV layer on top of upstream **KDE Plasma 6 Wayland** and **KDE Plasma Bigscreen**. It intentionally avoids modifying `/usr`, `/etc`, or unlocking immutable OS images (`ostree`), so customizations survive atomic updates and remain cleanly reversible.

For UI design details and operational commands, see [01 — Architecture and UI Design](01-Architecture-and-UI-Design.md) and [04 — Operations and Rollback Runbook](04-Operations-and-Rollback-Runbook.md).

---

## 1. Three Architectural Boundaries

To keep hardware/distro adaptation decoupled from living-room UI and daemon policy, the codebase is organized across three clear boundaries:

```text
+-------------------------------------------------------------------+
|  1. TV Experience (UI, Launchers, App Ergonomics)                 |
|  - plasma/plasmoids/org.kde.bigscreen.homescreen/ (QML override)  |
|  - desktop/*.desktop, configs/bigscreen-favs.template             |
|  - bin/tv-movie-mode-toggle, bin/steamos-add-to-steam             |
+---------------------------------+---------------------------------+
                                  | DBus / CLI / Desktop Entries
+---------------------------------v---------------------------------+
|  2. TV Services (Session, Display Policy, Auto-Pause, Input)      |
|  - bin/tv-display-mode (DBus daemon: org.nextgen.TvDisplayMode)   |
|  - kwin/tv-display-mode.js (KWin 6 Wayland window reporter)       |
|  - mpv/tv-display-mode.lua (optional mpv resolution hook)         |
|  - bin/tv-remote-keymap.py (evdev EVIOCSKEYCODE_V2 remapper)      |
|  - bin/tv-session-switch.sh (Bigscreen <-> Desktop switcher)      |
|  - systemd/user/*.service                                         |
+---------------------------------+---------------------------------+
                                  | Discovery / Profiles / Manifest
+---------------------------------v---------------------------------+
|  3. Platform Adapters (Hardware, Distro & State Ownership)        |
|  - bin/nextgen_platform.py (GPU/VA-API/NVDEC, DRM/KScreen/EDID,   |
|    CEC tunnel vs native classification, remote profile registry)  |
|  - bin/nextgen-manifest.py (ownership manifest, versioned backups,|
|    non-destructive Flatpak INI patching, safe rollback support)   |
|  - stremio/stremio_mpv_shim.c (libmpv preload shim)               |
+-------------------------------------------------------------------+
```

### Layer 1 — TV Experience
Owns the 10-foot living-room interface and user-facing interactions:
- **Homescreen Plasmoid Override (`plasma/plasmoids/org.kde.bigscreen.homescreen/`):** User-space QML override installed to `~/.local/share/plasma/plasmoids/org.kde.bigscreen.homescreen/`. Adds category pill tabs (`For You`, `Watch Now`, `Apps`, `Games`), brand-tinted Hero Spotlight Banner with live `● RUNNING` status, 16:9 Watch Now streaming row, Continue & Recent row, and long-press (`Hold OK`) context menu (`HomeHeader.qml`, `HomeScreen.qml`, `LauncherHome.qml`, `LauncherMenu.qml`, `FavDelegate.qml`, `AppDelegate.qml`).
- **Launchers, Favorites & App Ergonomics:** `desktop/*.desktop`, `desktop/*.template`, `configs/bigscreen-favs.template`, `configs/applications-blacklistrc`, `configs/plasma-bigscreen/*`, `bin/streaming_scripts/*`, and `bin/steamos-add-to-steam`.
- **On-Demand Mode Feedback (`bin/tv-movie-mode-toggle`):** Invokes `tv-display-mode toggle --json`, triggers Plasma OSD (`org.kde.osdService`), and presents a brief Wayland toast window so Bigscreen's `StartupFeedbackWindow` dismisses cleanly.

*Boundary rule:* TV Experience files must not hardcode machine-specific PCI IDs, DRM connectors, or GPU driver environment variables.

### Layer 2 — TV Services
Owns long-running user-session orchestration, window tracking, policy evaluation, and input translation:
- **Display Mode & Auto-Pause Daemon (`bin/tv-display-mode`):** Exposes session DBus service `org.nextgen.TvDisplayMode`. Enforces highest-priority `1080p` lock whenever Steam or a Steam child game is active/fullscreen, handles on-demand Movie Mode (`4k` ↔ `1080p`) and optional `auto_4k_video_switch`, debounces transitions, resolves `kscreen-doctor -j` mode IDs dynamically, and automatically calls MPRIS `Player.Pause()` on background media apps across Flatpak `xdg-dbus-proxy` PID/cgroup boundaries (never auto-calling `Play()`).
- **KWin 6 Wayland Script (`kwin/tv-display-mode.js`):** Subscribes to `windowActivated`, `windowAdded`, `windowRemoved`, and per-window geometry/fullscreen/minimized signals, pushing JSON snapshots to `org.nextgen.TvDisplayMode.ReportKWinState` and setting initial fullscreen for Stremio.
- **mpv Playback Hook (`mpv/tv-display-mode.lua`):** Optional hook writing JSON video dimensions and play/pause/idle state for `tv-display-mode` when `auto_4k_video_switch` is enabled.
- **Remote Keymap Service (`bin/tv-remote-keymap.py`):** User-space `EVIOCSKEYCODE_V2` evdev scancode remapper using `uaccess` ACLs and `udevadm monitor` hotplug watching (zero root privileges), driven by profile definitions rather than a single hardcoded dongle.
- **Session Switcher (`bin/tv-session-switch.sh`):** Live user-space switcher (`bigscreen`, `desktop`, `toggle`, `status`) that sources `/usr/bin/plasma-bigscreen-common-env`, protects user-curated `applications-blacklistrc` and `plasma-bigscreen-inputhandlerrc`, updates systemd/D-Bus activation environment, and restarts `plasma-plasmashell.service`.
- **Systemd User Units (`systemd/user/`):** `tv-display-mode.service`, `tv-remote-keymap.service`, and `plasma-bigscreen-inputhandler.service`.

*Boundary rule:* TV Services consume normalized capability/profile data from Platform Adapters and user configuration rather than assuming Bazzite, `DP-1`, or Intel `iHD`.

### Layer 3 — Platform Adapters
Owns hardware discovery, distro/GPU capability classification, and safe, reversible host-state management:
- **Platform Probe & Profile Library (`bin/nextgen_platform.py`):**
  - **GPU / Video Decode Classification:** Detects vendor and driver stacks (Intel Gen 9.5+ `iHD`, legacy Intel `i965`, AMD `radeonsi`/AMDGPU, NVIDIA proprietary/NVDEC/optional `nvidia-vaapi-driver`) and translates them into safe per-app environment recommendations without leaking Intel `LIBVA_DRIVER_NAME=iHD` onto AMD/NVIDIA hosts.
  - **Display & EDID/Mode Discovery:** Parses `kscreen-doctor -j` / `kscreen-doctor -o` and `/sys/class/drm/*/status` to identify active connectors, native/preferred modes, safe fallback modes, and refresh-rate caps (e.g., 4K@30 vs 4K@60).
  - **HDMI-CEC Classification:** Distinguishes tunneled `cec-DP-*` adapters (which can cause 2.1s DP-AUX timeouts and warrant `cec-ctl --clear` / `bwrap` isolation) from native or USB HDMI-CEC adapters (e.g., Pulse-Eight) and hosts with no `/dev/cec*` device.
  - **Data-Driven Remote Profiles:** Loads built-in and user-supplied scancode-to-keycode mapping profiles (`vendor_id`, `product_id`, scancode map) instead of requiring code edits in `tv-remote-keymap.py`.
- **Manifest & Safe File Ownership (`bin/nextgen-manifest.py`):**
  - Tracks every file and Flatpak override key installed or patched by NextGen in `~/.local/state/nextgen-plasmabigscreen/manifest.json`.
  - Creates versioned backups before modifying pre-existing user files (such as `kwinrulesrc`, `powerdevilrc`, or Flatpak INI overrides).
  - Performs key-scoped INI patching on Flatpak overrides so rollback restores only NextGen-managed keys instead of wiping unrelated user overrides.
- **Stremio `libmpv` Preload Shim (`stremio/stremio_mpv_shim.c`):** Minimal `dlopen`/`dlsym` wrapper enforcing `config=yes`, `hwdec=auto-safe`, and `hwdec-codecs=all` before `mpv_initialize` (compiled conditionally only when a C compiler is available; never installs a dangling `LD_PRELOAD` without a built `.so`).

---

## 2. Upstream KDE Plasma Bigscreen vs. NextGen Customizations

| Aspect | Upstream KDE Plasma Bigscreen | NextGen Plasma Bigscreen |
| :--- | :--- | :--- |
| **Install location** | System packages in `/usr` (e.g., `/usr/share/plasma/plasmoids/org.kde.bigscreen.homescreen/`, `/usr/bin/plasma-bigscreen-*`) | Strictly `$HOME` (`~/.local/`, `~/.config/`, `~/.var/app/`, `systemctl --user`) |
| **Session & compositor** | KWin 6 Wayland, `plasma-bigscreen-envmanager`, `plasma-bigscreen-inputhandler`, `plasma-bigscreen-wayland` | Live `bigscreen` ↔ `desktop` switcher (`tv-session-switch.sh`), `envmanager` blacklist preservation, conditional CEC isolation |
| **Homescreen UI** | Stock `org.kde.bigscreen.homescreen` QML plasmoid | User-space QML override adding category pill bar, Spotlight banner, 16:9 Watch Now row, Continue & Recent, `Hold OK` menu |
| **Display & media policy** | Standard KScreen display settings; no Steam 1080p lock or background auto-pause | `tv-display-mode` daemon, KWin state reporter, Movie Mode toggle, MPRIS background auto-pause |
| **App & hardware tuning** | Generic distro defaults | Opt-in Flatpak streaming launchers, Stremio `libmpv` shim, platform-aware GPU/CEC/remote profiles |
| **Licensing** | GPL-2.0-or-later / LGPL per KDE upstream headers | **GPL-2.0-or-later** ([LICENSE](../LICENSE)), preserving upstream KDE copyright notices in derivative QML files |

### Workflow for Reconciling Upstream KDE Plasma Bigscreen QML Updates

Because `~/.local/share/plasma/plasmoids/org.kde.bigscreen.homescreen/` completely shadows `/usr/share/plasma/plasmoids/org.kde.bigscreen.homescreen/`, major upstream Plasma Bigscreen releases (e.g., Plasma 6.x → 6.y) can introduce new QML properties, renamed C++ backend methods, or bug fixes that must be ported cleanly:

1. **Check the installed upstream version** and inspect the system plasmoid directory:
   ```bash
   plasmashell --version
   diff -ruN /usr/share/plasma/plasmoids/org.kde.bigscreen.homescreen/ \
     plasma/plasmoids/org.kde.bigscreen.homescreen/ > /tmp/bigscreen-qml.diff
   ```
2. **Audit changed QML files and C++ plugin imports:**
   - Review `metadata.json` (`X-Plasma-API-Minimum-Version`, plugin IDs) and `import org.kde.bigscreen...` versions.
   - Check `journalctl --user -u plasma-plasmashell.service --since "5 minutes ago"` for `ReferenceError`, `TypeError`, or deprecated QML property warnings after restarting `plasma-plasmashell.service`.
3. **Rebase NextGen UI deltas cleanly:**
   - Keep NextGen customizations isolated to focused QML components (`HomeHeader.qml`, `HomeScreen.qml`, `LauncherHome.qml`, `LauncherMenu.qml`, `FavDelegate.qml`, `AppDelegate.qml`) rather than drifting untouched upstream indicator/search files.
   - Copy unchanged upstream indicator/helper updates directly when they contain upstream bug fixes.
4. **Preserve SPDX & copyright headers:**
   - Retain all upstream KDE `SPDX-FileCopyrightText` and `SPDX-License-Identifier: GPL-2.0-or-later` headers on modified QML files and add contributor attribution where appropriate.
5. **Verify live D-Pad, keyboard, and controller navigation** across every tab, modal, search overlay, and launch delegate before merging.

---

## 3. Stable Configuration, Manifest & DBus Formats

All persistent formats follow additive, backward-compatible evolution: unknown keys are ignored safely, and missing keys fall back to documented defaults.

### 3.1 Display Mode Config (`~/.config/tv-display-mode/config.json`)
```json
{
  "output": "DP-1",
  "mode_4k": { "width": 3840, "height": 2160, "refresh_rate": 30.0 },
  "mode_1080p": { "width": 1920, "height": 1080, "refresh_rate": 60.0 },
  "video_4k_min_width": 1921,
  "video_4k_min_height": 1081,
  "debounce_to_4k_sec": 1.5,
  "debounce_to_1080p_sec": 2.0,
  "min_switch_interval_sec": 1.5,
  "poll_interval_sec": 3,
  "auto_4k_video_switch": false,
  "auto_pause_background_media": true,
  "title_4k_heuristic": true,
  "assume_4k_on_fullscreen_playback": []
}
```
- **Backward compatibility:** `load_config()` merges user JSON over `DEFAULT_CONFIG` recursively for dict fields (`mode_4k`, `mode_1080p`). Existing configs remain valid across upgrades; `install.sh` never overwrites an existing `config.json` unless `--force` is explicitly passed.

### 3.2 Remote Profiles Config (`~/.config/nextgen-plasmabigscreen/remote-profiles.json`)
Data-driven evdev remapping profile list (merged with built-in profiles in `bin/nextgen_platform.py` / `configs/remote-profiles.json`):
```json
{
  "schema_version": 1,
  "profiles": [
    {
      "id": "xing-wei-620a-0407",
      "name": "XING WEI 2.4G USB Remote",
      "vendor_id": "620a",
      "product_id": "0407",
      "scancode_map": {
        "0x0c0041": { "target": 28, "default": 353, "description": "Menu Pick (OK) -> KEY_ENTER" }
      }
    }
  ]
}
```
- **Migration path:** Users who previously edited `VENDOR_ID`/`PRODUCT_ID` directly in `tv-remote-keymap.py` can declare a user profile in `~/.config/nextgen-plasmabigscreen/remote-profiles.json` without maintaining local script forks.

### 3.3 Ownership Manifest (`~/.local/state/nextgen-plasmabigscreen/manifest.json`)
Records installer-owned paths, SHA-256 hashes, backup locations (under `~/.local/state/nextgen-plasmabigscreen/backups/<timestamp>/`), and individual Flatpak INI override keys managed by NextGen:
```json
{
  "schema_version": 1,
  "installed_at": "2026-11-22T00:00:00Z",
  "backup_dir": "~/.local/state/nextgen-plasmabigscreen/backups/20261122T000000Z",
  "files": [],
  "flatpak_overrides": {}
}
```
- **Migration path:** If no manifest exists (installs predating the manifest system), `rollback-tv-setup.sh` falls back safely to documented legacy cleanup paths while warning before destructive resets.

### 3.4 Session DBus Interface (`org.nextgen.TvDisplayMode`)
- **Bus / Path / Interface:** Session bus `org.nextgen.TvDisplayMode`, object `/org/nextgen/TvDisplayMode`, interface `org.nextgen.TvDisplayMode`.
- **Methods:**
  - `ReportKWinState(json_payload: s)` — Receives window focus/fullscreen/minimized snapshots from `kwin/tv-display-mode.js`.
  - `EvaluateNow() -> s` — Returns JSON status payload (display mode, policy decision, active window, playbacks).
  - `SetManualMode(mode: s) -> s` — Sets `4k`, `movie`, `1080p`, `auto`, or `toggle` and returns JSON decision result.

---

## 4. Component Status Matrix

Every capability is labeled strictly according to its current reality:

| Component | Layer | Status | Evidence / Notes |
| :--- | :--- | :--- | :--- |
| Android TV Homescreen QML override (`plasma/plasmoids/org.kde.bigscreen.homescreen/`) | TV Experience | **Tested on hardware** | Verified on Bazzite 45 / Plasma Bigscreen 6.8.3 Wayland |
| `bin/tv-session-switch.sh` (`bigscreen` ↔ `desktop`) | TV Services | **Tested on hardware** | Verified on Bazzite 45 / Plasma 6.8.3 Wayland |
| `bin/tv-display-mode` (Steam 1080p priority, Movie Mode, MPRIS auto-pause) | TV Services | **Tested on hardware** | Verified on DP-1 (4K@30 / 1080p@60) + unit tests in `tests/test_tv_display_mode.py` |
| `kwin/tv-display-mode.js` & `bin/tv-movie-mode-toggle` | TV Services / Experience | **Tested on hardware** | Verified on KWin 6.8.3 Wayland |
| `stremio/stremio_mpv_shim.c` (`libmpv` VA-API preload shim) | Platform Adapters | **Tested on hardware** | Verified on Intel UHD 630 (`iHD`) with Stremio Flatpak 1.3.0 |
| `bin/tv-remote-keymap.py` (`620a:0407` + `cec-DP-*` clear) | TV Services | **Tested on hardware** | Verified on XING WEI `620a:0407` + `cec-DP-1` |
| `bin/nextgen_platform.py` (GPU/DRM/CEC detection & remote profiles) | Platform Adapters | **Implemented** | Unit/fixture tested; hardware validation on AMD/NVIDIA/mutable distros needed |
| `bin/nextgen-manifest.py` (manifest, versioned backups, Flatpak INI patcher) | Platform Adapters | **Implemented** | Unit/temp-HOME tested; broader real-world upgrade/rollback validation ongoing |
| `tv-display-mode diagnose` & `tv-remote-keymap.py --diagnose` | TV Services | **Implemented** | Sanitized diagnostic output for bug & compatibility reports |
| Mutable distro support (Fedora KDE Spin, Ubuntu, Debian, Arch, openSUSE) | Platform Adapters | **In progress** | Tracked on [Contribution Board](CONTRIBUTION_BOARD.md); community hardware validation needed |
| AMD Radeon (`radeonsi`), NVIDIA (NVDEC/`nvidia-vaapi-driver`), legacy/new Intel | Platform Adapters | **In progress** | Adapter logic implemented/scoped; community hardware validation needed |
| Multi-monitor, 4K@60/120, HDR & VRR display policies | TV Services / Adapters | **In progress** | Research & testing tracked in [Contribution Board](CONTRIBUTION_BOARD.md) |
| Native/USB HDMI-CEC adapters & Bluetooth/RF remote profiles | TV Services / Adapters | **In progress** | Profile framework ready; real-device scancodes & CEC testing needed |
| **P2 Proposal: Optional User Profiles** | TV Experience | **Proposed** | Not yet implemented — profile switching for favourites/watch-history isolation |
| **P2 Proposal: Child-Safe Launcher & Parental Controls** | TV Experience | **Proposed** | Not yet implemented — allowlist mode, PIN-gated settings/Desktop Mode exit |
| **P2 Proposal: Accessibility (High-Contrast, Large Text, TTS/Screen Reader)** | TV Experience | **Proposed** | Not yet implemented — tracked in [Contribution Board](CONTRIBUTION_BOARD.md) |
| **P2 Proposal: Internationalisation / Localisation (`i18n`)** | TV Experience / Docs | **Proposed** | Not yet implemented — QML `i18n()` extraction & translation catalogs |
| **P2 Proposal: Opt-In Signed & Verified User-Space Updates** | Platform Adapters | **Proposed** | Not yet implemented — signed release tags/checksums with explicit user opt-in and instant manifest rollback |

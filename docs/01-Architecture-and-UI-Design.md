# 01 — Architecture and UI Design

## 1. User-Space First Design

On immutable atomic Linux distributions like **Bazzite** (`bazzite-deck:stable`) or **Fedora Kinoite**, system reliability depends on keeping `/usr` and the base OS image clean. Every customization in NextGen Plasma Bigscreen runs in `$HOME`:

1. **Flatpak applications:** Streaming apps (`rocks.shy.VacuumTube`, `com.stremio.Stremio`, `org.jellyfin.JellyfinDesktop`, `org.kde.haruna`) run isolated in Flatpak with explicit environment overrides.
2. **Declarative user-space configs (`~/.config`, `~/.local/bin`, `~/.local/share`):** Survive OS updates cleanly and never block atomic image upgrades.
3. **Systemd user units & KWin scripts:** Drive display mode management, controller/remote handling, and background media pause purely over the user session D-Bus.

---

## 2. Plasma Bigscreen Android TV / Google TV Homescreen & Session Switcher

### User-Space Session Switcher (`~/.local/bin/tv-session-switch.sh`)
Instead of changing SDDM's system login target away from `plasma.desktop`, `tv-session-switch.sh` swaps shells live in user-space (`bigscreen`, `desktop`, `toggle`, `status`):

- **`bigscreen` mode:**
  - Sources `/usr/bin/plasma-bigscreen-common-env`.
  - Immediately restores `~/.config/applications-blacklistrc` and `~/.config/plasma-bigscreen-inputhandlerrc` into `~/.config/plasma-bigscreen/` (preventing `plasma-bigscreen-envmanager --apply-settings` from clobbering curated TV blacklists/settings).
  - Restarts `plasma-plasmashell.service` with `PLASMA_DEFAULT_SHELL=org.kde.plasma.bigscreen`, `PLASMA_PLATFORM=mediacenter`, and `QT_FILE_SELECTORS=mediacenter`.
  - Starts `plasma-bigscreen-inputhandler.service` and `xdg-desktop-portal.service`.
- **`desktop` mode:**
  - Stops `plasma-bigscreen-inputhandler.service`.
  - Unsets Bigscreen environment variables in `systemd --user` and D-Bus activation (`dbus-update-activation-environment --systemd`).
  - Restarts `plasma-plasmashell.service` back into standard KDE Plasma Desktop (`org.kde.plasma.desktop`).
- **Login Autostart (`~/.config/autostart/plasma-bigscreen-autostart.desktop`):** Invokes `~/.local/bin/tv-session-switch.sh bigscreen` (`X-KDE-AutostartPhase=2`) on KDE Plasma Wayland login.

### Android TV Homescreen Plasmoid Override (`~/.local/share/plasma/plasmoids/org.kde.bigscreen.homescreen/`)
Installing into `~/.local/share/plasma/plasmoids/` overrides the system plasmoid cleanly without modifying `/usr`:

- **Top Navigation Pill Bar (`HomeHeader.qml`):** Adds Android TV pill tabs (`For You`, `Watch Now`, `Apps`, `Games`) with full keyboard, D-Pad, and controller navigation.
- **Dynamic Hero Spotlight Banner (`HomeScreen.qml`):** Brand-tinted backdrop (YouTube TV, Stremio, Jellyfin TV, Steam, Haruna, Desktop Mode, Movie Mode), live `● RUNNING` badge, medallion icon, description, and action hints (`[OK] Launch • [Hold OK] App Options`).
- **Dedicated 16:9 "Watch Now" Row, Cross-Row Games & Long-Press Context Menu (`LauncherHome.qml`, `LauncherMenu.qml`):** Filters `AudioVideo`/`Video`/`TV` launchers into **Watch Now**, includes `Categories=Game;Application;` apps in both **Applications** and **Games**, renames `Recent` to **Continue & Recent**, and provides a `Hold OK` context modal (`Open / Resume`, `Pin / Remove from Favorites`, `Move Left / Right in Favorites`, `Force Stop`).
- **Delegate Launch Handling (`FavDelegate.qml`, `AppDelegate.qml`):** Launches `return-to-desktop.desktop` cleanly without stalling on a launch splash overlay, and sends `bazzite-steam steam://open/bigpicture` reliably even when Steam is already running in tray/silent mode.

---

## 3. Display Mode Automation, Steam 1080p@60Hz Priority & Movie Mode (`tv-display-mode`)

Running a desktop/HTPC at 4K@30Hz makes Bigscreen UI animations sluggish, while switching to 4K@30Hz on demand improves razor-sharp cinema playback on HDMI 1.4b/2.0 TVs. `tv-display-mode` coordinates both:

1. **Steam 1080p@60Hz Priority (Always Active):**
   - KWin 6 script (`~/.local/share/tv-display-mode/kwin/tv-display-mode.js`) pushes window focus, fullscreen, and window-type state via D-Bus (`org.nextgen.TvDisplayMode`).
   - Whenever Steam (`steam`, `steamwebhelper`, `gamescope`) or any Steam child game (`app-*`, `reaper`, `steam-launch-wrapper`) is active or fullscreen in the foreground, the TV output immediately switches to `1920x1080@60.00`.
2. **Manual / On-Demand Movie Mode (`tv-movie-mode-toggle`):**
   - `auto_4k_video_switch` defaults to `false` so browsing Bigscreen stays crisp at `1080p@60Hz`.
   - Clicking the **Movie Mode** favorite tile (`~/.local/bin/tv-movie-mode-toggle`) or running `tv-movie` / `tv-toggle` switches cleanly between `3840x2160@30.00` and `1920x1080@60.00`, displaying a Plasma OSD notification and brief centered banner toast.
3. **Android TV-Style Background Media Auto-Pause:**
   - When returning to Plasma Bigscreen Home (`active=None` or `plasmashell` desktop/overlay shell) or switching focus to Steam / another app, `tv-display-mode` checks all live MPRIS players (skipping `playerctld`).
   - Any playing background player whose window is no longer focused receives `org.mpris.MediaPlayer2.Player.Pause()`.
   - Matches Flatpak apps across `xdg-dbus-proxy` PID boundaries via direct PID, shared `app-flatpak-*.scope` cgroup, normalized `DesktopEntry`, and `Identity`/bus suffix.
   - Ignores OSDs, notifications, transient popups, Polkit auth prompts, `fallback`/`init` states, and never calls `Play()` automatically when returning to a paused app.

---

## 4. Hardware / Gamescope Defense-in-Depth Notes

On some Intel Gen 9.5 (`i915`) HDMI setups, standalone `gamescope-session` can pick unsupported `1080p@120Hz` timings or fail `drmModeAddFB2WithModifiers`. Keeping SDDM on `plasma.desktop` and launching Steam Big Picture inside KWin Wayland avoids that black-screen failure, while optional presets in `configs/gamescope/` pin Gamescope outputs to `1920x1080@60` as defense in depth.

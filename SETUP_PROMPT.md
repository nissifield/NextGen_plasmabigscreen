# NextGen Plasma Bigscreen — Self-Service AI Agent Setup Prompt

Point any AI coding agent (**Claude Code, Codex, Gemini CLI, Antigravity, Cursor, OpenCode, etc.**) at this file to inspect a Linux machine, adapt **NextGen Plasma Bigscreen** to its hardware, install declaratively into `$HOME`, and verify everything end-to-end.

Raw URL for one-liner usage:
`https://raw.githubusercontent.com/nissifield/NextGen_plasmabigscreen/main/SETUP_PROMPT.md`

---

## Instructions for the AI Coding Agent

You are setting up **NextGen Plasma Bigscreen** (`https://github.com/nissifield/NextGen_plasmabigscreen`) on the user's Linux PC/TV. Follow all four phases in order. Do **not** skip Phase 1 or Phase 2.

### Ground Rules
1. **User-Space First (`$HOME`):** Install all NextGen customizations strictly inside `$HOME` (`~/.config/`, `~/.local/`, `systemctl --user`). Never modify `/usr` or `/etc`, and never unlock `ostree`.
2. **Explicit Confirmation for System Packages:** Never run `sudo`, `rpm-ostree`, `dnf`, `pacman`, `zypper`, `transactional-update`, or `apt` without first explaining what will be installed, showing the exact one-step rollback command, and receiving explicit user approval.
3. **Display Safety:** Never change display modes or resolutions blindly. Always inspect `kscreen-doctor -o` first and keep a verified fallback mode (`1920x1080@60` or the current working mode).
4. **No Machine-Specific Assumptions:** Never carry over repo defaults (`DP-1`, `3840x2160@30`, Intel `iHD`, USB remote `620a:0407`, tunneled `/dev/cec0`, `/usr/bin/bazzite-steam`, `WAYLAND_DISPLAY=wayland-1`) without verifying they match this host.

---

### Phase 1 — Read-Only Discovery (Do NOT Edit Any Files Yet)

Run read-only checks to inventory this machine:

1. **Session & KDE Plasma 6 Wayland:**
   - Check `$XDG_SESSION_TYPE`, `$WAYLAND_DISPLAY`, `plasmashell --version`, and `/etc/os-release`.
   - Confirm the user is running **KDE Plasma 6 Wayland** (stop and inform the user if they are on Plasma 5, X11, or another desktop environment).
2. **Base `plasma-bigscreen` OS Package:**
   - Check `command -v plasma-bigscreen-envmanager plasma-bigscreen-inputhandler plasma-bigscreen-wayland` and `[ -f /usr/bin/plasma-bigscreen-common-env ]`.
   - If missing, prepare the exact per-distro install and rollback commands for Phase 2 (do **not** run them yet):
     - **Bazzite / Fedora Kinoite (`rpm-ostree`):**
       - Install: `rpm-ostree install plasma-bigscreen plasma-bigscreen-wayland` *(requires reboot)*
       - Rollback: `rpm-ostree uninstall plasma-bigscreen plasma-bigscreen-wayland` (or `rpm-ostree rollback`)
     - **Fedora KDE (`dnf`):**
       - Install: `sudo dnf install plasma-bigscreen`
       - Rollback: `sudo dnf remove plasma-bigscreen`
     - **Arch / CachyOS / EndeavourOS (`pacman`):**
       - Install: `sudo pacman -S plasma-bigscreen`
       - Rollback: `sudo pacman -Rns plasma-bigscreen`
     - **openSUSE Tumbleweed / Kalpa (`zypper` / `transactional-update`):**
       - Install: `sudo zypper install plasma6-bigscreen` (or `sudo transactional-update pkg install plasma6-bigscreen` + reboot)
       - Rollback: `sudo zypper remove plasma6-bigscreen` (or `sudo transactional-update rollback`)
     - **Ubuntu / Kubuntu / Debian (Plasma 6 releases only, `apt`):**
       - Install: `sudo apt install plasma-bigscreen`
       - Rollback: `sudo apt remove plasma-bigscreen`
3. **TV Output Connector & Supported Modes:**
   - Run `kscreen-doctor -o` (and inspect `/sys/class/drm/*/status` if helpful).
   - Record the active TV connector name (e.g., `HDMI-A-1`, `DP-1`), the maximum supported `3840x2160` refresh rate (`60.0` vs `30.0`, or native max if non-4K), and `1920x1080@60.0`.
4. **GPU & Hardware Video Decoding (VA-API):**
   - Run `lspci -k | grep -A3 -iE 'vga|display|3d'` and `vainfo 2>&1 || true`.
   - Classify the GPU stack:
     - **Intel Gen 9.5+ (`iHD` / `intel-media-driver`)**
     - **Older Intel (`i965`)**
     - **AMD Radeon (`radeonsi` / AMDGPU)**
     - **NVIDIA (proprietary NVDEC / optional `nvidia-vaapi-driver`)**
5. **Flatpak, Steam, Compiler & Utility Check:**
   - Check `flatpak remotes`, `flatpak list --app`, and `uname -m`.
   - Detect Steam install type: `/usr/bin/bazzite-steam`, `/usr/bin/steam`, Flatpak `com.valvesoftware.Steam`, or not installed.
   - Check `command -v gcc cc bwrap cec-ctl desktop-file-validate`.
6. **Remotes, HDMI-CEC, Audio & Existing User Configs:**
   - Check `lsusb` (look for `620a:0407` or any other 2.4G USB air-mouse remote).
   - Check `ls -la /dev/cec* 2>/dev/null || true`. If `/dev/cec0` exists and `cec-ctl` is installed, run `cec-ctl -d /dev/cec0` to distinguish a **tunneled `cec-DP-*`** adapter vs a **real native/USB HDMI-CEC** adapter vs **absent**.
   - Check `wpctl status` to see if a USB remote exposes an audio device that competes with HDMI audio.
   - Check whether `~/.config/kwinrulesrc` or `~/.config/powerdevilrc` already exist so they are never blindly overwritten.

---

### Phase 2 — Present Tailored Plan & Confirm With User

Before modifying anything, present a concise **Hardware Delta Summary** comparing this machine against the repo defaults (`DP-1`, `3840x2160@30`, Intel `iHD`, USB remote `620a:0407`, tunneled `cec-DP-*`, `/usr/bin/bazzite-steam`, `WAYLAND_DISPLAY=wayland-1`), and ask the user to confirm:

1. **Missing OS package (only if `plasma-bigscreen` is missing):** Show the exact distro install + rollback command from Phase 1 and ask for explicit approval. *(On atomic/rpm-ostree/transactional-update distros, pause after installation so the user can reboot into the new deployment before continuing to Phase 3.)*
2. **Optional Flathub streaming apps:** Ask which of these they want installed (skip any they don't want):
   - `rocks.shy.VacuumTube` (YouTube TV)
   - `com.stremio.Stremio` (Stremio)
   - `org.jellyfin.JellyfinDesktop` (Jellyfin TV)
   - `org.kde.haruna` (Haruna local video player)
3. **Login behavior:** Ask whether they want Plasma to **auto-start into Bigscreen on login** or keep standard Desktop login and **switch manually** (`tv-session-switch.sh bigscreen`).
4. **Confirm proceeding** with the user-space `$HOME` installation and adaptations below.

---

### Phase 3 — Clone (HTTPS), Install into `$HOME`, & Adapt Cleanly

Once the user approves:

1. **Clone via HTTPS** (skip if already inside a clone of the repo):
   ```bash
   git clone https://github.com/nissifield/NextGen_plasmabigscreen.git
   cd NextGen_plasmabigscreen
   ```
2. **Install only the user's chosen Flatpak apps** (ensure the `flathub` remote exists if installing):
   ```bash
   flatpak install flathub <only-user-chosen-app-ids>
   ```
3. **Preview & Run Base User-Space Installer:**
   - Preview first: `./install.sh --dry-run`
   - Install without starting services yet: `./install.sh --skip-services`
   - **Do NOT blindly pass `--with-hardware-presets`** — it installs Intel-only `90-intel-vaapi.conf`, Intel PCH / `XING_WEI` WirePlumber rules, `TCL Beyond TV` Gamescope pins, and overwrites `~/.config/powerdevilrc` and `~/.config/kwinrulesrc`. Only copy or merge individual preset files if they genuinely match this hardware and never clobber existing `powerdevilrc` or `kwinrulesrc`.
4. **Apply Hardware & Distro Adaptations in `$HOME`:**
   1. **Display Policy (`~/.config/tv-display-mode/config.json`):**
      - Set `"output"` to the active connector from `kscreen-doctor -o`.
      - Set `"mode_4k"` (`width`, `height`, `refresh_rate` — e.g. `60.0` on HDMI 2.0+ or `30.0` on HDMI 1.4/passive adapters) and `"mode_1080p"` to exact modes present in `kscreen-doctor -o`.
      - Keep `"auto_4k_video_switch": false` (unless the user explicitly asks for auto-switching) and `"auto_pause_background_media": true`.
      - If `mode_4k.refresh_rate` is not `30.0`, optionally update the `"4K @ 30Hz"` OSD/toast strings in `~/.local/bin/tv-movie-mode-toggle` to match.
   2. **GPU & VA-API Overrides:**
      - **Intel Gen 9.5+ (`iHD`):** Install `configs/environment.d/90-intel-vaapi.conf` to `~/.config/environment.d/90-intel-vaapi.conf`, keep `LIBVA_DRIVER_NAME=iHD` in installed Flatpak overrides, and keep `~/.var/app/rocks.shy.VacuumTube/config/VacuumTube/flags.txt`.
      - **AMD (`radeonsi`), NVIDIA, or older Intel (`i965`):**
        - **Strip `LIBVA_DRIVER_NAME=iHD`** from **every** override in `~/.local/share/flatpak/overrides/` (`rocks.shy.VacuumTube`, `com.stremio.Stremio`, `org.jellyfin.JellyfinDesktop`, `org.kde.haruna`, and **`org.mozilla.firefox`** — remove override files entirely for apps the user did not choose/install, or if the override becomes empty).
        - Do **not** install `90-intel-vaapi.conf`.
        - On **NVIDIA**, set `HardwareDecoding=auto-safe` in `~/.var/app/org.kde.haruna/config/haruna/haruna.conf` (if Haruna is installed and `nvidia-vaapi-driver` is not in use).
        - On **NVIDIA / modern AMD**, review `~/.var/app/rocks.shy.VacuumTube/config/VacuumTube/flags.txt` and remove Intel-specific flags (`--disable-features=Vulkan`, `--use-webgpu-adapter=opengles`, `--enable-features=VaapiIgnoreDriverChecks`) if they are unnecessary or degrade decoding on that GPU.
   3. **Stremio `libmpv` Shim (`gcc` check):**
      - If Stremio was **not** chosen/installed, remove `~/.local/share/flatpak/overrides/com.stremio.Stremio` and `~/.local/share/applications/com.stremio.Stremio.desktop`.
      - If Stremio **was** chosen, verify `~/.var/app/com.stremio.Stremio/data/stremio-mpv-shim.so` exists. If `gcc`/`cc` was missing so it was not compiled, **strip the `LD_PRELOAD=...` line** from `~/.local/share/flatpak/overrides/com.stremio.Stremio` (do **not** layer `gcc` via `rpm-ostree install gcc`).
   4. **Steam & Chosen Apps Cleanup:**
      - In `~/.local/share/applications/steam-bigpicture.desktop`: if `/usr/bin/bazzite-steam` does not exist, update `Exec=` to `/usr/bin/steam steam://open/bigpicture` (native Steam) or `flatpak run com.valvesoftware.Steam steam://open/bigpicture` (Flatpak Steam). If Steam is not installed, remove the desktop entry and its `[Favs]` slot.
      - Prune unchosen/uninstalled apps from `~/.config/bigscreen-favs` (renumbering `[Favs][N]` sequentially starting at `0`), `~/.local/share/applications/`, and `~/.local/share/flatpak/overrides/`.
      - If Haruna was installed with `flatpak install --user`, update its `desktopPath`/`entryPath` in `~/.config/bigscreen-favs` from `/var/lib/flatpak/exports/...` to `$HOME/.local/share/flatpak/exports/share/applications/org.kde.haruna.desktop`.
      - On ARM64 (`aarch64`), remove `--arch=x86_64` from the installed Flatpak `.desktop` files in `~/.local/share/applications/`.
   5. **Input Handler Service (`~/.config/systemd/user/plasma-bigscreen-inputhandler.service`):**
      - If `$WAYLAND_DISPLAY` is not `wayland-1`, update `Environment=WAYLAND_DISPLAY=...` to match (or remove the hardcoded line so it inherits from the user systemd environment).
      - Only keep `ExecStart=/usr/bin/bwrap --dev-bind / / --dev-bind /dev/null /dev/cec0 /usr/bin/plasma-bigscreen-inputhandler --replace` (and `CecEnabled=false`) when `/dev/cec0` is a **tunneled `cec-DP-*`** device **and** `/usr/bin/bwrap` is installed.
      - Otherwise (no `/dev/cec0`, no `bwrap`, or a working native/USB HDMI-CEC adapter), change `ExecStart=` to `/usr/bin/plasma-bigscreen-inputhandler --replace` directly. If the user wants real native/USB HDMI-CEC enabled, set `CecEnabled=true` in `~/.config/plasma-bigscreen-inputhandlerrc` and `~/.config/plasma-bigscreen/plasma-bigscreen-inputhandlerrc`.
   6. **USB Remote Keymap Service (`tv-remote-keymap.service`):**
      - Only enable if the user has the `620a:0407` USB remote (or you customized `VENDOR_ID`/`PRODUCT_ID` in `~/.local/bin/tv-remote-keymap.py` for their remote) **or** needs `cec-ctl -d /dev/cec0 --clear` on a tunneled `cec-DP-*` adapter. Otherwise leave `tv-remote-keymap.service` disabled.
   7. **Autostart & Shell Helpers:**
      - If the user chose manual switching only, remove `~/.config/autostart/plasma-bigscreen-autostart.desktop`.
      - Note that `~/.bashrc.d/tv-display-mode.sh` is auto-sourced on Fedora/Bazzite; if the user's `~/.bashrc` does not source `~/.bashrc.d/*.sh`, inform them so they can source it if desired.
5. **Reload & Enable Only Applicable User Services:**
   ```bash
   systemctl --user daemon-reload
   systemctl --user enable --now tv-display-mode.service
   # Only if Step 4.6 applies:
   # systemctl --user enable --now tv-remote-keymap.service
   ```

---

### Phase 4 — Verify End-to-End & Hand Off Controls + Rollback

Run these verification checks and report exact results to the user:

1. **Unit tests:**
   ```bash
   python3 tests/test_tv_display_mode.py
   ```
2. **Daemon & KWin script health:**
   ```bash
   systemctl --user status tv-display-mode.service --no-pager
   ~/.local/bin/tv-display-mode status
   busctl --user call org.kde.KWin /Scripting org.kde.kwin.Scripting isScriptLoaded s tv-display-mode
   ```
   Confirm the output connector and mode match `kscreen-doctor -o`, `Daemon: running`, and `isScriptLoaded` returns `b true`.
3. **Flatpak overrides sanity check:**
   ```bash
   for app in rocks.shy.VacuumTube com.stremio.Stremio org.jellyfin.JellyfinDesktop org.kde.haruna org.mozilla.firefox; do
     flatpak override --user --show "$app" 2>/dev/null | sed "s/^/[$app] /"
   done
   ```
   Confirm no Intel `LIBVA_DRIVER_NAME=iHD` remains on AMD/NVIDIA systems and no dangling `LD_PRELOAD` exists if the Stremio shim was not built.
4. **Hand off day-to-day commands & rollback:**
   - **Switch to Plasma Bigscreen:** `~/.local/bin/tv-session-switch.sh bigscreen`
   - **Return to Plasma Desktop:** `~/.local/bin/tv-session-switch.sh desktop`
   - **Toggle Movie Mode (4K ↔ 1080p):** `~/.local/bin/tv-movie-mode-toggle` (or shell aliases `tv-movie` / `tv-toggle`)
   - **Full user-space rollback:** `./rollback-tv-setup.sh`
     - *Important rollback notes:* `rollback-tv-setup.sh` removes all `$HOME` files/services and runs `flatpak override --user --reset` on Firefox and the streaming Flatpaks (clearing any pre-existing user overrides on those apps). It does **not** uninstall the distro `plasma-bigscreen` OS package—use the per-distro rollback command from Phase 1 if you also want to remove that package.

# NextGen Compatibility & Contributions Board

> **Important:** Having an issue card on this board means **we want community help to test, research, or implement it**—it does **not** mean the distro, GPU, display mode, remote, or streaming service is currently supported or verified. Check [docs/COMPATIBILITY.md](COMPATIBILITY.md) for verified support status.

Maintainers can seed these exact labels, issues, and the GitHub Project v2 board (`NextGen Compatibility & Contributions`) once authenticated with `gh auth login` using [`scripts/seed-github-board.sh`](../scripts/seed-github-board.sh) (supports `--dry-run` by default).

---

## 1. Board Columns

| Column | Meaning |
| :--- | :--- |
| **Backlog** | Scoped idea or long-term proposal not yet prioritized for immediate work. |
| **Ready for contributors** | Well-defined task ready for a contributor to claim (check prerequisites and comment before starting). |
| **In progress** | Actively being implemented or investigated by a contributor or maintainer. |
| **Needs hardware validation** | Code or config exists (unit/fixture tested), waiting for real-hardware evidence & rollback verification. |
| **Review** | Pull Request open and awaiting maintainer review / CI checks. |
| **Done** | Merged, verified with honest evidence, and documented in `docs/COMPATIBILITY.md` / `docs/ARCHITECTURE.md`. |

### Current Board Snapshot

| # | Card | Column | Priority |
| :--- | :--- | :--- | :--- |
| 1 | [Mutable distro: Fedora KDE Spin](#1-mutable-distro-fedora-kde-spin) | Ready for contributors | `priority:P1` |
| 2 | [Mutable distro: Ubuntu + KDE Plasma](#2-mutable-distro-ubuntu--kde-plasma) | Ready for contributors | `priority:P1` |
| 3 | [Mutable distro: Debian KDE](#3-mutable-distro-debian-kde) | Ready for contributors | `priority:P1` |
| 4 | [Mutable distro: Arch Linux KDE](#4-mutable-distro-arch-linux-kde) | Ready for contributors | `priority:P1` |
| 5 | [Mutable distro: openSUSE Tumbleweed KDE](#5-mutable-distro-opensuse-tumbleweed-kde) | Ready for contributors | `priority:P1` |
| 6 | [GPU: AMD Radeon/Mesa](#6-gpu-amd-radeonmesa) | Needs hardware validation | `priority:P0` |
| 7 | [GPU: NVIDIA](#7-gpu-nvidia) | Needs hardware validation | `priority:P0` |
| 8 | [GPU: Intel legacy/new](#8-gpu-intel-legacynew) | Needs hardware validation | `priority:P1` |
| 9 | [Display: multi-monitor & connector switching](#9-display-multi-monitor--connector-switching) | Ready for contributors | `priority:P1` |
| 10 | [Display: 4K60/120, HDR and VRR research](#10-display-4k60120-hdr-and-vrr-research) | Ready for contributors | `priority:P1` |
| 11 | [Remote: HDMI-CEC adapters](#11-remote-hdmi-cec-adapters) | Needs hardware validation | `priority:P1` |
| 12 | [Remote: Bluetooth/RF controllers](#12-remote-bluetoothrf-controllers) | Ready for contributors | `priority:P1` |
| 13 | [Streaming: browser DRM compatibility](#13-streaming-browser-drm-compatibility) | Ready for contributors | `priority:P2` |
| 14 | [Installer: transactional install and rollback](#14-installer-transactional-install-and-rollback) | Needs hardware validation | `priority:P0` |
| 15 | [QA: hardware test matrix and CI](#15-qa-hardware-test-matrix-and-ci) | In progress | `priority:P0` |
| 16 | [UX: accessibility and translations](#16-ux-accessibility-and-translations) | Backlog | `priority:P2` |

---

## 2. Label Taxonomy

| Label | Color | Purpose |
| :--- | :--- | :--- |
| `good first issue` | `#7057ff` | Approachable starter task for first-time contributors |
| `help wanted` | `#008672` | Community contributions actively welcomed |
| `area:installer` | `#1d76db` | `install.sh`, `rollback-tv-setup.sh`, ownership manifest & backups |
| `area:display` | `#0e8a16` | `tv-display-mode`, KWin script, modes, connectors, HDR/VRR |
| `area:remote` | `#fbca04` | USB/BT/RF remote profiles, evdev keymaps, HDMI-CEC, controllers |
| `area:compatibility` | `#5319e7` | Distro, GPU, streaming app & compatibility matrix validation |
| `area:docs` | `#0075ca` | Guides, architecture, contributor docs, translations |
| `platform:atomic` | `#006b75` | Immutable/atomic distros (Bazzite, Kinoite, Kalpa) |
| `platform:mutable` | `#2b7a78` | Traditional mutable distros (Fedora Spin, Ubuntu, Debian, Arch, Tumbleweed) |
| `gpu:intel` | `#0052cc` | Intel iGPU/dGPU (`i915`, `xe`, `iHD`, `i965`) |
| `gpu:amd` | `#d93f0b` | AMD Radeon (`amdgpu`, Mesa `radeonsi` VA-API) |
| `gpu:nvidia` | `#2ea44f` | NVIDIA proprietary / NVDEC / `nvidia-vaapi-driver` |
| `needs-hardware-test` | `#e99695` | Requires real-hardware testing and sanitized diagnostics |
| `priority:P0` | `#b60205` | Foundational safety, installer integrity, or core GPU support |
| `priority:P1` | `#d93f0b` | High-value distro, display, or remote expansion |
| `priority:P2` | `#c5def5` | Research, accessibility, localization, and long-term UX proposals |

---

## 3. Contributor Issue Cards

### 1. Mutable distro: Fedora KDE Spin
- **Labels:** `help wanted`, `good first issue`, `area:compatibility`, `platform:mutable`, `needs-hardware-test`, `priority:P1`
- **Goal:** Validate end-to-end user-space install, session switching, streaming launchers, and rollback on mutable **Fedora KDE Plasma Desktop Spin** (`dnf`).
- **Current Unknowns:** Differences from Bazzite/Kinoite such as `/usr/bin/steam` vs `/usr/bin/bazzite-steam`, `plasma-bigscreen` package contents on Fedora KDE Spin, `~/.bashrc.d` sourcing, and `steamos-add-to-steam` relevance.
- **Scope / Non-goals:** Scope covers KDE Plasma 6 Wayland on Fedora KDE Spin and user-space `$HOME` integration. Non-goals: modifying `/usr` or `/etc`, or supporting X11/Plasma 5.
- **Prerequisites:** Fedora KDE Spin with KDE Plasma 6 Wayland and `plasma-bigscreen` installed via `dnf`.
- **Possible Files:** `install.sh`, `bin/nextgen_platform.py`, `bin/tv-session-switch.sh`, `desktop/steam-bigpicture.desktop`, `docs/COMPATIBILITY.md`, `docs/05-Complete-Setup-HowTo.md`.
- **Acceptance Checks:** `./install.sh --dry-run` succeeds cleanly; live session switch `bigscreen` ↔ `desktop` works without QML errors; `tv-display-mode` and KWin script report healthy; `./rollback-tv-setup.sh` restores pre-existing configs cleanly.
- **Hardware Evidence Needed:** Sanitized `tv-display-mode diagnose`, `plasmashell --version`, `/etc/os-release`, `kscreen-doctor -o`, Flatpak list, and completed Manual Hardware Acceptance Checklist.
- **Security Considerations:** Must not require `sudo` inside `install.sh` or `rollback-tv-setup.sh`; must not overwrite unrelated user configs or Flatpak overrides.
- **Documentation Expected:** Verified row in `docs/COMPATIBILITY.md` and any Fedora-Spin-specific notes in `docs/05-Complete-Setup-HowTo.md`.

### 2. Mutable distro: Ubuntu + KDE Plasma
- **Labels:** `help wanted`, `area:compatibility`, `platform:mutable`, `needs-hardware-test`, `priority:P1`
- **Goal:** Validate NextGen Plasma Bigscreen on **Ubuntu / Kubuntu** releases shipping **KDE Plasma 6 Wayland** (`apt`).
- **Current Unknowns:** Package availability and binary paths (`plasma-bigscreen-common-env`, `plasma-bigscreen-inputhandler`, `qdbus6`/`qdbus-qt6`, `kscreen-doctor`, `bwrap`), `~/.bashrc.d` non-default sourcing, and Snap vs Flatpak Firefox/Steam paths.
- **Scope / Non-goals:** Scope covers Ubuntu/Kubuntu Plasma 6 Wayland releases only. Non-goals: Plasma 5 (e.g., 24.04 LTS stock Plasma 5), X11 sessions, or Snap packaging workarounds requiring root.
- **Prerequisites:** Ubuntu/Kubuntu with KDE Plasma 6 Wayland and `plasma-bigscreen` package installed.
- **Possible Files:** `install.sh`, `rollback-tv-setup.sh`, `bin/tv-session-switch.sh`, `bin/nextgen_platform.py`, `docs/COMPATIBILITY.md`, `docs/05-Complete-Setup-HowTo.md`.
- **Acceptance Checks:** Dry-run and install work without missing-tool crashes; `qdbus6` / `busctl` commands work; `bigscreen` ↔ `desktop` switch and rollback succeed cleanly.
- **Hardware Evidence Needed:** Sanitized `tv-display-mode diagnose`, `/etc/os-release`, `plasmashell --version`, `which plasma-bigscreen-inputhandler kscreen-doctor busctl qdbus6`, and checklist results.
- **Security Considerations:** Keep all NextGen edits inside `$HOME`; do not invoke `apt`/`sudo` from installer scripts; clearly document explicit rollback for `apt install`.
- **Documentation Expected:** Verified row in `docs/COMPATIBILITY.md` and Ubuntu/Kubuntu Plasma 6 notes (including `~/.bashrc` sourcing note).

### 3. Mutable distro: Debian KDE
- **Labels:** `help wanted`, `area:compatibility`, `platform:mutable`, `needs-hardware-test`, `priority:P1`
- **Goal:** Validate NextGen Plasma Bigscreen on **Debian KDE (Testing / Trixie+ with Plasma 6 Wayland)**.
- **Current Unknowns:** Debian `plasma-bigscreen` packaging layout, `qt6-tools`/`qdbus6` binary names, `python3-dbus` / PyGObject GTK3 availability for `tv-movie-mode-toggle`, and `uaccess` ACL behavior for USB remotes.
- **Scope / Non-goals:** Scope covers Debian Plasma 6 Wayland only. Non-goals: Debian 12 Bookworm (Plasma 5) or root-level `/etc/udev` edits.
- **Prerequisites:** Debian Testing/Unstable/Trixie+ running KDE Plasma 6 Wayland.
- **Possible Files:** `install.sh`, `bin/tv-session-switch.sh`, `bin/tv-movie-mode-toggle`, `bin/nextgen_platform.py`, `docs/COMPATIBILITY.md`.
- **Acceptance Checks:** Installer detects/handles missing optional Python/Qt tools gracefully; daemon, KWin script, session switcher, and rollback pass on real hardware.
- **Hardware Evidence Needed:** Sanitized `tv-display-mode diagnose`, `tv-remote-keymap.py --diagnose`, `/etc/os-release`, installed package versions, and checklist results.
- **Security Considerations:** Zero root execution in user-space scripts; safe handling when optional dependencies (`bwrap`, `gcc`, `cec-ctl`) are absent.
- **Documentation Expected:** Verified row in `docs/COMPATIBILITY.md` and Debian prerequisite package list in `docs/05-Complete-Setup-HowTo.md`.

### 4. Mutable distro: Arch Linux KDE
- **Labels:** `help wanted`, `good first issue`, `area:compatibility`, `platform:mutable`, `needs-hardware-test`, `priority:P1`
- **Goal:** Validate NextGen Plasma Bigscreen on **Arch Linux** (and Arch derivatives such as CachyOS / EndeavourOS) running KDE Plasma 6 Wayland.
- **Current Unknowns:** Latest Plasma 6.x QML API compatibility (`org.kde.bigscreen.homescreen`), `qdbus6` path (`/usr/lib/qt6/bin/qdbus` vs `/usr/bin/qdbus6`), native vs Flatpak Steam/streaming apps, and shell profile sourcing (`~/.bashrc` / `~/.zshrc`).
- **Scope / Non-goals:** Scope covers official Arch `plasma-bigscreen` packages on Plasma 6 Wayland. Non-goals: AUR helper automation or `/usr` overrides.
- **Prerequisites:** Arch-based system with KDE Plasma 6 Wayland and `plasma-bigscreen` installed via `pacman`.
- **Possible Files:** `install.sh`, `rollback-tv-setup.sh`, `bin/tv-session-switch.sh`, `plasma/plasmoids/org.kde.bigscreen.homescreen/`, `docs/COMPATIBILITY.md`.
- **Acceptance Checks:** Zero QML errors on newest Arch Plasma Bigscreen; `tv-display-mode` daemon + KWin script active; full rollback verified.
- **Hardware Evidence Needed:** Sanitized `tv-display-mode diagnose`, `plasmashell --version`, `pacman -Q plasma-bigscreen`, journal excerpt for `plasma-plasmashell.service` (redacted), and checklist.
- **Security Considerations:** Never run `pacman` or `sudo` automatically; preserve existing user Flatpak/KDE configs.
- **Documentation Expected:** Verified row in `docs/COMPATIBILITY.md` and any QML reconciliation notes in `docs/ARCHITECTURE.md`.

### 5. Mutable distro: openSUSE Tumbleweed KDE
- **Labels:** `help wanted`, `area:compatibility`, `platform:mutable`, `platform:atomic`, `needs-hardware-test`, `priority:P1`
- **Goal:** Validate NextGen Plasma Bigscreen on **openSUSE Tumbleweed** (mutable `zypper`) and optionally **Kalpa** (`transactional-update`) with `plasma6-bigscreen`.
- **Current Unknowns:** Package naming (`plasma6-bigscreen`), binary paths (`qdbus6`, `plasma-bigscreen-common-env`), SELinux/AppArmor interaction with user systemd units or `bwrap`, and Flatpak portal integration.
- **Scope / Non-goals:** Scope covers Plasma 6 Wayland on Tumbleweed/Kalpa. Non-goals: Leap 15 (Plasma 5) or automatic `transactional-update` calls.
- **Prerequisites:** openSUSE Tumbleweed or Kalpa running KDE Plasma 6 Wayland with `plasma6-bigscreen`.
- **Possible Files:** `install.sh`, `bin/tv-session-switch.sh`, `bin/nextgen_platform.py`, `docs/COMPATIBILITY.md`, `docs/05-Complete-Setup-HowTo.md`.
- **Acceptance Checks:** Dry-run, install, Bigscreen ↔ Desktop switch, `tv-display-mode`, and rollback all pass cleanly with zero SELinux/AppArmor denials blocking user services.
- **Hardware Evidence Needed:** Sanitized `tv-display-mode diagnose`, `/etc/os-release`, `rpm -q plasma6-bigscreen`, and checklist results.
- **Security Considerations:** Do not weaken SELinux/AppArmor policies; stay strictly inside `$HOME`.
- **Documentation Expected:** Verified row in `docs/COMPATIBILITY.md` and openSUSE package/rollback notes in `docs/05-Complete-Setup-HowTo.md`.

### 6. GPU: AMD Radeon/Mesa
- **Labels:** `help wanted`, `area:compatibility`, `gpu:amd`, `needs-hardware-test`, `priority:P0`
- **Goal:** Verify platform adapter GPU detection and end-to-end VA-API (`radeonsi`) hardware video decoding on **AMD Radeon (`amdgpu` + Mesa)** systems.
- **Current Unknowns:** Exact Flatpak override set needed for VacuumTube, Stremio (`stremio_mpv_shim.c`), Jellyfin Desktop, and Haruna on AMD; whether Chromium/Electron Vulkan flags (`--disable-features=Vulkan`) help or hurt on RDNA2/RDNA3/Vega; AV1 hardware decode behavior on RDNA3+.
- **Scope / Non-goals:** Scope covers Mesa `radeonsi` VA-API on Wayland. Non-goals: AMDVLK-only hacks or proprietary AMDGPU-PRO stacks.
- **Prerequisites:** AMD Radeon GPU running KDE Plasma 6 Wayland with Mesa VA-API drivers installed.
- **Possible Files:** `bin/nextgen_platform.py`, `install.sh`, `configs/vacuumtube/flags.txt`, `configs/haruna/haruna.conf`, `tests/test_nextgen_platform.py`, `docs/COMPATIBILITY.md`.
- **Acceptance Checks:** Zero `LIBVA_DRIVER_NAME=iHD` injected into any Flatpak override or `environment.d`; live hardware decode verified via `vainfo` + `/proc/<pid>/maps` (`radeonsi_drv_video.so`) or `radeontop`; unit fixture test added.
- **Hardware Evidence Needed:** Sanitized `lspci -k`, `vainfo`, `tv-display-mode diagnose`, `flatpak override --user --show <app>`, and live decode verification for H.264/HEVC/VP9/(AV1 if supported).
- **Security Considerations:** Do not modify system Mesa packages or `/etc/environment`; patch only NextGen-owned Flatpak override keys.
- **Documentation Expected:** Verified AMD row in `docs/COMPATIBILITY.md` and AMD notes in `docs/02-Streaming-Apps-Guide.md`.

### 7. GPU: NVIDIA
- **Labels:** `help wanted`, `area:compatibility`, `gpu:nvidia`, `needs-hardware-test`, `priority:P0`
- **Goal:** Verify safe installation, Wayland compositor stability, and hardware video decoding behavior on **NVIDIA proprietary** Linux drivers (NVDEC / optional `nvidia-vaapi-driver`).
- **Current Unknowns:** Explicit-sync / GBM Wayland behavior across VacuumTube (Electron), Stremio (`libmpv`), Jellyfin Desktop, and Haruna (`HardwareDecoding=auto-safe` vs `nvdec` vs `vaapi`); Flatpak NVIDIA runtime extension interactions; `stremio_mpv_shim.c` behavior with `hwdec=auto-safe` on NVIDIA.
- **Scope / Non-goals:** Scope covers modern NVIDIA Wayland drivers (555+ explicit sync recommended). Non-goals: Nouveau VA-API hacks or kernel-module installation.
- **Prerequisites:** NVIDIA GPU with proprietary Wayland driver running KDE Plasma 6 Wayland.
- **Possible Files:** `bin/nextgen_platform.py`, `install.sh`, `configs/vacuumtube/flags.txt`, `configs/haruna/haruna.conf`, `tests/test_nextgen_platform.py`, `docs/COMPATIBILITY.md`.
- **Acceptance Checks:** Zero Intel `iHD` flags applied; no black-screen crashes in VacuumTube/Stremio/Jellyfin/Haruna; hardware decode vs software fallback documented accurately; unit fixture test added.
- **Hardware Evidence Needed:** Sanitized `nvidia-smi` (driver version & GPU model only), `tv-display-mode diagnose`, app decode logs/status (`nvdec` or software), and rollback confirmation.
- **Security Considerations:** Never install kernel drivers or touch `/etc/modprobe.d`; keep all tweaks scoped to user-space overrides tracked in the manifest.
- **Documentation Expected:** Verified NVIDIA row in `docs/COMPATIBILITY.md` and clear NVIDIA caveats in `docs/02-Streaming-Apps-Guide.md`.

### 8. GPU: Intel legacy/new
- **Labels:** `help wanted`, `area:compatibility`, `gpu:intel`, `needs-hardware-test`, `priority:P1`
- **Goal:** Validate GPU adapter behavior across **older Intel (`i965`)** and **newer Intel (Tiger Lake / Alder Lake / Iris Xe / Arc on `i915` or `xe`)** GPUs.
- **Current Unknowns:** Legacy Intel (`i965`) behavior when `iHD` is unsupported; modern Intel (`xe` kernel driver + `iHD`) AV1 hardware decode and whether VacuumTube `--disable-features=Vulkan` is still needed on Gen 12+/Arc.
- **Scope / Non-goals:** Scope covers Intel VA-API selection (`iHD` vs `i965` vs auto) and live decode verification. Non-goals: modifying kernel boot parameters (`i915.force_probe` / `xe.force_probe`).
- **Prerequisites:** Non-Gen-9.5 Intel GPU running KDE Plasma 6 Wayland.
- **Possible Files:** `bin/nextgen_platform.py`, `install.sh`, `configs/vacuumtube/flags.txt`, `tests/test_nextgen_platform.py`, `docs/COMPATIBILITY.md`.
- **Acceptance Checks:** Correct driver selection (never forcing `iHD` on `i965`-only GPUs); live decode evidence for supported codecs (including AV1 on Gen 12+/Arc); fixture test added.
- **Hardware Evidence Needed:** Sanitized `lspci -k`, `vainfo`, `tv-display-mode diagnose`, and verified codec table.
- **Security Considerations:** User-space only; no kernel parameter changes.
- **Documentation Expected:** Verified Intel rows in `docs/COMPATIBILITY.md` and codec notes in `docs/02-Streaming-Apps-Guide.md`.

### 9. Display: multi-monitor & connector switching
- **Labels:** `help wanted`, `area:display`, `needs-hardware-test`, `priority:P1`
- **Goal:** Safely support machines connected to multiple displays (e.g., desk monitor + living-room TV) or changing connectors (`HDMI-A-1`, `HDMI-A-2`, `DP-1`, `DP-2`) without switching the wrong output.
- **Current Unknowns:** How `tv-display-mode` should select/persist the target TV output when multiple outputs are connected, handle hotplug/unplug of the TV, and behave when `tv-display-mode.sh` encounters >1 connected DRM connector.
- **Scope / Non-goals:** Scope covers safe output targeting, connector discovery, and graceful fallback when the configured TV output is disconnected. Non-goals: full multi-head layout management or X11 `xrandr` support.
- **Prerequisites:** KDE Plasma 6 Wayland host with 2+ outputs (or real `kscreen-doctor -j` multi-output fixtures).
- **Possible Files:** `bin/tv-display-mode`, `bin/tv-display-mode.sh`, `bin/nextgen_platform.py`, `configs/tv-display-mode/config.json`, `tests/test_tv_display_mode.py`.
- **Acceptance Checks:** `tv-display-mode` never alters a non-target monitor; handles disconnected configured output cleanly without crashing; multi-output unit tests pass.
- **Hardware Evidence Needed:** Sanitized `kscreen-doctor -j` (redacting serials if present) and `tv-display-mode status` / `diagnose` before & after switching.
- **Security Considerations:** Always preserve a known-good fallback mode; never blind-disable the primary display.
- **Documentation Expected:** Multi-monitor configuration section in `docs/05-Complete-Setup-HowTo.md` and updated schema notes in `docs/ARCHITECTURE.md`.

### 10. Display: 4K60/120, HDR and VRR research
- **Labels:** `help wanted`, `area:display`, `needs-hardware-test`, `priority:P1`
- **Goal:** Research and validate **HDMI 2.0/2.1 4K@60Hz / 4K@120Hz**, **KWin 6 Wayland HDR**, and **VRR (Adaptive Sync)** behavior with `tv-display-mode` and Movie Mode.
- **Current Unknowns:** Whether `tv-movie-mode-toggle` should read actual configured refresh rate dynamically instead of hardcoding `30Hz`; how `kscreen-doctor` toggles/preserves HDR, WCG, maxbpc (8 vs 10-bit), and VRR flags across mode switches without breaking Steam or video playback.
- **Scope / Non-goals:** Scope covers research, fixture-tested mode/property selection, and honest documentation of KWin 6 Wayland HDR/VRR capabilities. Non-goals: assuming every TV supports 4K@60/HDR/VRR.
- **Prerequisites:** HDMI 2.0/2.1 TV/monitor supporting 4K@60+ and/or HDR/VRR on KDE Plasma 6 Wayland.
- **Possible Files:** `bin/tv-display-mode`, `bin/tv-movie-mode-toggle`, `bin/nextgen_platform.py`, `tests/test_tv_display_mode.py`, `docs/COMPATIBILITY.md`, `docs/ARCHITECTURE.md`.
- **Acceptance Checks:** Dynamic refresh rate displayed in OSD/toast; `kscreen-doctor -j` fixture tests covering 4K@60, 4K@120, HDR, and VRR; zero regression on 4K@30 SDR TVs.
- **Hardware Evidence Needed:** Sanitized `kscreen-doctor -j` output, TV mode/HDR/VRR test results, and rollback verification.
- **Security Considerations:** Display-safety first — never apply unverified custom timings or unsupported refresh rates automatically.
- **Documentation Expected:** Updated `docs/COMPATIBILITY.md` entries and HDR/VRR guidance in `docs/05-Complete-Setup-HowTo.md`.

### 11. Remote: HDMI-CEC adapters
- **Labels:** `help wanted`, `area:remote`, `needs-hardware-test`, `priority:P1`
- **Goal:** Validate real **native HDMI-CEC** and **USB HDMI-CEC** adapters (e.g., Pulse-Eight, Raspberry Pi/AMD/Intel native HDMI-CEC) alongside `plasma-bigscreen-inputhandler` and `nextgen_platform.py` CEC classification.
- **Current Unknowns:** Exact `cec-ctl -d /dev/cec*` output strings across native HDMI vs USB-CEC vs tunneled `cec-DP-*` adapters; whether `bwrap` isolation is accurately bypassed for real CEC adapters; TV wake/standby and remote key forwarding reliability.
- **Scope / Non-goals:** Scope covers accurate CEC classification, conditional `plasma-bigscreen-inputhandler.service` configuration, and real-hardware CEC navigation tests. Non-goals: breaking tunneled `cec-DP-*` timeout mitigation.
- **Prerequisites:** Linux PC with a native HDMI-CEC port or USB-CEC adapter connected to a CEC-capable TV.
- **Possible Files:** `bin/nextgen_platform.py`, `bin/tv-remote-keymap.py`, `systemd/user/plasma-bigscreen-inputhandler.service`, `configs/plasma-bigscreen-inputhandlerrc`, `tests/test_nextgen_platform.py`, `docs/03-Remote-Controls-and-HDMI-CEC.md`.
- **Acceptance Checks:** Native/USB CEC adapters are classified distinctly from `cec-DP-*` tunnels; TV remote D-Pad/OK/Back work via CEC without double-input; fixture tests cover both native and tunneled `cec-ctl` output.
- **Hardware Evidence Needed:** Sanitized `cec-ctl -d /dev/cec0` output, `tv-remote-keymap.py --diagnose`, and navigation test checklist.
- **Security Considerations:** No root privileges required (rely on `uaccess`/video/cec group permissions); document any distro permission caveats honestly.
- **Documentation Expected:** Updated HDMI-CEC section in `docs/03-Remote-Controls-and-HDMI-CEC.md` and entry in `docs/COMPATIBILITY.md`.

### 12. Remote: Bluetooth/RF controllers
- **Labels:** `help wanted`, `good first issue`, `area:remote`, `needs-hardware-test`, `priority:P1`
- **Goal:** Add data-driven remote profiles for common **Bluetooth and 2.4 GHz RF TV remotes / air-mice** (e.g., Shield/Fire TV/Chromecast Bluetooth remotes, G10/G20/WeChip RF remotes) and verify game controller ergonomics.
- **Current Unknowns:** Vendor/Product IDs, HID usage scancodes above `255` dropped by Wayland/XKB, power/back/home/menu key mappings, and whether Bluetooth HID devices expose `uaccess` `EVIOCSKEYCODE_V2` support identically to USB HID remotes.
- **Scope / Non-goals:** Scope covers profile entries in `configs/remote-profiles.json` (and `~/.config/nextgen-plasmabigscreen/remote-profiles.json`), `--diagnose` discovery, and unit tests. Non-goals: requiring root udev/hwdb writes in `/etc`.
- **Prerequisites:** Bluetooth or 2.4G RF remote paired/connected to a KDE Plasma 6 Wayland host.
- **Possible Files:** `bin/tv-remote-keymap.py`, `bin/nextgen_platform.py`, `configs/remote-profiles.json`, `tests/test_nextgen_platform.py`, `docs/03-Remote-Controls-and-HDMI-CEC.md`, `docs/COMPATIBILITY.md`.
- **Acceptance Checks:** Profile loads cleanly without editing Python code; `--apply`, `--status`, `--diagnose`, and `--reset` all work; unit tests validate profile schema & matching.
- **Hardware Evidence Needed:** Sanitized `tv-remote-keymap.py --diagnose`, USB/BT Vendor:Product IDs (redact MAC/serials!), and verified key map table.
- **Security Considerations:** Redact Bluetooth MAC addresses and device serial numbers from any submitted logs/fixtures; never run keymap remapper as root.
- **Documentation Expected:** Profile entry documented in `docs/03-Remote-Controls-and-HDMI-CEC.md` and verified row in `docs/COMPATIBILITY.md`.

### 13. Streaming: browser DRM compatibility
- **Labels:** `help wanted`, `area:compatibility`, `area:docs`, `needs-hardware-test`, `priority:P2`
- **Goal:** Document honest, reproducible **browser Widevine/DRM compatibility observations** (Netflix, Disney+, Prime Video, etc. in Firefox / Chromium Flatpaks) across Linux distros and GPUs, including 10-foot usability and known Linux DRM/HDCP caps.
- **Current Unknowns:** Actual delivered resolution/codec/audio behavior on unmodified stock browsers across Intel/AMD/NVIDIA Wayland, controller/remote ergonomics in web players, and whether MPRIS background auto-pause behaves reliably with browser media sessions.
- **Scope / Non-goals:** Scope is strictly honest testing, documentation, and standard Wayland/MPRIS usability improvements. **Explicit non-goals:** DRM circumvention, Widevine L1 spoofing, proprietary key extraction, or promising 1080p/4K DRM playback.
- **Prerequisites:** Legitimate streaming subscription + stock Flatpak/native browser on KDE Plasma 6 Wayland.
- **Possible Files:** `docs/COMPATIBILITY.md`, `docs/02-Streaming-Apps-Guide.md`.
- **Acceptance Checks:** Clear, factual table distinguishing VA-API hardware decode from DRM resolution caps (e.g., Widevine L3 720p limits); zero DRM-bypass instructions.
- **Hardware Evidence Needed:** Browser version, GPU/driver, observed stream stats (resolution/codec/HW decode), navigation experience, and MPRIS auto-pause result (redacting account info).
- **Security Considerations:** No unofficial patched binaries, DRM-bypass extensions, or credential leaks.
- **Documentation Expected:** Updated browser DRM rows in `docs/COMPATIBILITY.md` and realistic expectations note in `docs/02-Streaming-Apps-Guide.md`.

### 14. Installer: transactional install and rollback
- **Labels:** `help wanted`, `area:installer`, `platform:atomic`, `platform:mutable`, `needs-hardware-test`, `priority:P0`
- **Goal:** Harden `install.sh`, `bin/nextgen-manifest.py`, and `rollback-tv-setup.sh` so every `$HOME` mutation is manifest-tracked, pre-existing user files are backed up with timestamps, Flatpak overrides are key-patched rather than clobbered, and rollback restores exact pre-install state cleanly.
- **Current Unknowns:** Edge cases when upgrading from pre-manifest installs, partial failure recovery mid-install, missing `gcc`/`bwrap`/`flatpak`, and non-standard `$XDG_CONFIG_HOME` / `$XDG_DATA_HOME`.
- **Scope / Non-goals:** Scope covers user-space `$HOME` install/upgrade/rollback reliability, `--dry-run`, and manifest tests. Non-goals: system package installation (`sudo`/`dnf`/`apt`/`rpm-ostree`).
- **Prerequisites:** Linux shell environment with `bash` and `python3` (safe to test in `mktemp -d` temporary `$HOME`).
- **Possible Files:** `install.sh`, `rollback-tv-setup.sh`, `bin/nextgen-manifest.py`, `tests/test_install_rollback.py`, `docs/ARCHITECTURE.md`, `docs/04-Operations-and-Rollback-Runbook.md`.
- **Acceptance Checks:** Isolated temp-HOME tests prove pre-existing `powerdevilrc`, `kwinrulesrc`, and unrelated Flatpak overrides survive install + rollback byte-for-byte; `--dry-run` makes zero filesystem writes; missing `gcc` never leaves a broken `LD_PRELOAD`.
- **Hardware Evidence Needed:** Real-host `--dry-run` + install + rollback test confirming live desktop restoration without config loss.
- **Security Considerations:** Atomic temp-file writes, strict quoting, no destructive `rm -rf` outside manifest-owned paths, zero root escalation.
- **Documentation Expected:** Manifest schema & recovery steps in `docs/ARCHITECTURE.md` and `docs/04-Operations-and-Rollback-Runbook.md`.

### 15. QA: hardware test matrix and CI
- **Labels:** `help wanted`, `good first issue`, `area:compatibility`, `area:docs`, `priority:P0`
- **Goal:** Expand automated CI verification (`.github/workflows/ci.yml`), fixture test coverage (multi-GPU, multi-output, CEC, remote profiles, install/rollback in temp `$HOME`), and standardized hardware test reporting.
- **Current Unknowns:** Additional sanitized real-world `kscreen-doctor -j`, `vainfo`, and `cec-ctl` fixtures from diverse AMD/NVIDIA/mutable hosts needed to prevent regressions.
- **Scope / Non-goals:** Scope covers GitHub Actions CI, anonymized fixture tests, Markdown link checking, and test documentation. Non-goals: claiming CI replaces real-TV hardware testing.
- **Prerequisites:** `python3`, `bash`, `gcc` (optional), `shellcheck` (optional).
- **Possible Files:** `.github/workflows/ci.yml`, `tests/*.py`, `docs/COMPATIBILITY.md`, `CONTRIBUTING.md`.
- **Acceptance Checks:** CI passes on push/PR (unit tests, `py_compile`, `bash -n`, `shellcheck`, C syntax check, Markdown link checker); clear notice in CI & docs that hardware testing remains manual.
- **Hardware Evidence Needed:** Anonymized hardware fixtures contributed alongside real compatibility reports.
- **Security Considerations:** Every committed fixture must be audited for PII, serials, MACs, and private hostnames.
- **Documentation Expected:** Test commands and CI scope documented in `CONTRIBUTING.md` and `docs/COMPATIBILITY.md`.

### 16. UX: accessibility and translations
- **Labels:** `help wanted`, `good first issue`, `area:docs`, `priority:P2`
- **Goal:** Improve living-room **accessibility** (high-contrast focus rings, scalable 10-foot typography, screen reader / keyboard-only completeness, reduced-motion options) and prepare **internationalisation (`i18n`)** for QML strings and documentation.
- **Current Unknowns:** Current QML hardcoded English strings in `plasma/plasmoids/org.kde.bigscreen.homescreen/`, Plasma Bigscreen focus-indicator contrast across themes, and Orca/Qt accessibility behavior under Plasma Bigscreen Wayland.
- **Scope / Non-goals:** Scope covers auditing QML accessibility/focus rings, wrapping UI text in `i18n()`, and documenting localization workflow. Non-goals: machine-translated unreviewed UI catalogs.
- **Prerequisites:** KDE Plasma 6 Wayland (for live QML testing) or QML/i18n familiarity.
- **Possible Files:** `plasma/plasmoids/org.kde.bigscreen.homescreen/contents/ui/*.qml`, `docs/ARCHITECTURE.md`, `CONTRIBUTING.md`.
- **Acceptance Checks:** All interactive homescreen controls have clear visible focus indicators and keyboard/D-Pad reachability; UI strings use `i18n()` consistently; zero QML runtime errors.
- **Hardware Evidence Needed:** Screenshots/notes of focus visibility at 10-foot viewing distance (1080p and 4K scaling) and screen-reader/navigation test notes.
- **Security Considerations:** No external network calls for TTS/translation at runtime.
- **Documentation Expected:** Accessibility & translation guidelines in `CONTRIBUTING.md` and updated status in `docs/ARCHITECTURE.md`.

---

## 4. P2 Proposals (Proposed — Not Built)

The following long-term living-room capabilities are **proposed only** (not yet implemented or scheduled for P0/P1). Design discussions are welcome via [Feature Request issues](https://github.com/nissifield/NextGen_plasmabigscreen/issues/new?template=feature-request.yml):

1. **Optional User Profiles (`Proposed`):** Lightweight per-viewer favorites, Watch Now ordering, and session preferences in `$HOME` without requiring full OS user switching.
2. **Child-Safe Launcher & Parental Controls (`Proposed`):** Opt-in allowlist launcher mode hiding unapproved apps and PIN-gating Settings, Force Stop, and Desktop Mode exit.
3. **Accessibility Presets (`Proposed`):** One-toggle high-contrast focus outlines, extra-large 10-foot font scaling, reduced-motion mode, and screen-reader / audio-cue integration.
4. **Localisation / Translations (`Proposed`):** Community-maintained `.po` translation catalogs for the custom Homescreen QML strings, OSD toasts, and setup guides.
5. **Opt-In Signed & Verified User-Space Updates (`Proposed`):** Optional user-triggered update checker verifying signed Git tags/release checksums before applying manifest-backed updates with one-command rollback (never silent auto-updates).

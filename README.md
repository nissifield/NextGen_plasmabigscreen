<p align="center">
  <img src="assets/banner.jpg" alt="NextGen Plasma Bigscreen — Android TV Experience on Native Linux" width="100%">
</p>

# NextGen Plasma Bigscreen

**KDE Plasma Bigscreen customized to replicate an Android TV / Google TV experience on native Linux.**

Built for **KDE Plasma 6.x Wayland** and user-space-first living-room HTPCs (officially tested on **Bazzite / Fedora Kinoite with KDE Plasma 6 Wayland**) without modifying `/usr`—once the base `plasma-bigscreen` package is installed from your distro, every NextGen customization lives declaratively in `$HOME` (`~/.local/`, `~/.config/`, and systemd user services) with manifest-tracked backups and rollback.

---

## Set Up With Your AI Agent

Use **Claude Code, Codex, Gemini CLI, Antigravity, Cursor, OpenCode**, or any coding agent to inspect your hardware, adapt configs for your TV/GPU/distro, install safely into `$HOME`, and verify everything end-to-end.

Paste this into your AI coding agent:

```text
Fetch and follow https://raw.githubusercontent.com/nissifield/NextGen_plasmabigscreen/main/SETUP_PROMPT.md to inspect my Linux machine, adapt NextGen_plasmabigscreen to my hardware, install it into $HOME, and verify it end-to-end.
```

Already cloned the repo locally? Paste instead:

```text
Read and follow SETUP_PROMPT.md in this repository to inspect my Linux machine, adapt NextGen_plasmabigscreen to my hardware, install it into $HOME, and verify it end-to-end.
```

> See [SETUP_PROMPT.md](SETUP_PROMPT.md) for the full self-service setup prompt, or follow the manual [Quick Start](#quick-start) / [Complete Setup How-To Guide](docs/05-Complete-Setup-HowTo.md).

---

## Key Features

- **Android TV / Google TV Homescreen Override (`plasma/plasmoids/org.kde.bigscreen.homescreen/`)**
  - Category navigation tabs (`For You`, `Watch Now`, `Apps`, `Games`) with full keyboard, D-Pad, and controller navigation.
  - Dynamic brand-tinted Hero Spotlight Banner with live `● RUNNING` app status and remote action hints.
  - Wide 16:9 **Watch Now** streaming row (`YouTube TV`, `Stremio`, `Jellyfin TV`, `Haruna`), **Continue & Recent** row, and long-press (`Hold OK`) context menu (`Open / Resume`, `Pin / Remove from Favorites`, `Move Left / Right`, `Force Stop`).
  - Curated Favorites (`YouTube TV`, `Stremio`, `Jellyfin TV`, `Steam`, `Haruna`, `Desktop Mode`, `Movie Mode`) and clean app-grid filtering (`applications-blacklistrc`).
- **Automatic Display Mode Manager, Steam 1080p Priority & Movie Mode (`bin/tv-display-mode`)**
  - **Steam Priority:** Automatically locks the TV output (default `DP-1`) to `1920x1080 @ 60Hz` whenever Steam Big Picture or any Steam game child process is active or fullscreen in the foreground.
  - **On-Demand Movie Mode (`bin/tv-movie-mode-toggle`):** Bigscreen launcher tile + shell helpers (`tv-movie`, `tv-toggle`, `tv-4k`, `tv-1080p`) that cleanly toggle between configured 4K and 1080p modes with Plasma OSD + brief toast banner feedback (`auto_4k_video_switch: false` by default so navigation stays snappy at 60Hz).
  - **KWin 6 Wayland Integration (`kwin/tv-display-mode.js`):** Pushes active/added/minimized window metadata over DBus (`org.nextgen.TvDisplayMode`) and ensures Stremio opens fullscreen by default.
- **Android TV-Style Background Media Auto-Pause**
  - When returning to the Plasma Bigscreen Home screen / shell overlay or switching focus to Steam or another media app, `tv-display-mode` automatically calls MPRIS `Player.Pause()` on any playing background media app.
  - Matches Flatpak apps accurately across `xdg-dbus-proxy` PID boundaries (via PID, shared `app-flatpak-*.scope` cgroups, `DesktopEntry`, and `Identity`) so the focused player is never paused.
  - Ignores OSDs, notifications, transient popups, Polkit auth dialogs, and `fallback`/`init` states, and never calls `Play()` automatically when refocusing a paused app.
- **Hardware Video Acceleration & Platform Adapters (`bin/nextgen_platform.py`, `bin/nextgen-manifest.py`)**
  - **Platform Discovery & Safe Manifest:** Detects GPU/VA-API stack, DRM/KScreen outputs, and tunneled vs native HDMI-CEC devices, while tracking installed files, versioned backups, and key-scoped Flatpak overrides in `$HOME`.
  - **Stremio (`stremio/stremio_mpv_shim.c`):** Lightweight `LD_PRELOAD` shim for `libmpv.so` enforcing `config=yes`, `hwdec=auto-safe`, and `hwdec-codecs=all` so embedded libmpv honors hardware decode (`stremio/mpv.conf`).
  - **VacuumTube (YouTube TV), Jellyfin Desktop & Haruna:** Configured for Wayland and hardware video decoding with sanitized diagnostics (`tv-display-mode diagnose`).
- **Controller, Remote Keymap & Desktop <-> Bigscreen Session Swapping**
  - **`bin/tv-session-switch.sh`:** Cleanly swaps between `org.kde.plasma.bigscreen` and standard `org.kde.plasma.desktop` in user-space, preserving custom blacklists and input handler settings across `plasma-bigscreen-envmanager`.
  - **Gamepad Input Isolation (`configs/plasma-bigscreen-inputhandlerrc`):** `AutoSuppressInput=true` prevents double D-pad input when focused inside Steam Big Picture or controller-capable apps (Stremio / VacuumTube).
  - **USB Remote Remapper & DP-to-HDMI CEC Fix (`bin/tv-remote-keymap.py`):** User-space `EVIOCSKEYCODE_V2` remapper with data-driven remote profiles + `--clear` on tunneled `cec-DP-*` adapters to prevent DP-AUX timeouts.

---

## Help Bring NextGen to More Linux Systems

We warmly welcome contributors running **Ubuntu, Debian, Arch Linux, openSUSE Tumbleweed, mutable Fedora KDE Spin, AMD Radeon, NVIDIA, legacy or newer Intel GPUs, 4K@60/120/HDR/VRR TVs, HDMI-CEC or Bluetooth/RF remotes**, as well as **testers, accessibility advocates, and documentation writers**. You do **not** need Fedora Kinoite, Bazzite, or Intel hardware to help!

### Honest Support Status Definitions

- **Officially tested:** Reproducibly tested end-to-end on real TV hardware by a maintainer (currently **Bazzite / Fedora Kinoite + KDE Plasma 6 Wayland + Intel UHD 630 `iHD` + DP-1 4K@30/1080p@60 + XING WEI `620a:0407` remote**).
- **Community-tested:** Verified on real hardware by a contributor with sanitized diagnostics and rollback evidence in a Compatibility Report or PR.
- **Experimental:** Adapter or config support exists or is unit/fixture tested, but real-hardware validation is incomplete.
- **Untested:** Not yet verified on real hardware — check [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) before assuming support.

### Open Contribution Cards

Browse full card specifications in [docs/CONTRIBUTION_BOARD.md](docs/CONTRIBUTION_BOARD.md) or view/file issues on [GitHub Issues](https://github.com/nissifield/NextGen_plasmabigscreen/issues) ([choose an issue template](https://github.com/nissifield/NextGen_plasmabigscreen/issues/new/choose)). Having a card means **help is wanted**, not that the platform is already supported.

| Area | Contribution Card | Current Status | Priority |
| :--- | :--- | :--- | :--- |
| Mutable Distros | [Fedora KDE Spin](docs/CONTRIBUTION_BOARD.md#1-mutable-distro-fedora-kde-spin) · [Ubuntu + KDE](docs/CONTRIBUTION_BOARD.md#2-mutable-distro-ubuntu--kde-plasma) · [Debian KDE](docs/CONTRIBUTION_BOARD.md#3-mutable-distro-debian-kde) · [Arch Linux KDE](docs/CONTRIBUTION_BOARD.md#4-mutable-distro-arch-linux-kde) · [openSUSE Tumbleweed](docs/CONTRIBUTION_BOARD.md#5-mutable-distro-opensuse-tumbleweed-kde) | Untested — Ready for contributors | `P1` |
| GPUs | [AMD Radeon/Mesa](docs/CONTRIBUTION_BOARD.md#6-gpu-amd-radeonmesa) · [NVIDIA](docs/CONTRIBUTION_BOARD.md#7-gpu-nvidia) · [Intel legacy/new](docs/CONTRIBUTION_BOARD.md#8-gpu-intel-legacynew) | Experimental — Needs hardware validation | `P0` / `P1` |
| Displays | [Multi-monitor & connector switching](docs/CONTRIBUTION_BOARD.md#9-display-multi-monitor--connector-switching) · [4K60/120, HDR and VRR research](docs/CONTRIBUTION_BOARD.md#10-display-4k60120-hdr-and-vrr-research) | Untested — Ready for contributors | `P1` |
| Remotes & CEC | [HDMI-CEC adapters](docs/CONTRIBUTION_BOARD.md#11-remote-hdmi-cec-adapters) · [Bluetooth/RF controllers](docs/CONTRIBUTION_BOARD.md#12-remote-bluetoothrf-controllers) | Experimental — Needs hardware validation | `P1` |
| Streaming & DRM | [Browser DRM compatibility](docs/CONTRIBUTION_BOARD.md#13-streaming-browser-drm-compatibility) | Unverified / Restricted — Ready for contributors | `P2` |
| Safety & QA | [Transactional install & rollback](docs/CONTRIBUTION_BOARD.md#14-installer-transactional-install-and-rollback) · [Hardware test matrix & CI](docs/CONTRIBUTION_BOARD.md#15-qa-hardware-test-matrix-and-ci) | In progress / Needs validation | `P0` |
| UX & Inclusion | [Accessibility and translations](docs/CONTRIBUTION_BOARD.md#16-ux-accessibility-and-translations) | Backlog — Good first issue | `P2` |

### How to Contribute (Human-First, 3 Steps)

1. **Pick an issue** from [docs/CONTRIBUTION_BOARD.md](docs/CONTRIBUTION_BOARD.md) or [GitHub Issues](https://github.com/nissifield/NextGen_plasmabigscreen/issues) (or file a [Compatibility Report](https://github.com/nissifield/NextGen_plasmabigscreen/issues/new?template=compatibility-report.yml)).
2. **Test and modify safely on your machine** using `--dry-run`, isolated temporary `$HOME` runs, unit/fixture tests, and sanitized diagnostics (`tv-display-mode diagnose`, `tv-remote-keymap.py --diagnose`).
3. **Submit a Pull Request with honest evidence** separating what was tested on real hardware vs. simulated or untested, plus rollback outcome.

### Optional: Contribute Using an AI Coding Assistant

**AI assistants are completely optional.** If you choose to use an AI coding assistant, **you remain accountable** for reviewing every command, diff, test result, compatibility claim, and privacy redaction before running or submitting anything.

Copy and paste this prompt into your AI assistant:

```text
Act as my careful open-source contribution assistant for https://github.com/nissifield/NextGen_plasmabigscreen. Read the repository's CONTRIBUTING.md, CONTRIBUTOR_AI_PROMPT.md, compatibility matrix and the GitHub issue I select. Inventory my distro, KDE/Wayland session, GPU/driver, TV/connector and remote; do not assume I use Bazzite or Intel. Propose a narrowly scoped, reversible change, get my approval before installation/privileged commands, implement tests and documentation, run available checks, and prepare a PR with honest hardware evidence. Never overwrite unrelated settings, leak device/user secrets or claim untested compatibility. Do not merge without maintainer review.
```

Key contributor resources:
- [Contributing Guide (Human-First)](CONTRIBUTING.md) · [Contributor AI Prompt (Optional)](CONTRIBUTOR_AI_PROMPT.md)
- [Hardware & Distro Compatibility Matrix](docs/COMPATIBILITY.md) · [Architecture & Boundaries](docs/ARCHITECTURE.md) · [Contribution Board](docs/CONTRIBUTION_BOARD.md)
- [Issue Templates](https://github.com/nissifield/NextGen_plasmabigscreen/issues/new/choose) ([Compatibility Report](.github/ISSUE_TEMPLATE/compatibility-report.yml), [Feature Request](.github/ISSUE_TEMPLATE/feature-request.yml)) · [PR Template](.github/PULL_REQUEST_TEMPLATE.md) · [License (GPL-2.0-or-later)](LICENSE)

---

## Quick Start

### 1. Preview Installation (`--dry-run`)
```bash
git clone https://github.com/nissifield/NextGen_plasmabigscreen.git
cd NextGen_plasmabigscreen
./install.sh --help
./install.sh --dry-run
```

### 2. Install into `$HOME`
```bash
# Core Plasma Bigscreen UI, display daemon, Movie Mode toggle, Stremio shim & desktop files:
./install.sh

# Optionally include baseline hardware presets (Intel VA-API, WirePlumber HDMI audio, Gamescope & PowerDevil):
# Review first — do not pass blindly on non-Intel/non-baseline hardware.
./install.sh --with-hardware-presets
```

### 3. Configure Your Display Connector (If Not `DP-1`)
Find your connected display output name:
```bash
kscreen-doctor -o
```
Edit `~/.config/tv-display-mode/config.json` and update `"output"` (e.g. `"HDMI-A-1"` or `"DP-1"`), `"mode_4k"`, and `"mode_1080p"`, then restart the service and verify:
```bash
systemctl --user restart tv-display-mode.service
~/.local/bin/tv-display-mode status
~/.local/bin/tv-display-mode diagnose
```

### 4. Switch Between Bigscreen & Desktop
```bash
~/.local/bin/tv-session-switch.sh bigscreen
~/.local/bin/tv-session-switch.sh desktop
```

### 5. Roll Back Cleanly
```bash
./rollback-tv-setup.sh
```

---

## Repository Structure

```text
NextGen_plasmabigscreen/
├── .github/                                 # Issue templates, PR template & GitHub Actions CI
├── .gitignore
├── LICENSE                                  # GPL-2.0-or-later
├── README.md
├── CONTRIBUTING.md                          # Human-first contribution guide (AI optional)
├── CONTRIBUTOR_AI_PROMPT.md                 # Optional companion AI prompt for contributors
├── SETUP_PROMPT.md                          # Single-shot AI agent setup & hardware-adaptation prompt
├── assets/
│   └── banner.jpg                           # Repository hero banner graphic
├── install.sh                               # Idempotent user-space installer (--help, --dry-run)
├── rollback-tv-setup.sh                     # Manifest-aware user-space rollback script
├── bin/
│   ├── nextgen_platform.py                  # GPU/DRM/CEC probing & data-driven remote profiles
│   ├── nextgen-manifest.py                  # Ownership manifest, backups & Flatpak INI patcher
│   ├── tv-display-mode                      # Display switcher + Steam priority + MPRIS auto-pause daemon
│   ├── tv-movie-mode-toggle                 # Movie Mode (4K) <-> 1080p toggle with OSD/banner
│   ├── tv-session-switch.sh                 # Desktop <-> Plasma Bigscreen user-space switcher
│   ├── tv-remote-keymap.py                  # User-space USB/RF remote evdev keymap + CEC helper
│   ├── steamos-add-to-steam                 # Plasma 6 MIME fix for adding wrappers to Steam
│   ├── tv-display-mode.sh                   # Manual kscreen-doctor display helper
│   └── streaming_scripts/                   # Steam Non-Steam wrapper scripts
├── kwin/
│   └── tv-display-mode.js                   # KWin 6 Wayland window state & fullscreen reporter
├── stremio/
│   ├── stremio_mpv_shim.c                   # LD_PRELOAD libmpv shim enabling mpv.conf & hwdec=auto-safe
│   └── mpv.conf
├── mpv/
│   └── tv-display-mode.lua                  # Optional mpv playback resolution hook
├── plasma/
│   └── plasmoids/org.kde.bigscreen.homescreen/  # Customized Android TV homescreen plasmoid
├── systemd/user/
│   ├── tv-display-mode.service
│   ├── tv-remote-keymap.service
│   └── plasma-bigscreen-inputhandler.service
├── configs/                                 # Sanitized config files & @HOME@ templates
├── desktop/                                 # .desktop launchers & @HOME@ templates
├── scripts/
│   └── seed-github-board.sh                 # Maintainer gh CLI script (--dry-run default) to seed board
├── tests/                                   # Unit & fixture test suite
└── docs/                                    # Architecture, Compatibility Matrix, Contribution Board & guides
```

---

## Running Tests & Verification

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile bin/tv-display-mode bin/tv-movie-mode-toggle bin/tv-remote-keymap.py bin/nextgen_platform.py bin/nextgen-manifest.py tests/*.py
gcc -fsyntax-only -Wall -Wextra -fPIC -O2 stremio/stremio_mpv_shim.c
bash -n install.sh rollback-tv-setup.sh bin/tv-session-switch.sh bin/tv-display-mode.sh configs/bashrc.d/tv-display-mode.sh scripts/seed-github-board.sh
```

---

## Documentation & License

- [Architecture & Subsystem Boundaries](docs/ARCHITECTURE.md)
- [Hardware, Distro & App Compatibility Matrix](docs/COMPATIBILITY.md)
- [NextGen Compatibility & Contributions Board](docs/CONTRIBUTION_BOARD.md)
- [Contributing Guide (Human-First)](CONTRIBUTING.md) · [Contributor AI Prompt (Optional)](CONTRIBUTOR_AI_PROMPT.md)
- [AI Agent Self-Service Setup Prompt](SETUP_PROMPT.md)
- [01 — Architecture & UI Design](docs/01-Architecture-and-UI-Design.md)
- [02 — Streaming Apps Guide](docs/02-Streaming-Apps-Guide.md)
- [03 — Remote Controls & HDMI-CEC](docs/03-Remote-Controls-and-HDMI-CEC.md)
- [04 — Operations & Rollback Runbook](docs/04-Operations-and-Rollback-Runbook.md)
- [05 — Complete Setup How-To Guide](docs/05-Complete-Setup-HowTo.md)
- [06 — AI Agent & Multi-Model Prompt Library](docs/06-AI-Agent-Prompts.md)
- Licensed under **GPL-2.0-or-later** (see [LICENSE](LICENSE)) in compliance with KDE Plasma Bigscreen QML derivatives.

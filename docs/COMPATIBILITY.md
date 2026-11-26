# Hardware, Distro & App Compatibility Matrix

This document tracks **honest, evidence-backed compatibility** for NextGen Plasma Bigscreen.

- **Officially tested:** Reproducibly tested end-to-end on real TV hardware by a maintainer, including install, playback, navigation, and rollback.
- **Community-tested:** Verified on real hardware by a contributor with sanitized diagnostics and reproducible evidence in a Compatibility Report or PR.
- **Experimental:** Partial adapter/configuration support exists or only simulated/unit tests have run; expect rough edges and verify rollback first.
- **Untested / Community Validation Needed:** Not yet verified on real hardware. Do **not** assume it works out of the box.

> **Important policy on browser DRM & commercial streaming:** Working Linux VA-API hardware video decoding does **not** guarantee Full HD (1080p) or 4K playback, HDR, or HDCP handshakes on commercial DRM streaming services (such as Netflix, Disney+, or Prime Video) in Linux browsers. NextGen Plasma Bigscreen does **not** support or provide DRM circumvention.


## Automated CI vs. Manual Hardware Validation

GitHub Actions runs on a Linux software runner. It validates Python syntax and unit tests, synthetic platform fixtures, Bash syntax, ShellCheck, C syntax and linking for the Stremio shim, and internal Markdown links and heading anchors.

The test suite uses synthetic or mocked inputs for multi-GPU and multi-output discovery, VA-API output, CEC adapters, remote profiles, and installation and rollback under temporary HOME directories. These tests validate parsing, decision logic, and user-space safety. They do not prove compatibility with physical GPUs, displays, HDMI-CEC devices, remotes, or any distribution.

Real hardware validation remains manual. Contributors are requested to submit anonymized real-world `kscreen-doctor -j`, `vainfo`, and `cec-ctl` captures, particularly from AMD and NVIDIA systems and mutable distributions. Redact usernames, hostnames, serials, MAC addresses, tokens, private URLs, and other identifying data before submitting captures.

Do not promote a platform or device from Experimental / Untested based solely on CI or synthetic fixtures. Use the manual hardware acceptance checklist below when reporting hardware compatibility.

---

## 1. Platform & Hardware Support Summary

| Platform / Hardware Category | Current Support Tier | Notes |
| :--- | :--- | :--- |
| **Bazzite (`bazzite-deck:stable`, Fedora 45 Kinoite atomic) + KDE Plasma 6 Wayland** | **Officially tested** | Primary baseline; verified on real TV hardware (`2026-11-22`). |
| **Fedora Kinoite (Atomic) + KDE Plasma 6 Wayland** | **Officially tested (baseline family)** | Same `rpm-ostree` / KDE Plasma 6 Wayland base as Bazzite; validate non-Bazzite Steam path (`/usr/bin/steam` or Flatpak). |
| **Fedora KDE Spin (Mutable `dnf`)** | **Untested / Community Validation Needed** | Expected to work with `plasma-bigscreen` from Fedora repos; needs end-to-end hardware report. |
| **Ubuntu / Kubuntu + KDE Plasma 6 Wayland** | **Untested / Community Validation Needed** | Plasma 6 releases only; Plasma 5 & X11 are unsupported. |
| **Debian + KDE Plasma 6 Wayland** | **Untested / Community Validation Needed** | Testing/Trixie+ with Plasma 6 Wayland only. |
| **Arch Linux / CachyOS / EndeavourOS + KDE Plasma 6 Wayland** | **Untested / Community Validation Needed** | Needs verification of `plasma-bigscreen` package paths and Flatpak/native portals. |
| **openSUSE Tumbleweed / Kalpa + KDE Plasma 6 Wayland** | **Untested / Community Validation Needed** | Package name is typically `plasma6-bigscreen`; needs hardware validation. |
| **Intel Gen 9.5 (`i915` / UHD 630 / `iHD`)** | **Officially tested** | H.264, HEVC 10-bit, VP9 10-bit VA-API verified; no hardware AV1 on Gen 9.5. |
| **Intel Legacy (`i965`) / Modern Intel (Iris Xe, Arc / `xe`)** | **Untested / Community Validation Needed** | Needs `vainfo` + VacuumTube/Stremio/Jellyfin live decode verification. |
| **AMD Radeon (`amdgpu` / `radeonsi` VA-API)** | **Untested / Community Validation Needed** | Must **not** set `LIBVA_DRIVER_NAME=iHD`; needs real-TV VA-API & 4K@60 report. |
| **NVIDIA (Proprietary / NVDEC / optional `nvidia-vaapi-driver`)** | **Untested / Community Validation Needed** | Wayland/GBM/VA-API bridge varies by driver series; needs dedicated testing. |
| **4K@30 + 1080p@60 SDR (`DP-1` passive/active DP-to-HDMI)** | **Officially tested** | Baseline TV mode policy with Steam 1080p@60 priority & on-demand Movie Mode. |
| **4K@60 / 4K@120, HDR, VRR, Multi-Monitor** | **Untested / Community Validation Needed** | Needs EDID, `kscreen-doctor -j`, and KWin Wayland HDR/VRR testing. |
| **XING WEI 2.4G USB Remote (`620a:0407`) + tunneled `cec-DP-*` isolation** | **Officially tested** | Verified via `tv-remote-keymap.py` + `bwrap` `/dev/cec0` isolation. |
| **Native / USB HDMI-CEC (e.g., Pulse-Eight) & Other Bluetooth/RF Remotes** | **Untested / Community Validation Needed** | Needs real-device scancode/CEC captures; see [Contribution Board](CONTRIBUTION_BOARD.md). |
| **KDE Plasma 5, X11 sessions, non-KDE desktops** | **Unsupported** | Out of scope; KWin 6 Wayland APIs and Plasma 6 Bigscreen are required. |

---

## 2. Verified Baseline Matrix (Real Hardware Evidence)

| Distro/Version | Atomic/Mutable | Desktop/Session | GPU/Driver | Display/Connector/Modes | Remote/CEC | App/Version | Navigation | Tested Video Res/Codecs | Hardware Decode | Playback Restrictions | Test Date | Reporter |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Bazzite 45 (`bazzite-deck:stable`, Fedora 45 base), Kernel `7.3.4` | Atomic (`rpm-ostree` / Kinoite) | KDE Plasma `6.8.3`, Plasma Bigscreen `6.8.3`, Qt `6.11.2` (Wayland) | Intel Core i5-9500T, Intel UHD Graphics 630 (`i915`, Mesa `26.2.7`, Intel `iHD` `26.4.0`) | `DP-1` (TCL Beyond TV): `3840x2160@30` max native, `1920x1080@60`; no HDR, no VRR | XING WEI 2.4G USB (`620a:0407`) + tunneled `/dev/cec0` (`cec-DP-1`) isolated via `bwrap` | **Jellyfin Desktop** `2.0.0` (Flatpak) | Remote D-Pad/OK/Back + Controller (`--fullscreen --tv`) | Up to 4K (`H.264`, `HEVC 10-bit`, `VP9 10-bit`); no HW `AV1` on Gen 9.5 | **Verified** (`iHD` VA-API) | Local/self-hosted media; no DRM | 2026-11-22 | Maintainer baseline |
| Bazzite 45 (`bazzite-deck:stable`), Kernel `7.3.4` | Atomic (`rpm-ostree`) | KDE Plasma `6.8.3` / Bigscreen `6.8.3` / Qt `6.11.2` (Wayland) | Intel UHD Graphics 630 (`i915`, Mesa `26.2.7`, `iHD` `26.4.0`) | `DP-1` (TCL Beyond TV, 4K@30 + 1080p@60, SDR) | XING WEI `620a:0407` + `cec-DP-1` isolated | **Stremio** `1.3.0` (Flatpak + `stremio-mpv-shim.so`) | Remote + Controller (`gamepadSupport` + `AutoSuppressInput=true`); KWin initial fullscreen | Up to 4K (`H.264`, `HEVC 10-bit`, `VP9 10-bit`); no HW `AV1` | **Verified** (`iHD` VA-API via `stremio_mpv_shim.c`) | Depends on user add-ons/sources; shim requires `gcc`/`cc` at build time | 2026-11-22 | Maintainer baseline |
| Bazzite 45 (`bazzite-deck:stable`), Kernel `7.3.4` | Atomic (`rpm-ostree`) | KDE Plasma `6.8.3` / Bigscreen `6.8.3` / Qt `6.11.2` (Wayland) | Intel UHD Graphics 630 (`i915`, Mesa `26.2.7`, `iHD` `26.4.0`) | `DP-1` (TCL Beyond TV, 4K@30 + 1080p@60, SDR) | XING WEI `620a:0407` + `cec-DP-1` isolated | **VacuumTube** `2.1.1` (Flatpak, YouTube TV Leanback) | Remote D-Pad/OK/Back + Controller | Up to 4K (`VP9` / `H.264`); `AV1` falls back to software on Gen 9.5 | **Verified** (`iHD` VA-API EGL zero-copy, `--disable-features=Vulkan`) | YouTube Leanback web wrapper; no commercial Widevine DRM | 2026-11-22 | Maintainer baseline |
| Bazzite 45 (`bazzite-deck:stable`), Kernel `7.3.4` | Atomic (`rpm-ostree`) | KDE Plasma `6.8.3` / Bigscreen `6.8.3` / Qt `6.11.2` (Wayland) | Intel UHD Graphics 630 (`i915`, Mesa `26.2.7`, `iHD` `26.4.0`) | `DP-1` (TCL Beyond TV, 4K@30 + 1080p@60, SDR) | XING WEI `620a:0407` + `cec-DP-1` isolated | **Haruna** `1.9.1` (Flatpak) | Keyboard / Remote basic playback controls | Local files (`H.264`, `HEVC 10-bit`, `VP9 10-bit`); no HW `AV1` | **Verified** (`iHD` VA-API, `HardwareDecoding=vaapi`) | Local media playback only | 2026-11-22 | Maintainer baseline |
| Bazzite 45 (`bazzite-deck:stable`), Kernel `7.3.4` | Atomic (`rpm-ostree`) | KDE Plasma `6.8.3` / Bigscreen `6.8.3` / Qt `6.11.2` (Wayland) | Intel UHD Graphics 630 (`i915`, Mesa `26.2.7`, `iHD` `26.4.0`) | `DP-1` (locked to `1920x1080@60` via `steam_priority`) | Gamepad (`AutoSuppressInput=true` avoids double input) + `cec-DP-1` isolated | **Steam** `1.0.0.87` (Native `/usr/bin/bazzite-steam`) | Full controller navigation in Steam Big Picture | N/A (gaming UI; forces `1080p@60`) | N/A | Non-Bazzite distros must use `/usr/bin/steam` or Flatpak Steam | 2026-11-22 | Maintainer baseline |
| Bazzite 45 (`bazzite-deck:stable`), Kernel `7.3.4` | Atomic (`rpm-ostree`) | KDE Plasma `6.8.3` / Bigscreen `6.8.3` / Qt `6.11.2` (Wayland) | Intel UHD Graphics 630 (`i915`, Mesa `26.2.7`, `iHD` `26.4.0`) | `DP-1` (TCL Beyond TV, 4K@30 + 1080p@60, SDR) | Air-mouse / keyboard | **Firefox** (Flatpak) | Pointer / keyboard (not 10-foot native) | Standard web video (`H.264`/`VP9`) | **Partial** (`iHD` VA-API configured; DRM-protected playback **Unverified**) | **Unverified / Restricted** for Widevine DRM services | 2026-11-22 | Maintainer baseline |
| Any Linux + Plasma 6 Wayland | Atomic or Mutable | KDE Plasma 6 Wayland | Any GPU | Any TV/Monitor | Any | **Netflix, Disney+, Prime Video & other Widevine/DRM browser services** | Browser-dependent (typically requires pointer/air-mouse) | **Unverified** | **Unverified / Restricted** — VA-API decode does **not** guarantee 1080p/4K DRM or HDCP | Linux browsers typically receive Widevine L3 (often capped at 720p/SD or restricted audio/HDR); NextGen does **not** support DRM circumvention | N/A | Policy notice |

### Community-Validated Entries (Add via Compatibility Report PR)

| Distro/Version | Atomic/Mutable | Desktop/Session | GPU/Driver | Display/Connector/Modes | Remote/CEC | App/Version | Navigation | Tested Video Res/Codecs | Hardware Decode | Playback Restrictions | Test Date | Reporter |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| *Fedora KDE Spin (Mutable)* | Mutable | Plasma 6 Wayland | *Untested* | *Untested* | *Untested* | *Untested* | *Untested* | *Untested* | *Untested* | *Community validation needed* | — | — |
| *Ubuntu / Kubuntu KDE* | Mutable | Plasma 6 Wayland | *Untested* | *Untested* | *Untested* | *Untested* | *Untested* | *Untested* | *Untested* | *Community validation needed* | — | — |
| *Debian KDE* | Mutable | Plasma 6 Wayland | *Untested* | *Untested* | *Untested* | *Untested* | *Untested* | *Untested* | *Untested* | *Community validation needed* | — | — |
| *Arch Linux KDE* | Mutable | Plasma 6 Wayland | *Untested* | *Untested* | *Untested* | *Untested* | *Untested* | *Untested* | *Untested* | *Community validation needed* | — | — |
| *openSUSE Tumbleweed KDE* | Mutable / Transactional | Plasma 6 Wayland | *Untested* | *Untested* | *Untested* | *Untested* | *Untested* | *Untested* | *Untested* | *Community validation needed* | — | — |
| *AMD Radeon (`radeonsi`)* | Any | Plasma 6 Wayland | AMD AMDGPU + Mesa | *Untested* | *Untested* | *Untested* | *Untested* | *Untested* | *Untested* | *Community validation needed* | — | — |
| *NVIDIA Proprietary* | Any | Plasma 6 Wayland | NVIDIA + NVDEC / `nvidia-vaapi-driver` | *Untested* | *Untested* | *Untested* | *Untested* | *Untested* | *Untested* | *Community validation needed* | — | — |
| *Intel Legacy (`i965`) / New (Iris Xe, Arc)* | Any | Plasma 6 Wayland | Intel `i965` / `iHD` / `xe` | *Untested* | *Untested* | *Untested* | *Untested* | *Untested* | *Untested* | *Community validation needed* | — | — |

---

## 3. Manual Hardware Acceptance Checklist

Use this checklist before marking a platform, GPU, display mode, or remote as **Community-tested** or **Officially tested**:

### 1. Pre-Flight & Dry-Run
- [ ] Confirmed KDE Plasma 6 Wayland session (`$XDG_SESSION_TYPE=wayland`, `plasmashell --version`).
- [ ] Recorded `kscreen-doctor -o`, `lspci -k | grep -A3 -iE 'vga|display|3d'`, and `vainfo` (if installed).
- [ ] Ran `./install.sh --dry-run` and verified every planned path stays inside `$HOME`.
- [ ] Confirmed existing unrelated configs (`powerdevilrc`, `kwinrulesrc`, existing Flatpak overrides) are preserved or backed up before modification.

### 2. Boot / Login & Session Switching
- [ ] Switching to Bigscreen (`~/.local/bin/tv-session-switch.sh bigscreen`) loads the Android TV homescreen without QML errors in `journalctl --user -u plasma-plasmashell.service`.
- [ ] Returning to Desktop (`~/.local/bin/tv-session-switch.sh desktop`) cleanly restores standard KDE Plasma Desktop and stops `plasma-bigscreen-inputhandler.service`.
- [ ] If autostart is enabled, fresh login lands cleanly in Plasma Bigscreen with working audio and display output.

### 3. Remote & Controller Navigation
- [ ] D-Pad / Arrow keys navigate top pill tabs (`For You`, `Watch Now`, `Apps`, `Games`) and horizontal rows without focus traps.
- [ ] Center `OK` / `Enter` launches focused items; `Hold OK` opens the app context menu (`Open / Resume`, `Pin / Remove`, `Move`, `Force Stop`).
- [ ] `Back` / `Escape` closes modals and returns to the previous view cleanly.
- [ ] Gamepad navigation works on the Homescreen **without** double-input inside Steam Big Picture or controller-enabled apps (`AutoSuppressInput=true`).
- [ ] Remote power/standby behavior behaves as expected (and does not unexpectedly power off/suspend if DPMS toggle was configured).
- [ ] If `/dev/cec0` is a tunneled `cec-DP-*` device, confirmed no repeated DP-AUX timeout stalls in `journalctl` / `dmesg`.

### 4. App Launch & Return Home
- [ ] Each tested app launches fullscreen (or expected TV mode) from Bigscreen favorites/rows without hanging on `StartupFeedbackWindow`.
- [ ] Returning to Bigscreen Home or switching to another app automatically pauses background playing media via MPRIS (`auto_pause_background_media: true`).
- [ ] Refocusing a paused app does **not** unexpectedly auto-resume playback.
- [ ] Transient OSDs, notifications, and Movie Mode toast do **not** falsely pause active playback.

### 5. Display Mode & Steam Priority
- [ ] `~/.local/bin/tv-display-mode status` reports `Daemon: running` and matches the real connected output from `kscreen-doctor -o`.
- [ ] `busctl --user call org.kde.KWin /Scripting org.kde.kwin.Scripting isScriptLoaded s tv-display-mode` returns `b true`.
- [ ] Toggling Movie Mode (`~/.local/bin/tv-movie-mode-toggle`) switches cleanly between configured 4K and 1080p modes with OSD/toast feedback and zero black-screen hang.
- [ ] Launching Steam Big Picture or a Steam game immediately forces `1080p` (`steam_priority`), even if Movie Mode was active.

### 6. Media & Hardware Decode Verification
- [ ] Verified actual hardware decoding during playback (not just config flags) using `vainfo`, GPU utilization (`intel_gpu_top`, `radeontop`, `nvidia-smi`), or `/proc/<pid>/maps` & app logs (`iHD_drv_video.so` / `radeonsi_drv_video.so` / NVDEC).
- [ ] Recorded exact tested codecs/resolutions (`H.264`, `HEVC`, `VP9`, `AV1`) and noted any software fallbacks or playback restrictions honestly.

### 7. Rollback & Recovery
- [ ] Ran `./rollback-tv-setup.sh --dry-run` (or inspected rollback plan) and executed `./rollback-tv-setup.sh`.
- [ ] Confirmed user services are disabled, KWin script is unloaded, Plasma Desktop shell is restored, and pre-existing user configs / unrelated Flatpak overrides remain intact.

---

## 4. Sanitized Diagnostics Collection Guide

Before filing a Compatibility Report or PR, collect diagnostics using the built-in diagnostic commands:

```bash
# 1. Display, session, GPU, KWin, and policy diagnostics
~/.local/bin/tv-display-mode diagnose

# 2. Remote input device, profile match, and CEC adapter diagnostics
~/.local/bin/tv-remote-keymap.py --diagnose

# 3. Core hardware & session context (read-only)
cat /etc/os-release
uname -r
plasmashell --version
echo "XDG_SESSION_TYPE=$XDG_SESSION_TYPE WAYLAND_DISPLAY=$WAYLAND_DISPLAY"
kscreen-doctor -o
lspci -k | grep -A3 -iE 'vga|display|3d'
vainfo 2>&1 | head -n 40
flatpak list --app --columns=application,version
```

### Privacy & Redaction Checklist (Required Before Posting)

Always review your diagnostic output before pasting it into a public GitHub issue or PR and **redact**:
- Personal usernames, home directory names (replace `/home/<you>` with `$HOME`), hostnames, and local network IPs/hostnames (e.g., Jellyfin server URLs).
- Monitor/TV serial numbers from EDID dumps, Bluetooth/Wi-Fi MAC addresses, and USB device serial strings.
- API keys, auth tokens, Steam IDs, account emails, media library titles/file paths, and private server credentials.

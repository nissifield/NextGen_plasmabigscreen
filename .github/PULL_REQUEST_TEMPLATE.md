## Linked Issue

Closes #<!-- issue number, or N/A with brief context -->

## Problem

<!-- What issue, platform gap, bug, or UX improvement does this PR address? -->

## Fix / Summary of Changes

<!-- Describe the changes cleanly and note which layer(s) are touched:
     TV Experience / TV Services / Platform Adapters / Docs & QA -->

## Environment & Hardware Details (Sanitized)

- **Distro & Version:** <!-- e.g., Fedora 43 KDE Spin / Bazzite 45 / Arch Linux / N/A (code/docs only) -->
- **Atomic / Mutable:** <!-- Atomic / Mutable / N/A -->
- **KDE Plasma / Wayland / Kernel:** <!-- e.g., Plasma 6.8.3 Wayland, Kernel 7.3.4 -->
- **GPU & Driver:** <!-- e.g., AMD Radeon RX 7600 (amdgpu / Mesa radeonsi) -->
- **Display / Connector / Modes:** <!-- e.g., HDMI-A-1, 3840x2160@60 + 1920x1080@60 -->
- **Remote / CEC / Controller:** <!-- e.g., XING WEI 620a:0407 / none -->

## Evidence Classification (Be Honest & Specific)

Explicitly separate what was verified vs. not verified:

- **Tested on real hardware:**
  - <!-- e.g., Verified live Movie Mode toggle and MPRIS auto-pause on HDMI-A-1 -->
- **Simulated / unit-tested:**
  - <!-- e.g., Tested AMD/NVIDIA GPU overrides and rollback in temporary HOME with unit tests -->
- **Inferred / not yet hardware-tested:**
  - <!-- e.g., NVIDIA Wayland explicit-sync behavior inferred from fixture only; needs real NVIDIA hardware test -->
- **Untested:**
  - <!-- e.g., 4K@120 / HDR / Pulse-Eight CEC not tested in this PR -->

## Rollback & Compatibility Notes

- **Rollback tested?** <!-- Yes (isolated temp HOME / real host) / No / N/A -->
- **Backward compatibility / migration notes:** <!-- Does this preserve existing user configs, powerdevilrc/kwinrulesrc, and unrelated Flatpak overrides? -->
- **Compatibility matrix updated?** <!-- Yes (`docs/COMPATIBILITY.md`) / Not applicable -->

## Checklist

- [ ] Changes stay strictly in user-space (`$HOME`); no `/usr` or `/etc` modifications and no silent privileged commands.
- [ ] Unit/fixture tests pass: `python3 -m unittest discover -s tests -v`
- [ ] Python & shell syntax checks pass (`python3 -m py_compile`, `bash -n`, and `shellcheck` if available).
- [ ] C syntax check passes if `stremio/stremio_mpv_shim.c` was touched (`gcc -fsyntax-only -Wall -Wextra -fPIC -O2 stremio/stremio_mpv_shim.c`).
- [ ] GPL-2.0-or-later license and upstream KDE SPDX headers are preserved on any modified QML files.
- [ ] No secrets, tokens, serial numbers, MAC addresses, usernames, or private server URLs are included.
- [ ] If an AI assistant was used, I personally reviewed every command, diff, test result, and compatibility claim.

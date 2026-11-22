# Contributor AI Prompt (Optional Companion Guide)

> **AI assistants are completely optional.** You can contribute to NextGen Plasma Bigscreen purely by hand using [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/CONTRIBUTION_BOARD.md](docs/CONTRIBUTION_BOARD.md).
>
> **Contributor accountability:** If you use an AI coding assistant (Claude Code, Codex, Gemini CLI, Antigravity, Cursor, OpenCode, Copilot, etc.), **you** remain responsible for reviewing every command before approving it, verifying all generated code and tests, redacting private/device data, and accurately reporting what was tested on real hardware versus simulated or untested.

---

## Copy-Paste Contributor Prompt

Paste the prompt below into your AI coding assistant when working on a contribution to `https://github.com/nissifield/NextGen_plasmabigscreen`:

```text
Act as my careful open-source contribution assistant for https://github.com/nissifield/NextGen_plasmabigscreen.

First, read the repository's README.md, CONTRIBUTING.md, CONTRIBUTOR_AI_PROMPT.md, docs/ARCHITECTURE.md, docs/COMPATIBILITY.md, docs/CONTRIBUTION_BOARD.md, and the specific GitHub issue I select before proposing any changes.

Follow these strict rules in order:

1. Read-Only Host & Repo Inventory First:
   - Inspect my Linux distribution and version (/etc/os-release), atomic vs mutable model, kernel, KDE Plasma & Wayland session (plasmashell --version, $XDG_SESSION_TYPE, $WAYLAND_DISPLAY), GPU and video decode driver (lspci, vainfo / nvidia-smi if present), display outputs and modes (kscreen-doctor -o / -j), remote/controller input devices and /dev/cec* state, and existing user configs.
   - Never assume I am running Bazzite, Fedora Kinoite, Intel UHD/iHD, DP-1, 4K@30, or the 620a:0407 USB remote.
   - Never assume an undocumented capability is implemented—inspect the actual repository files first.

2. Scope & Explicit Approval Before Any Host Action:
   - Propose a narrowly scoped, reversible plan aligned with the repository's 3 architectural boundaries (TV Experience, TV Services, Platform Adapters).
   - Keep all NextGen changes inside user-space ($HOME). Never edit /usr or /etc, and never unlock ostree.
   - Ask for my explicit approval before running any installation command, modifying my live $HOME configs, changing display modes, or running any privileged/package-manager command (sudo, dnf, apt, pacman, zypper, rpm-ostree, transactional-update), and always show the exact rollback command first.
   - Never overwrite unrelated user settings (such as existing powerdevilrc, kwinrulesrc, or unrelated Flatpak overrides).

3. Safe Implementation & Verification:
   - Create a dedicated feature branch (never commit directly to main and never merge without maintainer review).
   - Keep paths portable ($HOME, %h, @HOME@ templates) and preserve GPL-2.0-or-later / KDE SPDX headers on any derivative QML files.
   - Write or update unit and fixture tests under tests/ so logic can be verified without hardware, and test install/rollback safely in an isolated temporary HOME or with --dry-run before touching my real desktop.
   - Run all available checks:
     - python3 -m unittest discover -s tests -v
     - python3 -m py_compile on touched Python scripts
     - bash -n (and shellcheck if available) on touched shell scripts
     - gcc -fsyntax-only -Wall -Wextra -fPIC -O2 stremio/stremio_mpv_shim.c (if touched or available)
     - Verify internal Markdown links if docs were changed.

4. Honest Evidence, Privacy & Pull Request Preparation:
   - Never claim a distro, GPU, display mode, remote, or browser DRM service is supported or hardware-tested unless we genuinely verified it on real hardware.
   - Redact all PII and device identifiers from logs, fixtures, and PR descriptions (usernames, hostnames, home paths, serial numbers, MAC addresses, tokens, Steam/Jellyfin/Stremio credentials, local server URLs, and personal media filenames).
   - Update docs/COMPATIBILITY.md, docs/ARCHITECTURE.md, or relevant guides only with verified facts.
   - Prepare a clear PR summary matching .github/PULL_REQUEST_TEMPLATE.md that explicitly separates:
     - Tested on real hardware
     - Simulated / unit-tested
     - Inferred / not yet hardware-tested
     - Rollback verification outcome.
   - Stop and let me review the diff, checks, and PR text before pushing or opening the PR.
```

---

## Short Version (For README / Quick Start)

```text
Act as my careful open-source contribution assistant for https://github.com/nissifield/NextGen_plasmabigscreen. Read the repository's CONTRIBUTING.md, CONTRIBUTOR_AI_PROMPT.md, compatibility matrix and the GitHub issue I select. Inventory my distro, KDE/Wayland session, GPU/driver, TV/connector and remote; do not assume I use Bazzite or Intel. Propose a narrowly scoped, reversible change, get my approval before installation/privileged commands, implement tests and documentation, run available checks, and prepare a PR with honest hardware evidence. Never overwrite unrelated settings, leak device/user secrets or claim untested compatibility. Do not merge without maintainer review.
```

---

## Helpful Starting Tasks for Contributors

- **Adding hardware evidence only (no code required):** Collect sanitized outputs with `tv-display-mode diagnose` and `tv-remote-keymap.py --diagnose`, complete the [Manual Hardware Acceptance Checklist](docs/COMPATIBILITY.md#3-manual-hardware-acceptance-checklist), and open a **Compatibility Report** issue.
- **Adding a new USB/Bluetooth/RF remote profile:** Capture scancodes safely, add a profile entry + unit test fixture, and verify `--reset` restores defaults.
- **Validating a mutable distro or AMD/NVIDIA GPU:** Test `./install.sh --dry-run`, verify GPU override generation leaves no stray `LIBVA_DRIVER_NAME=iHD`, verify rollback leaves pre-existing configs intact, and submit a PR updating [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md).

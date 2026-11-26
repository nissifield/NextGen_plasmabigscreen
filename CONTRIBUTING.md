# Contributing to NextGen Plasma Bigscreen

Thank you for helping bring an Android TV / Google TV-class living-room experience to more Linux distributions, GPUs, displays, and remotes!

**AI coding assistants are completely optional.** This repository is designed for human contributors first—whether you are testing on an Ubuntu/Arch/Debian/openSUSE/Fedora KDE machine, adding an AMD or NVIDIA profile, capturing USB remote scancodes, improving accessibility, or writing documentation. If you *do* choose to use an AI coding assistant, see the companion [CONTRIBUTOR_AI_PROMPT.md](CONTRIBUTOR_AI_PROMPT.md); you remain fully responsible for reviewing all commands, code, evidence, and privacy before executing or submitting anything.

---

## 1. Where to Start

1. Check the **[Contribution Board](docs/CONTRIBUTION_BOARD.md)** and open **[GitHub Issues](https://github.com/nissifield/NextGen_plasmabigscreen/issues)** to find an unclaimed task matching your hardware or interests (look for `good first issue`, `help wanted`, or `needs-hardware-test`).
2. Check the **[Compatibility Matrix](docs/COMPATIBILITY.md)** to see what is already verified vs. what needs community hardware validation.
3. Read **[Architecture & Subsystem Boundaries](docs/ARCHITECTURE.md)** so your change lands in the right layer (**TV Experience**, **TV Services**, or **Platform Adapters**).
4. Comment on the relevant GitHub issue before starting large changes so contributors do not duplicate effort.

> You do **not** need Bazzite, Fedora Kinoite, or Intel hardware to contribute. Reports and adapters for mutable distros, AMD/NVIDIA/other Intel GPUs, 4K@60/120 displays, HDMI-CEC/Bluetooth/RF remotes, tests, accessibility, and docs are especially valuable.

---

## 2. How to Test Safely Without Endangering Your Host

NextGen Plasma Bigscreen is strictly **user-space-first (`$HOME`)**, and every contribution should preserve host safety:

1. **Start with read-only & fixture checks:**
   - Run unit tests and syntax checks in the repo without installing anything into your real `$HOME`.
   - Use mocked/fixture inputs (for example, saved `kscreen-doctor -j` JSON, `vainfo` text, `cec-ctl` output, or synthetic `/sys/class/input` trees) for unit tests.
2. **Test installer and rollback in an isolated temporary `$HOME`:**
   ```bash
   TEST_HOME="$(mktemp -d)"
   HOME="$TEST_HOME" ./install.sh --dry-run
   HOME="$TEST_HOME" ./install.sh --skip-services
   HOME="$TEST_HOME" ./rollback-tv-setup.sh
   rm -rf "$TEST_HOME"
   ```
3. **Preview before touching your live desktop:**
   - Always run `./install.sh --dry-run` before `./install.sh`.
   - Never blindly pass `--with-hardware-presets` on non-Intel/non-baseline machines.
   - Prefer testing live session/display changes in a VM, spare Linux user account, or with a verified `1920x1080@60` fallback mode and SSH access ready.
4. **Never require root for user-space changes:**
   - Do not modify `/usr` or `/etc`, and never unlock `ostree` on atomic distros.
   - Any system package requirement (such as `plasma-bigscreen`) must be documented with explicit distro install and rollback commands, never executed silently by `install.sh`.

---

## 3. Architecture & Coding Standards

- **Respect the three boundaries ([docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)):**
  - **TV Experience:** QML homescreen override, `.desktop` launchers, favorites, OSD/toast UI. Keep hardware/distro assumptions out of UI code.
  - **TV Services:** `bin/tv-display-mode`, `kwin/tv-display-mode.js`, `mpv/tv-display-mode.lua`, `bin/tv-remote-keymap.py`, `bin/tv-session-switch.sh`.
  - **Platform Adapters:** `bin/nextgen_platform.py`, `bin/nextgen-manifest.py`, hardware profiles, GPU/DRM/CEC probing, `stremio/stremio_mpv_shim.c`.
- **Keep paths portable:** Use `$HOME`, `%h`, `%t`, and `@HOME@` templates. Never commit hardcoded usernames, `/home/<user>` paths, or machine-specific connector/PCI IDs into default code paths.
- **Keep edits reversible:** Any new file or config key managed by `install.sh` must be tracked in the ownership manifest (`bin/nextgen-manifest.py`) and cleanly handled by `rollback-tv-setup.sh` without clobbering unrelated user settings.
- **No undocumented capability claims:** Do not mark a distro, GPU, display feature, DRM service, or remote as supported/tested unless you have real hardware evidence or clearly label it as **Experimental / Simulated / Untested**.
- **Privacy & secrets hygiene:** Never commit or paste personal tokens, SSH keys, Steam IDs, Jellyfin/Stremio credentials or server URLs, local SQLite databases, serial numbers, MAC addresses, or personal media library titles.

---

## 4. Required Verification Commands

Run these checks locally before opening a Pull Request. Run Linux-specific tests in a Linux environment (native Linux or WSL).

```bash
python3 -m unittest discover -s tests -v

python3 -m compileall -q . -x '(^|/)(\.git|\.venv)/'

mapfile -t sh_files < <(
  find . -type f \
    \( -name '*.sh' -o -path './bin/steamos-add-to-steam' -o -path './bin/streaming_scripts/*' \) \
    -not -path './.git/*' \
    -not -path './.venv/*' | sort
)
for f in "${sh_files[@]}"; do bash -n "$f"; done
sh -n ./bin/steamos-add-to-steam
shellcheck -S warning "${sh_files[@]}"

gcc -fsyntax-only -Wall -Wextra -fPIC -O2 stremio/stremio_mpv_shim.c
gcc -Wall -Wextra -fPIC -O2 -shared -o /tmp/stremio_mpv_shim.so stremio/stremio_mpv_shim.c -ldl
nm -D --defined-only /tmp/stremio_mpv_shim.so | grep -q ' mpv_initialize$'

if command -v desktop-file-validate >/dev/null 2>&1; then
  desktop-file-validate desktop/*.desktop
fi
```

> Note: Automated CI runs Python syntax checks, unit and fixture tests, Bash syntax checks, ShellCheck, C syntax and linking checks, and Markdown link/heading checks. CI does **not** run on real TV hardware—hardware behavior must still be verified and classified honestly in your PR description.

---

## 5. Licensing & KDE Attribution (GPL-2.0-or-later)

- This repository is licensed under **GPL-2.0-or-later** ([LICENSE](LICENSE)) to stay fully compatible with upstream KDE Plasma Bigscreen QML derivatives.
- When editing files under `plasma/plasmoids/org.kde.bigscreen.homescreen/`, **preserve all upstream KDE `SPDX-FileCopyrightText` and `SPDX-License-Identifier` headers**.
- Do not copy proprietary code, closed-source binaries, or incompatible-license snippets into the repository.

---

## 6. Pull Request Checklist

Before submitting your PR (using [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md)):
- [ ] Linked to a GitHub issue (or clearly describes the scoped problem/hardware report).
- [ ] Keeps changes focused, reversible, and inside `$HOME` user-space boundaries.
- [ ] Includes unit/fixture tests for new logic and passes all local checks above.
- [ ] Classifies evidence honestly (**Tested on hardware**, **Simulated / unit-tested**, **Inferred**, or **Untested**).
- [ ] Documents rollback impact and updates [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md) / [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) where relevant.
- [ ] Contains zero PII, secrets, device serials, or unrelated host config changes.

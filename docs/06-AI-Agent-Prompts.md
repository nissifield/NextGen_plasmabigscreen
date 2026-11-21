# 06 — AI Agent & Multi-Model Prompt Library

Use these copy-paste prompts with **any AI coding assistant or LLM** (Claude Code, Codex, Gemini CLI, Antigravity, Cursor, OpenCode, Copilot, or local coding models) to set up this repository on your hardware, customize the Plasma Bigscreen QML UI, extend `tv-display-mode`, or debug issues.

> **Looking for single-shot, end-to-end setup?**
> Use the canonical setup prompt in **[`SETUP_PROMPT.md`](../SETUP_PROMPT.md)** (raw URL: `https://raw.githubusercontent.com/nissifield/NextGen_plasmabigscreen/main/SETUP_PROMPT.md`):
>
> ```text
> Fetch and follow https://raw.githubusercontent.com/nissifield/NextGen_plasmabigscreen/main/SETUP_PROMPT.md to inspect my Linux machine, adapt NextGen_plasmabigscreen to my hardware, install it into $HOME, and verify it end-to-end.
> ```

---

## 1. Hardware Discovery & Compatibility Audit (Read-Only)

For a **read-only** hardware audit without installing anything yet, ask your agent to run **Phase 1 & Phase 2** of [`SETUP_PROMPT.md`](../SETUP_PROMPT.md):

```text
Read SETUP_PROMPT.md (or fetch https://raw.githubusercontent.com/nissifield/NextGen_plasmabigscreen/main/SETUP_PROMPT.md) and execute ONLY Phase 1 (Read-Only Discovery) and Phase 2 (Hardware Delta Summary). Do NOT install packages, edit any files, or change display modes yet.
```

---

## 2. Full Hardware Adaptation, Install & Verification

To clone, adapt configs for your TV connector/GPU/distro/remote, install declaratively into `$HOME`, and verify end-to-end, follow [`SETUP_PROMPT.md`](../SETUP_PROMPT.md) in full:

```text
Read and follow SETUP_PROMPT.md in this repository (Phases 1 through 4) to inspect my machine, confirm my hardware/app choices, adapt NextGen_plasmabigscreen to my setup, install into $HOME, and verify it end-to-end.
```

---

## 3. Customize the Android TV Plasma Bigscreen Homescreen (QML)

```text
Inspect `plasma/plasmoids/org.kde.bigscreen.homescreen/` (and the installed copy at `~/.local/share/plasma/plasmoids/org.kde.bigscreen.homescreen/`) before editing.

Important Plasma 6 Wayland constraints on this codebase:
- Never modify `/usr/share/plasma/plasmoids/org.kde.bigscreen.homescreen/`; work strictly in the user-space override.
- `FavsManager` reads `~/.config/bigscreen-favs` at plasmashell startup and has no live file watcher—changes to `~/.config/bigscreen-favs` require `systemctl --user restart plasma-plasmashell.service`.
- Clicking any favourite in `FavDelegate.qml` triggers `StartupFeedbackWindow.qml` unless handled specially; headless scripts must either be exempted in `FavDelegate.qml` or show a brief focus-taking Wayland window so the launch splash dismisses.
- Keep full D-Pad, keyboard (`Enter`/`Backspace`/`Escape`), and controller navigation intact across `HomeHeader.qml`, `HomeScreen.qml`, `LauncherHome.qml`, and `LauncherMenu.qml`.

Task: <describe the UI change you want, e.g., add a new category tab / change spotlight colors / add a new action tile>.
After editing, sync to `~/.local/share/plasma/plasmoids/`, restart `plasma-plasmashell.service`, and check `journalctl --user -u plasma-plasmashell.service` for any QML errors.
```

---

## 4. Extend `tv-display-mode` (Display Rules, Steam Detection & Auto-Pause)

```text
Read `bin/tv-display-mode`, `kwin/tv-display-mode.js`, `configs/tv-display-mode/config.json`, and `tests/test_tv_display_mode.py` in full before making changes.

Rules to preserve:
- Mode switching must resolve KWin/kscreen mode IDs dynamically via `kscreen-doctor -j` (avoiding duplicate mode-name collisions) and skip redundant switches when already on the target mode.
- Steam (`steam`, `steamwebhelper`, `gamescope`, `steam_app_*`, or Steam-ancestor child PIDs) must always take highest priority (`steam_priority` -> `1080p`).
- Background media auto-pause (`_maybe_auto_pause`) must only react to real `ReportKWinState` focus pushes (never `reason="fallback"` or `"init"`), must ignore OSDs/notifications/transient popups/Polkit/`tv-movie-mode-toggle`, must match Flatpaks across `xdg-dbus-proxy` PID boundaries (shared `app-flatpak-*.scope` cgroup, `DesktopEntry`, `Identity`), and must never auto-call `Play()`.

Task: <describe the rule or app you want to add/modify>.
Update `tests/test_tv_display_mode.py` with unit tests covering the new behavior, run `python3 -m py_compile` and `python3 tests/test_tv_display_mode.py`, and verify with `--dry-run` before restarting `tv-display-mode.service`.
```

---

## 5. Debug Hardware Video Acceleration (VA-API / Flatpak)

```text
Audit hardware video decoding end-to-end (do not assume config flags mean VA-API is actually working):

1. Host check: run `vainfo` and inspect `/dev/dri/renderD128` permissions.
2. Sandbox check: verify `flatpak override --user --show <app-id>` and test inside the Flatpak sandbox (`flatpak run --command=ffmpeg <app-id> ...` or `mpv --hwdec=auto-safe`).
3. Live process verification: while a video is playing or the app is open, inspect `/proc/<pid>/maps` and `/proc/<pid>/fd` for `iHD_drv_video.so` (or `radeonsi_drv_video.so`), `libva*.so`, `/dev/dri/renderD128`, and `/dmabuf`, plus app/journal logs:
   - Stremio: check `stremio/stremio_mpv_shim.c` (`LD_PRELOAD`), `config=yes`, `hwdec=auto-safe`, and `MPV_RENDER_PARAM_WL_DISPLAY` behavior.
   - VacuumTube: check `flags.txt` (`--disable-features=Vulkan`, `--use-webgpu-adapter=opengles`) and GPU process journal logs.
   - Jellyfin Desktop & Haruna: check `jellyfin-desktop.log` for `hwdec` property status and `haruna.conf`.

Report exact observed maps, logs, and any fallback to software decoding, then fix and restart only the affected Flatpaks.
```

---

## 6. Improve Remote & Controller Ergonomics

```text
Inspect the current input stack before changing bindings:
- `/proc/bus/input/devices` and `lsusb`
- `~/.local/bin/tv-remote-keymap.py` and `tv-remote-keymap.service`
- `~/.config/plasma-bigscreen-inputhandlerrc` and `plasma-bigscreen-inputhandler.service`
- `~/.config/kglobalshortcutsrc`

Task: <choose one:
  (a) Add a Steam Input per-app layout for non-Steam shortcut Stremio (mapping D-pad/Left Stick -> Arrows, A -> Enter, B -> Backspace, Right Stick -> Mouse) while keeping `AutoSuppressInput=true` and `gamepadSupport=false`, OR
  (b) Build a lightweight window-aware mapper (e.g., via KWin focus state + uinput / input-remapper) so Remote Exit sends Backspace in Stremio UI menus and Escape during active video playback, and media keys work inside focused apps.>

Verify no double-input occurs in Plasma Bigscreen, Stremio, or Steam, and keep CEC isolated if connected over a tunneled `cec-DP-*` adapter.
```

---

## 7. Multi-Agent Team Workflow Prompt (Researcher → Implementer → Verifier)

If you are using an agentic framework that supports parallel subagents or a multi-agent swarm (Antigravity Swarm, Claude Agent Teams, CrewAI, LangGraph, etc.), use this coordination prompt:

```text
Use a 3-role agent team to implement and verify <describe your new feature/fix> in NextGen_plasmabigscreen:

1. Researcher (read-only):
   - Inspect existing files in `NextGen_plasmabigscreen` and live system state (`kscreen-doctor -o`, `systemctl --user`, `flatpak ps`, KWin D-Bus, logs).
   - Identify exact file paths, constraints, edge cases, and test strategy. Hand off `[done]` findings to Implementer.

2. Implementer:
   - Wait for Researcher's findings, then implement clean, well-scoped edits.
   - If editing `NextGen_plasmabigscreen` for public GitHub release, keep paths portable (`$HOME`, `%h`, `%t`, `@HOME@` templates) and never commit secrets, tokens, SSH keys, Steam user IDs, Jellyfin/Stremio user hashes, or local SQLite DBs.
   - Add/update unit tests in `tests/test_tv_display_mode.py` and hand off `[done]` to Verifier.

3. Verifier:
   - Independently run syntax checks (`py_compile`, `bash -n`, `desktop-file-validate`, JSON/C compile checks), unit tests, `--dry-run` checks, and a secret/PII grep scan before signing off.
   - Verify live services remain healthy (`tv-display-mode.service`, `tv-remote-keymap.service`, `plasma-bigscreen-inputhandler.service`) and DP-1 ends in a safe working mode.
```

---

## 8. Quick Troubleshooting Prompt

```text
Something broke after a Plasma, Flatpak, or Bazzite OS update. Diagnose cleanly before changing anything:
1. Check `systemctl --user status tv-display-mode.service tv-remote-keymap.service plasma-bigscreen-inputhandler.service plasma-plasmashell.service`.
2. Check `~/.local/bin/tv-display-mode status` and `busctl --user call org.kde.KWin /Scripting org.kde.kwin.Scripting isScriptLoaded s tv-display-mode`.
3. Check recent user journal logs (`journalctl --user -b -n 100 --no-pager`) for KWin, Wayland, Flatpak, VA-API, or CEC errors.
4. Check `kscreen-doctor -o` and `/sys/class/drm/*/status`.

Identify the root cause, fix it minimally, and verify the display returns to `1920x1080@60` (or my configured default) with all services active.
```

#!/usr/bin/env bash
# Transactional user-space installer for NextGen Plasma Bigscreen
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST_TOOL="$REPO_DIR/bin/nextgen-manifest.py"

DRY_RUN=0
SKIP_SERVICES=0
WITH_HARDWARE_PRESETS=0
FORCE_CONFIGS=0
REPAIR=0
GPU_MODE="auto"

usage() {
    cat <<'EOF'
Usage: ./install.sh [OPTIONS]

Install NextGen Plasma Bigscreen customizations cleanly into $HOME (user-space only;
no root/sudo, /usr edits, or linger changes). Tracks every file and Flatpak override
in ~/.local/state/nextgen-plasmabigscreen/manifest.json with pre-edit backups.

Options:
  -n, --dry-run                Preview every planned action without modifying $HOME
      --repair, --reconcile    Recover an interrupted install or reconcile missing/drifted
                               NextGen-managed files without clobbering user backups
      --gpu <profile>          VA-API GPU profile: auto (default), intel-ihd, intel-i965,
                               amd, nvidia, or none
      --with-hardware-presets  Also install WirePlumber HDMI audio, Gamescope,
                               PowerDevil/KScreenLocker/KWin rules, and (Intel Gen8+ only)
                               90-intel-vaapi.conf (existing files are backed up first)
      --skip-services          Install files without reloading/starting systemd units
      --force                  Overwrite user-edited configs (always backs them up first)
  -h, --help                   Show this help text and exit
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        -n|--dry-run)
            DRY_RUN=1
            ;;
        --repair|--reconcile)
            REPAIR=1
            ;;
        --gpu)
            if [ $# -lt 2 ]; then
                echo "Error: --gpu requires a value (auto|intel-ihd|intel-i965|amd|nvidia|none)" >&2
                exit 1
            fi
            GPU_MODE="$2"
            shift
            ;;
        --gpu=*)
            GPU_MODE="${1#*=}"
            ;;
        --with-hardware-presets)
            WITH_HARDWARE_PRESETS=1
            ;;
        --skip-services)
            SKIP_SERVICES=1
            ;;
        --force)
            FORCE_CONFIGS=1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
    shift
done

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is required to run install.sh" >&2
    exit 1
fi

if [ ! -f "$MANIFEST_TOOL" ]; then
    echo "Error: manifest helper not found at $MANIFEST_TOOL" >&2
    exit 1
fi

# Resolve GPU profile (read-only)
GPU_PROFILE="none"
VAAPI_DRIVER=""
INSTALL_INTEL_VAAPI_CONF=0
GPU_INFO="$(python3 -B "$MANIFEST_TOOL" detect-gpu --gpu "$GPU_MODE" --shell)"
while IFS='=' read -r key val; do
    case "$key" in
        GPU_PROFILE) GPU_PROFILE="$val" ;;
        VAAPI_DRIVER) VAAPI_DRIVER="$val" ;;
        INSTALL_INTEL_VAAPI_CONF) INSTALL_INTEL_VAAPI_CONF="$val" ;;
    esac
done <<< "$GPU_INFO"

manifest_cmd() {
    local subcmd="$1"
    shift
    local extra=()
    [ "$DRY_RUN" -eq 1 ] && extra+=(--dry-run)
    python3 -B "$MANIFEST_TOOL" "$subcmd" "${extra[@]}" "$@"
}

run_cmd() {
    if [ "$DRY_RUN" -eq 1 ]; then
        printf '[dry-run] %s\n' "$*"
    else
        "$@"
    fi
}

install_file() {
    local src="$1"
    local dst="$2"
    local mode="${3:-0644}"
    shift 3 || true
    local flags=()
    [ "$FORCE_CONFIGS" -eq 1 ] && flags+=(--force)
    [ "$REPAIR" -eq 1 ] && flags+=(--repair)
    manifest_cmd install-file --src "$src" --dst "$dst" --mode "$mode" "${flags[@]}" "$@"
}

install_template() {
    local src="$1"
    local dst="$2"
    local mode="${3:-0644}"
    shift 3 || true
    local flags=()
    [ "$FORCE_CONFIGS" -eq 1 ] && flags+=(--force)
    [ "$REPAIR" -eq 1 ] && flags+=(--repair)
    manifest_cmd install-template --src "$src" --dst "$dst" --mode "$mode" "${flags[@]}" "$@"
}

echo "=== NextGen Plasma Bigscreen User-Space Installer ==="
echo "Repository: $REPO_DIR"
echo "Target HOME: $HOME"
echo "GPU Profile: $GPU_PROFILE (LIBVA_DRIVER_NAME=${VAAPI_DRIVER:-unset})"
[ "$DRY_RUN" -eq 1 ] && echo "Mode: DRY RUN (no files will be modified)"
[ "$REPAIR" -eq 1 ] && echo "Mode: REPAIR / RECONCILE"

# 0. Begin / resume transactional install manifest
BEGIN_FLAGS=(--gpu-profile "$GPU_PROFILE")
[ "$REPAIR" -eq 1 ] && BEGIN_FLAGS+=(--repair)
manifest_cmd begin "${BEGIN_FLAGS[@]}"

# 1. Core scripts & binaries
install_file "$REPO_DIR/bin/tv-display-mode" "$HOME/.local/bin/tv-display-mode" 0755
install_file "$REPO_DIR/bin/tv-movie-mode-toggle" "$HOME/.local/bin/tv-movie-mode-toggle" 0755
install_file "$REPO_DIR/bin/tv-session-switch.sh" "$HOME/.local/bin/tv-session-switch.sh" 0755
install_file "$REPO_DIR/bin/tv-remote-keymap.py" "$HOME/.local/bin/tv-remote-keymap.py" 0755
install_file "$REPO_DIR/bin/steamos-add-to-steam" "$HOME/.local/bin/steamos-add-to-steam" 0755
install_file "$REPO_DIR/bin/nextgen-manifest.py" "$HOME/.local/bin/nextgen-manifest.py" 0755
if [ -f "$REPO_DIR/bin/nextgen_platform.py" ]; then
    install_file "$REPO_DIR/bin/nextgen_platform.py" "$HOME/.local/bin/nextgen_platform.py" 0755
fi
install_file "$REPO_DIR/bin/tv-display-mode.sh" "$HOME/tv-display-mode.sh" 0755
install_file "$REPO_DIR/rollback-tv-setup.sh" "$HOME/rollback-tv-setup.sh" 0755

for s in "$REPO_DIR/bin/streaming_scripts/"*; do
    [ -f "$s" ] || continue
    install_file "$s" "$HOME/Applications/streaming_scripts/$(basename "$s")" 0755
done

# 2. KWin script, unit tests, bashrc helper, mpv hook, user-editable configs
install_file "$REPO_DIR/kwin/tv-display-mode.js" "$HOME/.local/share/tv-display-mode/kwin/tv-display-mode.js" 0644
install_file "$REPO_DIR/tests/test_tv_display_mode.py" "$HOME/.local/share/tv-display-mode/test_tv_display_mode.py" 0644
install_file "$REPO_DIR/configs/bashrc.d/tv-display-mode.sh" "$HOME/.bashrc.d/tv-display-mode.sh" 0644
install_file "$REPO_DIR/mpv/tv-display-mode.lua" "$HOME/.config/mpv/scripts/tv-display-mode.lua" 0644

install_file "$REPO_DIR/configs/tv-display-mode/config.json" "$HOME/.config/tv-display-mode/config.json" 0644 --preserve-user-edits --keep-existing

if [ -f "$REPO_DIR/configs/tv-display-mode/remote-profiles.json" ]; then
    install_file "$REPO_DIR/configs/tv-display-mode/remote-profiles.json" "$HOME/.config/tv-display-mode/remote-profiles.json" 0644 --preserve-user-edits --keep-existing
elif [ -f "$REPO_DIR/configs/remote-profiles.json" ]; then
    install_file "$REPO_DIR/configs/remote-profiles.json" "$HOME/.config/tv-display-mode/remote-profiles.json" 0644 --preserve-user-edits --keep-existing
fi

# 3. Stremio libmpv VA-API shim & configs
install_file "$REPO_DIR/stremio/stremio_mpv_shim.c" "$HOME/.local/share/tv-display-mode/stremio/stremio_mpv_shim.c" 0644
install_file "$REPO_DIR/stremio/mpv.conf" "$HOME/.var/app/com.stremio.Stremio/config/mpv/mpv.conf" 0644 --preserve-user-edits

SHIM_SO="$HOME/.var/app/com.stremio.Stremio/data/stremio-mpv-shim.so"
SHIM_READY=0
CC_BIN=""
if command -v gcc >/dev/null 2>&1; then
    CC_BIN="gcc"
elif command -v cc >/dev/null 2>&1; then
    CC_BIN="cc"
fi

if [ -n "$CC_BIN" ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
        printf '[dry-run] %s -shared -fPIC -O2 %s -o %s -ldl\n' "$CC_BIN" "$REPO_DIR/stremio/stremio_mpv_shim.c" "$SHIM_SO"
        SHIM_READY=1
    else
        TMP_SO="$(mktemp "${TMPDIR:-/tmp}/nextgen-stremio-shim.XXXXXX.so")"
        if "$CC_BIN" -shared -fPIC -O2 "$REPO_DIR/stremio/stremio_mpv_shim.c" -o "$TMP_SO" -ldl; then
            install_file "$TMP_SO" "$SHIM_SO" 0755
            if [ -f "$SHIM_SO" ]; then
                SHIM_READY=1
            fi
        else
            echo "Warning: failed to compile $SHIM_SO with $CC_BIN; skipping Stremio LD_PRELOAD override" >&2
        fi
        rm -f "$TMP_SO"
    fi
else
    echo "Note: gcc/cc not found; skipping compilation of $SHIM_SO (LD_PRELOAD override will not be set)"
fi

# 4. Android TV-style Plasma Bigscreen homescreen plasmoid override (backs up any pre-existing directory)
PLASMOID_SRC="$REPO_DIR/plasma/plasmoids/org.kde.bigscreen.homescreen"
PLASMOID_DST="$HOME/.local/share/plasma/plasmoids/org.kde.bigscreen.homescreen"
manifest_cmd install-dir --src "$PLASMOID_SRC" --dst "$PLASMOID_DST"

# 5. Plasma Bigscreen configs, desktop entries, Flatpak overrides
for cfg in "$REPO_DIR/configs/plasma-bigscreen/"*; do
    [ -f "$cfg" ] || continue
    install_file "$cfg" "$HOME/.config/plasma-bigscreen/$(basename "$cfg")" 0644
done
install_file "$REPO_DIR/configs/plasma-bigscreen-inputhandlerrc" "$HOME/.config/plasma-bigscreen-inputhandlerrc" 0644
install_file "$REPO_DIR/configs/plasma-bigscreen-inputhandlerrc" "$HOME/.config/plasma-bigscreen/plasma-bigscreen-inputhandlerrc" 0644
install_file "$REPO_DIR/configs/applications-blacklistrc" "$HOME/.config/applications-blacklistrc" 0644 --preserve-user-edits
install_file "$REPO_DIR/configs/applications-blacklistrc" "$HOME/.config/plasma-bigscreen/applications-blacklistrc" 0644 --preserve-user-edits
install_template "$REPO_DIR/configs/bigscreen-favs.template" "$HOME/.config/bigscreen-favs" 0644 --preserve-user-edits

for d in steam-bigpicture.desktop com.stremio.Stremio.desktop org.jellyfin.JellyfinDesktop.desktop rocks.shy.VacuumTube.desktop; do
    install_file "$REPO_DIR/desktop/$d" "$HOME/.local/share/applications/$d" 0644
done
install_template "$REPO_DIR/desktop/tv-movie-mode.desktop.template" "$HOME/.local/share/applications/tv-movie-mode.desktop" 0644
install_template "$REPO_DIR/desktop/plasma-bigscreen-swap.desktop.template" "$HOME/.local/share/applications/plasma-bigscreen-swap.desktop" 0644
install_template "$REPO_DIR/desktop/return-to-desktop.desktop.template" "$HOME/.local/share/applications/return-to-desktop.desktop" 0644
install_template "$REPO_DIR/desktop/plasma-bigscreen-autostart.desktop.template" "$HOME/.config/autostart/plasma-bigscreen-autostart.desktop" 0644

install_file "$REPO_DIR/configs/vacuumtube/flags.txt" "$HOME/.var/app/rocks.shy.VacuumTube/config/VacuumTube/flags.txt" 0644 --preserve-user-edits
install_file "$REPO_DIR/configs/haruna/haruna.conf" "$HOME/.var/app/org.kde.haruna/config/haruna/haruna.conf" 0644 --preserve-user-edits

# INI-safe Flatpak override patching (preserves all unrelated user sections/keys)
STREMIO_OV_ARGS=()
if [ "$SHIM_READY" -eq 1 ]; then
    STREMIO_OV_ARGS+=(--set "Environment:LD_PRELOAD=$SHIM_SO")
else
    STREMIO_OV_ARGS+=(--unset "Environment:LD_PRELOAD")
fi
if [ -n "$VAAPI_DRIVER" ]; then
    STREMIO_OV_ARGS+=(--set "Environment:LIBVA_DRIVER_NAME=$VAAPI_DRIVER")
else
    STREMIO_OV_ARGS+=(--unset "Environment:LIBVA_DRIVER_NAME")
fi
manifest_cmd patch-flatpak-override --app-id "com.stremio.Stremio" "${STREMIO_OV_ARGS[@]}"

if [ -n "$VAAPI_DRIVER" ]; then
    manifest_cmd patch-flatpak-override --app-id "org.jellyfin.JellyfinDesktop" --set "Environment:LIBVA_DRIVER_NAME=$VAAPI_DRIVER"
    manifest_cmd patch-flatpak-override --app-id "org.kde.haruna" --set "Environment:LIBVA_DRIVER_NAME=$VAAPI_DRIVER"
    manifest_cmd patch-flatpak-override --app-id "org.mozilla.firefox" \
        --set "Session Bus Policy:org.kde.plasma.browser.integration=talk" \
        --set "Environment:LIBVA_DRIVER_NAME=$VAAPI_DRIVER"
    manifest_cmd patch-flatpak-override --app-id "rocks.shy.VacuumTube" \
        --set "Context:sockets=!fallback-x11;wayland;!x11;" \
        --set "Environment:LIBVA_DRIVER_NAME=$VAAPI_DRIVER"
else
    manifest_cmd patch-flatpak-override --app-id "org.jellyfin.JellyfinDesktop" --unset "Environment:LIBVA_DRIVER_NAME"
    manifest_cmd patch-flatpak-override --app-id "org.kde.haruna" --unset "Environment:LIBVA_DRIVER_NAME"
    manifest_cmd patch-flatpak-override --app-id "org.mozilla.firefox" \
        --set "Session Bus Policy:org.kde.plasma.browser.integration=talk" \
        --unset "Environment:LIBVA_DRIVER_NAME"
    manifest_cmd patch-flatpak-override --app-id "rocks.shy.VacuumTube" \
        --set "Context:sockets=!fallback-x11;wayland;!x11;" \
        --unset "Environment:LIBVA_DRIVER_NAME"
fi

# 6. Systemd user services
for unit in tv-display-mode.service tv-remote-keymap.service plasma-bigscreen-inputhandler.service; do
    install_file "$REPO_DIR/systemd/user/$unit" "$HOME/.config/systemd/user/$unit" 0644
done

# 7. Optional hardware / system behavior presets (all pre-existing files backed up via manifest)
if [ "$WITH_HARDWARE_PRESETS" -eq 1 ]; then
    if [ "$INSTALL_INTEL_VAAPI_CONF" -eq 1 ]; then
        install_file "$REPO_DIR/configs/environment.d/90-intel-vaapi.conf" "$HOME/.config/environment.d/90-intel-vaapi.conf" 0644
    else
        echo "Skipping 90-intel-vaapi.conf (GPU profile is $GPU_PROFILE; only installed for intel-ihd)"
    fi
    install_file "$REPO_DIR/configs/wireplumber/90-tv-hdmi-audio.conf.example" "$HOME/.config/wireplumber/wireplumber.conf.d/90-tv-hdmi-audio.conf" 0644
    install_file "$REPO_DIR/configs/gamescope/ogui-steam" "$HOME/.config/gamescope-session-plus/sessions.d/ogui-steam" 0644
    install_file "$REPO_DIR/configs/gamescope/modes.cfg" "$HOME/.config/gamescope/modes.cfg" 0644
    install_file "$REPO_DIR/configs/powerdevilrc" "$HOME/.config/powerdevilrc" 0644
    install_file "$REPO_DIR/configs/kscreenlockerrc" "$HOME/.config/kscreenlockerrc" 0644
    install_file "$REPO_DIR/configs/kwinrulesrc" "$HOME/.config/kwinrulesrc" 0644
fi

# 8. Commit manifest transaction
manifest_cmd commit

# 9. Reload systemd user services
if [ "$SKIP_SERVICES" -eq 0 ]; then
    if command -v systemctl >/dev/null 2>&1; then
        run_cmd systemctl --user daemon-reload
        run_cmd systemctl --user enable --now tv-display-mode.service
        run_cmd systemctl --user enable --now tv-remote-keymap.service
    fi
fi

echo ""
echo "=== Install Complete ==="
echo "Next steps:"
echo "1. Check your display connector name with: kscreen-doctor -o"
echo "   Update \"output\" in ~/.config/tv-display-mode/config.json if it is not DP-1."
echo "2. Start Plasma Bigscreen mode with: ~/.local/bin/tv-session-switch.sh bigscreen"
echo "3. Check status with: ~/.local/bin/tv-display-mode status"

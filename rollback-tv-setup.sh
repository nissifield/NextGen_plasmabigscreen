#!/usr/bin/env bash
# Safe, manifest-backed rollback/uninstaller for NextGen Plasma Bigscreen
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY_RUN=0
SKIP_SERVICES=0

usage() {
    cat <<'EOF'
Usage: ./rollback-tv-setup.sh [OPTIONS]

Safely roll back NextGen Plasma Bigscreen customizations in $HOME.
When a NextGen install manifest exists, restores pre-existing user files and
Flatpak overrides to their exact prior state and deletes only NextGen-created
files. Unrelated user configs, Flatpak overrides, and systemd linger are preserved.

Options:
  -n, --dry-run        Preview rollback actions without modifying $HOME
      --skip-services  Skip systemd, KWin DBus, session, and keymap runtime calls
  -h, --help           Show this help text and exit
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        -n|--dry-run)
            DRY_RUN=1
            ;;
        --skip-services)
            SKIP_SERVICES=1
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

MANIFEST_TOOL=""
if [ -f "$REPO_DIR/bin/nextgen-manifest.py" ]; then
    MANIFEST_TOOL="$REPO_DIR/bin/nextgen-manifest.py"
elif [ -f "$HOME/.local/bin/nextgen-manifest.py" ]; then
    MANIFEST_TOOL="$HOME/.local/bin/nextgen-manifest.py"
fi

MANIFEST_FILE="$HOME/.local/state/nextgen-plasmabigscreen/manifest.json"

run_service_cmd() {
    if [ "$SKIP_SERVICES" -eq 1 ]; then
        return 0
    fi
    if [ "$DRY_RUN" -eq 1 ]; then
        printf '[dry-run] %s\n' "$*"
    else
        "$@" 2>/dev/null || true
    fi
}

rm_safe_file() {
    local target="$1"
    if [ ! -e "$target" ] && [ ! -L "$target" ]; then
        return 0
    fi
    if [ "$DRY_RUN" -eq 1 ]; then
        printf '[dry-run] rm -f %s\n' "$target"
    else
        rm -f "$target"
    fi
}

rm_safe_dir() {
    local target="$1"
    if [ ! -e "$target" ] && [ ! -L "$target" ]; then
        return 0
    fi
    if [ "$DRY_RUN" -eq 1 ]; then
        printf '[dry-run] rm -rf %s\n' "$target"
    else
        rm -rf "$target"
    fi
}

echo "=== Rolling Back NextGen Plasma Bigscreen TV Setup ==="
[ "$DRY_RUN" -eq 1 ] && echo "Mode: DRY RUN (no files will be modified)"

# 1. Stop runtime services & restore desktop session (skipped under --skip-services)
if [ "$SKIP_SERVICES" -eq 0 ]; then
    echo "--> Stopping NextGen user services and restoring desktop session..."
    if command -v steamosctl >/dev/null 2>&1; then
        run_service_cmd steamosctl set-default-login-mode desktop
    fi
    if command -v systemctl >/dev/null 2>&1; then
        run_service_cmd systemctl --user disable --now tv-display-mode.service
        run_service_cmd systemctl --user disable --now tv-remote-keymap.service
        run_service_cmd systemctl --user disable --now plasma-bigscreen-inputhandler.service
    fi
    if command -v qdbus6 >/dev/null 2>&1; then
        run_service_cmd qdbus6 org.kde.KWin /Scripting org.kde.kwin.Scripting.unloadScript tv-display-mode
    fi
    if [ -x "$HOME/.local/bin/tv-session-switch.sh" ]; then
        run_service_cmd "$HOME/.local/bin/tv-session-switch.sh" desktop
    fi
    if [ -x "$HOME/.local/bin/tv-remote-keymap.py" ]; then
        run_service_cmd "$HOME/.local/bin/tv-remote-keymap.py" --reset
    fi
fi

# 2. Manifest-backed exact rollback OR conservative legacy rollback
if [ -f "$MANIFEST_FILE" ]; then
    if [ -z "$MANIFEST_TOOL" ] || ! command -v python3 >/dev/null 2>&1; then
        echo "Error: manifest found at $MANIFEST_FILE but python3 / nextgen-manifest.py is unavailable" >&2
        exit 1
    fi
    echo "--> Executing manifest-backed rollback ($MANIFEST_FILE)..."
    RB_FLAGS=()
    [ "$DRY_RUN" -eq 1 ] && RB_FLAGS+=(--dry-run)
    python3 -B "$MANIFEST_TOOL" rollback "${RB_FLAGS[@]}"
else
    echo "--> No manifest found; performing conservative legacy rollback..."
    echo "    (Preserving unrelated user configs and unrelated Flatpak overrides)"

    # Remove only clearly NextGen-owned scripts, units, launchers, and artifacts
    rm_safe_file "$HOME/.local/bin/tv-display-mode"
    rm_safe_file "$HOME/.local/bin/tv-movie-mode-toggle"
    rm_safe_file "$HOME/.local/bin/tv-session-switch.sh"
    rm_safe_file "$HOME/.local/bin/tv-remote-keymap.py"
    rm_safe_file "$HOME/.local/bin/steamos-add-to-steam"
    rm_safe_file "$HOME/.local/bin/nextgen-manifest.py"
    rm_safe_file "$HOME/.local/bin/nextgen_platform.py"
    rm_safe_file "$HOME/tv-display-mode.sh"
    rm_safe_file "$HOME/.bashrc.d/tv-display-mode.sh"
    rm_safe_file "$HOME/.config/mpv/scripts/tv-display-mode.lua"
    rm_safe_file "$HOME/.var/app/com.stremio.Stremio/data/stremio-mpv-shim.so"
    rm_safe_dir "$HOME/.local/share/tv-display-mode"

    rm_safe_file "$HOME/Applications/streaming_scripts/Youtube"
    rm_safe_file "$HOME/Applications/streaming_scripts/stremio"
    rm_safe_file "$HOME/Applications/streaming_scripts/jellyfin-media-player"

    rm_safe_file "$HOME/.config/systemd/user/tv-display-mode.service"
    rm_safe_file "$HOME/.config/systemd/user/tv-remote-keymap.service"
    rm_safe_file "$HOME/.config/systemd/user/plasma-bigscreen-inputhandler.service"

    rm_safe_file "$HOME/.local/share/applications/tv-movie-mode.desktop"
    rm_safe_file "$HOME/.local/share/applications/plasma-bigscreen-swap.desktop"
    rm_safe_file "$HOME/.local/share/applications/return-to-desktop.desktop"
    rm_safe_file "$HOME/.config/autostart/plasma-bigscreen-autostart.desktop"

    rm_safe_file "$HOME/.config/environment.d/90-intel-vaapi.conf"
    rm_safe_file "$HOME/.config/wireplumber/wireplumber.conf.d/90-tv-hdmi-audio.conf"

    # Strip ONLY known NextGen keys from Flatpak overrides (NEVER flatpak override --reset)
    if [ -n "$MANIFEST_TOOL" ] && command -v python3 >/dev/null 2>&1; then
        LEG_FLAGS=()
        [ "$DRY_RUN" -eq 1 ] && LEG_FLAGS+=(--dry-run)
        python3 -B "$MANIFEST_TOOL" legacy-clean-flatpak "${LEG_FLAGS[@]}"
    fi

    # Restore legacy backups if present
    if [ -f "$HOME/.tv-setup-backups/Return.desktop" ]; then
        if [ "$DRY_RUN" -eq 1 ]; then
            printf '[dry-run] restore %s -> %s\n' "$HOME/.tv-setup-backups/Return.desktop" "$HOME/Desktop/Return.desktop"
        else
            mkdir -p "$HOME/Desktop"
            cp -p "$HOME/.tv-setup-backups/Return.desktop" "$HOME/Desktop/Return.desktop"
            chmod +x "$HOME/Desktop/Return.desktop"
        fi
    fi
    if [ -f "$HOME/.tv-setup-backups/powerdevilrc" ]; then
        if [ "$DRY_RUN" -eq 1 ]; then
            printf '[dry-run] restore %s -> %s\n' "$HOME/.tv-setup-backups/powerdevilrc" "$HOME/.config/powerdevilrc"
        else
            mkdir -p "$HOME/.config"
            cp -p "$HOME/.tv-setup-backups/powerdevilrc" "$HOME/.config/powerdevilrc"
        fi
    fi
fi

# 3. Reload user services after file changes (never touch systemd linger)
if [ "$SKIP_SERVICES" -eq 0 ] && command -v systemctl >/dev/null 2>&1; then
    run_service_cmd systemctl --user daemon-reload
    run_service_cmd systemctl --user restart plasma-powerdevil.service
    run_service_cmd systemctl --user restart wireplumber
fi

echo ""
echo "=== Rollback Complete ==="
echo "Note: User systemd linger was left unchanged (manage manually with loginctl if needed)."

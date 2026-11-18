#!/usr/bin/env bash
# User-space installer for NextGen Plasma Bigscreen
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY_RUN=0
SKIP_SERVICES=0
WITH_HARDWARE_PRESETS=0
FORCE_CONFIGS=0

usage() {
    cat <<'EOF'
Usage: ./install.sh [OPTIONS]

Install NextGen Plasma Bigscreen customizations cleanly into $HOME (user-space only;
no root/sudo or /usr edits required).

Options:
  -n, --dry-run                Print every planned action without modifying $HOME
      --with-hardware-presets  Also install Intel VA-API, WirePlumber HDMI audio,
                               Gamescope, and PowerDevil/KScreenLocker presets
      --skip-services          Install files without reloading/starting systemd units
      --force                  Overwrite existing ~/.config/tv-display-mode/config.json
  -h, --help                   Show this help text and exit
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        -n|--dry-run)
            DRY_RUN=1
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
    if [ "$DRY_RUN" -eq 1 ]; then
        printf '[dry-run] install -m %s %s -> %s\n' "$mode" "$src" "$dst"
    else
        mkdir -p "$(dirname "$dst")"
        install -m "$mode" "$src" "$dst"
    fi
}

install_template() {
    local src="$1"
    local dst="$2"
    local mode="${3:-0644}"
    if [ "$DRY_RUN" -eq 1 ]; then
        printf '[dry-run] render(@HOME@=%s) %s -> %s (mode %s)\n' "$HOME" "$src" "$dst" "$mode"
    else
        mkdir -p "$(dirname "$dst")"
        local tmp="${dst}.tmp.$$"
        sed "s|@HOME@|${HOME}|g" "$src" > "$tmp"
        chmod "$mode" "$tmp"
        mv -f "$tmp" "$dst"
    fi
}

echo "=== NextGen Plasma Bigscreen User-Space Installer ==="
echo "Repository: $REPO_DIR"
echo "Target HOME: $HOME"
[ "$DRY_RUN" -eq 1 ] && echo "Mode: DRY RUN (no files will be modified)"

# 1. Core scripts & binaries
install_file "$REPO_DIR/bin/tv-display-mode" "$HOME/.local/bin/tv-display-mode" 0755
install_file "$REPO_DIR/bin/tv-movie-mode-toggle" "$HOME/.local/bin/tv-movie-mode-toggle" 0755
install_file "$REPO_DIR/bin/tv-session-switch.sh" "$HOME/.local/bin/tv-session-switch.sh" 0755
install_file "$REPO_DIR/bin/tv-remote-keymap.py" "$HOME/.local/bin/tv-remote-keymap.py" 0755
install_file "$REPO_DIR/bin/steamos-add-to-steam" "$HOME/.local/bin/steamos-add-to-steam" 0755
install_file "$REPO_DIR/bin/tv-display-mode.sh" "$HOME/tv-display-mode.sh" 0755

for s in "$REPO_DIR/bin/streaming_scripts/"*; do
    install_file "$s" "$HOME/Applications/streaming_scripts/$(basename "$s")" 0755
done

# 2. KWin script, unit tests, bashrc helper, mpv hook
install_file "$REPO_DIR/kwin/tv-display-mode.js" "$HOME/.local/share/tv-display-mode/kwin/tv-display-mode.js" 0644
install_file "$REPO_DIR/tests/test_tv_display_mode.py" "$HOME/.local/share/tv-display-mode/test_tv_display_mode.py" 0644
install_file "$REPO_DIR/configs/bashrc.d/tv-display-mode.sh" "$HOME/.bashrc.d/tv-display-mode.sh" 0644
install_file "$REPO_DIR/mpv/tv-display-mode.lua" "$HOME/.config/mpv/scripts/tv-display-mode.lua" 0644

if [ "$FORCE_CONFIGS" -eq 1 ] || [ ! -e "$HOME/.config/tv-display-mode/config.json" ]; then
    install_file "$REPO_DIR/configs/tv-display-mode/config.json" "$HOME/.config/tv-display-mode/config.json" 0644
else
    echo "Keeping existing $HOME/.config/tv-display-mode/config.json (pass --force to overwrite)"
fi

# 3. Stremio libmpv VA-API shim & configs
install_file "$REPO_DIR/stremio/stremio_mpv_shim.c" "$HOME/.local/share/tv-display-mode/stremio/stremio_mpv_shim.c" 0644
install_file "$REPO_DIR/stremio/mpv.conf" "$HOME/.var/app/com.stremio.Stremio/config/mpv/mpv.conf" 0644
SHIM_SO="$HOME/.var/app/com.stremio.Stremio/data/stremio-mpv-shim.so"
if command -v gcc >/dev/null 2>&1; then
    if [ "$DRY_RUN" -eq 1 ]; then
        printf '[dry-run] gcc -shared -fPIC -O2 %s -o %s -ldl\n' "$REPO_DIR/stremio/stremio_mpv_shim.c" "$SHIM_SO"
    else
        mkdir -p "$(dirname "$SHIM_SO")"
        gcc -shared -fPIC -O2 "$REPO_DIR/stremio/stremio_mpv_shim.c" -o "$SHIM_SO" -ldl
    fi
elif command -v cc >/dev/null 2>&1; then
    if [ "$DRY_RUN" -eq 1 ]; then
        printf '[dry-run] cc -shared -fPIC -O2 %s -o %s -ldl\n' "$REPO_DIR/stremio/stremio_mpv_shim.c" "$SHIM_SO"
    else
        mkdir -p "$(dirname "$SHIM_SO")"
        cc -shared -fPIC -O2 "$REPO_DIR/stremio/stremio_mpv_shim.c" -o "$SHIM_SO" -ldl
    fi
else
    echo "Note: gcc/cc not found; skipping compilation of $SHIM_SO"
fi

# 4. Android TV-style Plasma Bigscreen homescreen plasmoid override
PLASMOID_SRC="$REPO_DIR/plasma/plasmoids/org.kde.bigscreen.homescreen"
PLASMOID_DST="$HOME/.local/share/plasma/plasmoids/org.kde.bigscreen.homescreen"
if [ "$DRY_RUN" -eq 1 ]; then
    printf '[dry-run] sync %s -> %s\n' "$PLASMOID_SRC" "$PLASMOID_DST"
else
    mkdir -p "$(dirname "$PLASMOID_DST")"
    rm -rf "$PLASMOID_DST"
    cp -a "$PLASMOID_SRC" "$PLASMOID_DST"
fi

# 5. Plasma Bigscreen configs, desktop entries, Flatpak overrides
for cfg in "$REPO_DIR/configs/plasma-bigscreen/"*; do
    install_file "$cfg" "$HOME/.config/plasma-bigscreen/$(basename "$cfg")" 0644
done
install_file "$REPO_DIR/configs/plasma-bigscreen-inputhandlerrc" "$HOME/.config/plasma-bigscreen-inputhandlerrc" 0644
install_file "$REPO_DIR/configs/plasma-bigscreen-inputhandlerrc" "$HOME/.config/plasma-bigscreen/plasma-bigscreen-inputhandlerrc" 0644
install_file "$REPO_DIR/configs/applications-blacklistrc" "$HOME/.config/applications-blacklistrc" 0644
install_file "$REPO_DIR/configs/applications-blacklistrc" "$HOME/.config/plasma-bigscreen/applications-blacklistrc" 0644
install_template "$REPO_DIR/configs/bigscreen-favs.template" "$HOME/.config/bigscreen-favs" 0644

for d in steam-bigpicture.desktop com.stremio.Stremio.desktop org.jellyfin.JellyfinDesktop.desktop rocks.shy.VacuumTube.desktop; do
    install_file "$REPO_DIR/desktop/$d" "$HOME/.local/share/applications/$d" 0644
done
install_template "$REPO_DIR/desktop/tv-movie-mode.desktop.template" "$HOME/.local/share/applications/tv-movie-mode.desktop" 0644
install_template "$REPO_DIR/desktop/plasma-bigscreen-swap.desktop.template" "$HOME/.local/share/applications/plasma-bigscreen-swap.desktop" 0644
install_template "$REPO_DIR/desktop/return-to-desktop.desktop.template" "$HOME/.local/share/applications/return-to-desktop.desktop" 0644
install_template "$REPO_DIR/desktop/plasma-bigscreen-autostart.desktop.template" "$HOME/.config/autostart/plasma-bigscreen-autostart.desktop" 0644

install_file "$REPO_DIR/configs/vacuumtube/flags.txt" "$HOME/.var/app/rocks.shy.VacuumTube/config/VacuumTube/flags.txt" 0644
install_file "$REPO_DIR/configs/haruna/haruna.conf" "$HOME/.var/app/org.kde.haruna/config/haruna/haruna.conf" 0644
install_template "$REPO_DIR/configs/flatpak/overrides/com.stremio.Stremio.template" "$HOME/.local/share/flatpak/overrides/com.stremio.Stremio" 0644
for ov in org.jellyfin.JellyfinDesktop org.kde.haruna org.mozilla.firefox rocks.shy.VacuumTube; do
    install_file "$REPO_DIR/configs/flatpak/overrides/$ov" "$HOME/.local/share/flatpak/overrides/$ov" 0644
done

# 6. Systemd user services
for unit in tv-display-mode.service tv-remote-keymap.service plasma-bigscreen-inputhandler.service; do
    install_file "$REPO_DIR/systemd/user/$unit" "$HOME/.config/systemd/user/$unit" 0644
done

# 7. Optional hardware / system behavior presets
if [ "$WITH_HARDWARE_PRESETS" -eq 1 ]; then
    install_file "$REPO_DIR/configs/environment.d/90-intel-vaapi.conf" "$HOME/.config/environment.d/90-intel-vaapi.conf" 0644
    install_file "$REPO_DIR/configs/wireplumber/90-tv-hdmi-audio.conf.example" "$HOME/.config/wireplumber/wireplumber.conf.d/90-tv-hdmi-audio.conf" 0644
    install_file "$REPO_DIR/configs/gamescope/ogui-steam" "$HOME/.config/gamescope-session-plus/sessions.d/ogui-steam" 0644
    install_file "$REPO_DIR/configs/gamescope/modes.cfg" "$HOME/.config/gamescope/modes.cfg" 0644
    install_file "$REPO_DIR/configs/powerdevilrc" "$HOME/.config/powerdevilrc" 0644
    install_file "$REPO_DIR/configs/kscreenlockerrc" "$HOME/.config/kscreenlockerrc" 0644
    install_file "$REPO_DIR/configs/kwinrulesrc" "$HOME/.config/kwinrulesrc" 0644
fi

# 8. Reload systemd user services
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

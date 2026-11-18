#!/usr/bin/env bash
# User-Space KDE Plasma Desktop <-> Plasma Bigscreen Session Switcher
set -e

export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-1}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=${XDG_RUNTIME_DIR}/bus}"

CACHE_DIR="$HOME/.cache/plasma-bigscreen"
ACTIVE_MODE_FILE="$CACHE_DIR/active-mode"
SAVED_ENV_FILE="$CACHE_DIR/saved-env"

is_bigscreen_active() {
    local pid
    pid="$(pidof -s plasmashell 2>/dev/null || true)"
    if [ -z "$pid" ] || [ ! -r "/proc/${pid}/environ" ]; then
        return 1
    fi
    if tr '\0' '\n' < "/proc/${pid}/environ" | grep -q '^PLASMA_DEFAULT_SHELL=org\.kde\.plasma\.bigscreen$'; then
        return 0
    fi
    return 1
}

switch_to_bigscreen() {
    local force_flag="${1:-}"
    mkdir -p "$CACHE_DIR" "$HOME/.config/plasma-bigscreen"

    # Source upstream Bigscreen common environment (sets XDG_CONFIG_DIRS and runs plasma-bigscreen-envmanager --apply-settings)
    if [ -f /usr/bin/plasma-bigscreen-common-env ]; then
        # shellcheck disable=SC1091
        . /usr/bin/plasma-bigscreen-common-env
    fi

    # CRITICAL FIX: plasma-bigscreen-envmanager --apply-settings overwrites ~/.config/plasma-bigscreen/applications-blacklistrc
    # Restore user-space curated blacklist and inputhandler config immediately after sourcing common-env
    if [ -f "$HOME/.config/applications-blacklistrc" ]; then
        cp -f "$HOME/.config/applications-blacklistrc" "$HOME/.config/plasma-bigscreen/applications-blacklistrc"
    fi
    if [ -f "$HOME/.config/plasma-bigscreen-inputhandlerrc" ]; then
        cp -f "$HOME/.config/plasma-bigscreen-inputhandlerrc" "$HOME/.config/plasma-bigscreen/plasma-bigscreen-inputhandlerrc"
    fi

    echo "bigscreen" > "$ACTIVE_MODE_FILE"

    if [ "$force_flag" = "--force" ] || ! is_bigscreen_active; then
        systemctl --user set-environment \
            "XDG_CONFIG_DIRS=${XDG_CONFIG_DIRS}" \
            PLASMA_DEFAULT_SHELL=org.kde.plasma.bigscreen \
            PLASMA_PLATFORM=mediacenter \
            QT_FILE_SELECTORS=mediacenter \
            KWIN_IM_SHOW_ALWAYS=1 \
            PLASMA_INTEGRATION_USE_PORTAL=1
        systemctl --user restart plasma-plasmashell.service
    fi

    # Ensure xdg-desktop-portal and SDL3 controller input handler are active after compositor/portal ready
    systemctl --user start xdg-desktop-portal.service 2>/dev/null || true
    systemctl --user restart plasma-bigscreen-inputhandler.service 2>/dev/null || true
}

switch_to_desktop() {
    mkdir -p "$CACHE_DIR"
    echo "desktop" > "$ACTIVE_MODE_FILE"
    rm -f "$SAVED_ENV_FILE"

    # Stop Bigscreen input handler so desktop controller/CEC events don't conflict
    systemctl --user stop plasma-bigscreen-inputhandler.service 2>/dev/null || true

    # Strip ~/.config/plasma-bigscreen: from XDG_CONFIG_DIRS
    XDG_CONFIG_DIRS="${XDG_CONFIG_DIRS:-/etc/xdg}"
    XDG_CONFIG_DIRS="${XDG_CONFIG_DIRS//$HOME\/.config\/plasma-bigscreen:/}"
    export XDG_CONFIG_DIRS="${XDG_CONFIG_DIRS:-/etc/xdg}"

    # Unset mediacenter environment variables in systemd user manager and D-Bus activation
    systemctl --user unset-environment \
        PLASMA_DEFAULT_SHELL \
        PLASMA_PLATFORM \
        QT_FILE_SELECTORS \
        KWIN_IM_SHOW_ALWAYS \
        PLASMA_INTEGRATION_USE_PORTAL \
        PLASMA_BIGSCREEN_LAUNCH_REASON
    systemctl --user set-environment XDG_CONFIG_DIRS="/etc/xdg"
    dbus-update-activation-environment --systemd XDG_CONFIG_DIRS="/etc/xdg" 2>/dev/null || true

    # Restart standard KDE Plasma Desktop shell under systemd user service supervision
    systemctl --user restart plasma-plasmashell.service
}

print_status() {
    local pid
    pid="$(pidof -s plasmashell 2>/dev/null || true)"
    if is_bigscreen_active; then
        echo "Active Shell Mode: bigscreen (org.kde.plasma.bigscreen, PID: ${pid})"
    elif [ -n "$pid" ]; then
        echo "Active Shell Mode: desktop (org.kde.plasma.desktop, PID: ${pid})"
    else
        echo "Active Shell Mode: stopped (plasmashell not running)"
    fi
    local ps_state ih_state
    ps_state="$(systemctl --user is-active plasma-plasmashell.service 2>/dev/null || true)"
    ih_state="$(systemctl --user is-active plasma-bigscreen-inputhandler.service 2>/dev/null || true)"
    echo "Plasma Shell Service (plasma-plasmashell.service): ${ps_state:-inactive}"
    echo "Input Handler Service (plasma-bigscreen-inputhandler.service): ${ih_state:-inactive}"
}

MODE="${1:-toggle}"
FORCE_ARG="${2:-}"

case "$MODE" in
    bigscreen|tv)
        switch_to_bigscreen "$FORCE_ARG"
        ;;
    desktop|default)
        switch_to_desktop
        ;;
    toggle|swap)
        if is_bigscreen_active; then
            switch_to_desktop
        else
            switch_to_bigscreen "$FORCE_ARG"
        fi
        ;;
    status)
        print_status
        ;;
    *)
        echo "Usage: $0 {bigscreen|desktop|toggle|status} [--force]"
        exit 1
        ;;
esac

#!/usr/bin/env bash
# User-Space KDE Plasma Desktop <-> Plasma Bigscreen Session Switcher
set -e

if [ -z "${XDG_RUNTIME_DIR:-}" ]; then
    XDG_RUNTIME_DIR="/run/user/$(id -u)"
fi
export XDG_RUNTIME_DIR
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=${XDG_RUNTIME_DIR}/bus}"

detect_wayland_display() {
    local runtime_dir="$1"
    local current="${WAYLAND_DISPLAY:-}"

    if [ -n "$current" ] && [ -S "${runtime_dir}/${current}" ]; then
        printf '%s\n' "$current"
        return 0
    fi
    if [ -S "${runtime_dir}/wayland-1" ]; then
        printf '%s\n' "wayland-1"
        return 0
    fi
    if [ -S "${runtime_dir}/wayland-0" ]; then
        printf '%s\n' "wayland-0"
        return 0
    fi

    local sock base
    for sock in "${runtime_dir}"/wayland-*; do
        case "$sock" in
            *.lock) continue ;;
        esac
        if [ -S "$sock" ]; then
            base="$(basename "$sock")"
            printf '%s\n' "$base"
            return 0
        fi
    done

    if [ -n "$current" ]; then
        printf '%s\n' "$current"
    else
        printf '%s\n' "wayland-0"
    fi
}

WAYLAND_DISPLAY="$(detect_wayland_display "$XDG_RUNTIME_DIR")"
export WAYLAND_DISPLAY

CACHE_DIR="$HOME/.cache/plasma-bigscreen"
ACTIVE_MODE_FILE="$CACHE_DIR/active-mode"
SAVED_ENV_FILE="$CACHE_DIR/saved-env"
BIGSCREEN_CFG_DIR="$HOME/.config/plasma-bigscreen"

strip_bigscreen_from_xdg_config_dirs() {
    local raw="${1:-}"
    local result=""
    local entry
    local -a entries=()
    IFS=':' read -r -a entries <<< "$raw"
    for entry in "${entries[@]}"; do
        if [ -z "$entry" ] || [ "$entry" = "$BIGSCREEN_CFG_DIR" ]; then
            continue
        fi
        if [ -z "$result" ]; then
            result="$entry"
        else
            result="${result}:${entry}"
        fi
    done
    printf '%s\n' "${result:-/etc/xdg}"
}

get_systemd_xdg_config_dirs() {
    systemctl --user show-environment 2>/dev/null | sed -n 's/^XDG_CONFIG_DIRS=//p' | head -n 1 || true
}

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
    mkdir -p "$CACHE_DIR" "$BIGSCREEN_CFG_DIR"

    # Preserve any custom pre-Bigscreen XDG_CONFIG_DIRS so desktop recovery restores it reliably
    if [ ! -f "$SAVED_ENV_FILE" ]; then
        local orig_xdg
        orig_xdg="${XDG_CONFIG_DIRS:-$(get_systemd_xdg_config_dirs)}"
        orig_xdg="$(strip_bigscreen_from_xdg_config_dirs "$orig_xdg")"
        printf 'SAVED_XDG_CONFIG_DIRS=%s\n' "$orig_xdg" > "$SAVED_ENV_FILE"
    fi

    # Source upstream Bigscreen common environment (sets XDG_CONFIG_DIRS and runs plasma-bigscreen-envmanager --apply-settings)
    if [ -f /usr/bin/plasma-bigscreen-common-env ]; then
        # shellcheck disable=SC1091
        . /usr/bin/plasma-bigscreen-common-env
    else
        XDG_CONFIG_DIRS="${BIGSCREEN_CFG_DIR}:$(strip_bigscreen_from_xdg_config_dirs "${XDG_CONFIG_DIRS:-/etc/xdg}")"
        export XDG_CONFIG_DIRS
    fi

    # CRITICAL FIX: plasma-bigscreen-envmanager --apply-settings overwrites ~/.config/plasma-bigscreen/applications-blacklistrc
    # Restore user-space curated blacklist and inputhandler config immediately after sourcing common-env
    if [ -f "$HOME/.config/applications-blacklistrc" ]; then
        cp -f "$HOME/.config/applications-blacklistrc" "$BIGSCREEN_CFG_DIR/applications-blacklistrc"
    fi
    if [ -f "$HOME/.config/plasma-bigscreen-inputhandlerrc" ]; then
        cp -f "$HOME/.config/plasma-bigscreen-inputhandlerrc" "$BIGSCREEN_CFG_DIR/plasma-bigscreen-inputhandlerrc"
    fi

    echo "bigscreen" > "$ACTIVE_MODE_FILE"

    if [ "$force_flag" = "--force" ] || ! is_bigscreen_active; then
        systemctl --user set-environment \
            "WAYLAND_DISPLAY=${WAYLAND_DISPLAY}" \
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

    # Stop Bigscreen input handler so desktop controller/CEC events don't conflict
    systemctl --user stop plasma-bigscreen-inputhandler.service 2>/dev/null || true

    # Recover prior custom XDG_CONFIG_DIRS if saved, otherwise strip ~/.config/plasma-bigscreen cleanly
    local restored_xdg=""
    if [ -f "$SAVED_ENV_FILE" ]; then
        restored_xdg="$(sed -n 's/^SAVED_XDG_CONFIG_DIRS=//p' "$SAVED_ENV_FILE" | head -n 1 || true)"
    fi
    rm -f "$SAVED_ENV_FILE"

    if [ -z "$restored_xdg" ]; then
        local current_xdg
        current_xdg="${XDG_CONFIG_DIRS:-$(get_systemd_xdg_config_dirs)}"
        restored_xdg="$(strip_bigscreen_from_xdg_config_dirs "$current_xdg")"
    else
        restored_xdg="$(strip_bigscreen_from_xdg_config_dirs "$restored_xdg")"
    fi
    export XDG_CONFIG_DIRS="${restored_xdg:-/etc/xdg}"

    # Unset mediacenter environment variables in systemd user manager and D-Bus activation
    systemctl --user unset-environment \
        PLASMA_DEFAULT_SHELL \
        PLASMA_PLATFORM \
        QT_FILE_SELECTORS \
        KWIN_IM_SHOW_ALWAYS \
        PLASMA_INTEGRATION_USE_PORTAL \
        PLASMA_BIGSCREEN_LAUNCH_REASON
    systemctl --user set-environment \
        "WAYLAND_DISPLAY=${WAYLAND_DISPLAY}" \
        "XDG_CONFIG_DIRS=${XDG_CONFIG_DIRS}"
    dbus-update-activation-environment --systemd \
        "WAYLAND_DISPLAY=${WAYLAND_DISPLAY}" \
        "XDG_CONFIG_DIRS=${XDG_CONFIG_DIRS}" 2>/dev/null || true

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
    echo "Wayland Display:   ${WAYLAND_DISPLAY}"
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

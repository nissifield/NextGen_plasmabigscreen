#!/usr/bin/env bash
# Helper to switch TV display modes via kscreen-doctor on KDE Plasma Wayland
set -euo pipefail

export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-1}"
if [ -z "${XDG_RUNTIME_DIR:-}" ]; then
    XDG_RUNTIME_DIR="/run/user/$(id -u)"
fi
export XDG_RUNTIME_DIR
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=${XDG_RUNTIME_DIR}/bus}"

OUT="DP-1"
for p in /sys/class/drm/card*-*; do
  if [ -f "$p/status" ] && [ "$(cat "$p/status")" = "connected" ]; then
    card_name="${p##*/}"
    OUT="${card_name#card*-}"
    break
  fi
done

MODE="${1:-status}"

case "$MODE" in
  1080p120|120)
    echo "Switching $OUT to 1920x1080 @ 120Hz (Scale 1.0, 8-bit RGB)..."
    kscreen-doctor "output.${OUT}.maxbpc.8" "output.${OUT}.mode.1920x1080@120" "output.${OUT}.scale.1"
    ;;
  1080p60|60)
    echo "Switching $OUT to 1920x1080 @ 60Hz (Scale 1.0, 8-bit RGB)..."
    kscreen-doctor "output.${OUT}.maxbpc.8" "output.${OUT}.mode.1920x1080@60" "output.${OUT}.scale.1"
    ;;
  1440p120)
    echo "Switching $OUT to 2560x1440 @ 120Hz (Scale 1.33, 8-bit RGB)..."
    kscreen-doctor "output.${OUT}.maxbpc.8" "output.${OUT}.mode.2560x1440@120" "output.${OUT}.scale.1.33"
    ;;
  1440p60|1440)
    echo "Switching $OUT to 2560x1440 @ 60Hz (Custom CVT-RB, Scale 1.33, 8-bit RGB)..."
    kscreen-doctor "output.${OUT}.maxbpc.8" "output.${OUT}.addCustomMode.2560.1440.60000.reduced" || true
    kscreen-doctor "output.${OUT}.mode.2560x1440@60" "output.${OUT}.scale.1.33"
    ;;
  4k60)
    echo "Switching $OUT to 3840x2160 @ 60Hz (Scale 2.0, 8-bit RGB)..."
    kscreen-doctor "output.${OUT}.maxbpc.8" "output.${OUT}.mode.3840x2160@60" "output.${OUT}.scale.2"
    ;;
  4k30|4k)
    echo "Switching $OUT to 3840x2160 @ 30Hz (Scale 2.0, 8-bit RGB)..."
    kscreen-doctor "output.${OUT}.maxbpc.8" "output.${OUT}.mode.3840x2160@30" "output.${OUT}.scale.2"
    ;;
  off|dpms-off)
    echo "Turning off TV display ($OUT) via DPMS..."
    kscreen-doctor --dpms off
    ;;
  on|dpms-on)
    echo "Turning on TV display ($OUT) via DPMS..."
    kscreen-doctor --dpms on
    ;;
  toggle|dpms-toggle|power)
    if kscreen-doctor --dpms show 2>/dev/null | grep -qi ": on"; then
      echo "TV display ($OUT) is currently ON -> turning OFF via DPMS..."
      kscreen-doctor --dpms off
    else
      echo "TV display ($OUT) is currently OFF -> turning ON via DPMS..."
      kscreen-doctor --dpms on
    fi
    ;;
  retrain|reset)
    echo "Re-training $OUT link (DPMS cycle + 1920x1080 @ 60Hz, Scale 1.0, 8-bit RGB)..."
    kscreen-doctor --dpms off
    sleep 1
    kscreen-doctor "output.${OUT}.enable" "output.${OUT}.maxbpc.8" "output.${OUT}.mode.1920x1080@60" "output.${OUT}.scale.1"
    kscreen-doctor --dpms on
    ;;
  status|*)
    echo "Detected active connector: $OUT"
    echo "Usage: $0 {4k60|1440p120|1080p120|1440p60|1080p60|4k30|retrain|off|on|toggle|status}"
    echo ""
    kscreen-doctor --dpms show || true
    echo ""
    kscreen-doctor -o
    ;;
esac

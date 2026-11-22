# shellcheck shell=bash
# Shell helper functions for tv-display-mode (sourced via ~/.bashrc)

tv-mode() {
    command tv-display-mode "$@"
}

tv-4k() {
    command tv-display-mode 4k
}

tv-1080p() {
    command tv-display-mode 1080p
}

tv-auto() {
    command tv-display-mode auto
}

tv-movie() {
    command tv-display-mode movie
}

tv-toggle() {
    command tv-display-mode toggle
}

tv-status() {
    command tv-display-mode status "$@"
}

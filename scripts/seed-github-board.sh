#!/usr/bin/env bash
# Seed GitHub labels, contributor issues, and optional Project v2 board for
# nissifield/NextGen_plasmabigscreen.
#
# Safe by default: runs in --dry-run mode unless --apply is explicitly passed.
# Requires `gh` CLI authenticated with `gh auth login` (plus `project` scope
# only when --with-project is specified).
set -euo pipefail

REPO="${GITHUB_REPO:-nissifield/NextGen_plasmabigscreen}"
OWNER="${REPO%%/*}"
PROJECT_TITLE="NextGen Compatibility & Contributions"
APPLY=0
WITH_PROJECT=0

usage() {
    cat <<'EOF'
Usage: ./scripts/seed-github-board.sh [OPTIONS]

Idempotently seed the 16 labels, 16 contributor issues, and (optionally) the
"NextGen Compatibility & Contributions" GitHub Project v2 board.

Runs in DRY-RUN mode by default (no GitHub mutations).

Options:
  --dry-run             Print planned gh commands without executing (default)
  --apply               Execute gh commands against GitHub
  --repo OWNER/NAME     Target repository (default: nissifield/NextGen_plasmabigscreen)
  --with-project        Also create/reuse the GitHub Project v2 board and link issues
  -h, --help            Show this help message and exit
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run)
            APPLY=0
            ;;
        --apply)
            APPLY=1
            ;;
        --repo)
            shift
            if [ $# -eq 0 ]; then
                echo "Error: --repo requires OWNER/NAME" >&2
                exit 1
            fi
            REPO="$1"
            OWNER="${REPO%%/*}"
            ;;
        --with-project)
            WITH_PROJECT=1
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

if [ "$APPLY" -eq 1 ]; then
    if ! command -v gh >/dev/null 2>&1; then
        echo "Error: gh CLI is required for --apply. Install GitHub CLI and run 'gh auth login'." >&2
        exit 1
    fi
    if ! gh auth status >/dev/null 2>&1; then
        echo "Error: gh CLI is not authenticated. Run 'gh auth login' first." >&2
        exit 1
    fi
fi

echo "=== NextGen GitHub Board Seeder ==="
echo "Target Repo:  $REPO"
echo "Mode:         $([ "$APPLY" -eq 1 ] && echo "APPLY (live GitHub mutations)" || echo "DRY-RUN (no mutations)")"
echo "Project v2:   $([ "$WITH_PROJECT" -eq 1 ] && echo "enabled ($PROJECT_TITLE)" || echo "skipped (pass --with-project to enable)")"
echo ""

# ---------------------------------------------------------------------------
# 1. Seed Labels (idempotent via --force)
# ---------------------------------------------------------------------------
ensure_label() {
    local name="$1"
    local color="$2"
    local desc="$3"
    if [ "$APPLY" -eq 0 ]; then
        printf '[dry-run] gh label create %q --repo %q --color %q --description %q --force\n' \
            "$name" "$REPO" "$color" "$desc"
    else
        gh label create "$name" --repo "$REPO" --color "$color" --description "$desc" --force
    fi
}

echo "--- Step 1: Labels (16) ---"
ensure_label "good first issue"    "7057ff" "Approachable starter task for first-time contributors"
ensure_label "help wanted"         "008672" "Community contributions actively welcomed"
ensure_label "area:installer"      "1d76db" "Installer, rollback, ownership manifest, and backups"
ensure_label "area:display"        "0e8a16" "tv-display-mode, KWin script, modes, connectors, HDR/VRR"
ensure_label "area:remote"         "fbca04" "USB/BT/RF remote profiles, evdev keymaps, HDMI-CEC, controllers"
ensure_label "area:compatibility"  "5319e7" "Distro, GPU, streaming app, and compatibility matrix validation"
ensure_label "area:docs"           "0075ca" "Documentation, architecture, contributor guides, translations"
ensure_label "platform:atomic"     "006b75" "Immutable/atomic distros (Bazzite, Kinoite, Kalpa)"
ensure_label "platform:mutable"    "2b7a78" "Mutable distros (Fedora Spin, Ubuntu, Debian, Arch, Tumbleweed)"
ensure_label "gpu:intel"           "0052cc" "Intel iGPU/dGPU (i915, xe, iHD, i965)"
ensure_label "gpu:amd"             "d93f0b" "AMD Radeon (amdgpu, Mesa radeonsi VA-API)"
ensure_label "gpu:nvidia"          "2ea44f" "NVIDIA proprietary, NVDEC, nvidia-vaapi-driver"
ensure_label "needs-hardware-test" "e99695" "Requires real-hardware testing and sanitized diagnostics"
ensure_label "priority:P0"         "b60205" "Foundational safety, installer integrity, or core GPU support"
ensure_label "priority:P1"         "d93f0b" "High-value distro, display, or remote expansion"
ensure_label "priority:P2"         "c5def5" "Research, accessibility, localization, and long-term proposals"

# ---------------------------------------------------------------------------
# 2. Fetch existing issue titles for deduplication (when applying)
# ---------------------------------------------------------------------------
EXISTING_TITLES=""
if [ "$APPLY" -eq 1 ]; then
    EXISTING_TITLES="$(gh issue list --repo "$REPO" --state all --limit 200 --json title --jq '.[].title')"
fi

CREATED_ISSUE_URLS=()

ensure_issue() {
    local title="$1"
    local labels_csv="$2"
    local anchor="$3"
    local goal="$4"
    local unknowns="$5"
    local checks="$6"

    local body
    body="$(cat <<EOF
> **Notice:** This issue tracks community testing/implementation work. Having an open issue does **not** mean this platform, GPU, display mode, remote, or service is currently supported. See \`docs/COMPATIBILITY.md\`.

### Goal
${goal}

### Current Unknowns
${unknowns}

### Acceptance Checks
${checks}

### Full Specification & Checklist
See the complete card (Scope / Non-goals, Prerequisites, Possible Files, Hardware Evidence Needed, Security Considerations, Documentation Expected) in [\`docs/CONTRIBUTION_BOARD.md#${anchor}\`](https://github.com/${REPO}/blob/main/docs/CONTRIBUTION_BOARD.md#${anchor}).

### Contributor Safety Reminders
- Keep all NextGen changes inside user-space (\`\$HOME\`); never edit \`/usr\` or \`/etc\`.
- Run \`./install.sh --dry-run\` and unit tests before touching your live desktop.
- Redact usernames, serial numbers, MAC addresses, tokens, and private server URLs from any pasted diagnostics.
- Follow \`CONTRIBUTING.md\` (AI assistants are optional; see \`CONTRIBUTOR_AI_PROMPT.md\`).
EOF
)"

    if [ "$APPLY" -eq 0 ]; then
        printf '[dry-run] gh issue create --repo %q --title %q --label %q\n' \
            "$REPO" "$title" "$labels_csv"
        return 0
    fi

    if printf '%s\n' "$EXISTING_TITLES" | grep -Fxq "$title"; then
        echo "[skip] Issue already exists: $title"
        return 0
    fi

    local url
    url="$(gh issue create --repo "$REPO" --title "$title" --label "$labels_csv" --body "$body")"
    echo "[created] $title -> $url"
    CREATED_ISSUE_URLS+=("$url")
}

echo ""
echo "--- Step 2: Contributor Issues (16) ---"

ensure_issue \
    "Mutable distro: Fedora KDE Spin" \
    "help wanted,good first issue,area:compatibility,platform:mutable,needs-hardware-test,priority:P1" \
    "1-mutable-distro-fedora-kde-spin" \
    "Validate end-to-end user-space install, session switching, streaming launchers, and rollback on mutable Fedora KDE Spin (dnf)." \
    "Differences from Bazzite/Kinoite such as /usr/bin/steam vs /usr/bin/bazzite-steam, Fedora plasma-bigscreen package contents, and ~/.bashrc.d sourcing." \
    "Dry-run succeeds; Bigscreen <-> Desktop switch works without QML errors; tv-display-mode & KWin script healthy; rollback restores pre-existing configs cleanly."

ensure_issue \
    "Mutable distro: Ubuntu + KDE Plasma" \
    "help wanted,area:compatibility,platform:mutable,needs-hardware-test,priority:P1" \
    "2-mutable-distro-ubuntu--kde-plasma" \
    "Validate NextGen Plasma Bigscreen on Ubuntu/Kubuntu releases shipping KDE Plasma 6 Wayland (apt)." \
    "Binary paths (plasma-bigscreen-common-env, qdbus6/qdbus-qt6, bwrap), ~/.bashrc.d sourcing, and Snap vs Flatpak Steam/Firefox behavior." \
    "Dry-run and install handle missing optional tools cleanly; session switching, daemon, and rollback verified on real Plasma 6 Wayland hardware."

ensure_issue \
    "Mutable distro: Debian KDE" \
    "help wanted,area:compatibility,platform:mutable,needs-hardware-test,priority:P1" \
    "3-mutable-distro-debian-kde" \
    "Validate NextGen Plasma Bigscreen on Debian KDE (Testing / Trixie+ with KDE Plasma 6 Wayland)." \
    "Debian plasma-bigscreen packaging layout, qt6-tools/qdbus6 naming, python3-dbus / PyGObject GTK3 availability, and uaccess ACL behavior." \
    "Installer handles optional tools gracefully; daemon, KWin script, session switcher, and rollback verified on real hardware."

ensure_issue \
    "Mutable distro: Arch Linux KDE" \
    "help wanted,good first issue,area:compatibility,platform:mutable,needs-hardware-test,priority:P1" \
    "4-mutable-distro-arch-linux-kde" \
    "Validate NextGen Plasma Bigscreen on Arch Linux (and Arch derivatives) running KDE Plasma 6 Wayland." \
    "Latest Plasma 6.x QML homescreen API compatibility, qdbus6 binary paths, and native vs Flatpak app integrations." \
    "Zero QML errors on newest Arch plasma-bigscreen; tv-display-mode + KWin script active; full rollback verified."

ensure_issue \
    "Mutable distro: openSUSE Tumbleweed KDE" \
    "help wanted,area:compatibility,platform:mutable,platform:atomic,needs-hardware-test,priority:P1" \
    "5-mutable-distro-opensuse-tumbleweed-kde" \
    "Validate NextGen Plasma Bigscreen on openSUSE Tumbleweed (zypper) and optionally Kalpa (transactional-update) with plasma6-bigscreen." \
    "Package/binary paths, SELinux/AppArmor interaction with systemd user services or bwrap, and portal behavior." \
    "Dry-run, install, Bigscreen <-> Desktop switch, daemon, and rollback succeed cleanly with zero security-policy denials."

ensure_issue \
    "GPU: AMD Radeon/Mesa" \
    "help wanted,area:compatibility,gpu:amd,needs-hardware-test,priority:P0" \
    "6-gpu-amd-radeonmesa" \
    "Verify platform adapter GPU detection and end-to-end VA-API (radeonsi) hardware video decoding on AMD Radeon (amdgpu + Mesa)." \
    "Optimal Flatpak overrides and Electron/Vulkan flags for VacuumTube/Stremio/Jellyfin/Haruna on AMD; AV1 decode on RDNA3+." \
    "Zero LIBVA_DRIVER_NAME=iHD injected; live hardware decode verified via vainfo + maps/radeontop; unit fixture test added."

ensure_issue \
    "GPU: NVIDIA" \
    "help wanted,area:compatibility,gpu:nvidia,needs-hardware-test,priority:P0" \
    "7-gpu-nvidia" \
    "Verify safe installation, Wayland stability, and hardware video decode (NVDEC / optional nvidia-vaapi-driver) on NVIDIA proprietary drivers." \
    "GBM/explicit-sync behavior in Electron/libmpv/Haruna; Flatpak NVIDIA runtime interactions; stremio_mpv_shim.c behavior." \
    "Zero Intel iHD flags applied; no black-screen crashes; hardware decode vs software fallback documented accurately with fixture test."

ensure_issue \
    "GPU: Intel legacy/new" \
    "help wanted,area:compatibility,gpu:intel,needs-hardware-test,priority:P1" \
    "8-gpu-intel-legacynew" \
    "Validate GPU adapter behavior across older Intel (i965) and newer Intel (Iris Xe, Arc on i915 or xe)." \
    "Legacy i965 fallback when iHD is unsupported; AV1 hardware decode and VacuumTube Vulkan flags on Gen 12+/Arc." \
    "Never forces iHD on i965-only GPUs; live decode verified for supported codecs; unit fixture test added."

ensure_issue \
    "Display: multi-monitor & connector switching" \
    "help wanted,area:display,needs-hardware-test,priority:P1" \
    "9-display-multi-monitor--connector-switching" \
    "Safely support multi-monitor setups and dynamic TV connectors (HDMI-A-1, DP-1, etc.) without touching unrelated monitors." \
    "Target output selection/persistence when multiple displays are connected and graceful handling when the TV output disconnects." \
    "Never alters non-target monitors; survives TV unplug/replug cleanly; multi-output unit tests pass."

ensure_issue \
    "Display: 4K60/120, HDR and VRR research" \
    "help wanted,area:display,needs-hardware-test,priority:P1" \
    "10-display-4k60120-hdr-and-vrr-research" \
    "Research and validate HDMI 2.0/2.1 4K@60Hz/120Hz, KWin 6 Wayland HDR, and VRR behavior with tv-display-mode and Movie Mode." \
    "Dynamic refresh-rate OSD/toast text; preserving or toggling HDR/WCG/maxbpc/VRR cleanly across kscreen-doctor mode switches." \
    "Fixture tests cover 4K@60/120/HDR/VRR; dynamic refresh text works; zero regression on 4K@30 SDR baseline."

ensure_issue \
    "Remote: HDMI-CEC adapters" \
    "help wanted,area:remote,needs-hardware-test,priority:P1" \
    "11-remote-hdmi-cec-adapters" \
    "Validate native HDMI-CEC and USB HDMI-CEC adapters (e.g., Pulse-Eight) with platform CEC classification and plasma-bigscreen-inputhandler." \
    "Exact cec-ctl output across native/USB vs tunneled cec-DP-* adapters; reliable TV remote navigation without double-input." \
    "Native/USB CEC classified distinctly from cec-DP-* tunnels; real-device navigation verified; fixture tests added."

ensure_issue \
    "Remote: Bluetooth/RF controllers" \
    "help wanted,good first issue,area:remote,needs-hardware-test,priority:P1" \
    "12-remote-bluetoothrf-controllers" \
    "Add data-driven remote profiles for common Bluetooth and 2.4G RF TV remotes/air-mice and verify controller ergonomics." \
    "Vendor/Product IDs, >255 scancodes dropped by XKB/Wayland, and uaccess EVIOCSKEYCODE_V2 behavior on Bluetooth HID devices." \
    "Profiles load without code edits; --apply/--status/--diagnose/--reset verified; unit tests validate profile matching."

ensure_issue \
    "Streaming: browser DRM compatibility" \
    "help wanted,area:compatibility,area:docs,needs-hardware-test,priority:P2" \
    "13-streaming-browser-drm-compatibility" \
    "Document honest, reproducible browser Widevine/DRM compatibility observations (Netflix, Disney+, Prime Video) across Linux GPUs and distros." \
    "Observed stream resolution/codec caps (e.g. Widevine L3 limits), 10-foot ergonomics, and MPRIS auto-pause reliability in browsers." \
    "Factual compatibility documentation distinguishing VA-API decode from DRM resolution caps; zero DRM circumvention."

ensure_issue \
    "Installer: transactional install and rollback" \
    "help wanted,area:installer,platform:atomic,platform:mutable,needs-hardware-test,priority:P0" \
    "14-installer-transactional-install-and-rollback" \
    "Harden install.sh, nextgen-manifest.py, and rollback-tv-setup.sh for manifest-tracked installs, timestamped backups, and key-scoped Flatpak patching." \
    "Upgrade paths from pre-manifest installs, partial failure recovery, and missing optional tools (gcc/bwrap/flatpak)." \
    "Temp-HOME tests prove pre-existing configs and unrelated Flatpak overrides survive install + rollback intact; --dry-run writes nothing."

ensure_issue \
    "QA: hardware test matrix and CI" \
    "help wanted,good first issue,area:compatibility,area:docs,priority:P0" \
    "15-qa-hardware-test-matrix-and-ci" \
    "Expand GitHub Actions CI checks, anonymized hardware fixtures, and standardized manual hardware acceptance reporting." \
    "Real-world anonymized kscreen-doctor/vainfo/cec-ctl fixtures needed from AMD, NVIDIA, and mutable distros." \
    "CI passes unit/syntax/shellcheck/C-syntax/link checks on every PR and clearly notes hardware testing remains manual."

ensure_issue \
    "UX: accessibility and translations" \
    "help wanted,good first issue,area:docs,priority:P2" \
    "16-ux-accessibility-and-translations" \
    "Audit and improve 10-foot accessibility (high-contrast focus rings, large text, screen reader/keyboard reachability) and i18n readiness." \
    "Hardcoded English QML strings, focus contrast across Plasma themes, and Orca/Qt accessibility under Plasma Bigscreen Wayland." \
    "Interactive QML controls have clear focus rings and D-Pad reachability; strings wrapped in i18n(); zero QML errors."

# ---------------------------------------------------------------------------
# 3. Optional GitHub Project v2 Board
# ---------------------------------------------------------------------------
if [ "$WITH_PROJECT" -eq 1 ]; then
    echo ""
    echo "--- Step 3: GitHub Project v2 ($PROJECT_TITLE) ---"
    if [ "$APPLY" -eq 0 ]; then
        printf '[dry-run] gh project list --owner %q --format json\n' "$OWNER"
        printf '[dry-run] gh project create --owner %q --title %q (if not already present)\n' "$OWNER" "$PROJECT_TITLE"
        printf '[dry-run] gh project item-add <PROJECT_NUMBER> --owner %q --url <ISSUE_URL>\n' "$OWNER"
    else
        PROJECT_NUM="$(gh project list --owner "$OWNER" --format json \
            | python3 -c 'import sys,json; data=json.load(sys.stdin); items=data.get("projects", data) if isinstance(data, dict) else data; m=[p["number"] for p in items if p.get("title")=="'"$PROJECT_TITLE"'"]; print(m[0] if m else "")')"
        if [ -z "$PROJECT_NUM" ]; then
            PROJECT_NUM="$(gh project create --owner "$OWNER" --title "$PROJECT_TITLE" --format json \
                | python3 -c 'import sys,json; print(json.load(sys.stdin)["number"])')"
            echo "[created] Project v2 #$PROJECT_NUM: $PROJECT_TITLE"
        else
            echo "[reuse] Project v2 #$PROJECT_NUM: $PROJECT_TITLE"
        fi
        for url in "${CREATED_ISSUE_URLS[@]}"; do
            gh project item-add "$PROJECT_NUM" --owner "$OWNER" --url "$url" >/dev/null || true
            echo "[linked] $url -> Project #$PROJECT_NUM"
        done
    fi
fi

echo ""
echo "=== Seeder Complete ==="

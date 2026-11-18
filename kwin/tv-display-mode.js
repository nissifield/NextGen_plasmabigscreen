// KWin 6 Wayland event reporter for tv-display-mode daemon.
// Reports active window, fullscreen, minimized, and window list changes over DBus.

const TV_SERVICE = "org.nextgen.TvDisplayMode";
const TV_PATH = "/org/nextgen/TvDisplayMode";
const TV_IFACE = "org.nextgen.TvDisplayMode";

function serializeWindow(w) {
    if (!w) {
        return null;
    }
    let width = 0;
    let height = 0;
    try {
        if (w.frameGeometry) {
            width = Number(w.frameGeometry.width || 0);
            height = Number(w.frameGeometry.height || 0);
        }
    } catch (e) {}

    return {
        internalId: String(w.internalId || ""),
        resourceClass: String(w.resourceClass || ""),
        resourceName: String(w.resourceName || ""),
        desktopFileName: String(w.desktopFileName || ""),
        caption: String(w.caption || ""),
        pid: Number(w.pid || 0),
        fullScreen: Boolean(w.fullScreen),
        minimized: Boolean(w.minimized),
        active: Boolean(w.active),
        normalWindow: Boolean(w.normalWindow),
        desktopWindow: Boolean(w.desktopWindow),
        dock: Boolean(w.dock),
        specialWindow: Boolean(w.specialWindow),
        utility: Boolean(w.utility),
        dialog: Boolean(w.dialog),
        notification: Boolean(w.notification),
        onScreenDisplay: Boolean(w.onScreenDisplay),
        popupWindow: Boolean(w.popupWindow),
        transient: Boolean(w.transient),
        skipSwitcher: Boolean(w.skipSwitcher),
        windowType: Number(w.windowType || 0),
        layer: Number(w.layer || 0),
        width: width,
        height: height
    };
}

function isRelevantWindow(w) {
    if (!w) {
        return false;
    }
    if (w.desktopWindow || w.dock || w.specialWindow) {
        return false;
    }
    return true;
}

function pushState(reason) {
    try {
        const active = serializeWindow(workspace.activeWindow);
        const windows = [];
        const all = workspace.windowList();
        for (let i = 0; i < all.length; i++) {
            const w = all[i];
            if (!isRelevantWindow(w)) {
                continue;
            }
            windows.push(serializeWindow(w));
        }
        callDBus(
            TV_SERVICE,
            TV_PATH,
            TV_IFACE,
            "ReportKWinState",
            JSON.stringify({
                reason: reason,
                active: active,
                windows: windows
            })
        );
    } catch (e) {
        // Ignore transient DBus or window teardown errors
    }
}

function hookSignal(sig, reason) {
    if (sig && typeof sig.connect === "function") {
        sig.connect(() => pushState(reason));
    }
}

function ensureStremioInitialFullscreen(w) {
    if (!w || w._stremioInitFs || !w.normalWindow) {
        return;
    }
    const cls = String(w.resourceClass || "").toLowerCase();
    const df = String(w.desktopFileName || "").toLowerCase();
    if (cls === "com.stremio.stremio" || df === "com.stremio.stremio") {
        w._stremioInitFs = true;
        if (!w.fullScreen) {
            try {
                w.fullScreen = true;
            } catch (e) {}
        }
    }
}

function hookWindow(w) {
    if (!isRelevantWindow(w) || w._tvDisplayHooked) {
        return;
    }
    w._tvDisplayHooked = true;
    hookSignal(w.fullScreenChanged, "fullScreenChanged");
    hookSignal(w.minimizedChanged, "minimizedChanged");
    hookSignal(w.activeChanged, "activeChanged");
    hookSignal(w.captionChanged, "captionChanged");
    hookSignal(w.desktopFileNameChanged, "desktopFileNameChanged");
}

workspace.windowActivated.connect((w) => {
    if (w) {
        hookWindow(w);
    }
    pushState("windowActivated");
});

workspace.windowAdded.connect((w) => {
    hookWindow(w);
    ensureStremioInitialFullscreen(w);
    pushState("windowAdded");
});

workspace.windowRemoved.connect(() => {
    pushState("windowRemoved");
});

const existing = workspace.windowList();
for (let i = 0; i < existing.length; i++) {
    hookWindow(existing[i]);
}

pushState("init");

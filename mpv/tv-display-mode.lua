-- mpv Lua hook for tv-display-mode
-- Writes current video resolution and playback state to JSON so the host daemon
-- can switch DP-1 to 4K@30 for >1080p playback and back to 1080p@60 when stopped/paused.

local utils = require("mp.utils")

local function get_pid()
    if utils.getpid then
        return utils.getpid()
    end
    local f = io.open("/proc/self/stat", "r")
    if f then
        local line = f:read("*l")
        f:close()
        if line then
            local pid = line:match("^(%d+)")
            if pid then
                return tonumber(pid)
            end
        end
    end
    return 0
end

local PID = get_pid()
local HOME = assert(os.getenv("HOME"), "HOME not set")
local FLATPAK_ID = os.getenv("FLATPAK_ID") or ""

local function choose_state_dir()
    if FLATPAK_ID == "org.jellyfin.JellyfinDesktop" then
        return HOME .. "/.var/app/org.jellyfin.JellyfinDesktop/data/jellyfin-desktop/tv-display-mode"
    end
    return HOME .. "/.local/state/tv-display-mode"
end

local STATE_DIR = choose_state_dir()
local STATE_FILE = FLATPAK_ID ~= ""
    and string.format("%s/mpv-%s-%d.json", STATE_DIR, FLATPAK_ID, PID)
    or string.format("%s/mpv-%d.json", STATE_DIR, PID)

local function ensure_dir(path)
    if utils.file_info(path) then
        return true
    end
    -- Create parent dirs via subprocess only once if missing
    mp.command_native({
        name = "subprocess",
        playback_only = false,
        capture_stdout = false,
        args = {"mkdir", "-p", path},
    })
    return utils.file_info(path) ~= nil
end

local function json_escape(s)
    if not s then
        return ""
    end
    s = tostring(s)
    s = s:gsub("\\", "\\\\")
    s = s:gsub('"', '\\"')
    s = s:gsub("\n", "\\n")
    s = s:gsub("\r", "\\r")
    s = s:gsub("\t", "\\t")
    return s
end

local function write_state()
    if not ensure_dir(STATE_DIR) then
        return
    end
    local w = mp.get_property_number("video-params/w", 0) or 0
    local h = mp.get_property_number("video-params/h", 0) or 0
    local paused = mp.get_property_bool("pause", false)
    local idle = mp.get_property_bool("idle-active", false)
    local title = mp.get_property("media-title", "") or ""
    local path = mp.get_property("path", "") or ""
    local now = os.time()

    local payload = string.format(
        '{"pid":%d,"width":%d,"height":%d,"paused":%s,"idle":%s,"title":"%s","path":"%s","flatpak_id":"%s","updated_at":%d}\n',
        PID,
        math.floor(w),
        math.floor(h),
        paused and "true" or "false",
        idle and "true" or "false",
        json_escape(title),
        json_escape(path),
        json_escape(FLATPAK_ID),
        now
    )

    local tmp = STATE_FILE .. ".tmp"
    local f = io.open(tmp, "w")
    if f then
        f:write(payload)
        f:close()
        os.rename(tmp, STATE_FILE)
    end
end

local function remove_state()
    os.remove(STATE_FILE)
    os.remove(STATE_FILE .. ".tmp")
end

mp.observe_property("video-params/w", "number", write_state)
mp.observe_property("video-params/h", "number", write_state)
mp.observe_property("pause", "bool", write_state)
mp.observe_property("idle-active", "bool", write_state)
mp.register_event("file-loaded", write_state)
mp.register_event("end-file", write_state)
mp.register_event("shutdown", remove_state)

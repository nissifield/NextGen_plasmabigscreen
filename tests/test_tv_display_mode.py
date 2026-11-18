#!/usr/bin/env python3
"""Unit tests for tv-display-mode decision logic, mode selection, debouncer, and parsers."""

import importlib.machinery
import importlib.util
import json
import os
import tempfile
import unittest

BIN_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin", "tv-display-mode"))
loader = importlib.machinery.SourceFileLoader("tv_display_mode", BIN_PATH)
spec = importlib.util.spec_from_loader("tv_display_mode", loader)
assert spec is not None
mod = importlib.util.module_from_spec(spec)
loader.exec_module(mod)


SAMPLE_KSCREEN_JSON = json.dumps(
    {
        "outputs": [
            {
                "name": "DP-1",
                "enabled": True,
                "connected": True,
                "currentModeId": "12",
                "preferredModes": ["1"],
                "modes": [
                    {"id": "1", "name": "3840x2160@30", "refreshRate": 30.0, "size": {"width": 3840, "height": 2160}},
                    {"id": "7", "name": "3840x2160@30", "refreshRate": 30.0, "size": {"width": 3840, "height": 2160}},
                    {"id": "12", "name": "1920x1080@60", "refreshRate": 60.0, "size": {"width": 1920, "height": 1080}},
                    {"id": "13", "name": "1920x1080@60", "refreshRate": 60.0, "size": {"width": 1920, "height": 1080}},
                    {"id": "14", "name": "1920x1080@60", "refreshRate": 59.94, "size": {"width": 1920, "height": 1080}},
                ],
            }
        ]
    }
)


class TestModeResolution(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = json.loads(json.dumps(mod.DEFAULT_CONFIG))

    def test_selects_preferred_4k_and_primary_1080p(self) -> None:
        info = mod.parse_kscreen_json(SAMPLE_KSCREEN_JSON, "DP-1", self.cfg)
        self.assertEqual(info["mode_4k"]["id"], "1")
        self.assertEqual(info["mode_1080p"]["id"], "12")
        self.assertEqual(info["current_mode_id"], "12")

    def test_skips_redundant_switch(self) -> None:
        info = mod.parse_kscreen_json(SAMPLE_KSCREEN_JSON, "DP-1", self.cfg)
        self.assertTrue(mod.is_already_target_mode(info, "1080p", self.cfg))
        self.assertFalse(mod.is_already_target_mode(info, "4k", self.cfg))

        res_noop = mod.apply_display_mode("1080p", self.cfg, dry_run=True, kscreen_info=info)
        self.assertFalse(res_noop["changed"])

        res_switch = mod.apply_display_mode("4k", self.cfg, dry_run=True, kscreen_info=info)
        self.assertTrue(res_switch["changed"])
        self.assertEqual(res_switch["mode_id"], "1")
        self.assertIn("output.DP-1.mode.1", res_switch["command"])


class TestDecisionLogic(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = json.loads(json.dumps(mod.DEFAULT_CONFIG))
        self.no_ancestry = lambda _pid: []

    def test_steam_active_overrides_4k_playback_and_manual_4k(self) -> None:
        kwin_state = {
            "active": {
                "resourceClass": "steamwebhelper",
                "resourceName": "steamwebhelper",
                "desktopFileName": "steam",
                "caption": "Steam Big Picture Mode",
                "pid": 4069,
                "fullScreen": True,
                "minimized": False,
            },
            "windows": [],
        }
        pbs = [
            mod.PlaybackInfo(
                player="org.mpris.MediaPlayer2.JellyfinDesktop.test",
                status="Playing",
                width=3840,
                height=2160,
                requires_4k=True,
                source="mpv_lua",
            )
        ]
        dec_auto = mod.decide_target_mode(kwin_state, pbs, "auto", self.cfg, self.no_ancestry)
        self.assertEqual(dec_auto["target"], "1080p")
        self.assertEqual(dec_auto["reason"], "steam_priority")
        self.assertTrue(dec_auto["immediate"])

        dec_manual = mod.decide_target_mode(kwin_state, pbs, "4k", self.cfg, self.no_ancestry)
        self.assertEqual(dec_manual["target"], "1080p")
        self.assertEqual(dec_manual["reason"], "steam_priority")

    def test_steam_fullscreen_foreground_wins_even_if_unfocused(self) -> None:
        kwin_state = {
            "active": {
                "resourceClass": "plasmashell",
                "caption": "Notification",
                "pid": 999,
                "fullScreen": False,
                "minimized": False,
            },
            "windows": [
                {
                    "resourceClass": "steam_app_1245620",
                    "caption": "ELDEN RING",
                    "pid": 12345,
                    "fullScreen": True,
                    "minimized": False,
                }
            ],
        }
        pbs = [
            mod.PlaybackInfo(
                player="mpv:222",
                status="Playing",
                width=3840,
                height=2160,
                requires_4k=True,
                source="mpv_lua",
            )
        ]
        dec = mod.decide_target_mode(kwin_state, pbs, "auto", self.cfg, self.no_ancestry)
        self.assertEqual(dec["target"], "1080p")
        self.assertEqual(dec["reason"], "steam_priority")

    def test_steam_child_game_detected_via_pid_ancestry(self) -> None:
        kwin_state = {
            "active": {
                "resourceClass": "hollow_knight.x86_64",
                "caption": "Hollow Knight",
                "pid": 5555,
                "fullScreen": True,
                "minimized": False,
            },
            "windows": [],
        }
        ancestry = lambda _pid: [
            {"pid": 5555, "ppid": 5000, "comm": "hollow_knight", "cmdline": "./hollow_knight"},
            {"pid": 5000, "ppid": 4031, "comm": "reaper", "cmdline": "reaper SteamLaunch AppId=367520"},
        ]
        dec = mod.decide_target_mode(kwin_state, [], "auto", self.cfg, ancestry)
        self.assertEqual(dec["target"], "1080p")
        self.assertEqual(dec["reason"], "steam_priority")

    def test_4k_vs_1080p_playback(self) -> None:
        kwin_jellyfin = {
            "active": {
                "resourceClass": "org.jellyfin.JellyfinDesktop",
                "caption": "Jellyfin Desktop",
                "pid": 5888,
                "fullScreen": True,
                "minimized": False,
            },
            "windows": [],
        }
        pb_4k = [
            mod.PlaybackInfo(
                player="org.mpris.MediaPlayer2.JellyfinDesktop.x",
                status="Playing",
                width=3840,
                height=2160,
                requires_4k=True,
                source="jellyfin_log",
            )
        ]
        # With default auto_4k_video_switch=False, 4K playback stays at 1080p unless manual Movie Mode ("4k") is chosen
        dec_disabled = mod.decide_target_mode(kwin_jellyfin, pb_4k, "auto", self.cfg, self.no_ancestry)
        self.assertEqual(dec_disabled["target"], "1080p")
        self.assertEqual(dec_disabled["reason"], "auto_default_1080p")

        dec_movie_mode = mod.decide_target_mode(kwin_jellyfin, pb_4k, "4k", self.cfg, self.no_ancestry)
        self.assertEqual(dec_movie_mode["target"], "4k")
        self.assertEqual(dec_movie_mode["reason"], "manual_override_4k")

        # When opt-in auto_4k_video_switch=True, 4K playback auto-switches while 1080p/paused stays 1080p
        cfg_auto = dict(self.cfg, auto_4k_video_switch=True)
        dec_4k = mod.decide_target_mode(kwin_jellyfin, pb_4k, "auto", cfg_auto, self.no_ancestry)
        self.assertEqual(dec_4k["target"], "4k")
        self.assertEqual(dec_4k["reason"], "auto_4k_video")

        pb_1080 = [
            mod.PlaybackInfo(
                player="org.mpris.MediaPlayer2.JellyfinDesktop.x",
                status="Playing",
                width=1920,
                height=1080,
                requires_4k=False,
                source="jellyfin_log",
            )
        ]
        dec_1080 = mod.decide_target_mode(kwin_jellyfin, pb_1080, "auto", cfg_auto, self.no_ancestry)
        self.assertEqual(dec_1080["target"], "1080p")
        self.assertEqual(dec_1080["reason"], "auto_default_1080p")

        pb_paused = [
            mod.PlaybackInfo(
                player="org.mpris.MediaPlayer2.JellyfinDesktop.x",
                status="Paused",
                width=3840,
                height=2160,
                requires_4k=True,
                source="jellyfin_log",
            )
        ]
        dec_paused = mod.decide_target_mode(kwin_jellyfin, pb_paused, "auto", cfg_auto, self.no_ancestry)
        self.assertEqual(dec_paused["target"], "1080p")

    def test_4k_hint_regex(self) -> None:
        self.assertTrue(mod.text_indicates_4k("Dune.Part.Two.2024.2160p.WEB-DL.mkv"))
        self.assertTrue(mod.text_indicates_4k("Japan in 4K HDR 60fps"))
        self.assertTrue(mod.text_indicates_4k("Movie UHD BluRay"))
        self.assertFalse(mod.text_indicates_4k("YouTube on TV"))
        self.assertFalse(mod.text_indicates_4k("1080p Trailer"))


class TestDebouncer(unittest.TestCase):
    def test_debounce_prevents_flicker_and_steam_is_immediate(self) -> None:
        d = mod.Debouncer(
            debounce_to_4k_sec=1.5,
            debounce_to_1080p_sec=2.0,
            min_switch_interval_sec=1.5,
            last_applied_target="1080p",
            last_switch_time=0.0,
        )
        # Brief 4K trigger at t=10.0 does not switch immediately
        target, retry = d.evaluate("4k", False, "auto_4k_video", now=10.0)
        self.assertIsNone(target)
        self.assertAlmostEqual(retry or 0.0, 1.5, places=2)

        # Reverts to 1080p at t=10.8 -> cancels pending 4k without ever switching
        target, retry = d.evaluate("1080p", False, "auto_default_1080p", now=10.8)
        self.assertIsNone(target)
        self.assertIsNone(retry)
        self.assertEqual(d.last_applied_target, "1080p")

        # Continuous 4K trigger from t=20.0 -> switches at t=21.5
        target, _ = d.evaluate("4k", False, "auto_4k_video", now=20.0)
        self.assertIsNone(target)
        target, _ = d.evaluate("4k", False, "auto_4k_video", now=21.6)
        self.assertEqual(target, "4k")

        # Video stops at t=30.0 -> waits 2.0s before reverting to 1080p
        target, retry = d.evaluate("1080p", False, "auto_default_1080p", now=30.0)
        self.assertIsNone(target)
        self.assertAlmostEqual(retry or 0.0, 2.0, places=2)

        # Steam takes focus at t=30.2 -> IMMEDIATE 1080p switch!
        target, retry = d.evaluate("1080p", True, "steam_priority", now=30.2)
        self.assertEqual(target, "1080p")
        self.assertIsNone(retry)


class TestParsersAndEnv(unittest.TestCase):
    def test_jellyfin_log_parser(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "jellyfin-desktop.log")
            with open(log, "w", encoding="utf-8") as fh:
                fh.write("2026-11-15 19:57:44 [debug] libmpv_render: Video source: 960x540 (1:1)\n")
                fh.write("2026-11-15 20:01:10 [debug] libmpv_render: Video source: 3840x2160 (1:1)\n")
            self.assertEqual(mod.parse_jellyfin_log_resolution([log]), (3840, 2160))

    def test_mpv_lua_state_reader_prunes_dead_pids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            live_file = os.path.join(tmp, "mpv-111.json")
            dead_file = os.path.join(tmp, "mpv-222.json")
            flatpak_live = os.path.join(tmp, "mpv-org.jellyfin.JellyfinDesktop-2.json")
            flatpak_dead = os.path.join(tmp, "mpv-org.kde.haruna-2.json")
            with open(live_file, "w", encoding="utf-8") as fh:
                json.dump({"pid": 111, "width": 3840, "height": 2160, "paused": False, "idle": False}, fh)
            with open(dead_file, "w", encoding="utf-8") as fh:
                json.dump({"pid": 222, "width": 3840, "height": 2160, "paused": False, "idle": False}, fh)
            with open(flatpak_live, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "pid": 2,
                        "flatpak_id": "org.jellyfin.JellyfinDesktop",
                        "width": 3840,
                        "height": 2160,
                        "paused": False,
                        "idle": False,
                    },
                    fh,
                )
            with open(flatpak_dead, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "pid": 2,
                        "flatpak_id": "org.kde.haruna",
                        "width": 3840,
                        "height": 2160,
                        "paused": False,
                        "idle": False,
                    },
                    fh,
                )

            states = mod.read_mpv_lua_states(
                [tmp],
                pid_alive_fn=lambda p: p == 111,
                running_flatpaks_fn=lambda: {"org.jellyfin.jellyfindesktop"},
            )
            self.assertEqual(len(states), 2)
            self.assertFalse(os.path.exists(dead_file))
            self.assertTrue(os.path.exists(flatpak_live))
            self.assertFalse(os.path.exists(flatpak_dead))

    def test_title_4k_heuristic_does_not_override_known_1080p(self) -> None:
        cfg = json.loads(json.dumps(mod.DEFAULT_CONFIG))
        cache = mod.FFprobeCache()
        mpv_states = [
            {
                "pid": 2,
                "flatpak_id": "org.jellyfin.JellyfinDesktop",
                "width": 1920,
                "height": 1080,
                "paused": False,
                "idle": False,
            }
        ]
        info_known_1080 = mod.resolve_mpris_playback(
            name="org.mpris.MediaPlayer2.JellyfinDesktop.test",
            status="Playing",
            metadata={"xesam:title": "Movie.2024.4K.Remaster.1080p.mkv"},
            pid=5888,
            kwin_state=None,
            cfg=cfg,
            ffprobe_cache=cache,
            mpv_states=mpv_states,
            jellyfin_log_fn=lambda: (0, 0),
            open_files_fn=lambda _p: [],
        )
        self.assertEqual((info_known_1080.width, info_known_1080.height), (1920, 1080))
        self.assertFalse(info_known_1080.requires_4k)
        self.assertEqual(info_known_1080.source, "mpv_lua")

        # When Stremio shim reports exact 4K dimensions, requires_4k=True via mpv_lua
        stremio_4k = mod.resolve_mpris_playback(
            name="org.mpris.MediaPlayer2.Stremio",
            status="Playing",
            metadata={"xesam:title": "Spider-Man: Brand New Day"},
            pid=6907,
            kwin_state=None,
            cfg=cfg,
            ffprobe_cache=cache,
            mpv_states=[
                {
                    "pid": 2,
                    "flatpak_id": "com.stremio.Stremio",
                    "width": 3840,
                    "height": 2160,
                    "paused": False,
                    "idle": False,
                }
            ],
            jellyfin_log_fn=lambda: (0, 0),
            open_files_fn=lambda _p: [],
        )
        self.assertEqual((stremio_4k.width, stremio_4k.height), (3840, 2160))
        self.assertTrue(stremio_4k.requires_4k)
        self.assertEqual(stremio_4k.source, "mpv_lua")

        # When resolution is unknown (e.g. Stremio without shim state), 4K title hint still works
        info_unknown_res = mod.resolve_mpris_playback(
            name="org.mpris.MediaPlayer2.Stremio",
            status="Playing",
            metadata={"xesam:title": "Movie.2024.2160p.UHD.mkv"},
            pid=6907,
            kwin_state=None,
            cfg=cfg,
            ffprobe_cache=cache,
            mpv_states=[],
            jellyfin_log_fn=lambda: (0, 0),
            open_files_fn=lambda _p: [],
        )
        self.assertTrue(info_unknown_res.requires_4k)
        self.assertEqual(info_unknown_res.source, "metadata_4k_hint")

    def test_resolve_and_apply_session_env_populates_os_environ(self) -> None:
        env = mod.resolve_session_env({})
        self.assertEqual(env["XDG_RUNTIME_DIR"], f"/run/user/{os.getuid()}")
        self.assertTrue(env["WAYLAND_DISPLAY"].startswith("wayland-"))
        self.assertTrue(bool(env.get("HOME")))

        saved = dict(os.environ)
        try:
            for k in ("XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS", "WAYLAND_DISPLAY"):
                os.environ.pop(k, None)
            mod.apply_session_env()
            self.assertEqual(os.environ["XDG_RUNTIME_DIR"], f"/run/user/{os.getuid()}")
            self.assertTrue(os.environ["WAYLAND_DISPLAY"].startswith("wayland-"))
            if os.path.exists(f"/run/user/{os.getuid()}/bus"):
                self.assertIn(f"/run/user/{os.getuid()}/bus", os.environ["DBUS_SESSION_BUS_ADDRESS"])
        finally:
            os.environ.clear()
            os.environ.update(saved)


class TestAutoPauseBackgroundMedia(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = dict(mod.DEFAULT_CONFIG, auto_pause_background_media=True)
        self.stremio_win = {
            "resourceClass": "com.stremio.Stremio",
            "resourceName": "stremio",
            "desktopFileName": "com.stremio.Stremio",
            "caption": "Stremio",
            "pid": 21677,
            "fullScreen": True,
            "minimized": False,
            "active": True,
            "normalWindow": True,
            "desktopWindow": False,
            "specialWindow": False,
            "onScreenDisplay": False,
            "notification": False,
            "popupWindow": False,
            "transient": False,
            "windowType": 0,
        }
        self.vacuumtube_win = {
            "resourceClass": "chromium-browser",
            "resourceName": "vacuumtube",
            "desktopFileName": "rocks.shy.VacuumTube",
            "caption": "VacuumTube",
            "pid": 31001,
            "fullScreen": True,
            "minimized": False,
            "active": True,
            "normalWindow": True,
            "desktopWindow": False,
            "specialWindow": False,
            "onScreenDisplay": False,
            "notification": False,
            "popupWindow": False,
            "transient": False,
            "windowType": 0,
        }
        self.stremio_mpris = {
            "bus_name": "org.mpris.MediaPlayer2.Stremio",
            "playback_status": "Playing",
            "can_pause": True,
            "desktop_entry": "com.stremio.Stremio",
            "identity": "Stremio",
            "pid": 21699,  # Flatpak xdg-dbus-proxy PID differs from window PID
        }
        self.vacuumtube_mpris = {
            "bus_name": "org.mpris.MediaPlayer2.chromium.instance31001",
            "playback_status": "Playing",
            "can_pause": True,
            "desktop_entry": "",  # VacuumTube omits DesktopEntry
            "identity": "VacuumTube",
            "pid": 31099,
        }
        self.jellyfin_mpris = {
            "bus_name": "org.mpris.MediaPlayer2.JellyfinDesktop",
            "playback_status": "Playing",
            "can_pause": True,
            "desktop_entry": "org.jellyfin.JellyfinDesktop",
            "identity": "Jellyfin Desktop",
            "pid": 41099,
        }

    def test_pause_when_returning_to_bigscreen_home_or_none_or_overlay(self) -> None:
        players = [self.stremio_mpris, self.vacuumtube_mpris]

        # active=None (all tasks minimized to Bigscreen Home)
        out_none = mod.select_mpris_players_to_pause(
            {"reason": "windowActivated", "active": None}, players, self.cfg
        )
        self.assertEqual([p["bus_name"] for p in out_none], [self.stremio_mpris["bus_name"], self.vacuumtube_mpris["bus_name"]])

        # active=plasmashell desktopWindow
        home_win = {
            "resourceClass": "plasmashell",
            "resourceName": "plasmashell",
            "desktopFileName": "",
            "caption": "",
            "pid": 2200,
            "normalWindow": False,
            "desktopWindow": True,
            "specialWindow": True,
            "onScreenDisplay": False,
            "notification": False,
            "popupWindow": False,
            "transient": False,
            "windowType": 1,
        }
        out_home = mod.select_mpris_players_to_pause(
            {"reason": "windowActivated", "active": home_win}, players, self.cfg
        )
        self.assertEqual(len(out_home), 2)

        # Bigscreen HomeOverlayWindow / SearchWindow (plasmashell non-normal layer overlay)
        overlay_win = dict(home_win, desktopWindow=False, specialWindow=False, windowType=0)
        out_overlay = mod.select_mpris_players_to_pause(
            {"reason": "windowActivated", "active": overlay_win}, players, self.cfg
        )
        self.assertEqual(len(out_overlay), 2)

    def test_switch_to_steam_or_another_app_pauses_only_background_players(self) -> None:
        steam_win = {
            "resourceClass": "steamwebhelper",
            "resourceName": "steamwebhelper",
            "desktopFileName": "steam",
            "caption": "Steam Big Picture Mode",
            "pid": 5001,
            "normalWindow": True,
        }
        out_steam = mod.select_mpris_players_to_pause(
            {"reason": "windowActivated", "active": steam_win},
            [self.stremio_mpris, self.vacuumtube_mpris],
            self.cfg,
        )
        self.assertEqual([p["bus_name"] for p in out_steam], [self.stremio_mpris["bus_name"], self.vacuumtube_mpris["bus_name"]])

        # Switching to VacuumTube pauses Stremio + Jellyfin, keeps VacuumTube playing (by Identity / Flatpak scope)
        scopes = {
            31001: "app-flatpak-rocks.shy.VacuumTube-31000.scope",
            31099: "app-flatpak-rocks.shy.VacuumTube-31000.scope",
            21677: "app-flatpak-com.stremio.Stremio-21600.scope",
            21699: "app-flatpak-com.stremio.Stremio-21600.scope",
        }
        out_vt = mod.select_mpris_players_to_pause(
            {"reason": "windowActivated", "active": self.vacuumtube_win},
            [self.stremio_mpris, self.vacuumtube_mpris, self.jellyfin_mpris],
            self.cfg,
            flatpak_scope_fn=lambda pid: scopes.get(pid, ""),
        )
        self.assertEqual(
            [p["bus_name"] for p in out_vt],
            [self.stremio_mpris["bus_name"], self.jellyfin_mpris["bus_name"]],
        )

    def test_never_pauses_focused_player_by_pid_scope_or_desktop_entry(self) -> None:
        # Stremio focused matches via DesktopEntry even if flatpak scope is unavailable
        out_stremio = mod.select_mpris_players_to_pause(
            {"reason": "windowActivated", "active": self.stremio_win},
            [self.stremio_mpris],
            self.cfg,
            flatpak_scope_fn=lambda _p: "",
        )
        self.assertEqual(out_stremio, [])

        # Unknown DesktopEntry/Identity chromium player matches if PID matches directly
        direct_pid_mpris = {
            "bus_name": "org.mpris.MediaPlayer2.mpv",
            "playback_status": "Playing",
            "can_pause": True,
            "desktop_entry": "",
            "identity": "X",
            "pid": 9999,
        }
        mpv_win = {"resourceClass": "other", "pid": 9999, "normalWindow": True}
        self.assertEqual(
            mod.select_mpris_players_to_pause(
                {"reason": "windowActivated", "active": mpv_win},
                [direct_pid_mpris],
                self.cfg,
                flatpak_scope_fn=lambda _p: "",
            ),
            [],
        )

        # Flatpak scope match even with mismatched/empty DesktopEntry + Identity
        vt_no_id = dict(self.vacuumtube_mpris, identity="")
        self.assertEqual(
            mod.select_mpris_players_to_pause(
                {"reason": "windowActivated", "active": self.vacuumtube_win},
                [vt_no_id],
                self.cfg,
                flatpak_scope_fn=lambda pid: "app-flatpak-rocks.shy.VacuumTube-1.scope" if pid in {31001, 31099} else "",
            ),
            [],
        )

    def test_ignores_transients_osds_mode_toggle_polkit_fallback_and_init(self) -> None:
        players = [self.stremio_mpris]

        # Ignored reasons
        for reason in ("fallback", "init"):
            self.assertEqual(
                mod.select_mpris_players_to_pause({"reason": reason, "active": None}, players, self.cfg),
                [],
            )

        # OSD / notification / popupWindow / transient non-normal / Polkit / Movie Mode toggle
        ignored_windows = [
            {"resourceClass": "plasmashell", "onScreenDisplay": True, "normalWindow": False},
            {"resourceClass": "plasmashell", "notification": True, "normalWindow": False, "windowType": 10},
            {"resourceClass": "stremio", "popupWindow": True, "normalWindow": False},
            {"resourceClass": "stremio", "transient": True, "normalWindow": False, "desktopWindow": False},
            {"resourceClass": "tv-movie-mode", "desktopFileName": "tv-movie-mode", "caption": "Movie Mode", "normalWindow": True},
            {"resourceClass": "", "desktopFileName": "", "caption": "1080p Mode (Steam Priority)", "normalWindow": True},
            {"resourceClass": "polkit-kde-authentication-agent-1", "normalWindow": True},
        ]
        for win in ignored_windows:
            self.assertEqual(
                mod.select_mpris_players_to_pause({"reason": "windowActivated", "active": win}, players, self.cfg),
                [],
                msg=f"Expected transient window to be ignored: {win}",
            )

    def test_paused_stays_paused_and_filters_playerctld_canpause_and_disabled(self) -> None:
        paused_mpris = dict(self.stremio_mpris, playback_status="Paused")
        cant_pause_mpris = dict(self.jellyfin_mpris, can_pause=False)
        playerctld_mpris = {
            "bus_name": "org.mpris.MediaPlayer2.playerctld",
            "playback_status": "Playing",
            "can_pause": True,
            "desktop_entry": "",
            "identity": "playerctld",
            "pid": 1234,
        }
        # Returning to Stremio while paused never produces any action
        self.assertEqual(
            mod.select_mpris_players_to_pause(
                {"reason": "windowActivated", "active": self.stremio_win},
                [paused_mpris, cant_pause_mpris, playerctld_mpris],
                self.cfg,
            ),
            [],
        )
        # Returning home ignores Paused, CanPause=False, and playerctld
        self.assertEqual(
            mod.select_mpris_players_to_pause(
                {"reason": "windowActivated", "active": None},
                [paused_mpris, cant_pause_mpris, playerctld_mpris],
                self.cfg,
            ),
            [],
        )
        # Disabled in config
        disabled_cfg = dict(self.cfg, auto_pause_background_media=False)
        self.assertEqual(
            mod.select_mpris_players_to_pause(
                {"reason": "windowActivated", "active": None},
                [self.stremio_mpris],
                disabled_cfg,
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)

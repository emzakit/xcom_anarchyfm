"""XiPod unit tests — settings, config writers, library. No audio hardware needed.

Run from the project root:
    venv\\Scripts\\python.exe -m unittest discover -s tests -v
"""

import os
import sys
import json
import time
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import mms_config
import process_utils
import settings as settings_mod
from settings import EngineSettings
from library import MusicLibrary
from setup import STATE_FOLDERS
import addons

_ORIG_PRESETS_PATH = None
_TMP_PRESETS_DIR = None


def setUpModule():
    """Redirect user-preset persistence to a temp file so tests never
    touch the real project root's xipod_presets.json."""
    global _ORIG_PRESETS_PATH, _TMP_PRESETS_DIR
    _ORIG_PRESETS_PATH = settings_mod._PRESETS_PATH
    _TMP_PRESETS_DIR = tempfile.mkdtemp()
    settings_mod._PRESETS_PATH = os.path.join(_TMP_PRESETS_DIR, "xipod_presets.json")


def tearDownModule():
    settings_mod._PRESETS_PATH = _ORIG_PRESETS_PATH


def _reset_user_presets():
    """Clear the module-level preset slots and the temp JSON file."""
    for k in list(settings_mod.USER_PRESETS):
        settings_mod._set_user_preset_slot(k, {})
    if os.path.exists(settings_mod._PRESETS_PATH):
        os.remove(settings_mod._PRESETS_PATH)


class TestSettingsRoundTrip(unittest.TestCase):

    def test_ini_round_trip(self):
        """Settings written via get_settings_lines parse back identically."""
        s1 = EngineSettings()
        s1.toggles["battle"] = True
        s1.volumes["avenger"] = 0.35
        s1.radio["geoscape"] = True
        s1.loop["combat"] = True
        s1.random_start["explore"] = True
        s1.presets["battle"] = "field_radio"
        s1.fx_params["bassboost"] = 6

        with tempfile.TemporaryDirectory() as tmp:
            ini = os.path.join(tmp, "XComXiPod.ini")
            with open(ini, "w", encoding="utf-8") as f:
                f.write("[AnarchyRadioFM.XiPod_Settings]\n")
                f.write("\n".join(s1.get_settings_lines()) + "\n")

            s2 = EngineSettings()
            s2.load_from_ini(ini)

        self.assertEqual(s1.toggles, s2.toggles)
        self.assertEqual(s1.volumes, s2.volumes)
        self.assertEqual(s1.radio, s2.radio)
        self.assertEqual(s1.loop, s2.loop)
        self.assertEqual(s1.random_start, s2.random_start)
        self.assertEqual(s1.presets, s2.presets)
        self.assertEqual(s1.fx_params, s2.fx_params)


class TestMMSConfig(unittest.TestCase):

    def test_tactical_uses_double_backslash_continuation(self):
        """UE3 ini line continuation is '\\\\' — a single backslash breaks MMS."""
        content = mms_config._build_tactical_ini(True)
        for line in content.splitlines():
            if line.rstrip().endswith("\\"):
                self.assertTrue(line.rstrip().endswith("\\\\"),
                                f"single-backslash continuation: {line!r}")
        self.assertIn("+CombatDefs=", content)
        self.assertIn("+ExploreDefs=", content)

    def test_tactical_disabled_has_no_active_defs(self):
        content = mms_config._build_tactical_ini(False)
        for line in content.splitlines():
            if line.startswith("+CombatDefs") or line.startswith("+ExploreDefs"):
                self.fail(f"active def in disabled tactical ini: {line!r}")

    def test_strategy_geoscape_follows_toggle(self):
        toggles_on = {"avenger": True, "geoscape": True, "squadselect": True,
                      "victory": True, "defeat": True}
        toggles_off = dict(toggles_on, geoscape=False)
        self.assertIn("eSSG_Geoscape", self._active_lines(toggles_on))
        self.assertNotIn("eSSG_Geoscape", self._active_lines(toggles_off))

    def test_strategy_loss_follows_defeat_toggle(self):
        toggles = {"avenger": True, "geoscape": True, "squadselect": True,
                   "victory": True, "defeat": False}
        self.assertNotIn("eSSG_Loss)", self._active_lines(toggles))
        toggles["defeat"] = True
        self.assertIn("eSSG_Loss)", self._active_lines(toggles))

    @staticmethod
    def _active_lines(toggles):
        content = mms_config._build_strategy_ini(toggles)
        return "\n".join(l for l in content.splitlines() if not l.startswith(";"))


class TestLibrary(unittest.TestCase):

    def _make_library(self, tmp, folders):
        for folder, files in folders.items():
            path = os.path.join(tmp, folder)
            os.makedirs(path, exist_ok=True)
            for name in files:
                with open(os.path.join(path, name), "wb") as f:
                    f.write(b"\x00")
        lib = MusicLibrary()
        lib.load(tmp)
        return lib

    def test_resolve_playlist_loop_and_radio_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = self._make_library(tmp, {
                "STATE_AVENGER": ["a.mp3", "b.ogg", "notes.txt"],
                "STATE_AVENGER_LOOP": [],
                "STATE_RESISTANCE_RADIO": ["radio.mp3"],
            })
            # txt files are ignored
            self.assertEqual(len(lib.resolve_playlist("state_avenger")), 2)
            # empty _loop folder falls back to the base folder
            self.assertEqual(len(lib.resolve_playlist("state_avenger", use_loop=True)), 2)
            # radio pulls from the shared folder
            radio = lib.resolve_playlist("state_avenger", use_radio=True)
            self.assertEqual([t["name"] for t in radio], ["radio.mp3"])

    def test_export_ini_preserves_unknown_keys_and_owns_presets(self):
        try:
            with tempfile.TemporaryDirectory() as tmp:
                config_dir = os.path.join(tmp, "XComGame", "Config")
                logs_dir = os.path.join(tmp, "XComGame", "Logs")
                os.makedirs(config_dir)
                os.makedirs(logs_dir)
                log_path = os.path.join(logs_dir, "Launch.log")
                ini_path = os.path.join(config_dir, "XComXiPod.ini")

                # Simulate a file previously written by the game: unknown
                # keys, a stale UserPreset1, and a UserPreset2 whose slot
                # has since been cleared.
                with open(ini_path, "w", encoding="utf-8") as f:
                    f.write("[AnarchyRadioFM.XiPod_Settings]\n")
                    f.write("bEnableAvenger=False\n")
                    f.write("CurrentScreenType=Avenger\n")
                    f.write("UserPreset1=bassboost:12|radio:False\n")
                    f.write("UserPreset2=echodelay:100\n")

                s = EngineSettings()
                s.save_user_preset(1, {"bassboost": 3, "radio": True})

                music = os.path.join(tmp, "music")
                lib = self._make_library(music, {
                    "STATE_AVENGER": ["My Track.mp3"],
                })
                lib.export_ini(log_path, s.get_settings_lines())

                with open(ini_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Existing value wins over engine default (True)
                self.assertIn("bEnableAvenger=False", content)
                # Unknown keys survive the rewrite
                self.assertIn("CurrentScreenType=Avenger", content)
                # Python's fresh preset beats the game's stale line
                self.assertIn("UserPreset1=bassboost:3|radio:True", content)
                # Cleared slot is dropped, not resurrected from the file
                self.assertNotIn("UserPreset2", content)
                # Track manifest present, extension stripped for display
                self.assertIn('TrackList="0|state_avenger|My Track"', content)
                # Section headers use the mod's script package (AnarchyRadioFM),
                # so the in-game mod reads the settings + track manifest.
                self.assertIn("[AnarchyRadioFM.XiPod_Settings]", content)
                self.assertIn("[AnarchyRadioFM.XiPod_UI]", content)
        finally:
            _reset_user_presets()


class TestMusicAddons(unittest.TestCase):
    """Workshop packs are discovered and merged in place — never copied."""

    @staticmethod
    def _make_mod(tmp, mod_id, descriptor, files):
        mod_root = os.path.join(tmp, mod_id)
        for rel, names in files.items():
            d = os.path.join(mod_root, *rel.split("/"))
            os.makedirs(d, exist_ok=True)
            for n in names:
                with open(os.path.join(d, n), "wb") as f:
                    f.write(b"\x00")
        with open(os.path.join(mod_root, f"{mod_id}_xipod.json"), "w",
                  encoding="utf-8") as f:
            json.dump(descriptor, f)
        return mod_root

    def test_scan_parses_metadata_and_guards_bad_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            workshop = os.path.join(tmp, "workshop")
            os.makedirs(workshop)
            self._make_mod(workshop, "12345", {
                "name": "Test Pack",
                "author": "Someone",
                "description": "A pack.",
                "genres": ["Rock", "  Metal  "],          # whitespace trimmed
                "folders": {
                    "state_avenger": "music/avenger",      # lowercase key
                    "STATE_GEOSCAPE": "../../outside",     # traversal attempt
                    "STATE_NOT_REAL": "music/avenger",     # unknown state
                },
            }, {"music/avenger": ["song.mp3"]})

            found = addons.scan(workshop)
            self.assertEqual(len(found), 1)
            a = found[0]
            self.assertEqual(a.id, "12345")
            self.assertEqual(a.name, "Test Pack")
            self.assertEqual(a.genres, ["Metal", "Rock"])
            self.assertTrue(a.enabled)   # absent from map = enabled

            # Only the valid, in-bounds state folder survives.
            self.assertEqual(a.folders_resolved(), ["state_avenger"])

    def test_genres_accept_comma_separated_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            workshop = os.path.join(tmp, "workshop")
            os.makedirs(workshop)
            self._make_mod(workshop, "1", {"name": "P", "genres": "Rock, Funk"},
                           {"music": ["a.mp3"]})
            self.assertEqual(addons.scan(workshop)[0].genres, ["Funk", "Rock"])

    def test_enabled_map_disables_and_library_drops_tracks(self):
        with tempfile.TemporaryDirectory() as tmp:
            workshop = os.path.join(tmp, "workshop")
            os.makedirs(workshop)
            self._make_mod(workshop, "999", {
                "name": "Pack", "folders": {"STATE_AVENGER": "music/av"},
            }, {"music/av": ["addon.mp3"]})

            music = os.path.join(tmp, "library", "STATE_AVENGER")
            os.makedirs(music)
            with open(os.path.join(music, "mine.mp3"), "wb") as f:
                f.write(b"\x00")
            root = os.path.dirname(music)

            lib = MusicLibrary()
            lib.load(root, addons=addons.scan(workshop))
            names = [t["name"] for t in lib.library["state_avenger"]]
            self.assertEqual(sorted(names), ["addon.mp3", "mine.mp3"])
            # Nothing was copied into the user's folder.
            self.assertFalse(os.path.exists(os.path.join(music, "addon.mp3")))

            off = addons.scan(workshop, {"999": False})
            lib.load(root, addons=off)
            self.assertEqual([t["name"] for t in lib.library["state_avenger"]],
                             ["mine.mp3"])

    def test_user_folder_wins_duplicate_filenames(self):
        with tempfile.TemporaryDirectory() as tmp:
            workshop = os.path.join(tmp, "workshop")
            os.makedirs(workshop)
            self._make_mod(workshop, "a1", {
                "name": "A", "folders": {"STATE_AVENGER": "m"},
            }, {"m": ["same.mp3"]})
            self._make_mod(workshop, "b2", {
                "name": "B", "folders": {"STATE_AVENGER": "m"},
            }, {"m": ["same.mp3"]})

            music = os.path.join(tmp, "library", "STATE_AVENGER")
            os.makedirs(music)
            with open(os.path.join(music, "same.mp3"), "wb") as f:
                f.write(b"\x00")
            root = os.path.dirname(music)

            lib = MusicLibrary()
            lib.load(root, addons=addons.scan(workshop))
            tracks = lib.library["state_avenger"]
            self.assertEqual(len(tracks), 1, "duplicate filenames should collapse")
            self.assertIsNone(tracks[0]["source"], "the user's own file wins")

    def test_enabled_map_round_trips_through_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = os.path.join(tmp, "xipod_config.json")
            with open(cfg, "w", encoding="utf-8") as f:
                json.dump({"music_folder": "X:/keep"}, f)
            addons.save_enabled_map(cfg, {"111": False, "222": True})
            self.assertEqual(addons.load_enabled_map(cfg),
                             {"111": False, "222": True})
            with open(cfg, encoding="utf-8") as f:
                self.assertEqual(json.load(f)["music_folder"], "X:/keep")

    def test_state_folders_all_uppercase(self):
        """Descriptors canonicalize to upper — folder list must already be upper."""
        for folder in STATE_FOLDERS:
            self.assertEqual(folder, folder.upper())


class TestUserPresetPersistence(unittest.TestCase):
    """User presets live in xipod_presets.json (Python-owned). The game's
    SaveConfig round-trips UserPresetN ini lines with values from ITS
    launch, so stale ini copies must never win."""

    def setUp(self):
        _reset_user_presets()

    def tearDown(self):
        _reset_user_presets()

    def test_save_persists_and_survives_restart(self):
        s = EngineSettings()
        s.save_user_preset(2, {"bassboost": 5, "radio": True})
        self.assertTrue(os.path.exists(settings_mod._PRESETS_PATH))

        # Simulate a restart: wipe memory, new instance reloads from JSON
        settings_mod._set_user_preset_slot("user_2", {})
        EngineSettings()
        self.assertEqual(settings_mod.USER_PRESETS["user_2"],
                         {"bassboost": 5, "radio": True})

    def test_clear_removes_from_storage(self):
        s = EngineSettings()
        s.save_user_preset(2, {"bassboost": 5})
        s.clear_user_preset(2)
        EngineSettings()
        self.assertEqual(settings_mod.USER_PRESETS["user_2"], {})

    def test_json_wins_over_stale_ini(self):
        s = EngineSettings()
        s.save_user_preset(1, {"bassboost": 7})
        with tempfile.TemporaryDirectory() as tmp:
            ini = os.path.join(tmp, "XComXiPod.ini")
            with open(ini, "w", encoding="utf-8") as f:
                f.write("[AnarchyRadioFM.XiPod_Settings]\n")
                f.write("UserPreset1=bassboost:99\n")  # stale game copy
            s2 = EngineSettings()
            s2.load_from_ini(ini)
        self.assertEqual(settings_mod.USER_PRESETS["user_1"], {"bassboost": 7})

    def test_ini_presets_migrate_when_no_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            ini = os.path.join(tmp, "XComXiPod.ini")
            with open(ini, "w", encoding="utf-8") as f:
                f.write("[AnarchyRadioFM.XiPod_Settings]\n")
                f.write("UserPreset3=echodelay:250|reverb:True\n")
            s = EngineSettings()
            s.load_from_ini(ini)
        self.assertEqual(settings_mod.USER_PRESETS["user_3"],
                         {"echodelay": 250, "reverb": True})
        self.assertTrue(os.path.exists(settings_mod._PRESETS_PATH))


class _DummyPlayback:
    """Stand-in for PlaybackController — no PyAudio, no threads."""

    def __init__(self):
        self.is_playing = False
        self.current_segment = None
        self.playback_position = 0

    def capture_outgoing_tail(self, crossfade_ms):
        return None

    def stop(self, fade_out=False):
        self.is_playing = False

    def start(self, *args, **kwargs):
        self.is_playing = True

    def close(self):
        pass


class TestDuplicateStateTriggers(unittest.TestCase):
    """Regression for the tactical overlap bug: STATE_MISSION_COMBAT is
    followed ~0.5s later by the Kismet concealment line (and MMS's own
    'Transition to Combat'). The duplicate trigger used to hit the
    same-state resume path while the combat loader was still decoding —
    un-pausing the EXPLORE track (whose segment pause() never cleared)
    and making the combat loader bail with 'already playing'."""

    def _make_engine(self):
        import audio_engine
        orig = audio_engine.PlaybackController
        audio_engine.PlaybackController = _DummyPlayback
        try:
            engine = audio_engine.XiPodEngine()
        finally:
            audio_engine.PlaybackController = orig
        return engine

    def test_duplicate_trigger_no_resume_after_real_switch(self):
        """After a real switch the segment is cleared, so a duplicate
        same-state trigger must NOT resume — the loader owns playback."""
        engine = self._make_engine()
        engine.current_top = "state_mission_combat"
        engine.active_playlist = [{"name": "c.mp3", "path": "does_not_matter"}]
        engine.playback.is_playing = False
        engine.playback.current_segment = None   # cleared by the real switch

        resumed = []
        engine.play = lambda *a, **k: resumed.append(True)
        engine.switch_state("state_mission_combat")
        self.assertEqual(resumed, [], "duplicate trigger must not resume "
                                      "when no suspended segment exists")

    def test_resume_still_works_after_cinematic_pause(self):
        """A cinematic pause preserves current_segment, so a same-state
        trigger afterwards SHOULD resume it."""
        engine = self._make_engine()
        engine.current_top = "state_mission_combat"
        engine.active_playlist = [{"name": "c.mp3", "path": "does_not_matter"}]
        engine.playback.is_playing = False
        engine.playback.current_segment = object()  # suspended by cinematic

        resumed = []
        engine.play = lambda *a, **k: resumed.append(True)
        engine.switch_state("state_mission_combat")
        self.assertEqual(resumed, [True], "same-state resume must still fire "
                                          "when a suspended segment exists")

    def test_switch_state_abandons_old_segment(self):
        engine = self._make_engine()
        engine.library.library = {
            "state_mission_combat": [{"name": "c.mp3", "path": "c"}],
        }
        engine.settings.toggles["battle"] = True
        # Stub the background loader — we only assert switch_state's
        # synchronous state changes, not the decode.
        engine._load_and_play = lambda *a, **k: None
        engine.current_top = "state_mission_explore"
        engine.active_playlist = [{"name": "e.mp3", "path": "e"}]
        engine.playback.is_playing = True
        engine.playback.current_segment = object()  # the explore segment
        engine.playback.playback_position = 12345

        engine.switch_state("state_mission_combat")

        # Cleared synchronously, before the loader thread can matter — a
        # stray resume can now never continue the explore segment.
        self.assertIsNone(engine.playback.current_segment)
        self.assertEqual(engine.playback.playback_position, 0)


import playback as _playback_mod


class _RecPlayback(_playback_mod.PlaybackController):
    """Recording playback stub: subclasses the real controller (so the
    static apply_effects/crossfade_segments helpers still work) but skips
    PyAudio and records the committed segment instead of streaming — no
    audio device, no auto-advance cascade."""

    def __init__(self):
        self.is_playing = False
        self.current_segment = None
        self.playback_position = 0
        self._lock = threading.Lock()

    def capture_outgoing_tail(self, ms):
        return None

    def stop(self, fade_out=False):
        with self._lock:
            self.is_playing = False

    def start(self, segment, on_track_finished=None, get_volume=None, fade_in=False):
        with self._lock:
            self.current_segment = segment
            self.is_playing = True

    def close(self):
        pass


class TestCombatOverlapIntegration(unittest.TestCase):
    """End-to-end reproduction of the reported bug: explore music must
    stop when combat begins. Combat announces itself three times in quick
    succession (UC STATE line, Kismet concealment, MMS transition); the
    duplicates must not resume the explore track over combat.

    Tracks are distinguished by duration (explore 3s, combat 5s) so we can
    read which segment actually committed to playback."""

    def _which(self, seg):
        if seg is None:
            return None
        return "EXPLORE" if len(seg) < 4000 else "COMBAT"

    def _wait(self, pred, timeout=4.0):
        end = time.time() + timeout
        while time.time() < end:
            if pred():
                return True
            time.sleep(0.02)
        return False

    def test_combat_takes_over_from_explore(self):
        from pydub import AudioSegment
        import audio_engine
        from log_watcher import Bridge

        with tempfile.TemporaryDirectory() as tmp:
            music = os.path.join(tmp, "music")
            for st, fn, ms in [("STATE_MISSION_EXPLORE", "ex.wav", 3000),
                               ("STATE_MISSION_COMBAT", "co.wav", 5000)]:
                d = os.path.join(music, st)
                os.makedirs(d)
                AudioSegment.silent(duration=ms, frame_rate=44100).set_channels(2)\
                    .export(os.path.join(d, fn), format="wav")

            logs = os.path.join(tmp, "XComGame", "Logs")
            cfgd = os.path.join(tmp, "XComGame", "Config")
            os.makedirs(logs)
            os.makedirs(cfgd)
            log_path = os.path.join(logs, "Launch.log")

            orig = audio_engine.PlaybackController
            audio_engine.PlaybackController = _RecPlayback
            try:
                engine = audio_engine.XiPodEngine()
                engine.settings.toggles["battle"] = True
                engine.load_library(music, log_path, game_config_folder=cfgd)

                # Simulate real decode latency (the real bug window is the
                # ~430ms the combat loader spends decoding, during which the
                # Kismet duplicate arrives). Without this the loader commits
                # before the duplicate lands and the race never happens.
                real_prepare = engine._prepare_segment
                def slow_prepare(track, **kw):
                    time.sleep(0.3)
                    return real_prepare(track, **kw)
                engine._prepare_segment = slow_prepare

                bridge = Bridge(log_path, engine)

                # Drive the Bridge's line processor directly — deterministic,
                # no file-watch polling. Loaders still run on real threads.
                bridge._process_line("Music Modding System - Starting Ambience")
                self.assertTrue(
                    self._wait(lambda: self._which(engine.playback.current_segment) == "EXPLORE"),
                    "explore music should start")

                # Combat burst, real ordering: the UC STATE line dispatches
                # the combat loader; the Kismet + MMS duplicates arrive while
                # it is still decoding (is_playing briefly False). They must
                # NOT resume the (now abandoned) explore segment over combat.
                bridge._process_line("XIPOD: STATE_MISSION_COMBAT")
                bridge._process_line("Kismet: << XCOM : Concealment Broken >>")
                bridge._process_line("Music Modding System - Transition to Combat!")

                # Wait for the loader to commit, then let anything settle
                self._wait(lambda: self._which(engine.playback.current_segment) == "COMBAT")
                time.sleep(0.5)

                self.assertEqual(self._which(engine.playback.current_segment), "COMBAT",
                                 "combat must be playing, not explore")
                self.assertTrue(engine.playback.is_playing,
                                "combat must still be playing after the duplicate burst")
            finally:
                audio_engine.PlaybackController = orig
                try:
                    engine.shutdown()
                except Exception:
                    pass
                # Let any in-flight loader threads finish so the temp dir
                # (holding the wav files they decode) can be removed on Windows.
                for th in list(threading.enumerate()):
                    if th.name.startswith("Loader-"):
                        th.join(timeout=3)


class TestProcessUtils(unittest.TestCase):

    def test_empty_names_short_circuits(self):
        self.assertEqual(process_utils.running_processes([]), set())

    def test_running_processes_returns_set_or_none(self):
        result = process_utils.running_processes(["definitely_not_running_xyz.exe"])
        self.assertTrue(result is None or result == set())


class TestSpotifyParsing(unittest.TestCase):

    def test_parse_context_uri(self):
        import spotify
        p = spotify.parse_context_uri
        self.assertEqual(p("https://open.spotify.com/playlist/37i9dQ?si=x"),
                         "spotify:playlist:37i9dQ")
        self.assertEqual(p("spotify:playlist:37i9dQ"), "spotify:playlist:37i9dQ")
        self.assertEqual(p("37i9dQ"), "spotify:playlist:37i9dQ")  # bare id
        self.assertEqual(p("https://open.spotify.com/album/1DFix"),
                         "spotify:album:1DFix")
        self.assertEqual(p("https://open.spotify.com/intl-de/playlist/abc"),
                         "spotify:playlist:abc")
        self.assertEqual(p("spotify:track:xyz"), "")   # tracks aren't contexts
        self.assertEqual(p("just some text"), "")
        self.assertEqual(p(""), "")

    def test_parse_context_uri_rejects_lookalike_hosts(self):
        """The host is checked after parsing, not as a substring of the URL.

        A substring test accepts any of these; each one embeds the allowed
        host somewhere it doesn't belong.
        """
        import spotify
        p = spotify.parse_context_uri
        for bad in (
            "https://evil.example/open.spotify.com/playlist/abc",
            "https://open.spotify.com.evil.example/playlist/abc",
            "https://notspotify.com/playlist/abc",
            "https://evil.example/?u=open.spotify.com/playlist/abc",
            "https://open.spotify.com@evil.example/playlist/abc",
        ):
            self.assertEqual(p(bad), "", f"should have rejected {bad}")

        # Genuine subdomains still work.
        self.assertEqual(p("https://open.spotify.com/playlist/abc"),
                         "spotify:playlist:abc")
        self.assertEqual(p("https://play.spotify.com/album/abc"),
                         "spotify:album:abc")


class TestSpotifyController(unittest.TestCase):
    """Config round-trip and playlist assignment. No network is touched —
    authorize()/_api() are never called here."""

    def _controller(self, tmp, cfg=None):
        import spotify
        config_path = os.path.join(tmp, "xipod_config.json")
        cache_path = os.path.join(tmp, ".spotify_cache.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(cfg or {"music_folder": "X"}, f)
        return spotify.SpotifyController(config_path, cache_path), config_path

    def test_config_round_trip_preserves_other_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp, config_path = self._controller(tmp, {"music_folder": "keepme"})
            sp.enabled = True
            sp.client_id = "cid"
            sp.client_secret = "secret"
            sp.set_playlist("state_avenger",
                            "https://open.spotify.com/playlist/AV123")
            sp.save_config()

            with open(config_path, encoding="utf-8") as f:
                raw = json.load(f)
            # Unrelated config keys are preserved
            self.assertEqual(raw["music_folder"], "keepme")
            self.assertTrue(raw["spotify"]["enabled"])
            self.assertEqual(raw["spotify"]["playlists"]["state_avenger"],
                             "spotify:playlist:AV123")

            # A fresh controller reloads the same values
            import spotify
            sp2 = spotify.SpotifyController(config_path,
                                           os.path.join(tmp, ".spotify_cache.json"))
            self.assertTrue(sp2.enabled)
            self.assertEqual(sp2.playlist_for("state_avenger"),
                             "spotify:playlist:AV123")

    def test_set_playlist_rejects_garbage_and_clears_on_blank(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp, _ = self._controller(tmp)
            with self.assertRaises(ValueError):
                sp.set_playlist("state_avenger", "not a spotify link")
            sp.set_playlist("state_avenger", "spotify:playlist:X")
            self.assertEqual(sp.playlist_for("state_avenger"), "spotify:playlist:X")
            sp.set_playlist("state_avenger", "")  # blank clears
            self.assertEqual(sp.playlist_for("state_avenger"), "")

    def test_volume_round_trips_and_defaults_to_60(self):
        import spotify
        with tempfile.TemporaryDirectory() as tmp:
            sp, config_path = self._controller(tmp)
            self.assertEqual(sp.volume, 60)  # default
            sp.volume = 45
            sp.save_config()
            sp2 = spotify.SpotifyController(config_path,
                                            os.path.join(tmp, ".spotify_cache.json"))
            self.assertEqual(sp2.volume, 45)

    def test_api_tolerates_non_json_body(self):
        """Regression: pause() returns 204 with an empty/whitespace body;
        json.loads on it used to crash the SpotifyPause thread."""
        import spotify
        import urllib.request
        with tempfile.TemporaryDirectory() as tmp:
            sp, _ = self._controller(tmp)
            sp._access_token = "tok"
            sp._access_expires_at = time.time() + 3600  # skip refresh/network

            class _FakeResp:
                status = 204
                def read(self):
                    return b"  "  # whitespace, not JSON
                def __enter__(self):
                    return self
                def __exit__(self, *a):
                    return False

            orig = urllib.request.urlopen
            urllib.request.urlopen = lambda *a, **k: _FakeResp()
            try:
                status, data = sp._api("PUT", "/me/player/pause")
            finally:
                urllib.request.urlopen = orig
            self.assertEqual(status, 204)
            self.assertIsNone(data)

    def test_is_active_requires_enabled_configured_and_authorized(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp, _ = self._controller(tmp)
            sp.enabled = True
            self.assertFalse(sp.is_active())          # no creds
            sp.client_id, sp.client_secret = "a", "b"
            self.assertFalse(sp.is_active())          # not authorized
            sp._refresh_token = "rt"                  # simulate a linked account
            self.assertTrue(sp.is_active())
            sp.enabled = False
            self.assertFalse(sp.is_active())


class _FakeSpotify:
    """Records control calls; never hits the network."""

    def __init__(self, playlists):
        self._playlists = playlists
        self.calls = []

    def is_active(self):
        return True

    def playlist_for(self, state):
        return self._playlists.get(state, "")

    def play_context_async(self, uri):
        self.calls.append(("play", uri))

    def pause_async(self):
        self.calls.append(("pause", None))

    def resume_async(self):
        self.calls.append(("resume", None))

    def next_async(self):
        self.calls.append(("next", None))

    def prev_async(self):
        self.calls.append(("prev", None))


class TestEngineSpotifyOverride(unittest.TestCase):
    """switch_state hands assigned states to Spotify and stands the local
    engine down; unassigned states fall back to local playback."""

    def _engine(self):
        import audio_engine
        orig = audio_engine.PlaybackController
        audio_engine.PlaybackController = _RecPlayback
        try:
            e = audio_engine.XiPodEngine()
        finally:
            audio_engine.PlaybackController = orig
        return e

    def test_assigned_state_goes_to_spotify(self):
        e = self._engine()
        fake = _FakeSpotify({"state_avenger": "spotify:playlist:AV"})
        e.spotify = fake
        e.settings.toggles["avenger"] = True

        e.switch_state("state_avenger")
        self.assertTrue(e.is_spotify_active())
        self.assertEqual(fake.calls, [("play", "spotify:playlist:AV")])
        # Local engine stood down — no local playlist loaded
        self.assertEqual(e.active_playlist, [])

        # Duplicate trigger for the same state must not re-issue play
        e.switch_state("state_avenger")
        self.assertEqual(fake.calls, [("play", "spotify:playlist:AV")])

    def test_unassigned_state_stops_spotify_and_uses_local(self):
        e = self._engine()
        fake = _FakeSpotify({"state_avenger": "spotify:playlist:AV"})
        e.spotify = fake
        e.settings.toggles["avenger"] = True
        e.settings.toggles["geoscape"] = True
        e.library.library = {"state_geoscape": [{"name": "g.mp3", "path": "g"}]}
        e._load_and_play = lambda *a, **k: None  # stub local loader

        e.switch_state("state_avenger")     # -> Spotify
        e.switch_state("state_geoscape")    # no playlist -> local
        self.assertIn(("pause", None), fake.calls)
        self.assertFalse(e.is_spotify_active())
        self.assertEqual(e.current_top, "state_geoscape")

    def test_transport_routes_to_spotify_when_active(self):
        e = self._engine()
        fake = _FakeSpotify({"state_avenger": "spotify:playlist:AV"})
        e.spotify = fake
        e.settings.toggles["avenger"] = True
        e.switch_state("state_avenger")

        e.next_track()
        e.prev_track()
        e.pause()
        e.play()
        kinds = [c[0] for c in fake.calls]
        self.assertIn("next", kinds)
        self.assertIn("prev", kinds)
        self.assertIn("pause", kinds)
        self.assertIn("resume", kinds)


if __name__ == "__main__":
    unittest.main()

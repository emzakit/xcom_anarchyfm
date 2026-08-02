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

import zipfile

import build_manifest
import mms_config
import process_utils
import updater
import settings as settings_mod
from settings import EngineSettings
from library import (
    MusicLibrary, interleave_pools,
    RADIO_SOURCE_RADIO, RADIO_SOURCE_STATE, RADIO_SOURCE_BOTH,
)
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


class TestBuildManifest(unittest.TestCase):
    """build.json proves a download arrived intact, and catches an update that
    only half applied."""

    def _build(self, tmp, files):
        for rel, text in files.items():
            path = os.path.join(tmp, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        return tmp

    def test_write_then_verify_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._build(tmp, {"AnarchyRadioFM.exe": "exe",
                              "_internal/thing.pyd": "pyd",
                              "_internal/assets/check_x.svg": "svg"})
            build_manifest.write(tmp, "9.9")
            manifest = build_manifest.read(tmp)
            self.assertEqual(manifest["version"], "9.9")
            self.assertEqual(sorted(manifest["files"]),
                             ["AnarchyRadioFM.exe",
                              "_internal/assets/check_x.svg",
                              "_internal/thing.pyd"])
            # Paths are stored forward-slashed so they're platform-stable.
            self.assertTrue(all("\\" not in k for k in manifest["files"]))
            self.assertEqual(build_manifest.verify(tmp), (True, []))

    def test_corruption_and_truncation_are_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._build(tmp, {"AnarchyRadioFM.exe": "exe",
                              "_internal/thing.pyd": "pyd"})
            build_manifest.write(tmp, "9.9")

            # Same length, different content — the old size-only check passed this.
            with open(os.path.join(tmp, "AnarchyRadioFM.exe"), "w") as f:
                f.write("EXE")
            ok, problems = build_manifest.verify(tmp)
            self.assertFalse(ok)
            self.assertIn("corrupt: AnarchyRadioFM.exe", problems)

    def test_missing_file_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._build(tmp, {"AnarchyRadioFM.exe": "exe",
                              "_internal/thing.pyd": "pyd"})
            build_manifest.write(tmp, "9.9")
            os.remove(os.path.join(tmp, "_internal", "thing.pyd"))
            ok, problems = build_manifest.verify(tmp)
            self.assertFalse(ok)
            self.assertIn("missing: _internal/thing.pyd", problems)

    def test_user_files_are_not_part_of_the_build(self):
        """Config and presets appear after install. Hashing them would make
        every install fail verification the moment someone changed a setting."""
        with tempfile.TemporaryDirectory() as tmp:
            self._build(tmp, {"AnarchyRadioFM.exe": "exe",
                              "xipod_config.json": "{}",
                              "xipod_presets.json": "{}"})
            build_manifest.write(tmp, "9.9")
            self.assertEqual(list(build_manifest.read(tmp)["files"]),
                             ["AnarchyRadioFM.exe"])
            with open(os.path.join(tmp, "xipod_config.json"), "w") as f:
                f.write('{"changed": true}')
            self.assertEqual(build_manifest.verify(tmp), (True, []))

    def test_build_without_a_manifest_still_verifies(self):
        """Releases predating build.json must keep installing."""
        with tempfile.TemporaryDirectory() as tmp:
            self._build(tmp, {"AnarchyRadioFM.exe": "exe"})
            self.assertIsNone(build_manifest.read(tmp))
            self.assertEqual(build_manifest.verify(tmp), (True, []))

    def test_unreadable_manifest_is_ignored_not_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._build(tmp, {"AnarchyRadioFM.exe": "exe"})
            with open(os.path.join(tmp, "build.json"), "w") as f:
                f.write("{ not json")
            self.assertIsNone(build_manifest.read(tmp))
            self.assertEqual(build_manifest.verify(tmp), (True, []))

    def test_installed_version_reads_the_stamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._build(tmp, {"AnarchyRadioFM.exe": "exe"})
            build_manifest.write(tmp, "2.4")
            self.assertEqual(build_manifest.installed_version(tmp), "2.4")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(build_manifest.installed_version(tmp), "")


class TestUpdaterStaging(unittest.TestCase):
    """Verification happens before anything is copied over an install."""

    def _zip_build(self, tmp, files, version_str=None):
        build = os.path.join(tmp, "AnarchyRadioFM")
        for rel, text in files.items():
            path = os.path.join(build, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        if version_str:
            build_manifest.write(build, version_str)
        zip_path = os.path.join(tmp, "AnarchyRadioFM_APP_v9.9.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            for root, _dirs, names in os.walk(build):
                for name in names:
                    full = os.path.join(root, name)
                    zf.write(full, os.path.join(
                        "AnarchyRadioFM", os.path.relpath(full, build)))
        return zip_path

    def test_good_build_stages(self):
        with tempfile.TemporaryDirectory() as tmp:
            zp = self._zip_build(tmp, {"AnarchyRadioFM.exe": "exe",
                                       "_internal/a.pyd": "a"}, "9.9")
            root = updater.stage(zp)
            self.assertTrue(os.path.isfile(
                os.path.join(root, "AnarchyRadioFM.exe")))

    def test_tampered_build_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            build = os.path.join(tmp, "AnarchyRadioFM")
            os.makedirs(os.path.join(build, "_internal"))
            for rel, text in (("AnarchyRadioFM.exe", "exe"),
                              ("_internal/a.pyd", "aaa")):
                with open(os.path.join(build, rel.replace("/", os.sep)), "w") as f:
                    f.write(text)
            build_manifest.write(build, "9.9")
            # Corrupt AFTER hashing, keeping the length identical.
            with open(os.path.join(build, "_internal", "a.pyd"), "w") as f:
                f.write("bbb")
            zip_path = os.path.join(tmp, "AnarchyRadioFM_APP_v9.9.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                for root, _dirs, names in os.walk(build):
                    for name in names:
                        full = os.path.join(root, name)
                        zf.write(full, os.path.join(
                            "AnarchyRadioFM", os.path.relpath(full, build)))

            with self.assertRaises(ValueError) as ctx:
                updater.stage(zip_path)
            self.assertIn("_internal/a.pyd", str(ctx.exception))

    def test_zip_without_our_exe_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = os.path.join(tmp, "AnarchyRadioFM_APP_v9.9.zip")
            with zipfile.ZipFile(zip_path, "w") as zf:
                zf.writestr("something/readme.txt", "not our app")
            with self.assertRaises(ValueError):
                updater.stage(zip_path)

    def test_unversioned_build_still_stages(self):
        with tempfile.TemporaryDirectory() as tmp:
            zp = self._zip_build(tmp, {"AnarchyRadioFM.exe": "exe"})
            self.assertTrue(os.path.isdir(updater.stage(zp)))


class TestLoopResolution(unittest.TestCase):
    """Battle's Loop Track box is a master over both mission phases. It used
    to write bLoopBattle to the ini and show up in MCM while nothing read it —
    no state maps to the "battle" LOOP key."""

    def setUp(self):
        self.s = EngineSettings()
        for key in ("battle", "explore", "combat"):
            self.s.loop[key] = False

    def test_battle_loops_both_phases(self):
        self.s.loop["battle"] = True
        self.assertTrue(self.s.is_loop_enabled("state_mission_explore"))
        self.assertTrue(self.s.is_loop_enabled("state_mission_combat"))

    def test_phase_toggles_stay_independent(self):
        self.s.loop["explore"] = True
        self.assertTrue(self.s.is_loop_enabled("state_mission_explore"))
        self.assertFalse(self.s.is_loop_enabled("state_mission_combat"))

    def test_nothing_set_means_no_loop(self):
        self.assertFalse(self.s.is_loop_enabled("state_mission_explore"))
        self.assertFalse(self.s.is_loop_enabled("state_mission_combat"))

    def test_states_without_a_master_are_unaffected(self):
        self.s.loop["battle"] = True
        self.s.loop["avenger"] = False
        self.assertFalse(self.s.is_loop_enabled("state_avenger"))
        # Stingers have no loop key at all
        self.assertFalse(self.s.is_loop_enabled("state_victory"))


class TestMMSConfig(unittest.TestCase):

    # The _build_* helpers take a "skip reason" — None means "silence this
    # state", a string means "leave it to MMS, and here's why".

    def test_tactical_uses_double_backslash_continuation(self):
        """UE3 ini line continuation is '\\\\' — a single backslash breaks MMS."""
        content = mms_config._build_tactical_ini(None)
        for line in content.splitlines():
            if line.rstrip().endswith("\\"):
                self.assertTrue(line.rstrip().endswith("\\\\"),
                                f"single-backslash continuation: {line!r}")
        self.assertIn("+CombatDefs=", content)
        self.assertIn("+ExploreDefs=", content)

    def test_tactical_defs_outscore_mms_stock(self):
        """MMS breaks a score tie with a random shuffle, so the silent defs
        must win on score or the mission is a coin flip. Stock defs leave
        every field unset and score 1186; wildcards score 2338."""
        content = mms_config._build_tactical_ini(None)
        for block in ("+CombatDefs", "+ExploreDefs"):
            start = content.index(block)
            end = content.index(")", start)
            body = content[start:end]
            self.assertIn('MissionMusicSet="wildcard"', body, block)
            self.assertIn('biome="wildcard"', body, block)
            self.assertIn('plot="wildcard"', body, block)
            # rain is deliberately absent — see test_tactical_envreq_omits_rain.

    def test_tactical_disabled_has_no_active_defs(self):
        content = mms_config._build_tactical_ini("toggled off")
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

    def test_empty_folder_leaves_state_to_mms(self):
        """A state with no tracks must not be silenced — otherwise the user
        gets dead air instead of their MMS pack."""
        toggles = {"avenger": True, "geoscape": True, "squadselect": True,
                   "victory": True, "defeat": True}
        has_tracks = dict.fromkeys(toggles, True)
        has_tracks["geoscape"] = False
        self.assertNotIn("eSSG_Geoscape", self._active_lines(toggles, has_tracks))
        self.assertIn("eSSG_SquadSelect", self._active_lines(toggles, has_tracks))

        self.assertIn("no tracks",
                      mms_config._build_tactical_ini(
                          mms_config._reason("battle", {"battle": True},
                                             {"battle": False})))
        self.assertIn("+CombatDefs=",
                      mms_config._build_tactical_ini(
                          mms_config._reason("battle", {"battle": True},
                                             {"battle": True})))

    def test_reason_prefers_toggle_over_empty_folder(self):
        self.assertIsNone(mms_config._reason("avenger", {"avenger": True}, None))
        self.assertEqual("toggled off",
                         mms_config._reason("avenger", {"avenger": False},
                                            {"avenger": True}))
        self.assertEqual("no tracks in its folder",
                         mms_config._reason("avenger", {"avenger": True},
                                            {"avenger": False}))

    def test_pack_defs_registered_only_for_owned_states(self):
        """MMS breaks a tie between a pack and us with Rand(), so a pack's
        defs must be demoted to fallbacks on states we cover — and left alone
        on states we don't, or the pack goes silent where it should play."""
        toggles = {"avenger": True, "geoscape": False, "squadselect": True,
                   "victory": True, "defeat": True}
        packs = {"avenger": ["PackHQ1", "PackHQ2"], "geoscape": ["PackGeo"]}
        active = self._active_lines(toggles, None, packs)

        self.assertIn('+FallbackSongs="PackHQ1"', active)
        self.assertIn('+FallbackSongs="PackHQ2"', active)
        # geoscape is ours to leave alone — its pack def must stay eligible
        self.assertNotIn("PackGeo", active)

    def test_pack_defs_absent_when_no_packs(self):
        toggles = {"avenger": True, "geoscape": True, "squadselect": True,
                   "victory": True, "defeat": True}
        self.assertNotIn("FallbackSongs", self._active_lines(toggles, None, None))
        self.assertNotIn("FallbackDefs", mms_config._build_tactical_ini(None, None))

    def test_tactical_envreq_omits_rain(self):
        """rain=eRR_Always inside the nested struct stopped the whole entry
        parsing, so the def silently vanished from MMS's pool. The struct
        defaults it anyway."""
        content = mms_config._build_tactical_ini(None)
        self.assertIn('EnvReq=(biome="wildcard", plot="wildcard")', content)
        self.assertNotIn("rain=", content)

    def test_shell_pack_cues_moved_to_fallback_bucket(self):
        """The shell has no MusicID to register, so a pack's cue has to be
        moved between arrays instead."""
        packs = {"shell_menu": ["SomePack.Shell_cue"]}
        owned = mms_config._build_shell_ini(None, packs)
        self.assertIn('-ShellCues="SomePack.Shell_cue"', owned)
        self.assertIn('+FallbackCues="SomePack.Shell_cue"', owned)

        # Not ours to cover -> the pack keeps the menu untouched.
        off = mms_config._build_shell_ini("toggled off", packs)
        self.assertNotIn("SomePack.Shell_cue", off)

    def test_tactical_pack_defs_registered(self):
        content = mms_config._build_tactical_ini(None, {"battle": ["PackCombat1"]})
        self.assertIn('+FallbackDefs="PackCombat1"', content)

    @staticmethod
    def _active_lines(toggles, has_tracks=None, pack_defs=None):
        content = mms_config._build_strategy_ini(toggles, has_tracks, pack_defs)
        return "\n".join(l for l in content.splitlines() if not l.startswith(";"))


class TestMMSPacks(unittest.TestCase):

    def test_finds_own_config_in_local_mods_folder(self):
        """MMS reads config from the mod's own folder, and a hand-installed
        or locally-built mod lives under the game install rather than the
        workshop. Both hang off the same steamapps root."""
        import mms_packs
        with tempfile.TemporaryDirectory() as tmp:
            workshop = os.path.join(tmp, "workshop", "content", "268500")
            local = os.path.join(tmp, "common", "XCOM 2", "XComGame",
                                 "Mods", "AnarchyRadioFM")
            os.makedirs(workshop)
            os.makedirs(os.path.join(local, "Config"))
            with open(os.path.join(local, "AnarchyRadioFM.XComMod"), "w") as f:
                f.write("[mod]\n")

            dirs = mms_packs.find_own_config_dirs(workshop)
            self.assertEqual(len(dirs), 1)
            self.assertTrue(dirs[0].endswith(os.path.join("AnarchyRadioFM", "Config")))

    def test_workshop_folder_derived_from_game_exe(self):
        """Required now, so it needs to auto-fill — including for libraries on
        another drive and for launchers that aren't XCom2.exe."""
        from setup import find_workshop_folder
        with tempfile.TemporaryDirectory() as tmp:
            steamapps = os.path.join(tmp, "SteamLibrary", "steamapps")
            exe = os.path.join(steamapps, "common", "XCOM 2",
                               "SomeLauncher", "Launcher.exe")
            os.makedirs(os.path.dirname(exe))
            open(exe, "w").close()
            os.makedirs(os.path.join(steamapps, "workshop", "content", "268500"))

            found = find_workshop_folder(exe)
            self.assertTrue(found.endswith(os.path.join("workshop", "content", "268500")))
            self.assertTrue(os.path.isdir(found))

    def test_workshop_folder_absent_returns_empty(self):
        from setup import find_workshop_folder
        with tempfile.TemporaryDirectory() as tmp:
            exe = os.path.join(tmp, "nowhere", "game.exe")
            os.makedirs(os.path.dirname(exe))
            open(exe, "w").close()
            self.assertEqual(find_workshop_folder(exe), "")

    def test_launcher_settings_win_over_guessing(self):
        """A mod launcher can load the mod from anywhere — the SDK's build
        output, say. Its own settings.json says where, and that beats
        searching the usual places."""
        import mms_packs
        with tempfile.TemporaryDirectory() as tmp:
            launcher_dir = os.path.join(tmp, "AML")
            elsewhere = os.path.join(tmp, "some", "build", "output",
                                     "AnarchyRadioFM")
            os.makedirs(launcher_dir)
            os.makedirs(os.path.join(elsewhere, "Config"))
            exe = os.path.join(launcher_dir, "Launcher.exe")
            open(exe, "w").close()
            with open(os.path.join(launcher_dir, "settings.json"), "w",
                      encoding="utf-8") as f:
                json.dump({"Mods": {"Entries": {"Unsorted": {"Entries": [
                    {"ID": "SomeOtherMod", "Path": "C:/nope", "isActive": True},
                    {"ID": "AnarchyRadioFM", "Path": elsewhere, "isActive": True},
                ]}}}}, f)

            dirs = mms_packs.find_own_config_dirs("", game_exe=exe)
            self.assertEqual(len(dirs), 1)
            self.assertTrue(dirs[0].startswith(elsewhere))

    def test_launcher_path_used_even_when_mod_toggled_off(self):
        """Whether the launcher currently has the mod ticked is none of our
        business — someone toggling mods around while testing shouldn't get
        nagged, and settings written to a folder that isn't loaded right now
        are simply correct already when they switch it back on."""
        import mms_packs
        with tempfile.TemporaryDirectory() as tmp:
            launcher_dir = os.path.join(tmp, "AML")
            modpath = os.path.join(tmp, "AnarchyRadioFM")
            os.makedirs(launcher_dir)
            os.makedirs(os.path.join(modpath, "Config"))
            exe = os.path.join(launcher_dir, "Launcher.exe")
            open(exe, "w").close()
            with open(os.path.join(launcher_dir, "settings.json"), "w",
                      encoding="utf-8") as f:
                json.dump({"Mods": {"Entries": {"Unsorted": {"Entries": [
                    {"ID": "AnarchyRadioFM", "Path": modpath, "isActive": False},
                ]}}}}, f)

            dirs = mms_packs.find_own_config_dirs("", game_exe=exe)
            self.assertEqual(len(dirs), 1)
            self.assertTrue(dirs[0].startswith(modpath))

    def test_addon_test_folder_defaults_to_modbuddy_output(self):
        """Building a pack should make it testable immediately — no copying."""
        from setup import default_addon_test_folder
        with tempfile.TemporaryDirectory() as tmp:
            steamapps = os.path.join(tmp, "steamapps")
            workshop = os.path.join(steamapps, "workshop", "content", "268500")
            modbuddy = os.path.join(steamapps, "common", "XCOM 2 SDK",
                                    "Binaries", "Win32", "ModBuddy", "Mods")
            os.makedirs(workshop)
            os.makedirs(modbuddy)

            self.assertEqual(
                os.path.normcase(default_addon_test_folder(workshop_folder=workshop)),
                os.path.normcase(modbuddy))

    def test_addon_test_folder_falls_back_without_the_sdk(self):
        from setup import default_addon_test_folder, data_path
        with tempfile.TemporaryDirectory() as tmp:
            workshop = os.path.join(tmp, "steamapps", "workshop", "content", "268500")
            os.makedirs(workshop)
            self.assertEqual(default_addon_test_folder(workshop_folder=workshop),
                             data_path("addon_test"))

    def test_plain_game_exe_falls_back_to_searching(self):
        """Launching the game directly means no settings.json — the usual
        install locations are then the right answer."""
        import mms_packs
        with tempfile.TemporaryDirectory() as tmp:
            steamapps = os.path.join(tmp, "steamapps")
            workshop = os.path.join(steamapps, "workshop", "content", "268500")
            local = os.path.join(steamapps, "common", "XCOM 2", "XComGame",
                                 "Mods", "AnarchyRadioFM")
            os.makedirs(workshop)
            os.makedirs(os.path.join(local, "Config"))
            with open(os.path.join(local, "AnarchyRadioFM.XComMod"), "w") as f:
                f.write("[mod]\n")
            exe = os.path.join(steamapps, "common", "XCOM 2", "XCom2.exe")
            open(exe, "w").close()

            dirs = mms_packs.find_own_config_dirs(workshop, game_exe=exe)
            self.assertEqual(len(dirs), 1)
            self.assertTrue(dirs[0].startswith(local))

    def test_active_mods_are_deduped_and_lowercased(self):
        import mms_packs
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "XComModOptions.ini"), "w") as f:
                f.write("[Engine.XComModOptions]\n")
                f.write("ActiveMods=AnarchyRadioFM\n")
                f.write("ActiveMods=AnarchyRadioFM\n")
                f.write("ActiveMods=Halo3MusicPack\n")
            self.assertEqual(mms_packs.active_mod_ids(tmp),
                             {"anarchyradiofm", "halo3musicpack"})


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

    def test_empty_base_folder_falls_back_to_the_loop_sibling(self):
        """Tracks dropped only into STATE_MISSION_COMBAT_LOOP used to resolve
        to nothing whenever the Combat Loop toggle was off — and since the
        state still counted as covered, MMS was silenced and combat went
        completely quiet."""
        with tempfile.TemporaryDirectory() as tmp:
            lib = self._make_library(tmp, {
                "STATE_MISSION_COMBAT": [],
                "STATE_MISSION_COMBAT_LOOP": ["c1.mp3", "c2.mp3"],
            })
            for use_loop in (False, True):
                self.assertEqual(
                    sorted(t["name"] for t in lib.resolve_playlist(
                        "state_mission_combat", use_loop=use_loop)),
                    ["c1.mp3", "c2.mp3"], f"use_loop={use_loop}")

    def test_loop_toggle_still_picks_the_folder_when_both_are_filled(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = self._make_library(tmp, {
                "STATE_MISSION_COMBAT": ["base.mp3"],
                "STATE_MISSION_COMBAT_LOOP": ["loop.mp3"],
            })
            names = lambda use_loop: [
                t["name"] for t in lib.resolve_playlist(
                    "state_mission_combat", use_loop=use_loop)]
            self.assertEqual(names(True), ["loop.mp3"])
            self.assertEqual(names(False), ["base.mp3"])

    def test_radio_sources_resolve_to_the_right_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = self._make_library(tmp, {
                "STATE_AVENGER": ["a.mp3"],
                "STATE_RESISTANCE_RADIO": ["r1.mp3", "r2.mp3"],
            })
            names = lambda src: sorted(
                t["name"] for t in lib.resolve_radio_playlist("state_avenger", src))

            self.assertEqual(names(RADIO_SOURCE_RADIO), ["r1.mp3", "r2.mp3"])
            self.assertEqual(names(RADIO_SOURCE_STATE), ["a.mp3"])
            self.assertEqual(names(RADIO_SOURCE_BOTH), ["a.mp3", "r1.mp3", "r2.mp3"])
            # Only "both" has two folders to choose between.
            self.assertEqual(
                [len(lib.resolve_radio_pools("state_avenger", s))
                 for s in (RADIO_SOURCE_RADIO, RADIO_SOURCE_STATE, RADIO_SOURCE_BOTH)],
                [1, 1, 2])

    def test_empty_radio_folder_falls_back_to_the_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib = self._make_library(tmp, {
                "STATE_AVENGER": ["a.mp3"],
                "STATE_RESISTANCE_RADIO": [],
            })
            for src in (RADIO_SOURCE_RADIO, RADIO_SOURCE_BOTH):
                self.assertEqual(
                    [t["name"] for t in lib.resolve_radio_playlist("state_avenger", src)],
                    ["a.mp3"], src)
                # Nothing to alternate with — one pool, so no mix is attempted.
                self.assertEqual(len(lib.resolve_radio_pools("state_avenger", src)), 1)

    def test_mix_splits_airtime_evenly_between_uneven_folders(self):
        """The bug this replaced: pooling both folders and shuffling gave each
        a share proportional to its size, so twelve podcast files against two
        Avenger tracks played six podcasts per song."""
        radio = [{"name": f"r{i}", "path": f"r{i}"} for i in range(12)]
        own = [{"name": f"a{i}", "path": f"a{i}"} for i in range(2)]
        side = {t["path"]: ("radio" if t in radio else "own")
                for t in radio + own}

        counts, runs = {"radio": 0, "own": 0}, []
        for _ in range(200):
            seq = [side[t["path"]] for t in interleave_pools([radio, own])]
            self.assertTrue(seq)
            for s in seq:
                counts[s] += 1
            run = 1
            for prev, cur in zip(seq, seq[1:]):
                if cur == prev:
                    run += 1
                else:
                    runs.append(run)
                    run = 1
            runs.append(run)

        total = counts["radio"] + counts["own"]
        self.assertAlmostEqual(counts["radio"] / total, 0.5, delta=0.05)
        # Streak penalty: same-folder runs stay short.
        self.assertLess(sum(r for r in runs if r >= 4) / len(runs), 0.02)
        self.assertLessEqual(max(runs), 6)

    def test_mix_rotates_a_folder_rather_than_picking_at_random(self):
        radio = [{"name": f"r{i}", "path": f"r{i}"} for i in range(12)]
        own = [{"name": "a0", "path": "a0"}]

        for _ in range(50):
            drawn = [t["path"] for t in interleave_pools([radio, own])
                     if t["path"] != "a0"]
            # A pool is served in shuffled rotation, so a track can't come
            # back around until the rest of the folder has had its turn.
            first_pass = drawn[:len(radio)]
            self.assertEqual(len(set(first_pass)), len(first_pass))

        # Nothing is starved either — how far into a pass a weave gets varies,
        # but each one reshuffles from scratch.
        heard = set()
        for _ in range(10):
            heard.update(t["path"] for t in interleave_pools([radio, own]))
        self.assertEqual(len(heard), len(radio) + len(own))

    def test_interleave_handles_empty_and_single_pools(self):
        self.assertEqual(interleave_pools([]), [])
        self.assertEqual(interleave_pools([[], []]), [])
        solo = [{"name": "a", "path": "a"}, {"name": "b", "path": "b"}]
        self.assertCountEqual(interleave_pools([solo, []]), solo)

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

    def test_test_folder_packs_are_found_and_tagged(self):
        """A pack under test loads exactly like a subscribed one, but is
        flagged and id-prefixed so enabling the local copy can't flip the
        published one's setting."""
        with tempfile.TemporaryDirectory() as tmp:
            workshop = os.path.join(tmp, "workshop")
            testdir = os.path.join(tmp, "addon_test")
            os.makedirs(workshop)
            os.makedirs(testdir)

            self._make_mod(workshop, "12345", {
                "name": "Published Pack",
                "folders": {"STATE_AVENGER": "music/avenger"},
            }, {"music/avenger": ["a.mp3"]})
            # Same folder name as the workshop one, to prove they don't collide.
            self._make_mod(testdir, "12345", {
                "name": "Work In Progress",
                "folders": {"STATE_AVENGER": "music/avenger"},
            }, {"music/avenger": ["b.mp3"]})

            found = addons.scan(workshop, test_folder=testdir)
            self.assertEqual(len(found), 2)

            # Tested packs sort first — they're the ones being worked on.
            self.assertTrue(found[0].is_test)
            self.assertEqual(found[0].id, addons.TEST_ID_PREFIX + "12345")
            self.assertEqual(found[0].name, "Work In Progress")

            self.assertFalse(found[1].is_test)
            self.assertEqual(found[1].id, "12345")

            # Disabling the published one leaves the local copy alone.
            off = addons.scan(workshop, {"12345": False}, test_folder=testdir)
            by_id = {a.id: a for a in off}
            self.assertFalse(by_id["12345"].enabled)
            self.assertTrue(by_id[addons.TEST_ID_PREFIX + "12345"].enabled)

    def test_test_folder_finds_nested_modbuddy_project(self):
        """ModBuddy wraps a project in a solution folder of the same name, so
        a freshly created pack sits a level deeper than a workshop one. It has
        to be found there, and enabled without being touched first."""
        with tempfile.TemporaryDirectory() as tmp:
            testdir = os.path.join(tmp, "addon_test")
            nested = os.path.join(testdir, "MyPack")   # solution folder
            os.makedirs(nested)
            self._make_mod(nested, "MyPack", {        # project folder inside
                "name": "Nested Pack",
                "folders": {"STATE_AVENGER": "music/avenger"},
            }, {"music/avenger": ["a.mp3"]})

            found = addons.scan("", test_folder=testdir)
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].name, "Nested Pack")
            self.assertTrue(found[0].is_test)
            self.assertTrue(found[0].enabled, "a pack just dropped in must be on")
            self.assertEqual(found[0].folders_resolved(), ["state_avenger"])

    def test_workshop_subscribed_mods_stay_shallow(self):
        """A Steam-installed mod folder is named after the numeric workshop id
        and always holds its descriptor at the root. Those must NOT get a deep
        walk — thousands of them is what made startup crawl."""
        with tempfile.TemporaryDirectory() as tmp:
            workshop = os.path.join(tmp, "workshop")
            buried = os.path.join(workshop, "12345", "extra")
            os.makedirs(buried)
            self._make_mod(buried, "deep", {
                "name": "Too Deep",
                "folders": {"STATE_AVENGER": "music/avenger"},
            }, {"music/avenger": ["a.mp3"]})
            self.assertEqual(addons.scan(workshop), [])

    def test_hand_placed_workshop_folder_is_searched_deeper(self):
        """A folder someone copied into the workshop directory themselves is
        named whatever they liked, not a numeric id — and may well be a nested
        ModBuddy project. Those get found."""
        with tempfile.TemporaryDirectory() as tmp:
            workshop = os.path.join(tmp, "workshop")
            nested = os.path.join(workshop, "MyPack")   # solution folder
            os.makedirs(nested)
            self._make_mod(nested, "MyPack", {          # project folder inside
                "name": "Hand Placed",
                "folders": {"STATE_AVENGER": "music/avenger"},
            }, {"music/avenger": ["a.mp3"]})

            found = addons.scan(workshop)
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].name, "Hand Placed")
            self.assertEqual(found[0].id, "MyPack")
            self.assertFalse(found[0].is_test)
            self.assertTrue(found[0].enabled)

    def test_no_test_folder_behaves_as_before(self):
        with tempfile.TemporaryDirectory() as tmp:
            workshop = os.path.join(tmp, "workshop")
            os.makedirs(workshop)
            self._make_mod(workshop, "12345", {
                "name": "Pack", "folders": {"STATE_AVENGER": "music/avenger"},
            }, {"music/avenger": ["a.mp3"]})

            self.assertEqual(len(addons.scan(workshop)), 1)
            self.assertEqual(len(addons.scan(workshop, test_folder="")), 1)
            self.assertEqual(
                len(addons.scan(workshop, test_folder="/does/not/exist")), 1)

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

    def test_fixed_descriptor_name_and_legacy_suffix_both_work(self):
        """The descriptor is a fixed filename now — no renaming to match your
        mod. Packs published under the old `<Name>_xipod.json` scheme still
        have to load; breaking someone's uploaded mod over a filename would
        be indefensible."""
        with tempfile.TemporaryDirectory() as tmp:
            workshop = os.path.join(tmp, "workshop")
            os.makedirs(workshop)

            for mod_id, fname, label in (
                ("111", addons.DESCRIPTOR_NAME, "New"),
                ("222", "WhateverTheyCalledIt_xipod.json", "Legacy"),
            ):
                root = os.path.join(workshop, mod_id, "music")
                os.makedirs(root)
                with open(os.path.join(root, "a.mp3"), "wb") as f:
                    f.write(b"\x00")
                with open(os.path.join(workshop, mod_id, fname), "w",
                          encoding="utf-8") as f:
                    json.dump({"name": label,
                               "folders": {"STATE_AVENGER": "music"}}, f)

            found = {a.id: a.name for a in addons.scan(workshop)}
            self.assertEqual(found, {"111": "New", "222": "Legacy"})

    def test_uninstalled_addons_are_forgotten(self):
        """The descriptor is the identity — no *_xipod.json, no pack. Its
        remembered on/off setting goes with it rather than lingering."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = os.path.join(tmp, "xipod_config.json")
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump({"addons": {"still_here": False, "deleted": False}}, f)

            addons.prune_enabled_map(cfg_path, {"still_here"})

            with open(cfg_path, encoding="utf-8") as f:
                left = json.load(f)["addons"]
            self.assertEqual(left, {"still_here": False})

    def test_prune_leaves_config_alone_when_nothing_changed(self):
        """Must not rewrite the file on every startup for no reason."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = os.path.join(tmp, "xipod_config.json")
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump({"addons": {"a": True}, "other_setting": 42}, f)
            before = os.path.getmtime(cfg_path)

            addons.prune_enabled_map(cfg_path, {"a"})

            self.assertEqual(os.path.getmtime(cfg_path), before)
            with open(cfg_path, encoding="utf-8") as f:
                self.assertEqual(json.load(f)["other_setting"], 42)

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

    def test_schema_is_the_only_source_of_state_folders(self):
        """setup.STATE_FOLDERS and library.STATE_FOLDERS_FOR_MODS used to be
        two hand-written spellings of one fact. Both now come from
        helpers/state_folders.json, so they cannot drift apart."""
        import state_schema
        from library import STATE_FOLDERS_FOR_MODS

        self.assertEqual(list(STATE_FOLDERS), list(state_schema.STATE_FOLDERS))
        self.assertEqual(list(STATE_FOLDERS_FOR_MODS), list(STATE_FOLDERS))

        # Every folder maps back to a state the scanner recognises.
        for folder in STATE_FOLDERS:
            self.assertIn(folder.lower(), state_schema.ALL_KNOWN, folder)
        self.assertEqual(len(STATE_FOLDERS), len(state_schema.ALL_KNOWN))

        # Each looping state is immediately followed by its own _LOOP sibling.
        for i, folder in enumerate(STATE_FOLDERS):
            if folder.endswith("_LOOP"):
                self.assertEqual(STATE_FOLDERS[i - 1], folder[:-len("_LOOP")])

    def test_schema_key_mappings_match_settings(self):
        import state_schema
        import settings as settings_module

        for state, toggle in state_schema.TOGGLE_KEYS.items():
            self.assertEqual(settings_module._get_toggle_key(state), toggle)
        for state, loop in state_schema.LOOP_KEYS.items():
            self.assertEqual(settings_module._get_loop_key(state), loop)
        # Stingers and the radio folder have no loop key at all.
        for state in list(state_schema.STINGER_STATES) + [state_schema.RADIO_STATE]:
            self.assertIsNone(settings_module._get_loop_key(state), state)

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

    def test_volume_round_trips_and_uses_default(self):
        import spotify
        with tempfile.TemporaryDirectory() as tmp:
            sp, config_path = self._controller(tmp)
            # Against the constant, not a literal: the default is a tuning
            # value and has already moved once (60 -> 80, Spotify sat too
            # quiet under the game).
            self.assertEqual(sp.volume, spotify.DEFAULT_VOLUME)
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

    def __init__(self, playlists, active=True):
        self._playlists = playlists
        self.calls = []
        self.active = active

    def is_active(self):
        return self.active

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

    def test_toggled_off_state_is_not_handed_to_spotify(self):
        """A toggled-off screen belongs to the game's own music. Spotify used
        to ignore the toggle and play on top of MMS and the stock score."""
        e = self._engine()
        fake = _FakeSpotify({"state_shell_menu": "spotify:playlist:SH"})
        e.spotify = fake
        e.settings.toggles["shell_menu"] = False

        e.switch_state("state_shell_menu")
        self.assertEqual(fake.calls, [])
        self.assertFalse(e.is_spotify_active())
        # Silence, so the game's music comes through as it does without Spotify
        self.assertTrue(e._silent_override)

    def test_spotify_stands_down_when_entering_a_toggled_off_state(self):
        e = self._engine()
        fake = _FakeSpotify({"state_avenger": "spotify:playlist:AV",
                             "state_shell_menu": "spotify:playlist:SH"})
        e.spotify = fake
        e.settings.toggles["avenger"] = True
        e.settings.toggles["shell_menu"] = False

        e.switch_state("state_avenger")
        e.switch_state("state_shell_menu")
        self.assertIn(("pause", None), fake.calls)
        self.assertNotIn(("play", "spotify:playlist:SH"), fake.calls)
        self.assertTrue(e._silent_override)

    def test_spotify_state_counts_as_covered_for_silencing(self):
        """MMS silencing used to look only at local folders, so a Spotify-only
        state kept the game's music underneath the playlist."""
        e = self._engine()
        e.spotify = _FakeSpotify({"state_mission_combat": "spotify:playlist:CB"})
        for key in ("battle", "geoscape"):
            e.settings.toggles[key] = True
        e.library.library = {}          # no local tracks anywhere

        covered = e._toggle_keys_with_tracks()
        self.assertTrue(covered["battle"])      # Spotify covers it
        self.assertFalse(covered["geoscape"])   # nothing does — leave it to MMS

        # With the feature off, Spotify covers nothing.
        e.spotify.active = False
        self.assertFalse(e._toggle_keys_with_tracks()["battle"])


if __name__ == "__main__":
    unittest.main()

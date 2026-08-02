"""Anarchy Radio FM setup plumbing — config I/O, music-folder scaffolding,
game-path auto-detection, and Workshop music-pack import.

The actual first-run UI lives in setup_gui.py; this module holds the shared,
non-GUI pieces both the wizard and the running app use.
"""

import os
import json
import shutil
import console
import state_schema

from paths import data_path
from library import AUDIO_EXTENSIONS

# Per-user config — lives next to the exe when frozen, project root in dev.
CONFIG_PATH = data_path("xipod_config.json")

# Every state folder the music library expects, from helpers/state_folders.json.
# This was a hand-written list that had to match what library.py derived from
# its own state groupings; they were two spellings of one fact, and a test
# existed solely to check they still agreed.
STATE_FOLDERS = list(state_schema.STATE_FOLDERS)


# ------------------------------------------------------------------ #
#  Config I/O
# ------------------------------------------------------------------ #

def config_exists():
    return os.path.exists(CONFIG_PATH)


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    console.faint(f"Config saved: {CONFIG_PATH}")


# ------------------------------------------------------------------ #
#  Folder Structure
# ------------------------------------------------------------------ #

# Default locations, both sitting next to the exe (or the project root when
# running from source). Keeping them beside the app means the whole thing is
# portable — copy the folder to another drive and your music comes with it —
# and it means first-run setup has something sensible to offer instead of an
# empty box the user has to think about.
def default_music_folder():
    return data_path("music")


# Where ModBuddy drops a freshly built mod, relative to the steamapps root.
_MODBUDDY_OUTPUT = os.path.join(
    "common", "XCOM 2 SDK", "Binaries", "Win32", "ModBuddy", "Mods")


def default_addon_test_folder(game_exe="", workshop_folder=""):
    """Where to watch for music packs under test.

    Prefers ModBuddy's own output folder when the SDK is installed: a pack
    lands there the moment it builds, so testing it needs no copying at all —
    build, hit Save & Rescan, listen. That's the whole loop.

    Falls back to a folder beside the app for anyone without the SDK, who'll
    be dropping in packs by hand anyway.
    """
    from mms_packs import steamapps_root

    root = steamapps_root(workshop_folder) or steamapps_root(game_exe)
    if root:
        candidate = os.path.join(root, _MODBUDDY_OUTPUT)
        if os.path.isdir(candidate):
            return candidate

    return data_path("addon_test")


def default_addon_projects_folder():
    # Always beside the app, never derived from the test folder — the test
    # folder may well be somewhere that isn't ours to put things in.
    return data_path("addon_projects")


_ADDON_TEST_README = """Addon testing folder
====================

Drop an in-progress music pack in here — the whole mod folder, the one with
the xipod_settings.json descriptor in it — and Anarchy Radio FM will pick it
up exactly as if you'd subscribed to it on the Workshop.

    addon_test/
        MyMusicPack/
            xipod_settings.json
            music/
                STATE_AVENGER/
                    track.mp3

It shows up in the Music Addons panel with a TEST tag, and you can switch it
on and off like any other pack. Hit Save & Rescan after changing files.

This is for checking a pack works before you publish it. Nothing in here is
uploaded anywhere.

Its sibling addon_projects/ is where the ModBuddy solution itself belongs.
Keep the two apart: this folder holds BUILT packs, that one holds the project
you build them from.

Full guide: https://github.com/emzakit/xcom_anarchyfm/wiki/Making-a-music-pack
"""

_ADDON_PROJECTS_README = """Addon projects folder
=====================

Where your ModBuddy solutions live. Point ModBuddy at this folder under
Tools > Options > Projects and Solutions, and every music pack you start
lands here.

Built packs go in the addon_test folder next door — that's the one Anarchy
Radio FM watches. Keeping the project and the built copy apart means a
rebuild can't half-overwrite something the app is reading.

Full guide: https://github.com/emzakit/xcom_anarchyfm/wiki/Making-a-music-pack
"""


def _write_readme(folder, text):
    """Create `folder` and drop a README.txt in it if there isn't one."""
    os.makedirs(folder, exist_ok=True)
    readme = os.path.join(folder, "README.txt")
    if not os.path.exists(readme):
        with open(readme, "w", encoding="utf-8") as f:
            f.write(text)


def create_addon_test_folder(path):
    """Create the addon testing folder, and a projects folder for solutions.

    The README only goes in if we actually created the folder. The default
    testing folder is now ModBuddy's output directory, which already exists
    and already has a job — dropping our leaflet in someone else's filing
    cabinet isn't on.
    """
    if not path:
        return
    try:
        existed = os.path.isdir(path)
        os.makedirs(path, exist_ok=True)
        if not existed:
            _write_readme(path, _ADDON_TEST_README)
    except Exception as e:
        console.warn(f"Couldn't create the addon test folder: {e}")
        return

    try:
        _write_readme(default_addon_projects_folder(), _ADDON_PROJECTS_README)
    except Exception as e:
        console.debug(f"Couldn't create the addon projects folder: {e}")


def _create_state_folders(music_folder):
    """Create all expected state subfolders in the music library."""
    created = 0
    for folder in STATE_FOLDERS:
        path = os.path.join(music_folder, folder)
        if not os.path.exists(path):
            os.makedirs(path)
            created += 1
    if created:
        console.shen(f"Created {created} music folders in {music_folder}")
    else:
        console.shen("All music folders already exist. Good to go.")


# ------------------------------------------------------------------ #
#  Workshop Music Addons
# ------------------------------------------------------------------ #

def discover_addons(cfg):
    """Find the user's subscribed music addons, with their enabled state.

    Replaces the old import_workshop_mods(), which copied every pack's audio
    into the music folder on startup. Packs are now referenced where they sit
    and merged at scan time — see addons.py for why.
    """
    import addons

    workshop = cfg.get("workshop_folder", "")
    test_folder = cfg.get("addon_test_folder", "")

    found = addons.scan(
        workshop,
        addons.load_enabled_map(CONFIG_PATH),
        test_folder=test_folder,
    )

    # Forget packs that have gone. Guarded on the folders actually being
    # readable: an unplugged drive scans as zero addons, and pruning on that
    # would silently reset every on/off choice the user had made.
    if any(os.path.isdir(r) for r in (workshop, test_folder) if r):
        addons.prune_enabled_map(CONFIG_PATH, {a.id for a in found})

    return found


# ------------------------------------------------------------------ #
#  Path Helpers — auto-detection of the game's user folders
# ------------------------------------------------------------------ #

def find_log_path_silent():
    """Auto-detect the XCOM 2 WotC Launch.log, or return "" if not found.
    (The log is created the first time the game runs.)"""
    userprofile = os.environ.get("USERPROFILE", os.path.expanduser("~"))
    candidates = [
        os.path.join(userprofile, "Documents", "my games",
                     "XCOM2 War of the Chosen", "XComGame", "Logs", "Launch.log"),
        os.path.join(userprofile, "OneDrive", "Documents", "my games",
                     "XCOM2 War of the Chosen", "XComGame", "Logs", "Launch.log"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return ""


def find_workshop_folder(game_exe=None):
    """Auto-detect <Steam>/steamapps/workshop/content/268500.

    This is no longer a nicety for music packs. MMS reads its settings from
    each mod's own Config folder — the game does not mirror mod config files
    into the user's Documents config directory — so without a route to the
    installed Anarchy Radio FM folder nothing gets silenced and the mod plays
    on top of the game's music. See mms_packs.find_own_config_dirs.

    Derived from the game executable, which sits under the same steamapps
    root, so an install on any drive or library folder resolves without
    asking the user to find it themselves.
    """
    roots = []

    if game_exe:
        # Walk up looking for the steamapps component.
        path = os.path.abspath(game_exe)
        while True:
            parent = os.path.dirname(path)
            if parent == path:
                break
            if os.path.basename(path).lower() == "steamapps":
                roots.append(path)
                break
            path = parent

    userprofile = os.environ.get("USERPROFILE", os.path.expanduser("~"))
    roots.extend([
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                     "Steam", "steamapps"),
        os.path.join(userprofile, "Steam", "steamapps"),
    ])

    for root in roots:
        candidate = os.path.join(root, "workshop", "content", "268500")
        if os.path.isdir(candidate):
            return candidate
    return ""


def _find_game_config_folder(log_path=None):
    """Auto-detect the XCOM 2 user Config folder.

    Tries: derive from log_path, then common default locations.
    Returns path string or None if not found.
    """
    # If we have a log path, derive from it (Logs/ -> Config/)
    if log_path:
        xcomgame_dir = os.path.dirname(os.path.dirname(log_path))
        candidate = os.path.join(xcomgame_dir, "Config")
        if os.path.isdir(candidate):
            return candidate

    # Try common locations
    userprofile = os.environ.get("USERPROFILE", os.path.expanduser("~"))
    candidates = [
        os.path.join(userprofile, "Documents", "my games",
                     "XCOM2 War of the Chosen", "XComGame", "Config"),
        os.path.join(userprofile, "OneDrive", "Documents", "my games",
                     "XCOM2 War of the Chosen", "XComGame", "Config"),
    ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    return None

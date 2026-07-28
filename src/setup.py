"""Anarchy Radio FM setup plumbing — config I/O, music-folder scaffolding,
game-path auto-detection, and Workshop music-pack import.

The actual first-run UI lives in setup_gui.py; this module holds the shared,
non-GUI pieces both the wizard and the running app use.
"""

import os
import json
import shutil
import console

from paths import data_path
from library import AUDIO_EXTENSIONS

# Per-user config — lives next to the exe when frozen, project root in dev.
CONFIG_PATH = data_path("xipod_config.json")

# Every state folder the music library expects
STATE_FOLDERS = [
    "STATE_SHELL_MENU",
    "STATE_SHELL_MENU_LOOP",
    "STATE_AVENGER",
    "STATE_AVENGER_LOOP",
    "STATE_GEOSCAPE",
    "STATE_GEOSCAPE_LOOP",
    "STATE_SQUADSELECT",
    "STATE_SQUADSELECT_LOOP",
    "STATE_MISSION_EXPLORE",
    "STATE_MISSION_EXPLORE_LOOP",
    "STATE_MISSION_COMBAT",
    "STATE_MISSION_COMBAT_LOOP",
    "STATE_VICTORY",
    "STATE_DEFEAT",
    "STATE_RESISTANCE_RADIO",
]


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
    return addons.scan(
        cfg.get("workshop_folder", ""),
        addons.load_enabled_map(CONFIG_PATH),
    )


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

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

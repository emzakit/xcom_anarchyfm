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
#  Workshop Mod Import
# ------------------------------------------------------------------ #

def import_workshop_mods(cfg):
    """Scan the workshop folder for *_xipod.json descriptors and copy tracks.

    Descriptors live in each mod's ROOT folder (per the modding guide), so
    only look one level deep — a full os.walk over thousands of workshop
    mods made every startup crawl."""
    workshop = cfg.get("workshop_folder", "")
    music_folder = cfg.get("music_folder", "")
    if not workshop or not music_folder:
        return

    if not os.path.isdir(workshop):
        return

    found = 0
    try:
        mod_dirs = [os.path.join(workshop, d) for d in os.listdir(workshop)]
    except OSError as e:
        console.warn(f"Couldn't read workshop folder: {e}")
        return

    for mod_root in mod_dirs:
        if not os.path.isdir(mod_root):
            continue
        try:
            files = os.listdir(mod_root)
        except OSError:
            continue
        for fname in files:
            if fname.lower().endswith("_xipod.json"):
                json_path = os.path.join(mod_root, fname)
                try:
                    _import_single_mod(json_path, mod_root, music_folder)
                    found += 1
                except Exception as e:
                    console.warn(f"Couldn't import {fname}: {e}")

    if found:
        console.shen(f"Imported {found} community music pack(s).")
    else:
        console.faint("No community music packs found in the workshop yet.")


def _import_single_mod(json_path, mod_root, music_folder):
    """Read one _xipod.json descriptor and copy its music into the library.

    Expected JSON format:
    {
        "name": "My Music Pack",
        "author": "SomeModder",
        "folders": {
            "STATE_MISSION_EXPLORE": "music/explore",
            "STATE_MISSION_COMBAT":  "music/combat"
        }
    }

    Each key in "folders" is a target state folder name.
    Each value is a relative path (from the mod root) containing audio files.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        descriptor = json.load(f)

    mod_name = descriptor.get("name", os.path.basename(json_path))
    folders = descriptor.get("folders", {})
    if not folders:
        return

    console.shen(f"Importing music pack: {mod_name}")
    copied = 0

    for state_folder, source_sub in folders.items():
        # Validate target state folder (case-insensitive; use canonical name)
        canonical = state_folder.strip().upper()
        if canonical not in STATE_FOLDERS:
            console.warn(f"  Unknown state folder '{state_folder}' in {mod_name} — skipping.")
            continue

        src_dir = os.path.normpath(os.path.join(mod_root, source_sub))
        dst_dir = os.path.join(music_folder, canonical)

        # Descriptor paths must stay inside the mod folder
        if not src_dir.lower().startswith(os.path.normpath(mod_root).lower()):
            console.warn(f"  Path outside mod folder '{source_sub}' in {mod_name} — skipping.")
            continue

        if not os.path.isdir(src_dir):
            continue
        if not os.path.isdir(dst_dir):
            os.makedirs(dst_dir)

        for audio_file in os.listdir(src_dir):
            if audio_file.lower().endswith(AUDIO_EXTENSIONS):
                src_path = os.path.join(src_dir, audio_file)
                dst_path = os.path.join(dst_dir, audio_file)
                if not os.path.exists(dst_path):
                    shutil.copy2(src_path, dst_path)
                    console.faint(f"  + {state_folder}/{audio_file}")
                    copied += 1

    if copied:
        console.debug(f"{copied} track(s) added from {mod_name}.")


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

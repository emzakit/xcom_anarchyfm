"""Music Mod Scaffolding — creates a ready-to-fill workshop music mod project."""

import os
import json

from setup import STATE_FOLDERS

# Folders a mod can target (exclude RESISTANCE_RADIO — that's user-only)
MOD_FOLDERS = [f for f in STATE_FOLDERS if f != "STATE_RESISTANCE_RADIO"]


def scaffold_music_mod(project_dir):
    """Create folder structure + _xipod.json + README in the given directory."""
    music_dir = os.path.join(project_dir, "music")
    os.makedirs(music_dir, exist_ok=True)

    folders_map = {}
    for state in MOD_FOLDERS:
        sub = state.replace("STATE_", "").lower()
        os.makedirs(os.path.join(music_dir, sub), exist_ok=True)
        folders_map[state] = f"music/{sub}"

    descriptor = {
        "name": os.path.basename(project_dir),
        "author": "",
        "folders": folders_map,
    }
    json_name = os.path.basename(project_dir).lower().replace(" ", "_") + "_xipod.json"
    with open(os.path.join(project_dir, json_name), "w", encoding="utf-8") as f:
        json.dump(descriptor, f, indent=2)

    with open(os.path.join(project_dir, "README.txt"), "w", encoding="utf-8") as f:
        f.write("Anarchy Radio FM Music Mod\n" + "=" * 40 + "\n\n")
        f.write("Drop your audio files (.mp3, .ogg, .wav, .flac, .m4a, .opus)\n"
                "into the folders\n")
        f.write("inside music/ that match the game states you want to replace.\n\n")
        f.write("Folder reference:\n")
        for state in MOD_FOLDERS:
            nice = state.replace("STATE_", "").replace("_", " ").title()
            sub = state.replace("STATE_", "").lower()
            f.write(f"  music/{sub}/  ->  {nice}\n")
        f.write("\nLeave folders empty for states you don't want to change.\n")
        f.write("Empty folders are ignored during import.\n\n")
        f.write(f"Edit {json_name} to set your mod name and author.\n")
        f.write("Then publish your mod folder to Steam Workshop.\n")
        f.write("Users with Anarchy Radio FM will auto-import your tracks.\n")

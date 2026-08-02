"""The state taxonomy, loaded from helpers/state_folders.json.

Every list of game states in this app derives from that one file. Before it,
the same taxonomy was written out four times — the folder names in setup.py,
the state groupings in library.py, and the toggle and loop mappings in
settings.py — and adding a state meant finding all four and keeping them in
agreement. A test existed purely to check two of them still matched.

Nothing here is configurable by the user. It's the app's own structure, kept in
JSON so there is exactly one place to change it.
"""

import json
import os

from paths import resource_path

SCHEMA_PATH = resource_path("helpers", "state_folders.json")


def _load():
    """Read the schema. Raises if it isn't there — this is not optional data.

    A missing or broken schema means no states, which means no folders, no
    music and no silencing: an app that starts up and does nothing, with no
    clue as to why. Failing here with the path in the message is considerably
    kinder than that. It's a bundled file, so this can only fire on a build
    that was assembled wrong, which build.json verification would also catch.
    """
    try:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise RuntimeError(
            f"Couldn't read the state schema at {SCHEMA_PATH}: {e}\n"
            "This build is incomplete — reinstall from a release zip."
        ) from e

    states = data.get("states")
    if not isinstance(states, list) or not states:
        raise RuntimeError(f"State schema at {SCHEMA_PATH} lists no states.")
    return data


_DATA = _load()
_STATES = _DATA["states"]


def _role(entry):
    return (entry.get("role") or "music").lower()


def folder_for(state_key):
    """The folder name on disk for a state key. STATE_AVENGER, and so on."""
    return state_key.upper()


# --- Groupings ----------------------------------------------------------- #

# States with their own music folder AND a _LOOP sibling. The everyday ones.
BASE_STATES = [s["key"] for s in _STATES
               if _role(s) == "music" and s.get("loop_folder")]

# The _LOOP variants, as a set because membership is all anyone asks of it.
LOOP_STATES = {s["key"] + "_loop" for s in _STATES if s.get("loop_folder")}

# Play once, then stand by: no loop, no advance to a next track.
STINGER_STATES = [s["key"] for s in _STATES if _role(s) == "stinger"]

# The shared Resistance Radio folder.
RADIO_STATE = next((s["key"] for s in _STATES if _role(s) == "radio"), "")

# Every state key the scanner recognises, loop variants included.
ALL_KNOWN = set(BASE_STATES) | LOOP_STATES | set(STINGER_STATES) | {RADIO_STATE}
ALL_KNOWN.discard("")

def _folder_order():
    """Every folder on disk, each state followed by its own _LOOP sibling.

    The pairing is for whoever reads this list — the setup wizard scaffolds
    from it and the pack docs print it, and STATE_AVENGER sitting next to
    STATE_AVENGER_LOOP explains the relationship without a word of prose.
    Stingers and the radio folder come last; neither has a loop variant.
    """
    out = []
    for entry in _STATES:
        if _role(entry) != "music":
            continue
        out.append(folder_for(entry["key"]))
        if entry.get("loop_folder"):
            out.append(folder_for(entry["key"] + "_loop"))
    out += [folder_for(k) for k in STINGER_STATES]
    if RADIO_STATE:
        out.append(folder_for(RADIO_STATE))
    return out


# Used to scaffold a new music folder, and to tell pack authors which folders
# a mod may ship.
STATE_FOLDERS = _folder_order()


# --- Settings key mappings ------------------------------------------------ #

TOGGLE_KEYS = {s["key"]: s["toggle"] for s in _STATES if s.get("toggle")}
LOOP_KEYS = {s["key"]: s["loop"] for s in _STATES if s.get("loop")}

# A loop key that a broader toggle also switches on: Battle loops the whole
# mission, while Explore and Combat narrow it to one phase.
LOOP_MASTERS = {str(k): str(v) for k, v in
                (_DATA.get("loop_masters") or {}).items()}

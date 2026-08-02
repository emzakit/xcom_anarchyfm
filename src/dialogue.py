"""The station's dialogue, loaded from helpers/dialogue.json.

Every line the app says to a user lives in that file, keyed by an id, with its
speaker attached. Call sites say `dialogue.say("engine.switching", old=..,
new=..)` and never contain the words themselves — so the voice can be rewritten
by anyone, in one file, without touching a line of Python.

Deliberately forgiving. This is flavour text: an unknown key, a missing
placeholder or a missing file are all annoying, none are worth taking the app
down for. Every failure degrades to something readable and carries on.
"""

import json
import os
import random

import console
from paths import resource_path

DIALOGUE_PATH = resource_path("helpers", "dialogue.json")

# Where an unknown speaker ends up. Shen is the safe default: she's the one who
# talks when something's off, which is what an unknown key means.
_DEFAULT_SPEAKER = "shen"

_WARNED = set()


def _load():
    try:
        with open(DIALOGUE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        console.warn(f"Couldn't read the dialogue file ({e}). "
                     "Falling back to plain messages.")
        return {"speakers": {}, "lines": {}}
    return {
        "speakers": data.get("speakers") or {},
        "lines": data.get("lines") or {},
    }


_DATA = _load()


def reload():
    """Re-read the file. Handy while writing lines — no restart needed."""
    global _DATA
    _DATA = _load()
    _WARNED.clear()
    return len(_DATA["lines"])


def _entry(key):
    entry = _DATA["lines"].get(key)
    if entry is None and key not in _WARNED:
        _WARNED.add(key)
        console.debug(f"No dialogue line for '{key}'.")
    return entry or {}


def speaker_of(key):
    """Which of shen/jax/silo says this line."""
    return _entry(key).get("speaker") or _DEFAULT_SPEAKER


def line(key, **kwargs):
    """The formatted text for `key`, or a readable stand-in.

    `variants` beats `text` when present — one is chosen at random, so lines
    said many times an evening don't wear a groove.
    """
    entry = _entry(key)
    variants = entry.get("variants")
    template = random.choice(variants) if variants else entry.get("text")
    if not template:
        # Never nothing. The key is ugly but it's traceable, which beats a
        # blank line in someone's log.
        return f"[{key}]"

    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError) as e:
        # A renamed placeholder shouldn't silence the station.
        if key not in _WARNED:
            _WARNED.add(key)
            console.debug(f"Dialogue '{key}' wanted a value it didn't get: {e}")
        return template


def say(key, **kwargs):
    """Speak a line, routed to whoever owns it."""
    text = line(key, **kwargs)
    {
        "jax": console.jax,
        "silo": console.silo,
        "shen": console.shen,
    }.get(speaker_of(key), console.shen)(text)
    return text


def alert(key, **kwargs):
    """Speak a line in red, as SHEN, whatever the file says.

    Anything urgent enough to call this is a broadcast problem, and broadcast
    problems are hers regardless of who happened to be on shift.
    """
    text = line(key, **kwargs)
    console.alert(text)
    return text

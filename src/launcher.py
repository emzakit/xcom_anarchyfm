"""Alternative Mod Launcher integration — adding `-forcelogflush` for the user.

The app learns what XCOM is doing by reading `Launch.log`, and the game buffers
that file. Without `-forcelogflush` a cinematic writes nothing while it plays,
so "a cinematic started" can arrive up to 27 seconds late — after the film has
finished and your music has already talked over it.

It is the single most important setup step and the easiest one to skip, which
is a miserable combination. When someone launches through AML we can just look
at its settings and offer to add the flag ourselves.

Rules for touching somebody else's launcher config, none of them negotiable:

  * **Back up first.** Always, to a timestamped file, before a byte changes.
  * **Only ever append.** Existing arguments are left exactly as they are —
    people have their own reasons for what's in that list.
  * **Ask first.** This module only ever reports; the GUI does the asking.
  * **Write it back the way AML wrote it** — UTF-8 with a BOM, indented — or
    the launcher may not read its own file afterwards.
"""

import datetime
import json
import os
import shutil

import console

FLAG = "-forcelogflush"

SETTINGS_NAME = "settings.json"

# Keys that together mean "this really is an AML settings file" rather than
# some other program's settings.json that happens to sit beside an exe.
_AML_MARKERS = ("ArgumentList", "Mods")


def settings_path(game_exe):
    """Path to the launcher's settings.json, or "" if this isn't AML.

    Identified by the file's own shape rather than the exe's name: the exe is
    called "XCOM2 Launcher.exe", which is exactly what somebody would name a
    shortcut, a wrapper, or their own script.
    """
    if not game_exe:
        return ""
    path = os.path.join(os.path.dirname(os.path.abspath(game_exe)), SETTINGS_NAME)
    if not os.path.isfile(path):
        return ""
    data = _read(path)
    if data is None:
        return ""
    if not all(key in data for key in _AML_MARKERS):
        return ""
    return path


def _read(path):
    """Load AML's settings.json. It's UTF-8 with a BOM; utf-8-sig eats that."""
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        console.debug(f"Couldn't read the launcher settings: {e}")
        return None
    return data if isinstance(data, dict) else None


def status(game_exe):
    """What we know about this launcher. Never raises.

    Returns a dict:
        is_aml    — settings.json found and it looks like AML's
        path      — where that file is
        has_flag  — whether -forcelogflush is already in ArgumentList
        args      — the current argument list, for showing the user
    """
    path = settings_path(game_exe)
    if not path:
        return {"is_aml": False, "path": "", "has_flag": False, "args": []}

    data = _read(path) or {}
    args = [str(a) for a in (data.get("ArgumentList") or [])]
    return {
        "is_aml": True,
        "path": path,
        "has_flag": any(a.strip().lower() == FLAG for a in args),
        "args": args,
    }


def backup(path):
    """Copy settings.json aside before touching it. Returns the backup path.

    Timestamped, and never reused. A date-only name would let a second run on
    the same Tuesday overwrite the pristine original with one already edited —
    which defeats the entire point — and seconds alone aren't enough either,
    because two calls in the same second collide just as happily. So the name
    is checked and a counter appended until it's genuinely free.
    """
    folder = os.path.dirname(path)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(folder, f"settings_{stamp}.bkp")
    counter = 2
    while os.path.exists(dest):
        dest = os.path.join(folder, f"settings_{stamp}-{counter}.bkp")
        counter += 1
    shutil.copy2(path, dest)
    return dest


def add_forcelogflush(game_exe):
    """Append the flag to AML's argument list. Returns (ok, message, backup).

    Appends only. Everything already in the list stays, in its original order.
    """
    info = status(game_exe)
    if not info["is_aml"]:
        return False, "That doesn't look like the Alternative Mod Launcher.", ""
    if info["has_flag"]:
        return True, f"{FLAG} was already set — nothing to do.", ""

    path = info["path"]
    data = _read(path)
    if data is None:
        return False, "Couldn't read the launcher's settings.json.", ""

    try:
        saved = backup(path)
    except OSError as e:
        # No backup, no edit. Failing here costs the user a manual step;
        # editing without one could cost them their launcher setup.
        return False, f"Couldn't back up settings.json ({e}) — left it alone.", ""

    args = list(data.get("ArgumentList") or [])
    args.append(FLAG)
    data["ArgumentList"] = args

    tmp = path + ".tmp"
    try:
        # Same encoding AML uses, or it may not read its own file back.
        with open(tmp, "w", encoding="utf-8-sig") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except OSError as e:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False, f"Couldn't write settings.json ({e}). Your backup: {saved}", saved

    console.shen(f"Added {FLAG} to the Alternative Mod Launcher's arguments.")
    console.faint(f"(previous settings saved as {os.path.basename(saved)})")
    return True, f"Added {FLAG}. Restart the launcher for it to take effect.", saved


# ------------------------------------------------------------------ #
#  Plain game exe
# ------------------------------------------------------------------ #

# The two places XCOM's own exe lives. Vanilla and War of the Chosen.
_GAME_EXE_NAMES = ("xcom2.exe",)


def is_game_exe(path):
    """True when this is XCOM's own executable rather than a launcher.

    There's no arguments field to edit and no settings file to patch, so the
    flag can't be stored anywhere — but it doesn't need to be. When this app
    launches the game it simply passes the flag itself; see
    process_utils.launch_args.
    """
    if not path:
        return False
    return os.path.basename(path).lower() in _GAME_EXE_NAMES


# ------------------------------------------------------------------ #
#  Launch-time check
# ------------------------------------------------------------------ #

def warn_if_flag_missing(game_exe):
    """Shout, in red, if the launcher has lost its -forcelogflush.

    Checked once at startup rather than watched continuously: the flag only
    changes when someone edits their launcher, and that isn't something that
    happens mid-session. Worth checking every launch though, because it
    absolutely does get removed — by a launcher update, by tidying the
    arguments list, or by someone else's guide.

    Returns True when everything's fine.
    """
    try:
        info = status(game_exe)
    except Exception as e:
        console.debug(f"Launch-option check failed: {e}")
        return True

    if not info["is_aml"]:
        return True                     # nothing we can inspect
    if info["has_flag"]:
        console.debug(f"{FLAG} present in the launcher's arguments.")
        return True

    console.alert(f"{FLAG} is MISSING from your Alternative Mod Launcher "
                  "arguments!")
    console.alert("Music will play straight over your cinematics until it's "
                  "back. Run setup and press the button, or add it under "
                  "Options > Settings > Active arguments.")
    return False

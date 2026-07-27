"""Process helpers — tasklist queries and game/launcher lifecycle plumbing.

Detection runs a single unfiltered `tasklist` call (with CREATE_NO_WINDOW so
nothing flashes while the app is windowless) and matches any number of
process names against it. This module also owns launching the configured
game/launcher exe, shared by the GUI and CLI front-ends.
"""

import os
import subprocess

import console

GAME_PROCESS = "XCom2.exe"  # Same binary name for base game and WotC

# Windows-only flag; guarded so the module still imports elsewhere.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def running_processes(names):
    """Return the subset of `names` that are currently running (case-insensitive).

    On any failure returns None — callers should treat that as "unknown"
    rather than "not running" so a transient tasklist hiccup never
    triggers an auto-shutdown.
    """
    wanted = {n.lower(): n for n in names if n}
    if not wanted:
        return set()
    try:
        result = subprocess.run(
            ["tasklist", "/NH", "/FO", "CSV"],
            capture_output=True, text=True, timeout=10,
            creationflags=_NO_WINDOW,
        )
        if result.returncode != 0:
            return None
        found = set()
        for line in result.stdout.splitlines():
            if not line.startswith('"'):
                continue
            proc = line.split('","', 1)[0].strip('"').lower()
            if proc in wanted:
                found.add(wanted[proc])
        return found
    except Exception:
        return None


def is_running(name, default=False):
    """True if the named process is running. Returns `default` when the
    check itself fails — pass default=True where the safe assumption is
    "already running" (e.g. to avoid double-launching the game)."""
    found = running_processes([name])
    if found is None:
        return default
    return bool(found)


def is_game_running(default=False):
    """True if XCOM 2 is currently running."""
    return is_running(GAME_PROCESS, default=default)


# ------------------------------------------------------------------ #
#  Game / launcher lifecycle (shared by GUI and CLI)
# ------------------------------------------------------------------ #

def watched_names(game_exe):
    """The process names whose lifetimes keep the app alive: the game
    itself, plus the configured launcher (e.g. AML) when it's a separate
    executable. Used by the dual-gate auto-shutdown logic."""
    names = [GAME_PROCESS]
    exe = os.path.basename(game_exe or "")
    if exe and exe.lower() != GAME_PROCESS.lower():
        names.append(exe)
    return names


def launch_game(cfg):
    """Start the configured game/launcher exe, unless it's already running
    (or the path is missing). Fire-and-forget; failures just warn."""
    game_exe = cfg.get("game_exe", "")
    if not game_exe or not os.path.isfile(game_exe):
        console.warn("Game executable not found. Launch it manually, Commander.")
        return
    exe_name = os.path.basename(game_exe)
    # Don't spawn a second copy if the launcher/game is already up
    if is_running(exe_name, default=True):
        console.shen(f"{exe_name} is already running. Standing by.")
        return
    console.shen(f"Launching {exe_name}...")
    try:
        subprocess.Popen(
            [game_exe], cwd=os.path.dirname(game_exe),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        console.warn(f"Couldn't launch {exe_name}: {e}")
        console.shen("Launch it manually — I'll be waiting.")

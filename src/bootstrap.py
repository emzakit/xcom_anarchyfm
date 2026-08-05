"""Getting the app open when the first-run wizard can't be.

No config beside the exe means the setup wizard runs, and the wizard is a
single point of failure for the entire application: it draws before the main
window exists, so anything that goes wrong inside it takes the whole app down
in a windowless build — silently, with no window ever appearing. v2.4.2 shipped
exactly that (an AttributeError in ``SetupWindow.__init__``), and a first-time
install had no way in at all.

The wizard is still the front door. This module is the key under the mat:

  * ``run_setup_gui_safely`` runs the wizard, and if it fails to open, writes
    a blank config and lets the app carry on to its main window. Every path
    the wizard asks for can be set in Options, so a broken wizard costs
    convenience rather than the whole program.

  * ``write_blank_config`` is that config. Every path in it empty on purpose —
    ``start_engine`` says which one is missing and stops with the window up,
    whereas a guessed path is a wrong answer nobody is prompted to check.

  * ``ensure_rescue_script`` writes ``create_config.bat``, the manual way to
    produce the same config for when the app can't be started at all. A plain
    batch file for the same reasons ``update_manually.bat`` is one: it still
    works when nothing else in the folder does, needs no build step, and can't
    add to the antivirus false-positive problem the real exe already has.

Both file bodies are embedded here rather than bundled as PyInstaller datas,
and that's the point. They exist to rescue an install that has had something
go wrong with it; sourcing them from another file in that same install would
make the rescue depend on exactly the thing being rescued.

Nothing here ever overwrites. A file that's already there is somebody's — it
holds their paths, or their edits — and replacing it would be the single most
destructive thing this module could do. Missing is the only case it acts on.
"""

import os

import console
from paths import data_path

CONFIG_NAME = "xipod_config.json"
CREATE_CONFIG_NAME = "create_config.bat"


# ------------------------------------------------------------------ #
#  xipod_config.json
# ------------------------------------------------------------------ #
# Every path left empty on purpose. The app starts perfectly well without
# them — start_engine simply says which one is missing and stops, with the
# window up and Options reachable — whereas a guessed path is a wrong answer
# that nobody is prompted to check.
#
# The _README key is ignored by every reader and preserved by every writer
# (they all read-modify-write the whole dict), so the instructions survive
# being edited from Options. Forward slashes are laboured because a single
# backslash is a JSON escape character: "C:\XCOM" doesn't load, and the file
# it breaks is the one holding the instructions for fixing it.

_CONFIG_TEMPLATE = r"""{
  "_README": [
    "Anarchy Radio FM - config file. Put this next to AnarchyRadioFM.exe.",
    "",
    "Its presence alone is enough to get the app open. You can then set",
    "every path below from the Options window instead of editing this file.",
    "",
    "If you do edit it: USE FORWARD SLASHES.",
    "   RIGHT:  C:/Program Files (x86)/Steam/steamapps/common/XCOM 2",
    "   WRONG:  C:\\Program Files (x86)\\Steam\\steamapps\\common\\XCOM 2",
    "A single backslash makes this file unreadable and the app will show",
    "an error instead of starting. Forward slashes work fine on Windows.",
    "",
    "Leave anything you cannot find as \"\" and fix it later in Options.",
    "",
    "game_exe           your XCom2.exe, or your mod launcher's exe. Usually",
    "                   C:/Program Files (x86)/Steam/steamapps/common/",
    "                   XCOM 2/XCom2-WarOfTheChosen/Binaries/Win64/XCom2.exe",
    "",
    "music_folder       where your music lives. The 'music' folder next to",
    "                   AnarchyRadioFM.exe is the normal answer. The STATE_",
    "                   folders inside it are created for you on first launch.",
    "",
    "log_path           the Launch.log FILE, not the folder. Usually",
    "                   C:/Users/YOU/Documents/my games/",
    "                   XCOM2 War of the Chosen/XComGame/Logs/Launch.log",
    "                   If OneDrive backs up your Documents, it is under",
    "                   C:/Users/YOU/OneDrive/Documents/ instead.",
    "",
    "game_config_folder same place as the log, ending in Config instead of",
    "                   Logs/Launch.log",
    "",
    "workshop_folder    C:/Program Files (x86)/Steam/steamapps/workshop/",
    "                   content/268500",
    "                   This one matters most: without it XCOM's own music is",
    "                   NOT silenced and plays over yours."
  ],

  "game_exe": "",
  "music_folder": "",
  "log_path": "",
  "game_config_folder": "",
  "workshop_folder": "",

  "addon_test_folder": "",
  "mod_config_folder": "",
  "auto_close_with_game": true,
  "default_volume": 0.8,
  "shuffle": true,
  "crossfade_ms": 2500,
  "radio_chunk_minutes": 10
}
"""


# ------------------------------------------------------------------ #
#  create_config.bat
# ------------------------------------------------------------------ #
# ASCII only, and it has to stay that way: cmd reads a .bat in the console's
# OEM codepage, so anything fancier turns to mojibake on somebody else's
# machine. There's a test pinning this.

_CREATE_CONFIG_BAT = r"""@echo off
rem Anarchy Radio FM - write xipod_config.json by hand.
rem
rem Ships inside the install folder, next to AnarchyRadioFM.exe. Same reasoning
rem as update_manually.bat: a plain batch file still works when nothing else in
rem the folder does, needs no build step, and can't add to the antivirus
rem false-positive problem the real exe already has.
rem
rem Why this exists: the app only opens its setup wizard when there is no
rem xipod_config.json beside the exe. v2.4.2 shipped with that wizard broken
rem (an AttributeError before the window is drawn), so a first-time install had
rem no way in. Writing the config here skips the wizard entirely - every other
rem window, including Options, is unaffected, so paths can be corrected in the
rem app afterwards.
rem
rem It asks rather than searches. The usual location for each path is printed
rem above its prompt, which is enough for anyone to find it in Explorer, and it
rem means there is no detection logic here that can quietly guess wrong on a
rem machine nobody tested.
rem
rem Paths are written with forward slashes. Windows accepts them everywhere,
rem and it avoids the one mistake that silently breaks a hand-edited JSON file:
rem a single backslash is an escape character, so "C:\XCOM" is invalid JSON.
rem
rem ASCII only. cmd reads a .bat in the console's OEM codepage, so anything
rem fancier turns to mojibake on somebody else's machine.

setlocal
title Anarchy Radio FM - Create Config

cd /d "%~dp0"
set "OUT=%~dp0xipod_config.json"

echo.
echo  ============================================================
echo   Anarchy Radio FM - create xipod_config.json
echo  ============================================================
echo.
echo   Writing into: %~dp0
echo.

rem A note, not a refusal - the file is written wherever this is put. But the
rem app reads its config from beside the exe, so anywhere else does nothing.
if not exist "AnarchyRadioFM.exe" echo   NOTE: AnarchyRadioFM.exe is not in this folder. The app only
if not exist "AnarchyRadioFM.exe" echo         reads the config sitting next to it, so put this file in
if not exist "AnarchyRadioFM.exe" echo         that folder and run it again if you meant to fix an install.
if not exist "AnarchyRadioFM.exe" echo.

rem Never clobber a working config without being told to. Deliberately not
rem written as an if(...) block: cmd expands %REPLY% when it PARSES the block,
rem which is before set /p has run, so the answer would always read as empty.
if not exist "%OUT%" goto :no_existing_config

echo   You already have a xipod_config.json in this folder.
echo.
set "REPLY="
set /p "REPLY=  Replace it? Type Y to overwrite, anything else to stop: "
if /i "%REPLY%"=="Y" goto :no_existing_config

echo.
echo   Left it alone. Nothing was changed.
echo.
pause
endlocal
exit /b 0

:no_existing_config
echo   Four paths are needed. The usual place for each is shown above
echo   its question - check there first.
echo.
echo   Tip: drag the folder or file from Explorer into this window and
echo        the path types itself. Then press Enter.
echo.
echo  ------------------------------------------------------------
echo.
echo   1. Your XCOM 2 executable, or your mod launcher's exe.
echo.
echo      Usually:
echo      C:\Program Files (x86)\Steam\steamapps\common\XCOM 2\
echo          XCom2-WarOfTheChosen\Binaries\Win64\XCom2.exe
echo.
echo      Using the Alternative Mod Launcher? Point this at
echo      "XCOM2 Launcher.exe" instead.
call :ask GAME_EXE

echo.
echo  ------------------------------------------------------------
echo.
echo   2. Your XCOM 2 Logs FOLDER - the folder, not Launch.log.
echo.
echo      Usually:
echo      %USERPROFILE%\Documents\my games\XCOM2 War of the Chosen\XComGame\Logs
echo.
echo      If OneDrive backs up your Documents it will be under
echo      %USERPROFILE%\OneDrive\Documents\ instead.
call :ask LOGDIR

echo.
echo  ------------------------------------------------------------
echo.
echo   3. Your XCOM 2 Config folder.
echo.
echo      Same place as the Logs folder, but ending in Config:
echo      %USERPROFILE%\Documents\my games\XCOM2 War of the Chosen\XComGame\Config
call :ask CFGDIR

echo.
echo  ------------------------------------------------------------
echo.
echo   4. Your Steam Workshop folder - the one ending in 268500.
echo.
echo      Usually:
echo      C:\Program Files (x86)\Steam\steamapps\workshop\content\268500
echo.
echo      This one matters: without it the game's own music is NOT
echo      silenced and XCOM plays its soundtrack over yours. If Steam
echo      is on another drive, look for steamapps\workshop there.
call :ask WORKSHOP

rem Not asked for. It is simply the "music" folder beside the app, which is
rem what the setup wizard offers anyway, and the app creates the STATE_
rem folders inside it on first launch. Changeable later in Options.
set "MUSIC=%~dp0music"

rem The config stores the log FILE, which is what the app reads. It is
rem created by the game on first launch, so it is fine if it isn't there yet.
rem Left blank when no folder was given, rather than becoming "\Launch.log".
set "LOGFILE="
if defined LOGDIR set "LOGFILE=%LOGDIR%\Launch.log"

rem ---------------------------------------------------------------- rem
rem  Check what's missing
rem ---------------------------------------------------------------- rem
rem Done BEFORE the slashes are flipped: `if exist` is not dependable on a
rem forward-slashed path, so these have to run while the paths are still
rem ordinary Windows ones.

set "WARNED="
call :need_file "%GAME_EXE%" "the game exe was not found at that path"
call :need_dir "%LOGDIR%" "the Logs folder was not found at that path"
call :need_dir "%CFGDIR%" "the Config folder was not found at that path"
call :need_dir "%WORKSHOP%" "no valid Workshop folder - the game's music will NOT be silenced"

rem ---------------------------------------------------------------- rem
rem  Write it
rem ---------------------------------------------------------------- rem

call :slashes GAME_EXE
call :slashes MUSIC
call :slashes LOGFILE
call :slashes CFGDIR
call :slashes WORKSHOP

rem Delayed expansion for the values only. A path is allowed to contain an
rem ampersand ("D:\Games & Mods\..."), and with plain %VAR% that ampersand
rem reaches cmd as a command separator and truncates the line mid-JSON.
rem !VAR! is substituted after parsing, so it can't. Values holding a literal
rem "!" are safe too - the result of an expansion is not rescanned.
setlocal enabledelayedexpansion
>"%OUT%" echo {
>>"%OUT%" echo   "game_exe": "!GAME_EXE!",
>>"%OUT%" echo   "music_folder": "!MUSIC!",
>>"%OUT%" echo   "log_path": "!LOGFILE!",
>>"%OUT%" echo   "game_config_folder": "!CFGDIR!",
>>"%OUT%" echo   "workshop_folder": "!WORKSHOP!",
>>"%OUT%" echo   "addon_test_folder": "",
>>"%OUT%" echo   "mod_config_folder": "",
>>"%OUT%" echo   "auto_close_with_game": true,
>>"%OUT%" echo   "default_volume": 0.8,
>>"%OUT%" echo   "shuffle": true,
>>"%OUT%" echo   "crossfade_ms": 2500,
>>"%OUT%" echo   "radio_chunk_minutes": 10
>>"%OUT%" echo }
endlocal

echo.
echo  ============================================================
echo.
if not exist "%OUT%" (
    echo   ERROR: could not write xipod_config.json into this folder.
    echo   If the app lives under Program Files, Windows may be blocking
    echo   the write - move the whole folder somewhere like your Desktop
    echo   and run this again.
    echo.
    pause
    endlocal
    exit /b 1
)

echo   Written: xipod_config.json
echo.

rem Anything flagged further up, said plainly rather than left to fail later.
if defined WARNED echo   None of that stops the app starting. Open Options
if defined WARNED echo   once it is running and correct the paths there.
if defined WARNED echo.

echo   Your music goes in the "music" folder next to the app. The
echo   STATE_ folders inside it are created on first launch.
echo.
echo   Now run AnarchyRadioFM.exe.
echo.
echo   Do NOT start it with the --setup switch - that forces the broken
echo   setup wizard open again. Everything it asked for can be changed
echo   from the Options window instead.
echo.
pause
endlocal
exit /b 0


rem ---------------------------------------------------------------- rem
rem  Helpers
rem ---------------------------------------------------------------- rem

rem :ask VARNAME - read one path, strip the quotes Explorer adds when a path
rem is dragged in, and leave the variable empty if nothing was typed.
:ask
setlocal
echo.
set "ANS="
set /p "ANS=      Path: "
rem Only strip quotes when there is something to strip. A substitution on an
rem empty variable does not reliably come back empty - it can leave the
rem substitution pattern itself behind as the value.
if not defined ANS goto :ask_out
set ANS=%ANS:"=%
:ask_out
endlocal & set "%~1=%ANS%"
goto :eof

rem Warn when a path is blank or isn't there. Takes the path as an argument so
rem an empty variable can't weld itself onto the next backslash: `if exist
rem "%EMPTY%\"` becomes `if exist "\"`, and the escaped quote swallows the
rem rest of the line.
:need_file
if "%~1"=="" goto :need_warn
if exist "%~1" goto :eof
goto :need_warn

:need_dir
if "%~1"=="" goto :need_warn
if exist "%~1\" goto :eof
:need_warn
call :warn "%~2"
goto :eof

rem Backslashes to forward slashes, so the JSON is valid.
:slashes
setlocal
call set "V=%%%~1%%"
if not defined V goto :sl_out
set "V=%V:\=/%"
:sl_out
endlocal & set "%~1=%V%"
goto :eof

:warn
echo   NOTE: %~1.
set "WARNED=1"
goto :eof
"""


# ------------------------------------------------------------------ #
#  Writing
# ------------------------------------------------------------------ #

def _write_new(path, text, encoding="utf-8", crlf=False):
    """Write `text` to `path`, but only if nothing is there. True if written.

    Via a temp file and os.replace, so the file either appears complete or
    doesn't appear at all. A half-written config is worse than none: the app
    would find it, fail to parse it, and never offer to write another — and
    the user has no reason to suspect the file it keeps complaining about is
    one it created itself.

    Line endings are normalised first so the source's own don't leak through.
    The batch file needs CRLF; cmd is unreliable about LF-only scripts, and
    the failure is a mangled `goto` rather than an error anybody can read.
    """
    if os.path.exists(path):
        return False

    data = text.replace("\r\n", "\n").replace("\r", "\n")
    if crlf:
        data = data.replace("\n", "\r\n")

    tmp = path + ".tmp"
    try:
        with open(tmp, "wb") as f:
            f.write(data.encode(encoding))
        os.replace(tmp, path)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return True


def _try_write(name, body, encoding="utf-8", crlf=False):
    """_write_new against the app folder, swallowing whatever it hits.

    Never raises. These run at startup, and the folder they write into may
    well be one Windows won't allow writes to — an install under Program
    Files, or a folder still marked read-only by whatever unzipped it.
    Neither is a reason for the app not to start.
    """
    try:
        return _write_new(data_path(name), body, encoding=encoding, crlf=crlf)
    except Exception as e:
        console.debug(f"Couldn't write {name}: {e}")
        return False


def ensure_rescue_script():
    """Put create_config.bat beside the exe if it isn't there. True if written.

    Every start, not just the first. It's the way back in when the app won't
    open, which is precisely the moment nobody can rely on the app having put
    it there — so it gets replaced as soon as anything notices it's gone.
    """
    # ASCII by intent, not by accident — see the note above the batch body.
    # Encoding here is what enforces it.
    return _try_write(CREATE_CONFIG_NAME, _CREATE_CONFIG_BAT,
                      encoding="ascii", crlf=True)


def write_blank_config():
    """Write an empty xipod_config.json if there isn't one. True if written.

    Not called at startup. Its presence is what tells the app the wizard has
    already been through, so writing it up front would mean nobody ever sees
    the wizard again — this is the fallback for when the wizard cannot run,
    and nothing else.
    """
    return _try_write(CONFIG_NAME, _CONFIG_TEMPLATE)


def run_setup_gui_safely(existing_cfg=None):
    """Open the first-run wizard. Survive it not opening.

    Returns the config to carry on with, or None to mean "no config, and no
    way to make one" — which is the only case that should still stop the app.

    The wizard draws before the main window exists, so an exception inside it
    escapes with nothing on screen: in a windowless build the app appears not
    to start, and there's nothing written down. That's a bad enough failure to
    be worth a net under it, permanently, rather than only until the bug of
    the day is fixed.

    Cancelling is not failing. A user who closes the wizard gets None from it
    and None from here, and the caller treats that as they always have.
    """
    from setup_gui import run_setup_gui

    try:
        return run_setup_gui(existing_cfg=existing_cfg)
    except Exception as e:
        import traceback
        console.alert(f"The setup window wouldn't open: {type(e).__name__}: {e}")
        for line in traceback.format_exc().rstrip().splitlines():
            console.faint(line)

        # Already configured — the wizard was a re-run (--setup), so there's
        # a perfectly good config sitting there. Let the caller keep it.
        if existing_cfg is not None:
            console.shen("Carrying on with your existing settings. Options can "
                         "change anything the wizard would have.")
            return None

        if not write_blank_config():
            return None

        console.shen(
            f"I've written a blank {CONFIG_NAME} instead so we can still get "
            "airborne. Open Options and point me at your game, your music and "
            "your log.")
        try:
            from setup import load_config
            return load_config()
        except Exception as e:
            console.warn(f"...and then couldn't read it back: {e}")
            return None

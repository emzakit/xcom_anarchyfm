@echo off
rem Anarchy Radio FM - manual update helper.
rem
rem Ships inside the install folder. Deliberately a plain batch file rather
rem than a second exe: it works even when nothing else in this folder does,
rem it needs no build step, and it can't add to the antivirus false-positive
rem problem the real exe already has.
rem
rem ASCII only. cmd reads a .bat in the console's OEM codepage, so anything
rem fancier turns to mojibake on somebody else's machine.

setlocal
title Anarchy Radio FM - Update Manually

rem The folder name carries the version, so no parsing required.
for %%I in ("%~dp0.") do set "HERE=%%~nxI"

echo.
echo  ============================================================
echo   Anarchy Radio FM - update by hand
echo  ============================================================
echo.
echo   This folder : %HERE%
echo.

rem Any kept previous version means reverting is still possible.
set "FOUND="
for /d %%D in ("%~dp0_previous_v*") do (
    if not defined FOUND echo   You can also go back to:
    set "FOUND=1"
    echo     %%~nxD    ^(see HOW_TO_REVERT.txt inside it^)
)
if defined FOUND echo.

echo   Opening the releases page in your browser...
echo.
start "" "https://github.com/emzakit/xcom_anarchyfm/releases"

echo   To install the newest version by hand:
echo.
echo     1. Download the AnarchyRadioFM_APP_v...zip from that page.
echo     2. Unzip it wherever you like - it makes its own folder.
echo     3. Run AnarchyRadioFM.exe inside it.
echo.
echo   Your settings and music are NOT inside the app folder unless you
echo   put them there. If you want to carry settings over, copy these
echo   from this folder into the new one:
echo.
echo     xipod_config.json
echo     xipod_presets.json
echo.
echo   Nothing here has been changed. This only opened a web page.
echo.
pause
endlocal

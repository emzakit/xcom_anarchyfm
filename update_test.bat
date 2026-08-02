@echo off
rem Try the update path against a local zip, without publishing anything.
rem Asks for a release zip and an install folder, then runs the real updater.
cd /d "%~dp0"

if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" update_test.py
) else (
    python update_test.py
)

echo.
pause

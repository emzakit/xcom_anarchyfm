@echo off
:: Anarchy Radio FM launcher. First run creates a virtual environment and
:: installs dependencies; after that it just boots the app windowless (no
:: console — the comms log is shown inside the app). Anarchy Radio FM itself
:: starts the game / mod launcher (and skips that if it's already running).

cd /d "%~dp0"

:: --- Create the virtual environment on first run ---
if not exist "venv\Scripts\activate.bat" (
    echo First run: creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo.
        echo ERROR: Could not create the virtual environment.
        echo Make sure Python 3.10+ is installed and on your PATH.
        pause
        exit /b 1
    )
    echo Installing dependencies...
    ".\venv\Scripts\python.exe" -m pip install --upgrade pip
    ".\venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: Dependency install failed. See messages above.
        pause
        exit /b 1
    )
)

:: Launch the GUI with pythonw (no console window), detached, then exit so
:: this command window closes too. Advanced/CLI users: run the app directly
:: with  venv\Scripts\python.exe src\main.py --cli
start "" ".\venv\Scripts\pythonw.exe" src\main.py %*

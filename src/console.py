"""Anarchy Radio FM Console — Shen-flavored terminal output with ANSI green styling.

Also writes timestamped logs to _logs/ inside the music folder for debugging.
Call init_file_log(music_folder) once at startup to enable file logging.
"""

import atexit
import os
import sys
import threading
from datetime import datetime

# ------------------------------------------------------------------ #
#  ANSI Escape Codes (green terminal theme)
# ------------------------------------------------------------------ #

# When the GUI is launched with pythonw.exe there is NO console, so
# sys.stdout / sys.stderr are None. Route them to devnull first so the
# many print() calls below never crash — the GUI comms log and the file
# log still capture everything.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")
    _HAS_CONSOLE = False
else:
    _HAS_CONSOLE = True

# Enable ANSI escape codes on Windows 10+ (only when a real console exists;
# os.system("") would otherwise pop a console window under pythonw).
if sys.platform == "win32" and _HAS_CONSOLE:
    os.system("")  # Triggers VT100 mode on Windows console

# When stdout is piped/redirected it may use a legacy code page (cp1252)
# that can't encode our box-drawing characters. A print() raising
# UnicodeEncodeError mid-state-switch kills the switch — replace
# unencodable characters instead of crashing.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
GREEN  = "\033[32m"
BRIGHT = "\033[92m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
GRAY   = "\033[90m"

# Composite styles
SHEN    = f"{BRIGHT}"          # Main text
HEADER  = f"{BOLD}{BRIGHT}"    # Section headers
TRACK   = f"{BOLD}{CYAN}"      # Track names
SIGNAL  = f"{YELLOW}"          # Incoming signals
SUBTLE  = f"{GREEN}"           # Debug/dim info
FAINT   = f"{GRAY}"            # Very low priority


# ------------------------------------------------------------------ #
#  File Logging — timestamped log file in _logs/ folder
# ------------------------------------------------------------------ #

_log_file = None
_log_lock = threading.Lock()

# Keep this many log files around; older ones are pruned at startup.
_MAX_LOG_FILES = 10


def _prune_old_logs(logs_dir):
    """Delete the oldest xipod_*.log files, keeping the newest few."""
    try:
        logs = sorted(
            f for f in os.listdir(logs_dir)
            if f.startswith("xipod_") and f.endswith(".log")
        )
        # Keep the newest (_MAX_LOG_FILES - 1); the new session's log makes it max.
        excess = len(logs) - (_MAX_LOG_FILES - 1)
        for old in logs[:excess] if excess > 0 else []:
            try:
                os.remove(os.path.join(logs_dir, old))
            except OSError:
                pass
    except Exception:
        pass


def _close_file_log():
    global _log_file
    if _log_file is not None:
        try:
            _log_file.close()
        except Exception:
            pass
        _log_file = None


def init_file_log(music_folder):
    """Create _logs/ folder inside the music directory and open a dated log file."""
    global _log_file
    try:
        logs_dir = os.path.join(music_folder, "_logs")
        os.makedirs(logs_dir, exist_ok=True)
        _prune_old_logs(logs_dir)
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = os.path.join(logs_dir, f"xipod_{stamp}.log")
        _log_file = open(path, "w", encoding="utf-8", buffering=1)  # line-buffered
        atexit.register(_close_file_log)
        _file_write(f"Anarchy Radio FM log started: {stamp}")
        _file_write(f"Music folder: {music_folder}")
    except Exception as e:
        print(f"  WARNING: Could not create log file: {e}")


def _file_write(msg):
    """Write a timestamped line to the log file (thread-safe)."""
    if _log_file is None:
        return
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    tid = threading.current_thread().name
    with _log_lock:
        try:
            _log_file.write(f"[{ts}][{tid}] {msg}\n")
        except Exception:
            pass


# ------------------------------------------------------------------ #
#  Styled Print Helpers
# ------------------------------------------------------------------ #

def shen(msg):
    """Standard Shen message."""
    print(f"{SHEN}  SHEN: {msg}{RESET}")
    _file_write(f"SHEN: {msg}")

def track(label, name):
    """Track name display."""
    print(f"{SHEN}  {label}: {TRACK}{name}{RESET}")
    _file_write(f"TRACK: {label}: {name}")

def signal(msg):
    """Incoming game signal."""
    print(f"{SIGNAL}  >> {msg}{RESET}")
    _file_write(f"SIGNAL: {msg}")

def debug(msg):
    """Low-priority debug info."""
    print(f"{SUBTLE}     {msg}{RESET}")
    _file_write(f"DEBUG: {msg}")

def warn(msg):
    """Warning message."""
    print(f"{YELLOW}  SHEN: {msg}{RESET}")
    _file_write(f"WARN: {msg}")

def error(msg):
    """Error message."""
    print(f"{BOLD}{YELLOW}  SHEN: {msg}{RESET}")
    _file_write(f"ERROR: {msg}")

def faint(msg):
    """Very dim text for noise."""
    print(f"{FAINT}     {msg}{RESET}")
    _file_write(f"FAINT: {msg}")

def divider():
    """Horizontal rule."""
    print(f"{GREEN}  {'─' * 52}{RESET}")


# ------------------------------------------------------------------ #
#  Boot Screen (plaintext title)
# ------------------------------------------------------------------ #

def show_boot_art():
    """Print a simple plaintext title banner (CLI / terminal mode)."""
    print()
    print(f"{HEADER}  ANARCHY RADIO FM{RESET}")
    print(f"{GREEN}  {'─' * 40}{RESET}")
    print(f"{FAINT}  Local & Spotify soundtracks for XCOM 2{RESET}")
    print()

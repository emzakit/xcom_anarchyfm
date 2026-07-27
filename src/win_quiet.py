"""Stop child processes from flashing a console window on Windows.

When Anarchy Radio FM runs windowless (pythonw.exe, no console of its own),
a child process spawned without a "no window" flag pops a brief blank console
and grabs foreground focus — which, in a fullscreen game, throws you to the
desktop.

Track decoding used to be the worst offender: pydub shelled out to
ffmpeg/ffprobe for every single track, so each music-state change flashed a
console. That path is gone — decode.py now decodes in-process via PyAV — but
we still spawn tasklist, explorer and the game launcher. Patching
subprocess.Popen to always add CREATE_NO_WINDOW covers all of them; they're
GUI or piped-stdio processes, so suppressing the console is harmless.
"""

import subprocess
import sys

# subprocess.CREATE_NO_WINDOW exists on Windows / Python 3.7+.
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def silence_child_console_windows():
    """Idempotently patch subprocess.Popen so children get no console window."""
    if sys.platform != "win32":
        return
    if getattr(subprocess.Popen.__init__, "_arfm_no_window", False):
        return  # already patched

    _orig_init = subprocess.Popen.__init__

    def _init(self, *args, **kwargs):
        flags = kwargs.get("creationflags", 0) or 0
        kwargs["creationflags"] = flags | _CREATE_NO_WINDOW
        _orig_init(self, *args, **kwargs)

    _init._arfm_no_window = True
    subprocess.Popen.__init__ = _init

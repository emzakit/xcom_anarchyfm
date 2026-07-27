"""Path resolution that works both from source and in a PyInstaller build.

Two kinds of files, two roots:

* resource_path(...)  — read-only files bundled with the app
                        (xipod_defaults.json, the banner, assets/).
                        Frozen: PyInstaller's extraction dir (sys._MEIPASS
                        for onefile, the app dir for onedir).
                        Source: the project root (parent of src/).

* data_path(...)      — files the app WRITES and must persist between runs
                        (xipod_config.json, xipod_presets.json).
                        Frozen: the folder next to the .exe.
                        Source: the project root.

Never store writable data under resource_path — in a onefile build that's a
temp dir that vanishes on exit.
"""

import os
import sys

# Project root when running from source: parent of src/
_SOURCE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def is_frozen():
    """True when running inside a PyInstaller bundle."""
    return getattr(sys, "frozen", False)


def resource_path(*parts):
    """Absolute path to a bundled read-only resource."""
    if is_frozen():
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = _SOURCE_ROOT
    return os.path.join(base, *parts)


def data_path(*parts):
    """Absolute path for persistent, user-writable app data."""
    if is_frozen():
        base = os.path.dirname(sys.executable)
    else:
        base = _SOURCE_ROOT
    return os.path.join(base, *parts)

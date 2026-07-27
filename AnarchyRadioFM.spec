# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Anarchy Radio FM.

Build with:
    venv\\Scripts\\pyinstaller.exe AnarchyRadioFM.spec --noconfirm

Produces a ONEDIR build at dist/AnarchyRadioFM/ — zip that folder for
release. Onedir (not onefile) on purpose: Qt starts faster, and
xipod_config.json / xipod_presets.json are written next to the exe where
users can find them (see src/paths.py).

On build size: this used to be ~507 MB, almost entirely QtWebEngine — the
old embedded-browser Web Player pulled in a whole copy of Chromium. That
feature is gone, so nothing here imports QtWebEngine and PySide6-Addons isn't
installed at all. The excludes and the prune pass below keep it that way and
clear out the leftovers Qt ships by default.
"""

import os


a = Analysis(
    ["src\\main.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        # (source, dest-folder-inside-bundle) — read via paths.resource_path()
        ("xipod_defaults.json", "."),
        ("assets/banner.png", "assets"),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        # QtWebEngine and the QML/Quick stack it drags behind it. Listed even
        # though PySide6-Addons shouldn't be installed, so that a dev with a
        # stale venv doesn't silently ship a 500 MB build again.
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineQuick", "PySide6.QtWebChannel",
        "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuick3D",
        "PySide6.QtQuickWidgets", "PySide6.QtQuickControls2",
        "PySide6.QtPdf", "PySide6.QtPdfWidgets",
        "PySide6.QtPositioning", "PySide6.QtDesigner", "PySide6.QtUiTools",
        "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtSensors",
        "PySide6.QtSerialPort", "PySide6.QtTest",
        "PySide6.QtRemoteObjects", "PySide6.QtScxml",
        "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
        "PySide6.Qt3DCore", "PySide6.Qt3DRender",
    ],
    noarchive=False,
)


# ------------------------------------------------------------------ #
#  Prune pass
# ------------------------------------------------------------------ #
# Qt hooks collect a fixed set of side files regardless of what's imported.
# These are the ones we know this app never reads.

def _drop(entry):
    """True if this collected file should be left out of the bundle."""
    dest = entry[0].replace("\\", "/")
    low = dest.lower()

    # Qt's UI translations — the app is English-only and never calls
    # QTranslator, so every .qm here is dead weight (~7 MB).
    if "/translations/" in low and low.endswith(".qm"):
        return True

    # Mesa software OpenGL fallback (~20 MB). Qt Widgets renders through the
    # normal desktop GL/D3D path; this is only a rescue for machines with no
    # usable GL driver, which was really a QtWebEngine concern.
    if os.path.basename(low) == "opengl32sw.dll":
        return True

    # Qt's debug-symbol .pak variants, if a stale Addons install leaks any
    # WebEngine resources through.
    if low.endswith((".debug.pak", ".debug.bin")):
        return True

    return False


_before = len(a.binaries) + len(a.datas)
a.binaries = TOC([e for e in a.binaries if not _drop(e)])
a.datas = TOC([e for e in a.datas if not _drop(e)])
print(f"[spec] prune pass dropped {_before - len(a.binaries) - len(a.datas)} files")


pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AnarchyRadioFM",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,             # windowless — the comms log lives in the GUI
    icon="assets\\AnarchyRadioFM.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="AnarchyRadioFM",
)

# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Anarchy Radio FM.

Build with:
    venv\\Scripts\\pyinstaller.exe AnarchyRadioFM.spec --noconfirm

Produces a ONEDIR build at dist/AnarchyRadioFM/ — zip that folder for
release. Onedir (not onefile) on purpose: Qt/WebEngine start faster, and
xipod_config.json / xipod_presets.json are written next to the exe where
users can find them (see src/paths.py).
"""

a = Analysis(
    ["src\\main.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        # (source, dest-folder-inside-bundle) — read via paths.resource_path()
        ("xipod_defaults.json", "."),
        ("AnarchyFM.png", "."),
    ],
    hiddenimports=[
        # Imported lazily (inside the Web Player button handler), so
        # PyInstaller's static analysis would otherwise miss it — and with
        # it, the whole QtWebEngine stack.
        "gui.browser",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineCore",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Trim things we definitely don't use to keep the bundle smaller.
        "tkinter",
        "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuick3D",
        "PySide6.QtPdf", "PySide6.QtPdfWidgets",
        "PySide6.QtDesigner", "PySide6.QtUiTools",
        "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtSensors",
        "PySide6.QtSerialPort", "PySide6.QtTest",
        "PySide6.QtRemoteObjects", "PySide6.QtScxml",
        "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
        "PySide6.Qt3DCore", "PySide6.Qt3DRender",
    ],
    noarchive=False,
)

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

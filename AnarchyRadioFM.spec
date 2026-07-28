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
        # ModBuddy project template stamped out by the Create Mod button.
        # Tree() keeps the folder structure; .XCOM_suo is ModBuddy's per-user
        # state and has no business shipping.
        *[(os.path.join(dp, f), os.path.join("addon_template", os.path.relpath(dp, "addon_template")))
          for dp, _dn, fn in os.walk(os.path.join("addon_template", "ModName_xipod"))
          for f in fn if not f.lower().endswith((".xcom_suo", ".user"))],
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


# ------------------------------------------------------------------ #
#  Windows version resource
# ------------------------------------------------------------------ #

def _version_resource():
    import re
    src = open(os.path.join("src", "version.py"), encoding="utf-8").read()
    ver = re.search(r'__version__\s*=\s*"([^"]+)"', src).group(1)
    parts = [int(p) for p in re.findall(r"\d+", ver)][:4]
    parts += [0] * (4 - len(parts))
    quad = ", ".join(str(p) for p in parts)

    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({quad}), prodvers=({quad}),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)
  ),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'emzakit'),
      StringStruct('FileDescription', 'Anarchy Radio FM - custom soundtracks for XCOM 2'),
      StringStruct('FileVersion', '{ver}'),
      StringStruct('InternalName', 'AnarchyRadioFM'),
      StringStruct('LegalCopyright', 'Copyright (c) 2026 emzakit. MIT Licence.'),
      StringStruct('OriginalFilename', 'AnarchyRadioFM.exe'),
      StringStruct('ProductName', 'Anarchy Radio FM'),
      StringStruct('ProductVersion', '{ver}'),
      StringStruct('Comments', 'Open source: https://github.com/emzakit/xcom_anarchyfm'),
    ])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    path = os.path.join("build", "version_info.txt")
    os.makedirs("build", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"[spec] version resource: {ver}")
    return path


_VERSION_FILE = _version_resource()


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
    version=_VERSION_FILE,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="AnarchyRadioFM",
)

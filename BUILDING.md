# Building the Anarchy Radio FM .exe

This turns the Python app into a standalone Windows build that users can run
without installing Python. The in-game Workshop mod is built separately (in
ModBuddy) and is not covered here.

## One-time setup

```bash
venv\Scripts\pip install pyinstaller
```

## Before you build a release

Bump `__version__` in **`src/version.py`**, and make the GitHub release tag
match it. That number is what the in-app updater compares against the latest
release, so if it lags behind the tag every user gets offered an update they
already have — and if it runs ahead, nobody is ever told about a real one.

## Build

```bash
venv\Scripts\pyinstaller.exe AnarchyRadioFM.spec --noconfirm
```

That produces a **onedir** build:

```
dist/AnarchyRadioFM/
  AnarchyRadioFM.exe      <- the app
  _internal/              <- Python runtime, Qt, bundled resources
```

Zip the whole `AnarchyRadioFM` folder for release as
`AnarchyRadioFM_App_v<version>.zip` (the `_App` suffix keeps it distinct from
the Workshop mod download) — the exe does not work without its `_internal`
sibling.

```powershell
Compress-Archive -Path dist\AnarchyRadioFM -DestinationPath dist\AnarchyRadioFM_App_v2.2.0.zip -Force
```

Current release: **174 MB installed, 72 MB zipped.**

## Why onedir (not onefile)

- Qt starts noticeably faster without the self-extract step.
- `xipod_config.json` and `xipod_presets.json` are written **next to the
  exe**, so users can find/back up their settings (see `src/paths.py` for
  how frozen vs. source paths are resolved).

## What ships inside vs. what users still need

Bundled: Python, PySide6-Essentials, PyAV (which carries ffmpeg's decoder
libraries), pydub, pedalboard, PyAudio, the banner art, and
`xipod_defaults.json`.

**Not bundled — users still need:**
- The **in-game Workshop mod** + **MMS**, as always.
- **Nothing else.** ffmpeg used to be a prerequisite; it isn't any more.

## Build size

The build is ~174 MB installed / 72 MB zipped. It was ~507 MB until the
embedded-browser Web Player
was removed — QtWebEngine alone was ~360 MB of that (a 195 MB
`Qt6WebEngineCore.dll`, 101 MB of resources, 44 MB of locales). The app no
longer embeds a browser engine at all, so none of it ships.

Keeping it down:

- **Install `PySide6-Essentials`, never `PySide6`.** The `PySide6`
  meta-package pulls in `PySide6-Addons`, which is what carries QtWebEngine.
  The spec `excludes` list guards against this, but a venv with Addons
  installed is still the easiest way to accidentally re-bloat the build.
  (Note: `pip uninstall PySide6-Addons` deletes shared Qt DLLs that
  Essentials also needs — reinstall Essentials with `--force-reinstall
  --no-deps` afterwards, or QtWidgets fails to import.)
- The spec's **prune pass** drops Qt's `.qm` translations (~7 MB, unused —
  the app never calls `QTranslator`) and `opengl32sw.dll` (~20 MB, the Mesa
  software-GL fallback that was really a WebEngine concern).
- The bundled banner is **`assets/banner.png`** (512 px, 1 MB), not the
  2048 px `AnarchyFM.png` in the project root — it's never drawn wider than
  ~240 px, and the original cost 9.6 MB for nothing. The big one stays in the
  repo for the README.

The largest remaining block is `av.libs` at ~63 MB. It can't be trimmed:
`avcodec` statically imports the video codec DLLs (libx265, libSvtAv1Enc,
libvpx, libx264), so deleting them breaks `import av` outright even though we
only ever decode audio.

## First run of a fresh build

The exe starts with no config, so the setup wizard opens — point it at the
game/launcher and a music folder, same as the source version. Config files
appear next to the exe.

## Gotchas

- Add new bundled resource files to BOTH the `datas` list in
  `AnarchyRadioFM.spec` and read them via `paths.resource_path()`.
- Anything the app *writes* must go through `paths.data_path()` (or a
  user-chosen folder), never `resource_path()`.
- Modules imported lazily must be listed in `hiddenimports` in the spec, or
  PyInstaller won't bundle them. Nothing needs this right now.
- `build/` and `dist/` are git-ignored; the `.spec` file is tracked.
- Supported audio extensions live in **one place**: `AUDIO_EXTENSIONS` in
  `src/library.py`. The scanner and the Workshop importer both use it. If you
  add a format there, update the tables in `music/music_readme.md` and
  `addon_template/MODDING_GUIDE.md` to match — and check `src/decode.py` actually reads it
  (PyAV handles far more than the list advertises).

## Smoke-testing a build

The exe is windowless, so a crash on startup is silent. Quickest check that the
bundle actually loaded Qt, PyAV and the rest:

```powershell
$p = Start-Process dist\AnarchyRadioFM\AnarchyRadioFM.exe -PassThru
Start-Sleep 9
if ($p.HasExited) { "CRASHED $($p.ExitCode)" } else { "OK"; Stop-Process $p.Id -Force }
```

# Building the Anarchy Radio FM .exe

This turns the Python app into a standalone Windows build that users can run
without installing Python. The in-game Workshop mod is built separately (in
ModBuddy) and is not covered here.

## One-time setup

```bash
venv\Scripts\pip install pyinstaller
```

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

Zip the whole `AnarchyRadioFM` folder for release — the exe does not work
without its `_internal` sibling.

## Why onedir (not onefile)

- Qt / QtWebEngine start noticeably faster without the self-extract step.
- `xipod_config.json` and `xipod_presets.json` are written **next to the
  exe**, so users can find/back up their settings (see `src/paths.py` for
  how frozen vs. source paths are resolved).

## What ships inside vs. what users still need

Bundled: Python, PySide6 (incl. QtWebEngine for the Web Player), pydub,
pedalboard, PyAudio, the banner art, and `xipod_defaults.json`.

**Not bundled — users still need:**
- **ffmpeg on PATH** for `.mp3` / `.ogg` decoding (`.wav` needs nothing).
- The **in-game Workshop mod** + **MMS**, as always.

## First run of a fresh build

The exe starts with no config, so the setup wizard opens — point it at the
game/launcher and a music folder, same as the source version. Config files
appear next to the exe.

## Gotchas

- Add new bundled resource files to BOTH the `datas` list in
  `AnarchyRadioFM.spec` and read them via `paths.resource_path()`.
- Anything the app *writes* must go through `paths.data_path()` (or a
  user-chosen folder), never `resource_path()`.
- Modules imported lazily (like `gui.browser`) must be listed in
  `hiddenimports` in the spec, or PyInstaller won't bundle them.
- `build/` and `dist/` are git-ignored; the `.spec` file is tracked.

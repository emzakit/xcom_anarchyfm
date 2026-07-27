# Anarchy Radio FM Music Modding Guide

Create custom music packs for Anarchy Radio FM, the external music extension for XCOM 2.

---

## How Anarchy Radio FM Works

Anarchy Radio FM replaces XCOM 2's in-game music by feeding silent SoundCues to MMS (Music Modding System), then playing your own audio files externally. Each game state (main menu, Avenger, combat, etc.) maps to a folder. Drop audio files into those folders and Anarchy Radio FM plays them when the game enters that state.

**Requirements**: Anarchy Radio FM mod + MMS (Music Modding System) must both be installed and enabled in XCOM 2.

---

## Folder Structure

Anarchy Radio FM's music library is a single folder containing state subfolders. Each subfolder corresponds to a game state:

| Folder | Game State | Description |
|--------|-----------|-------------|
| `STATE_SHELL_MENU/` | Main menu | Title screen / shell menu |
| `STATE_SHELL_MENU_LOOP/` | Main menu (loop) | Looping variant of shell music |
| `STATE_AVENGER/` | Avenger | Base management (Avenger interior) |
| `STATE_AVENGER_LOOP/` | Avenger (loop) | Looping variant of Avenger music |
| `STATE_GEOSCAPE/` | Geoscape | Hologlobe / world map |
| `STATE_GEOSCAPE_LOOP/` | Geoscape (loop) | Looping variant of Geoscape music |
| `STATE_SQUADSELECT/` | Squad Select | Pre-mission squad loadout screen |
| `STATE_SQUADSELECT_LOOP/` | Squad Select (loop) | Looping variant |
| `STATE_MISSION_EXPLORE/` | Tactical: Explore | Tactical mission, no enemies alerted |
| `STATE_MISSION_EXPLORE_LOOP/` | Tactical: Explore (loop) | Looping variant |
| `STATE_MISSION_COMBAT/` | Tactical: Combat | Tactical mission, enemies engaged |
| `STATE_MISSION_COMBAT_LOOP/` | Tactical: Combat (loop) | Looping variant |
| `STATE_VICTORY/` | Victory stinger | After-action: flawless or with casualties |
| `STATE_DEFEAT/` | Defeat stinger | After-action: squad wipe / mission loss |
| `STATE_RESISTANCE_RADIO/` | Resistance Radio | The station pool — used by the Radio Mode button (Avenger) and the per-state Radio Source checkbox |

### How Playlists Resolve

Checked in this order:

1. **Radio Mode button ON, and the state is the Avenger.** Tracks come from
   whichever folder the Radio Source buttons select — `STATE_RESISTANCE_RADIO/`,
   `STATE_AVENGER/`, or both pooled — always with a forced random start.
   This path **ignores `STATE_AVENGER_LOOP/` and the Loop setting entirely**:
   a station that repeats one track forever isn't a station.
2. **Per-state Radio Source checkbox** (Effects panel, works on any state).
   Tracks play from `STATE_RESISTANCE_RADIO/` instead of the state's own
   folder, falling back to the state folder if the radio pool is empty.
3. **Loop enabled for the state.** Anarchy Radio FM checks the `_LOOP` folder
   first. If it has tracks, those are used and repeated. If empty, falls back
   to the base folder.
4. **Otherwise**, tracks play from the base state folder.
5. **If a folder is empty**, Anarchy Radio FM does nothing for that state and
   the game's native music (via MMS) plays through.

> The Radio Mode button is **Avenger-only by design** — long-form radio content
> fights the game's own music on the shell menu and wrecks the tension mid-
> combat. If you want radio content on other states, that's what the per-state
> checkbox in step 2 is for.

### Stinger States

`STATE_VICTORY` and `STATE_DEFEAT` are **stingers** -- they play once and stop (no looping, no advancing to the next track). Use short celebratory or somber tracks here.

---

## Supported Audio Formats

- `.mp3` -- recommended for file size
- `.ogg` -- good quality/size ratio
- `.wav` -- uncompressed, larger files but zero quality loss
- `.flac` -- lossless, still compressed
- `.m4a` / `.opus` / `.wma` -- also supported

As of v2 the decoder (PyAV) ships inside the app, so **users no longer need
ffmpeg installed** — v1 only handled `.mp3`/`.ogg`/`.wav`, and only if the user
had put ffmpeg on their PATH. If you're distributing a pack that targets both
versions, `.mp3` remains the safest bet.

All tracks are normalized to 16-bit 44100Hz stereo at runtime. You can use any sample rate or bit depth, but 44100Hz 16-bit stereo is optimal.

---

## Creating a Workshop Music Pack

Workshop music packs let you distribute music via Steam Workshop. Each pack includes a `_xipod.json` descriptor that tells Anarchy Radio FM which audio files go into which state folders.

### 1. Create the Descriptor File

Create a file ending in `_xipod.json` (e.g., `my_pack_xipod.json`) in your mod's root folder:

```json
{
    "name": "My Awesome Music Pack",
    "author": "YourName",
    "folders": {
        "STATE_AVENGER": "music/avenger",
        "STATE_MISSION_EXPLORE": "music/explore",
        "STATE_MISSION_COMBAT": "music/combat",
        "STATE_VICTORY": "music/victory"
    }
}
```

### 2. Organize Your Audio Files

Place your audio files in subfolders relative to the mod root, matching the paths in `"folders"`:

```
YourMod/
  my_pack_xipod.json
  music/
    avenger/
      chill_base_01.mp3
      chill_base_02.mp3
    explore/
      stealth_ambient.ogg
    combat/
      intense_battle.mp3
    victory/
      fanfare.mp3
```

### 3. How Import Works

When the user sets their Workshop folder in Anarchy Radio FM setup, the app scans all workshop mod folders for `*_xipod.json` files. For each descriptor found:

1. Reads the `"folders"` mapping
2. Copies audio files from each source path into the corresponding `STATE_*` folder in the user's music library
3. Skips files that already exist (won't overwrite user's existing tracks)

Only recognised audio files are copied — `.mp3`, `.wav`, `.ogg`, `.flac`, `.m4a`, `.opus` and `.wma`. Anything else in the source folders is ignored.

### 4. Descriptor Reference

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Display name for your pack |
| `author` | No | Your name/handle |
| `folders` | Yes | Map of `STATE_*` folder names to relative source paths |

Valid folder keys are any of the state folders listed in the Folder Structure table above (e.g., `STATE_AVENGER`, `STATE_MISSION_COMBAT_LOOP`, `STATE_RESISTANCE_RADIO`, etc.).

---

## Manual Installation (No Workshop)

Users can also manually drop audio files into the state folders in their music library. No descriptor needed -- just put any supported audio file directly into the appropriate `STATE_*` folder. See [`music/music_readme.md`](music/music_readme.md) for the folder-by-folder rundown.

---

## Tips for Music Mod Creators

- **Match the mood**: Avenger music should feel like downtime/base management. Combat should be intense. Explore should be ambient/tense.
- **Loop-friendly tracks**: If providing `_LOOP` variants, use tracks that loop seamlessly. The base folder tracks will crossfade between each other instead.
- **Volume consistency**: Anarchy Radio FM applies per-state volume scaling, but try to keep your tracks at a consistent loudness level. Normalize to around -14 LUFS.
- **File naming**: Use descriptive names -- they show up in the Anarchy Radio FM desktop app's "Now Playing" and logs (e.g., `Avenger_Chill_Vibes.mp3` instead of `track_01.mp3`). File extensions are stripped for display.
- **Stinger length**: Victory/defeat stingers work best at 30-90 seconds. They play once and stop.
- **Radio tracks**: `STATE_RESISTANCE_RADIO/` is the station pool. When the user hits Radio Mode, the Avenger plays from here with random start points. This is where long-form content shines — hour-long DJ sets, mixtapes, fake ad breaks. Short single tracks work, but the "always live" effect needs room to roam, so favour long continuous audio here.
- **Don't put combat music in the radio folder**: Radio Mode only ever applies to the Avenger, so anything here is downtime music by definition.

---

## How Anarchy Radio FM Interacts with MMS

Anarchy Radio FM uses MMS (Music Modding System) as a dependency. Here's what happens under the hood:

1. Anarchy Radio FM registers silent SoundCue entries in MMS's config files (`XComStrategySound.ini`, `XComTacticalSound.ini`, `XComShellSound.ini`)
2. These silent entries take priority over MMS's own music, effectively muting the in-game music
3. Anarchy Radio FM then plays your audio files externally through the system audio
4. When the user disables Anarchy Radio FM for a specific state (via MCM toggle), the silent entry is removed and MMS's own music plays through for that state

**Important**: Config changes (toggling states on/off) take effect on the **next game launch**, not mid-game. The in-game MCM tooltips explain this.

---

## Troubleshooting

- **No music playing**: Check that both Anarchy Radio FM and MMS mods are enabled. Ensure audio files are in the correct `STATE_*` folder.
- **Wrong state playing**: Make sure folder names match exactly (case-insensitive, but the `STATE_` prefix is required).
- **Workshop pack not imported**: The `_xipod.json` file must end with exactly `_xipod.json`. Check that the `"folders"` paths are relative to the mod root.
- **Tracks sound distorted**: Anarchy Radio FM auto-normalizes to 16-bit 44100Hz stereo. If your source files are at extreme sample rates or bit depths, pre-convert them for best results.

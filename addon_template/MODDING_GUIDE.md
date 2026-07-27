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

Workshop music packs let you distribute music via Steam Workshop. Each pack includes a `_xipod.json` descriptor that tells Anarchy Radio FM which audio files belong to which game states.

### 1. Start from the template

**The easy way:** open Anarchy Radio FM and hit **Create Mod**. Give it a name
and pick a folder, and it stamps out a complete, ready-to-publish ModBuddy
project — solution file, project file, Config INIs, the DLC class, all fifteen
`music/STATE_*` folders and a filled-in descriptor. Nothing to wire up
yourself.

You get:

```
MyPack_xipod/
  MyPack_xipod.XCOM_sln
  MyPack_xipod/
    MyPack_xipod.json         <- the descriptor
    MyPack_xipod.x2proj
    ReadMe.txt
    Config/                   <- generated INIs
    Src/MyPack_xipod/Classes/ <- generated DLC class
    music/
      STATE_AVENGER/
      STATE_MISSION_COMBAT/
      ... (all fifteen)
```

The descriptor name matters: it must end in **`_xipod.json`** or the app won't
find it. Because the project is named `<YourName>_xipod`, that falls out
naturally.

### 2. Fill in the descriptor

```json
{
    "name": "My Awesome Music Pack",
    "author": "YourName",
    "description": "Orchestral covers of 80s rock. Heavy on the Avenger, tense in the field.",
    "genres": ["Orchestral", "Rock", "Covers"],
    "folders": {
        "STATE_AVENGER": "music/STATE_AVENGER",
        "STATE_MISSION_EXPLORE": "music/STATE_MISSION_EXPLORE",
        "STATE_MISSION_COMBAT": "music/STATE_MISSION_COMBAT",
        "STATE_VICTORY": "music/STATE_VICTORY"
    }
}
```

`description` and `genres` are optional — older descriptors without them still
load — but they're worth filling in. Both appear in the app's **Music Addons**
panel, where players sort and filter their installed packs by genre.
`genres` accepts a list or a comma-separated string.

Delete any `folders` entries you're not using; empty folders are simply
skipped.

### 3. Drop your audio in and publish

Put files in the `music/STATE_*` folders that match your `folders` map, then
publish from ModBuddy as normal.

### 4. How Loading Works

On startup the app scans every workshop mod folder (one level deep) for
`*_xipod.json` and merges those tracks into the player's library **alongside**
their own music.

**Nothing is copied.** Your pack's audio plays straight out of the workshop
folder where Steam put it. That matters for two reasons:

- A station-rip pack can run to gigabytes. Copying would duplicate all of it
  onto the player's drive.
- Once copied, files are indistinguishable from the player's own, so there'd be
  no way to turn a pack back off. Because tracks are referenced, the app's
  **Music Addons** panel can enable and disable packs freely.

Only recognised audio files are picked up — `.mp3`, `.wav`, `.ogg`, `.flac`,
`.m4a`, `.opus` and `.wma`. Anything else in the source folders is ignored, so
cover art and readme files sitting alongside your tracks are harmless.

**Filename collisions:** if two sources offer the same filename for the same
state, only one survives. The player's own music folder always wins; between
two packs it resolves alphabetically by pack name. Give your files distinctive
names (`MyPack_Avenger_01.mp3`, not `track01.mp3`) so yours aren't swallowed by
someone else's pack.

### 5. Descriptor Reference

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Display name for your pack — shown in the Music Addons panel |
| `author` | No | Your name/handle |
| `description` | No | A sentence or two, shown under the name in the panel |
| `genres` | No | Tags players can sort and filter by, e.g. `["Rock", "Orchestral"]`. A comma-separated string also works |
| `folders` | Yes | Map of `STATE_*` folder names to relative source paths |

Valid folder keys are any of the state folders listed in the Folder Structure table above (e.g., `STATE_AVENGER`, `STATE_MISSION_COMBAT_LOOP`, `STATE_RESISTANCE_RADIO`, etc.). Keys are case-insensitive; unknown keys and paths pointing outside your mod folder are ignored.

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

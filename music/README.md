# Anarchy Radio FM Music Library

Drop your audio files (`.mp3`, `.ogg`, `.wav`) into the folder that matches
the game state you want to score. Anarchy Radio FM plays a shuffled selection from the
active state's folder while you're in that part of the game.

| Folder | Plays during |
|--------|--------------|
| `STATE_SHELL_MENU/` | Main menu / title screen |
| `STATE_AVENGER/` | Avenger base interior |
| `STATE_GEOSCAPE/` | Geoscape / hologlobe |
| `STATE_SQUADSELECT/` | Squad select (pre-mission) |
| `STATE_MISSION_EXPLORE/` | Tactical: exploring (no combat) |
| `STATE_MISSION_COMBAT/` | Tactical: combat |
| `STATE_VICTORY/` | Post-mission victory stinger |
| `STATE_DEFEAT/` | Post-mission defeat stinger |
| `STATE_RESISTANCE_RADIO/` | Shared "radio" pool (see below) |

Each state also has a `_LOOP` sibling folder. If "Loop" is enabled for a state
and its `_LOOP` folder has tracks, those are used and looped; otherwise Anarchy Radio FM
falls back to the base folder.

`STATE_RESISTANCE_RADIO/` is a shared pool. When you enable **Radio Mode** for a
state, its tracks come from here instead, each starting at a random position
(like tuning into a live station).

Empty folders are simply skipped — the game's own music (via MMS) plays through.

See [`../MODDING_GUIDE.md`](../MODDING_GUIDE.md) for building shareable music packs.

# Anarchy Radio FM Music Library

Drop your audio files into the folder that matches the game state you want to
score. Anarchy Radio FM plays a shuffled selection from the active state's
folder while you're in that part of the game.

**Supported formats:** `.mp3`, `.ogg`, `.wav`, `.flac`, `.m4a`, `.opus`, `.wma`

> As of v2 the decoder ships inside the app — there's **no ffmpeg to install**
> any more. v1 only handled `.mp3`, `.ogg` and `.wav`, and only if you'd put
> ffmpeg on your PATH yourself.

Anything that isn't one of those extensions is ignored, so it's safe to leave
cover art, `.txt` notes or stray files sitting in these folders.

## The folders

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
| `STATE_RESISTANCE_RADIO/` | The radio station pool (see below) |

**Empty folders are simply skipped** — the game's own music (via MMS) plays
through instead. You don't have to fill them all; start with `STATE_AVENGER/`
and go from there.

## `_LOOP` folders

Each state also has a `_LOOP` sibling. If **Loop Track** is enabled for that
state in Effects and its `_LOOP` folder has tracks, those are used and repeated;
otherwise Anarchy Radio FM falls back to the base folder.

Good for a single ambient bed you want running continuously, rather than a
playlist that moves on.

## `STATE_RESISTANCE_RADIO/` and Radio Mode

This folder is the station. Hit the **Radio Mode** button in the app and the
Avenger tunes into it, with **every track starting at a random point** — like
catching a broadcast that was already running.

Radio Mode is **Avenger-only**, on purpose. Long radio content is downtime
atmosphere: it's great while you potter around the ship, and actively bad
elsewhere. On the main menu it fights the game's own music, and a DJ cracking
a joke mid-firefight kills the tension.

Three **Radio Source** buttons decide where the Avenger pulls from:

| Button | What plays |
|---|---|
| **Radio Only** | `STATE_RESISTANCE_RADIO/` only *(falls back to `STATE_AVENGER/` if empty)* |
| **Avenger Only** | `STATE_AVENGER/` only — your normal Avenger music, with the random start points |
| **Mix Both** | Both folders pooled; when a track ends the next can come from either |

While Radio Mode is on it **overrides `STATE_AVENGER_LOOP/`** and the Loop
Track setting — a station that repeats one track forever isn't a station.
Switch it off and your loop track comes straight back.

> **Best thing to try:** grab a long GTA radio station rip — DJ banter, fake
> adverts, the lot — and drop it in here. An hour-long unbroken mix gives that
> random start plenty of room to roam, so every trip back to the Avenger lands
> you somewhere new.

There's also a per-state **Radio Source** checkbox in Effects, which works
independently of the Radio Mode button if you want radio content on other
screens.

## Per-state settings

Everything else — volume, effects presets, reverb, random start, looping — is
per-state and lives in the **Effects** panel in the app. Nothing in this folder
needs configuring beyond dropping files in.

---

See [`../MODDING_GUIDE.md`](../MODDING_GUIDE.md) for building shareable music
packs you can put on the Steam Workshop.

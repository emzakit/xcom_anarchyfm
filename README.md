<p align="center">
  <img src="AnarchyFM.png" alt="Anarchy Radio FM" width="520">
</p>

# Anarchy Radio FM

**Replace the soundtrack of XCOM 2 with your own music.**

https://steamcommunity.com/sharedfiles/filedetails/?id=3772839338

Anarchy Radio FM is a little desktop app that plays your own `.mp3` / `.ogg` / `.wav` files
in sync with the game — title music on the menu, chill tunes on the Avenger,
something loud when the shooting starts. It quietly watches XCOM 2's log, notices
when the game changes screens, and plays the right tracks from folders on your
PC while the game's own music gets muted (through MMS). That's the whole trick.

---

## A bit of backstory

Anarchy Radio FM is the follow-up to my
**[Resistance Radio](https://steamcommunity.com/sharedfiles/filedetails/?id=2863096697)**
mod, and honestly it's been a bit of a saga. I've been poking at this idea for
**about three years** — basically ever since Resistance Radio came out. The
dream was always simple: *let people drop in any music they like and have it play
in the right place.* The problem was XCOM's audio system, which is… let's say
**deeply reluctant** to cooperate. Every route ran into 60GB SDKs, Wwise
soundbanks, and giant `.upk` files (15gb was the size of the original mod, not ideal!).

So, I spent time putting my lockdown Python skills to use and eventually got to coding, but I kept hitting a brick wall trying to figure out exactly how to link the two together. 

Then Google Gemini and Claude came along, which suggested a completely different approach: have the game
just *announce* what it's doing to a log, and let a small external app do the
actual playing. Suddenly the thing that had been stuck for years was **doable**! It's not perfect, but it works. That's good enough.

I'm making this open source because everything should be (especially if AI helped out) and also in case one of you XCOM gurus figures out a way to make it work within the Unreal Engine itself and doesn't require an external Python audio player. That's the real dream, but I couldn't quite pull it off. Maybe one of you will.

The heart of it is having **your own music on the Avenger and Squad Select**. This is the part that works properly, and it's where the vast majority of the effort went.
Everything else is a fun bonus that's still finding its feet (more on that
below).

> **Just want a no-fuss radio?** The original
> **[Resistance Radio](https://steamcommunity.com/sharedfiles/filedetails/?id=2863096697)**
> mod is still on the Workshop and still great — no Python, no setup, just
> subscribe and go. If Anarchy Radio FM's tinkering isn't your thing, start there.

### The honest heads-up

The tactical side (combat, explore, geoscape, the victory/defeat stingers,
cinematic handling) is **beta**. It works most of the time, but it *will* trip
occasionally — a track overlapping, the wrong mood playing, a beat of awkward
timing. If what you really want is a bulletproof full-game soundtrack, you'll be
happier grabbing a music pack and running it straight through MMS. Think of
Anarchy Radio FM's combat stuff as "ooh neat" rather than "rock solid."

I made this as a companion to MMS specifically so that you can have the two running at the same time and cover the gaps that this system fails at, it is not a **replacement.**

> **One thing that's not optional:** Anarchy Radio FM is an **add-on to MMS, not a
> replacement.** The
> [Music Modding System (MMS)](https://steamcommunity.com/workshop/filedetails/?id=757398474) does the
> heavy lifting of silencing the game's built-in music, and Anarchy Radio FM leans on it to
> work at all. **Install and enable MMS first** — nothing here works without it.

---

## How it actually works

There are two halves, and they gossip through a log file:

1. **The in-game mod** (a tiny companion Workshop item) watches XCOM's screens
   and scribbles the current state (`XIPOD: STATE_AVENGER`, and friends) into the
   game's `Launch.log`. It also slots *silent* cues into MMS so the game hushes
   its own music for that state.
2. **This app** keeps an eye on that log, and the moment the state changes it
   fades into a shuffled pick of your local tracks for that screen — crossfades,
   optional effects, the works.

Nice side effect of doing the audio in a separate process: a dodgy file can't
take the game down with it. Worst case, Anarchy Radio FM shrugs and skips that one track.

---

## What you'll need

- **XCOM 2: War of the Chosen** (Windows).
- **[Music Modding System (MMS)](https://steamcommunity.com/workshop/filedetails/?id=757398474)** — the
  in-game music framework. Required, and enabled in your mod list.
- **The Anarchy Radio FM in-game mod** — the companion Workshop item that tells the app what
  the game's up to. *(Add your Workshop link here.)*
- **Python 3.10+** (built on 3.13), on Windows.
- **[ffmpeg](https://ffmpeg.org/)** on your PATH — only needed for `.mp3` and
  `.ogg`. Plain `.wav` plays without it, so if you're a WAV purist you can skip
  this entirely.

---

## Getting it running

The lazy (recommended) way is **`launch.bat`**:

1. Install [Python](https://www.python.org/downloads/) — and *do* tick **"Add
   Python to PATH"** on the first screen, it saves a headache.
2. Grab this repo (download the ZIP or clone it).
3. Double-click **`launch.bat`**.

First time through, `launch.bat` quietly sets up a virtual environment, installs
what it needs, and opens Anarchy Radio FM. After that it just launches straight away.

If you'd rather drive stick:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python src/main.py
```

Want it windowless, console only? Add `--cli`:

```bash
python src/main.py --cli
```

### The first-run wizard

On the very first launch a little setup wizard pops up. Just point it at:

- **Game launcher / .exe** — either `XCom2.exe` or a mod launcher like the
  Alternative Mod Launcher (AML). Anarchy Radio FM launches it for you and bows out when the
  game closes.
- **Music library folder** — wherever you want your tunes to live. Anarchy Radio FM builds
  all the `STATE_*` folders inside it for you.
- **Workshop folder** *(optional)* — lets Anarchy Radio FM auto-import community music packs.
- **Game config folder** — usually auto-detected; it's where Anarchy Radio FM writes the MMS
  "shush" overrides.

Everything gets saved to `xipod_config.json` (stays on your machine, never
committed — peek at `xipod_config.example.json` if you're curious about the
shape). Changed your mind later? Re-run the wizard any time with
`python src/main.py --setup`.

---

## Adding your music

Drop audio files into whichever state folder you want to score:

| Folder | Plays during |
|--------|--------------|
| `STATE_SHELL_MENU/` | Main menu / title screen |
| `STATE_AVENGER/` | Avenger base interior |
| `STATE_GEOSCAPE/` | Geoscape / hologlobe |
| `STATE_SQUADSELECT/` | Squad select (pre-mission) |
| `STATE_MISSION_EXPLORE/` | Tactical: creeping around, nobody shooting yet |
| `STATE_MISSION_COMBAT/` | Tactical: it's kicking off |
| `STATE_VICTORY/` | Post-mission victory sting |
| `STATE_DEFEAT/` | Post-mission "well, that went badly" sting |
| `STATE_RESISTANCE_RADIO/` | Shared "radio" pool (random-start — the fun one) |

Every state also has a `_LOOP` twin (`STATE_AVENGER_LOOP/`, etc.) for tracks you
want to loop rather than shuffle through. Leave a folder empty and Anarchy Radio FM just
steps aside, letting the game's own music play for that screen. The full
rundown — plus how to package up shareable Workshop music packs — lives in
**[`MODDING_GUIDE.md`](MODDING_GUIDE.md)** and **[`music/README.md`](music/README.md)**.

---

## Resistance Radio mode (the good stuff)

If you try one thing, try this. The `STATE_RESISTANCE_RADIO/` folder is a shared
pool, and flipping **Radio Mode** on for a state pulls its music from here — with
a lovely little twist: **every track starts from a random spot.** Like the
station was already playing and you just tuned in mid-song. Nothing ever kicks
off from the top, so it never feels like a playlist looping round the block — it
feels like an actual *broadcast* you're ducking in and out of between the
Avenger, the Geoscape, and wherever else the war takes you. This is the soul of
the original Resistance Radio, and it's the first thing I'd send anyone to.

**Want to *get it* in about thirty seconds?** Go download one of the **GTA radio
stations** — they're long, unbroken mixes with DJ banter, fake adverts, the whole
vibe. Drop one into `STATE_RESISTANCE_RADIO/`, switch Radio Mode on, and every
time you change screens you'll land somewhere new in the broadcast: mid-track,
mid-advert, mid-DJ-ramble. It just *clicks*. Toss in a few stations and you've
got your own pirate radio humming away under the resistance.

> Pro tip: long files really shine here. A 30–60 minute station mix gives that
> random start loads of room to roam. Short single tracks work fine too, but the
> "always live" magic is strongest with big, continuous audio.

**Changing stations, the lazy way:** there's no in-game menu to fiddle with — to
skip to something new, just **dip in and out of the Geoscape** and back, exactly
like the original Resistance Radio. Each round-trip reshuffles, and with Radio
Mode on it drops you at a fresh random spot — basically retuning the dial. (If
you'd rather have buttons, the in-game mod also ships `XiPodPlay` / `XiPodPause`
/ `XiPodNext` / `XiPodPrev` console commands you can bind to keys.)

---

## The buttons

- **Transport** — play/pause, next/previous, and a master volume slider.
- **State toggles** — flip Anarchy Radio FM on or off per state. Switch one off and MMS
  hands the game's own music back for that screen. *(Heads-up: toggle changes
  land on the **next** game launch, since XCOM only reads its config at startup.)*
- **Options** — tweak your configured paths.
- **Effects** — per-state presets and FX (radio filter, reverb, bass, chorus,
  bitcrush, echo), plus loop / random-start switches.
- **Create Music Mod…** — spins up a ready-to-fill Workshop music-pack project.
- **Web Player** *(experimental, Avenger only)* — more below.
- **Spotify** *(experimental)* — also below.
- It tucks into the system tray while you play and quietly shuts itself down when
  the game (and your launcher) close.

---

## Web Player (experimental — Avenger only)

A fun little extra: a **browser baked right into Anarchy Radio FM** so you can stream music
without alt-tabbing while you mooch around the base. The **Web Player** button
only lights up **on the Avenger** — it's a downtime toy, and it's **experimental**,
so enjoy it as a bonus rather than leaning on it.

- **YouTube / YouTube Music work great** — log in and it remembers you next time.
- Type a web address, or just bash in a band name and it'll search YouTube for
  you.
- Want Spotify per state instead? That's its own feature — see the next section.
- It's deliberately *not* tied into the state engine — it plays whatever you tell
  it and mixes over the game like any other app. If you only want to DJ from
  here, just leave the `STATE_*` folders empty.

Runs on QtWebEngine, which rides along with `PySide6-Addons` (already in
`requirements.txt`). If it's somehow missing, the button will tell you how to
grab it.

---

## Spotify per state (experimental — your keys, your risk)

Here's a spicy one: pin a **Spotify playlist to each game state** — a combat
playlist for combat, something mellow for the Avenger, and so on. It's
**experimental** and very much **at your own risk**, because it runs on *your*
Spotify account through *your own* API app.

**Read this bit before you get excited:** Spotify's API can't actually stream
audio — it can only **remote-control a Spotify app that's already open**. So what
Anarchy Radio FM really does is nudge your **Spotify desktop app** onto the right playlist
when the game changes state. Which means:

- **You need Spotify Premium** (controlling playback is a Premium-only thing).
- **The Spotify desktop app has to be open and running.**
- It does **not** pipe through the in-app Web Player (that's YouTube's turf).
- You bring your **own** Client ID / Secret from the Spotify Developer Dashboard.
  They live **only on your machine** (git-ignored) — guard the secret like a
  password.

Leave any state blank and it happily falls back to your local files, so you can
mix and match — Spotify for the base, local tracks for combat, whatever you fancy.
The full walkthrough (making the app, grabbing the keys, linking your account) is
in **[`SPOTIFY_SETUP.md`](SPOTIFY_SETUP.md)**, and there's a **Spotify** button
in Anarchy Radio FM that opens it all up.

---

## What's in the box

| Path | What it is |
|------|-----------|
| `src/` | The app itself (audio engine, log watcher, GUI, web player, Spotify control, setup, MMS config writer) |
| `tests/` | Unit + integration tests (`python -m unittest discover -s tests`) |
| `SPOTIFY_SETUP.md` | Step-by-step for the experimental Spotify hook-up |
| `music/` | Your music library — ships as empty `STATE_*` folders ready to fill |
| `launch.bat` | The one-click launcher (sets the venv up on first run) |
| `requirements.txt` | Python dependencies |
| `xipod_defaults.json` | Built-in presets, INI defaults, and cinematic timing data |
| `xipod_config.example.json` | A template for the per-user config |
| `MODDING_GUIDE.md` | How to build and share music packs |

---

## Status & credits

Beta, and proudly so — provided as-is. **Avenger and Squad Select are the
polished bits I actually stand behind; everything else is experimental, so for a
watertight full soundtrack, reach for an MMS music pack.**

Built on the shoulders of the **[Music Modding System (MMS)](https://steamcommunity.com/workshop/filedetails/?id=757398474)** — none of this
happens without it. Anarchy Radio FM and the original
**[Resistance Radio](https://steamcommunity.com/sharedfiles/filedetails/?id=2863096697)**
are both mine, **emzakit (Moondear)**. 

Released under the MIT License —
see [`LICENSE`](LICENSE). Now go make the Avenger sound like *yours*.

<p align="center">
  <img src="assets/git_banner.png" alt="Anarchy Radio FM" width="640">
</p>

<h1 align="center">Anarchy Radio FM</h1>

<p align="center">
  <strong>Your music. Your XCOM. Finally.</strong>
</p>

<p align="center">
  <a href="https://github.com/emzakit/xcom_anarchyfm/releases/latest">
    <img alt="Latest release" src="https://img.shields.io/github/v/release/emzakit/xcom_anarchyfm?style=for-the-badge&labelColor=08141a&color=5fd3e3">
  </a>
  <a href="https://steamcommunity.com/sharedfiles/filedetails/?id=3772839338">
    <img alt="Steam Workshop" src="https://img.shields.io/badge/Steam-Workshop-d9a441?style=for-the-badge&labelColor=08141a&logo=steam">
  </a>
  <a href="LICENSE">
    <img alt="MIT licence" src="https://img.shields.io/badge/licence-MIT-5fd3e3?style=for-the-badge&labelColor=08141a">
  </a>
</p>

<p align="center">
  <a href="https://youtu.be/y4coRhi1n3w">
    <img src="assets/youtube_video.png" alt="Watch Anarchy Radio FM in action" width="640">
  </a>
</p>

<p align="center">
  <a href="https://youtu.be/y4coRhi1n3w"><strong>Watch me in action</strong></a>
</p>

---

Hans Zimmer scoring your Geoscape while the world quietly falls apart? Go on
then. Slipknot the second the shooting starts? Absolutely. The Spice Girls over
an ADVENT ambush because you thought it'd be funny and now it's canon? Nobody
here is going to stop you.

**Anarchy Radio FM replaces XCOM 2's soundtrack with whatever you want.** Drop
your files into folders, and each screen gets its own music. That's the whole
idea.

No conversions. No renaming. No ffmpeg. Just files in folders and an exe.

---

## Get it running

**1.** Subscribe to **[the mod](https://steamcommunity.com/sharedfiles/filedetails/?id=3772839338)**
and **[Music Modding System](https://steamcommunity.com/workshop/filedetails/?id=757398474)**.
You need both — MMS does the silencing, this does the music.

**2.** **[Download the app](https://github.com/emzakit/xcom_anarchyfm/releases/latest)**,
unzip it anywhere, and **run the exe.** A wizard walks you through the rest.

**3.** Drop your music into the folders it makes for you. Done.

<p align="center">
  <img src="assets/img_main_menu.png" alt="The Anarchy Radio FM control panel" width="420">
</p>

> **One setting worth changing:** turn XCOM's own Music volume to **0**
> (*Options → Audio*). MMS silences most of the game's soundtrack but not all
> of it, and the gaps are where you'd hear two at once.

---

## 📻 The good bit: Radio Mode

One button. The Avenger tunes into a station, and **every track starts at a
random point** — like the broadcast was already running and you just walked in.

Grab an hour-long **GTA radio station rip**, DJ banter and fake adverts and all,
drop it in, and every trip back to the ship lands you mid-song, mid-advert or
mid-ramble. It's ridiculous and it's the best thing here.

[**→ Radio Mode in full**](https://github.com/emzakit/xcom_anarchyfm/wiki/Features#radio-mode)

---

## What else it does

|   |   |
|---|---|
| 🎚️ | **Effects** — radio filter, reverb, bitcrush, echo and more, per state. Make the Avenger sound like a beaten-up field radio in two clicks. |
| 📦 | **Music Addons** — subscribe to Workshop music packs and flick them on and off. |
| 🎧 | **Spotify** *(experimental)* — pin a playlist to each screen. Needs Premium and your own API keys. |
| 🔄 | **Self-updating** — checks GitHub on startup, installs it for you, never touches your settings or music. |
| 🎛️ | **Per-state everything** — volume, looping, random start, all remembered. |

[**→ Full feature tour**](https://github.com/emzakit/xcom_anarchyfm/wiki/Features)

---

## Docs

Everything past "run the exe" lives in the
**[wiki](https://github.com/emzakit/xcom_anarchyfm/wiki)**.

|   |   |
|---|---|
| ✨ | [Every feature, in detail](https://github.com/emzakit/xcom_anarchyfm/wiki/Features) |
| 🔧 | [Something's wrong](https://github.com/emzakit/xcom_anarchyfm/wiki/Troubleshooting) |
| 🎧 | [Setting up Spotify](https://github.com/emzakit/xcom_anarchyfm/wiki/Spotify-setup) |
| ⚙️ | [How it works / running from source](https://github.com/emzakit/xcom_anarchyfm/wiki/How-it-works) |
| 🔨 | [Building the exe yourself](https://github.com/emzakit/xcom_anarchyfm/wiki/Building-the-exe) |
| 📝 | [Changelog](https://github.com/emzakit/xcom_anarchyfm/wiki/Changelog) |
| 📂 | [Using the music folders](music/music_readme.md) |
| 🛠️ | [Making your own music pack](addon_template/MODDING_GUIDE.md) |

---

## Fair warning

The **Avenger and Squad Select** are the polished bits I actually stand behind —
that's where the effort went. The **tactical side is beta** and trips
occasionally: an overlap, the wrong mood, awkward timing. If you want a
watertight full-game soundtrack, run an MMS music pack; this is happy to sit
alongside one and cover the gaps.

There's a **[known bug](https://github.com/emzakit/xcom_anarchyfm/wiki/Troubleshooting#known-issues)** where music can
keep playing when you back out to the main menu. I'm on it.

**[Scanner flagged the exe?](https://github.com/emzakit/xcom_anarchyfm/wiki/Troubleshooting#flagged-as-a-virus)** It's
a false positive — it's a Python packaging thing. Build it yourself if you'd
rather not trust the binary.

---

## Credits

Three years in the making, and a follow-up to my
**[Resistance Radio](https://steamcommunity.com/sharedfiles/filedetails/?id=2863096697)**
mod. Built on the shoulders of
**[Music Modding System](https://steamcommunity.com/workshop/filedetails/?id=757398474)** —
none of this happens without it.

Open source because everything should be, and partly in the hope that one of you
XCOM gurus figures out how to do this inside Unreal itself instead of leaning on
an external audio player. That's the real dream. I couldn't quite pull it off.

Both mods are mine — **emzakit (Moondear)**. MIT licensed, see [`LICENSE`](LICENSE).

Now go make the Avenger sound like *yours*, Commander.

<p align="center">
  <a href="https://youtu.be/y4coRhi1n3w">Watch it</a>
  &nbsp;·&nbsp;
  <a href="https://github.com/emzakit/xcom_anarchyfm/releases/latest">Download</a>
  &nbsp;·&nbsp;
  <a href="https://steamcommunity.com/sharedfiles/filedetails/?id=3772839338">Steam Workshop</a>
  &nbsp;·&nbsp;
  <a href="https://github.com/emzakit/xcom_anarchyfm/issues">Report a bug</a>
</p>

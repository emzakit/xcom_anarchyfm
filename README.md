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

**2.** Add **`-forcelogflush`** to XCOM 2's launch options. Without it, music
plays over cinematics.

<details>
<summary><strong>Show me exactly where →</strong>&nbsp; (Steam, and the Alternative Mod Launcher)</summary>

<br>

**Steam** — right-click **XCOM 2 → Properties → General → Launch Options**, and
type it into the box at the bottom.

<table>
<tr>
<td width="50%"><img src="assets/img_inst_forceflush_xcom_launcher_01.png" alt="Right-click XCOM 2 in your Steam library and choose Properties"></td>
<td width="50%"><img src="assets/img_inst_forceflush_xcom_launcher_02.png" alt="Type -forcelogflush into the Launch Options box"></td>
</tr>
</table>

**Alternative Mod Launcher** — **Options → Settings → Active arguments**. Add it
to the **end** of the arguments already there; don't replace the line.

<table>
<tr>
<td width="50%"><img src="assets/img_inst_forceflush_aml_launcher_01.png" alt="AML Options menu, Settings"></td>
<td width="50%"><img src="assets/img_inst_forceflush_aml_launcher_02.png" alt="-forcelogflush added to the end of Active arguments"></td>
</tr>
</table>

</details>

**3.** **[Download the app](https://github.com/emzakit/xcom_anarchyfm/releases/latest)**,
unzip it anywhere, and **run the exe.** A wizard walks you through the rest.

**4.** Drop your music into the folders it makes for you. Done.

<p align="center">
  <img src="assets/img_main_menu.png" alt="The Anarchy Radio FM control panel" width="420">
</p>

> **Upgrading from v2.2 or earlier?** You can turn XCOM's Music volume back up
> (*Options → Audio*). Setting it to 0 used to be the workaround for the game's
> soundtrack playing underneath everything — that's fixed, and muting it also
> silences MMS and any music packs you're running.

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

<table>
<tr>
<td width="42%"><img src="assets/img_effects.png" alt="Effects panel"></td>
<td>

### 🎚️ Effects

Radio filter, reverb, bass, chorus, bitcrush, echo — set per state, with
presets. Want the Avenger sounding like a beaten-up field radio? Two clicks.

**[Effects and per-state settings →](https://github.com/emzakit/xcom_anarchyfm/wiki/Features#the-buttons)**

</td>
</tr>
<tr>
<td width="42%"><img src="assets/img_spotify.png" alt="Spotify panel"></td>
<td>

### 🎧 Spotify *(experimental)*

Pin a Spotify playlist to each screen. Needs Premium, the desktop app running,
and your own API keys — it drives *your* account through *your* registration.

**[Set up Spotify →](https://github.com/emzakit/xcom_anarchyfm/wiki/Spotify-setup)**

</td>
</tr>
<tr>
<td width="42%"><img src="assets/img_addons.png" alt="Music Addons panel"></td>
<td>

### 📦 Music Addons

Subscribe to a Workshop music pack and it just turns up in your library. Flick
packs on and off, sort by genre. Nothing gets copied to your drive. You don't need to enable them in any mod launcher, the app will automatically detect them and allow you to toggle on/off.

**[Music Addons →](https://github.com/emzakit/xcom_anarchyfm/wiki/Features#music-addons)**
· **[Make your own →](https://github.com/emzakit/xcom_anarchyfm/wiki/Making-a-music-pack)**

</td>
</tr>
</table>

Plus **self-updating** (checks GitHub on startup, never touches your settings or
music) and **per-state everything** — volume, looping, random start, all
remembered between sessions.

---

## Docs

Everything past "run the exe" lives in the
**[wiki](https://github.com/emzakit/xcom_anarchyfm/wiki)**.

|   |   |   |
|---|---|---|
| 📂 | [Using the music folders](music/music_readme.md) | Which folder scores which screen |
| ✨ | [Every feature, in detail](https://github.com/emzakit/xcom_anarchyfm/wiki/Features) | The full tour |
| 🔧 | [Something's wrong](https://github.com/emzakit/xcom_anarchyfm/wiki/Troubleshooting) | Two soundtracks, no music, known bugs |
| 🛠️ | [Making your own music pack](https://github.com/emzakit/xcom_anarchyfm/wiki/Making-a-music-pack) | Publish one to the Workshop |
| ⚙️ | [How it works](https://github.com/emzakit/xcom_anarchyfm/wiki/How-it-works) | And running it from source |
| 🔨 | [Building the exe](https://github.com/emzakit/xcom_anarchyfm/wiki/Building-the-exe) | If you'd rather compile it yourself |
| 📝 | [Changelog](https://github.com/emzakit/xcom_anarchyfm/wiki/Changelog) | What changed, and when |

---

## Fair warning

The **Avenger and Squad Select** are the polished bits I actually stand behind —
that's where the effort went. The **tactical side is beta** and trips
occasionally: an overlap, the wrong mood, awkward timing.

Running an **MMS music pack alongside this** works properly as of v2.3 — fill
the folders you care about and the pack covers everything else. Rarely, one
place will play your music one session and the pack's the next; turn off that
toggle in the app and the pack has it every time.

**[Known issues →](https://github.com/emzakit/xcom_anarchyfm/wiki/Troubleshooting#known-issues)**

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

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

## 📡 Incoming transmission

Somewhere out in the Wilderness there's a van. Inside it, two idiots called
**JAX** and **SILO** are running a pirate radio station on stolen broadcast gear
and no discernible survival instinct.

They have no idea XCOM is listening. They'd be alarmed to find out. They have
never once stopped talking.

Firaxis gave you a soundtrack. Very nice. Very orchestral. Very **the same, 40
hours later.** This is the other option — and it takes requests.

- 🎻 **Hans Zimmer** scoring the Geoscape while the world quietly ends? Go on then.
- 🤘 **Slipknot** the instant a Sectoid pops out? Absolutely.
- 💃 **The Spice Girls** over an ADVENT ambush because you thought it'd be funny and now it's canon? Nobody here is stopping you.

We've got eyes on your troops, Commander, and we give them the soundtrack their efforts deserve.

**Anarchy Radio FM replaces XCOM 2's soundtrack with whatever you want.** Drop
files into folders. Each screen gets its own music. That's the entire idea.

> No conversions. No renaming. No ffmpeg. No `.upk` files the size of a small
> moon. **Just files in folders and an exe.**

---

## 🚀 Get it running (four steps, Commander)

**1.** Subscribe to **[the mod](https://steamcommunity.com/sharedfiles/filedetails/?id=3772839338)**
and **[Music Modding System](https://steamcommunity.com/workshop/filedetails/?id=757398474)**.

> You need **both**. MMS shuts the game's own music up; we play yours. Think
> Bradford clearing the channel so you can actually hear the radio.

**2.** Add **`-forcelogflush`** to XCOM 2's launch options.

> Skip this and your music plays straight over the cinematics like a lad with
> Bluetooth speakers on a train. **Do the step.**

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
to the **end** of what's already there. Don't nuke the line — you'll regret it.

<table>
<tr>
<td width="50%"><img src="assets/img_inst_forceflush_aml_launcher_01.png" alt="AML Options menu, Settings"></td>
<td width="50%"><img src="assets/img_inst_forceflush_aml_launcher_02.png" alt="-forcelogflush added to the end of Active arguments"></td>
</tr>
</table>

</details>

**3.** **[Download the app](https://github.com/emzakit/xcom_anarchyfm/releases/latest)**,
unzip it anywhere, **run the exe.** A wizard does the boring bits.

**4.** Drop your music into the folders it makes for you. **Done.** Go be a menace.

<p align="center">
  <img src="assets/img_main_menu.png" alt="The Anarchy Radio FM control panel" width="420">
</p>

> **☝️ Coming from v2.2 or earlier?** Turn XCOM's Music volume **back up**
> (*Options → Audio*). Cranking it to 0 was the old workaround for the game's
> soundtrack bleeding through — that's fixed, and muting it now also gags MMS
> and any music packs you're running. Free your sliders.

---

## 📻 The good bit: Radio Mode

One button. The Avenger tunes into a station and **every track starts at a
random point** — as if the broadcast was already running and you just walked in
mid-sentence.

**Tip:** grab an hour-long **GTA radio station
rip** — DJ banter, fake adverts, the lot — and drop it in. Every trip back to
the ship lands you mid-song, mid-advert, or mid-ramble about legally distinct
energy drinks.

Alternatively, subscribe to this silly XCOM podcast and enable it under music addons:

https://steamcommunity.com/sharedfiles/filedetails/?id=3775888357

It's fun! *Vigilo Confido.*

[**→ Radio Mode in full**](https://github.com/emzakit/xcom_anarchyfm/wiki/Features#radio-mode)

---

## 🎁 What else is in the crate

<table>
<tr>
<td width="42%"><img src="assets/img_effects.png" alt="Effects panel"></td>
<td>

### 🎚️ Effects

Radio filter, reverb, bass, chorus, bitcrush, echo — per screen, with presets.

Want the Avenger sounding like a beaten-up field radio held together with tape
and hope? **Two clicks.**

**[Effects and per-state settings →](https://github.com/emzakit/xcom_anarchyfm/wiki/Features#the-buttons)**

</td>
</tr>
<tr>
<td width="42%"><img src="assets/img_spotify.png" alt="Spotify panel"></td>
<td>

### 🎧 Spotify *(experimental, and it's your call)*

Pin a Spotify playlist to each screen. Works genuinely well — including
different playlists for sneaking around versus everything going sideways.

Needs Premium, the desktop app running, and **your own API keys**. It drives
*your* account under *your* registration, which is deliberate.

**[Set up Spotify →](https://github.com/emzakit/xcom_anarchyfm/wiki/Spotify-setup)**

</td>
</tr>
<tr>
<td width="42%"><img src="assets/img_addons.png" alt="Music Addons panel"></td>
<td>

### 📦 Music Addons

Subscribe to a Workshop music pack and it **just turns up** in your library.
Flick packs on and off, sort by genre, nothing copied to your drive.

No mod launcher wrangling. The app finds them itself, like a Skyranger that
actually shows up on time.

**[Music Addons →](https://github.com/emzakit/xcom_anarchyfm/wiki/Features#music-addons)**
· **[Make your own →](https://github.com/emzakit/xcom_anarchyfm/wiki/Making-a-music-pack)**

</td>
</tr>
</table>

Plus **self-updating** — it keeps your old version in a folder next to the new
one, so rolling back is drag-and-drop, not a rescue mission — and **per-screen
everything**: volume, looping, random start, all remembered between sessions.

---

## 🎙️ The comms log isn't a status readout

It's the station.

```
SILO: No carrier yet. We're just talking to ourselves out here.
JAX : WE ARE LIVE. Anarchy FM, broadcasting from a van that is definitely on fire.
JAX : SILO, cut state_mission_explore. We're going to state_mission_combat. 3 ready.
SILO: Carrier's gone. Killing the transmitter before ADVENT triangulates us. Again.
```

**SHEN** handles setup and tells you when something's genuinely on fire — she
knows you're listening. **JAX** (on the decks) and **SILO** (on the wire) do
not, and never will.

Every line they say lives in **one editable file** inside the app folder.
Don't like them? Rewrite the entire crew. No code involved.

---

## 📚 The Codex

Everything past "run the exe" lives in the
**[wiki](https://github.com/emzakit/xcom_anarchyfm/wiki)**.

|   |   |   |
|---|---|---|
| 📂 | [Using the music folders](music/music_readme.md) | Which folder scores which screen |
| ✨ | [Every feature, in detail](https://github.com/emzakit/xcom_anarchyfm/wiki/Features) | The full tour |
| 🔧 | [Something's wrong](https://github.com/emzakit/xcom_anarchyfm/wiki/Troubleshooting) | Two soundtracks, no music, known gremlins |
| 🛠️ | [Making your own music pack](https://github.com/emzakit/xcom_anarchyfm/wiki/Making-a-music-pack) | Publish one to the Workshop |
| ⚙️ | [How it works](https://github.com/emzakit/xcom_anarchyfm/wiki/How-it-works) | And running it from source |
| 🔨 | [Building the exe](https://github.com/emzakit/xcom_anarchyfm/wiki/Building-the-exe) | Compile it yourself, trust nobody |
| 📝 | [Changelog](https://github.com/emzakit/xcom_anarchyfm/wiki/Changelog) | What changed, and when |

---

## ⚠️ Mission briefing: the honest bit

Every mod page promises perfection. Here's the truth instead.

**✅ The Avenger and Squad Select are the polished bits.** That's where the
effort went and I'll happily stand behind them.

**🚧 The tactical side is beta.** It trips occasionally — an overlap, the wrong
mood, timing that lands like a rookie panicking on turn one. It's good. It's not
flawless.

**🤝 Running an MMS music pack alongside this** works properly as of v2.3. Fill
the folders you care about; the pack covers the rest. *Very* rarely one screen
plays your music one session and the pack's the next — flip that toggle off in
the app and the pack wins every time.

**[Known issues →](https://github.com/emzakit/xcom_anarchyfm/wiki/Troubleshooting#known-issues)**

> **🛡️ Scanner flagged the exe?**
> [It's a false positive](https://github.com/emzakit/xcom_anarchyfm/wiki/Troubleshooting#flagged-as-a-virus).
> PyInstaller bundles Python into a single exe, which to an antivirus looks
> **exactly** like what actual malware does — same trick, wildly different
> intent. Classic case of mistaken identity. Don't fancy trusting a stranger's
> binary? Sensible. [Build it yourself.](https://github.com/emzakit/xcom_anarchyfm/wiki/Building-the-exe)

---

## 🏅 Credits

Three years in the making, and a follow-up to my
**[Resistance Radio](https://steamcommunity.com/sharedfiles/filedetails/?id=2863096697)**
mod. Built on the shoulders of
**[Music Modding System](https://steamcommunity.com/workshop/filedetails/?id=757398474)** —
none of this happens without it. Genuinely. Go say thanks.

Open source because everything should be, and partly in the hope that one of you
XCOM gurus cracks doing this *inside* Unreal instead of leaning on an external
audio player. That's the real dream. I got close. I did not get there.

Both mods are mine — **emzakit (Moondear)**. MIT licensed, see [`LICENSE`](LICENSE).

**Now go make the Avenger sound like *yours*, Commander.**

<p align="center">
  <a href="https://youtu.be/y4coRhi1n3w">Watch it</a>
  &nbsp;·&nbsp;
  <a href="https://github.com/emzakit/xcom_anarchyfm/releases/latest">Download</a>
  &nbsp;·&nbsp;
  <a href="https://steamcommunity.com/sharedfiles/filedetails/?id=3772839338">Steam Workshop</a>
  &nbsp;·&nbsp;
  <a href="https://github.com/emzakit/xcom_anarchyfm/issues">Report a bug</a>
</p>

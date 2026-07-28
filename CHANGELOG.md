# Changelog

All notable changes to Anarchy Radio FM. Versions refer to the **desktop app**;
where the in-game Workshop mod also changed, it's called out.

---

## v2.2.0

Mostly a fix release, plus the app can now update itself. Note the menu-music
bug is **not** resolved — see Known issues below.

### Added

- **Self-updating.** Checks GitHub on startup, shows the release notes, and can
  install the update itself — download, verify, swap, relaunch. The copy is
  copy-over rather than mirror, and `xipod_config.json`, `xipod_presets.json`
  and `.spotify_cache.json` are excluded, so settings and any music kept beside
  the exe survive. Opt out with a tickbox.
- **Shuffle toggle** in the Spotify panel.
- A **Why?** button in the setup wizard explaining the Radio Mode station
  length, instead of a wall of text.

### Known issues

- **Music can still keep playing when you back out to the main menu.** This
  release adds a detection path for it — the app now picks up the game's own
  `LoadMap: XComShell` line, because the mod's shell listener doesn't reliably
  fire and MMS emits no shell signal at all. Replaying real logs shows the
  state change is now detected, but it isn't reliably stopping playback in
  practice yet. Still being worked on.

### Fixed

- **Settings never persisted.** Toggles, per-state volumes and effects reverted
  on every launch — the ini writer merged with the *file* winning over the app,
  so each save rewrote the value it was meant to replace.
- **Radio Mode forgot itself.** The switch and the Radio Source choice now
  persist between sessions.
- **Spotify replayed one track forever.** Starting a playlist always begins at
  track 1 and shuffle was never set, so a screen played its first song every
  time. Shuffle is now enabled before playback.
- **Skip could play the wrong screen's music.** A state with no tracks left the
  previous state's playlist loaded.
- **Radio Mode leaked between screens.** A "same playlist" optimisation let the
  Avenger's track carry on into other states.
- **Tactical detection is more robust.** Combat and explore have fallback
  triggers, and MMS log matching is case-insensitive. (MMS never actually logs
  a "Transition to explore" line — explore had only ever worked by accident.)

### Security

- Spotify share links were validated by substring, so a URL merely *containing*
  `open.spotify.com` was accepted. The host is now parsed and verified.
  *(Reported by CodeQL.)*

### Mod

- `XiPod_UISL_Strategy` emits its state unconditionally. The old guard compared
  against a screen name persisted from a previous session and could stay silent
  for an entire playthrough.

---

## v2.1.0

### Added

- **Music Addons.** Workshop music packs are discovered automatically and merged
  into your library, with a panel to turn each on or off and sort by name, genre
  or track count. Pack audio plays from the workshop folder — nothing is copied,
  which is what makes the on/off switch possible.
- **Descriptors gained `description` and `genres`**, both optional and shown in
  the Music Addons panel.
- **Create Mod** now stamps out a complete, publishable ModBuddy project rather
  than a bare folder.
- **Radio Mode** as a panel button, with three **Radio Source** options
  (Radio Only / Avenger Only / Mix Both).
- Playback **pauses when XCOM closes**, instead of playing on until the mod
  launcher is closed too.

### Changed

- Radio Mode is **Avenger-only** by design. It applied everywhere in earlier
  builds, which fought the game's own music on the menu and killed the tension
  mid-firefight.
- Radio Mode loads a **slice at a time** (10 minutes by default, configurable)
  and re-tunes when it ends. An hour-long station rip previously cost ~657 MB
  and ten seconds of silence before the first note; it's now ~2.5 seconds.
- **New look** — repainted in XCOM 2's Avenger palette, cyan on near-black with
  amber for signals and warnings.

---

## v2.0.0

### Removed

- **The Web Player.** It embedded a full copy of Chromium (QtWebEngine) — about
  360 MB of the download — to show one web page, and a bundled browser engine is
  a lot of attack surface to attach to a music mod. Streaming per state lives in
  the Spotify feature instead.

### Changed

- **No more ffmpeg install.** The decoder ships inside the app, so `.mp3`,
  `.ogg`, `.wav`, `.flac`, `.m4a`, `.opus` and `.wma` all work out of the box.
  Tracks also load roughly 10× faster, since decoding no longer spawns a process
  per track.
- **The download is about a third of the size** — ~507 MB installed down to
  ~174 MB, 72 MB zipped.

---

## v1.0.0

First public release.

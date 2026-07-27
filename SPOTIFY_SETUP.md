# Spotify Setup (Experimental)

Anarchy Radio FM can bind a **Spotify playlist to each game state** — combat plays your
combat playlist, the Avenger plays your chill playlist, and so on. This is an
**experimental** feature and you use it **at your own risk**: it drives *your*
Spotify account through *your own* API app registration.

## Read this first — how it actually works

The Spotify Web API **does not stream audio**. It can only **remote-control a
Spotify client that is already running**. So Anarchy Radio FM doesn't play Spotify itself —
it tells your **Spotify desktop app** which playlist to switch to when the game
state changes.

That means:

- ✅ You need **Spotify Premium** (playback control is Premium-only).
- ✅ The **Spotify desktop app must be open and running** while you play.
- ✅ Start playing *something* in Spotify once so it becomes the "active device."
- ❌ It won't work on a free account.
- ⚠️ Your API keys and OAuth tokens are stored **locally** on your PC
  (`xipod_config.json` and `.spotify_cache.json`, both git-ignored). Keep them
  private — treat your Client Secret like a password.

If any of that is a dealbreaker, just use local files or MMS music packs — those
are the primary, supported path.

---

## 1. Create a Spotify app (get your keys)

1. Go to the **Spotify Developer Dashboard**:
   <https://developer.spotify.com/dashboard>
2. Log in with your Spotify account and click **Create app**.
3. Fill in:
   - **App name / description**: anything (e.g. "Anarchy Radio FM").
   - **Redirect URI**: add exactly
     ```
     http://127.0.0.1:8888/callback
     ```
     Click **Add**. This must match what Anarchy Radio FM uses (it's the default).
   - **Which API/SDKs**: tick **Web API**.
4. Save. Open the app's **Settings**.
5. Copy the **Client ID**. Click **View client secret** and copy the
   **Client Secret** too.

## 2. Enter them in Anarchy Radio FM

1. In Anarchy Radio FM, click **Spotify**.
2. Paste your **Client ID** and **Client Secret**.
3. Leave **Redirect URI** as `http://127.0.0.1:8888/callback` (unless you
   registered a different one — it must match exactly).
4. Click **Link Spotify Account**. Your browser opens; approve access. When it
   says you can close the tab, you're linked (the dialog shows "Linked ✓").

## 3. Assign playlists

For each state, paste a Spotify **playlist link** (or URI). Examples of accepted
formats:

```
https://open.spotify.com/playlist/37i9dQZF1DX0XUsuxWHRQd
spotify:playlist:37i9dQZF1DX0XUsuxWHRQd
```

To get a link: in Spotify, right-click a playlist → **Share** → **Copy link to
playlist**. Albums and artist pages work too.

Leave a state **blank** to use your **local files** for it instead — you can mix
and match (e.g. Spotify for the Avenger, local files for combat).

Tick **Enable Spotify mode**, then **Save**.

## 4. Play

1. Open the **Spotify desktop app** and start playing anything once (so it's the
   active device).
2. Launch the game through Anarchy Radio FM as usual.
3. When the game enters a state you assigned a playlist to, Anarchy Radio FM tells Spotify
   to switch to it. The play/pause and next/previous buttons in Anarchy Radio FM control
   Spotify while it's driving a state.

---

## Troubleshooting

- **"No Spotify device found"** — open the Spotify desktop app and press play
  once, then re-enter the state (or press play in Anarchy Radio FM).
- **"requires Spotify Premium"** — playback control is Premium-only; there's no
  workaround.
- **Nothing happens on state change** — confirm **Enable Spotify mode** is
  ticked, the account shows **Linked ✓**, and the state actually has a playlist
  assigned.
- **"Couldn't open local port 8888"** — something else is using it. Change the
  Redirect URI (in both the Dashboard and Anarchy Radio FM) to another port, e.g.
  `http://127.0.0.1:8899/callback`.
- **Re-linking** — if you change your Client ID/Secret, click **Link Spotify
  Account** again.

## Notes & limits

- Cinematics don't pause Spotify (the game's own cutscene audio plays over it).
- There's a short delay on state changes (a network round-trip to Spotify).
- Anarchy Radio FM's volume slider, crossfade, and effects do **not** apply to Spotify
  playback — that's all handled by Spotify itself.

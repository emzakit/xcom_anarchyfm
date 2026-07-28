[h1]Anarchy Radio FM[/h1]

[b]Anarchy Radio FM replaces XCOM 2's soundtrack with local files![/b]

Drop in .mp3, .ogg, .wav, .flac, .m4a or .opus and it plays in sync with the game. No need to learn how to create those scary gigantic upk files anymore.

Hans Zimmer scoring your Geoscape while the world quietly falls apart? Go on then. Slipknot the second the shooting starts? Absolutely. Spice Girls playing over an ADVENT ambush because you thought it would be funny GTA radio playing over the Avengers so you can have a laugh at Chatterbox FM? Sure!

[b]Watch it in action:[/b] https://youtu.be/y4coRhi1n3w

You will see the current primary bug, backing out to the menu keeps playing whatever was playing. Yeah, yeah, I'm on it.

This is the follow-up to my [url=https://steamcommunity.com/sharedfiles/filedetails/?id=2863096697]Resistance Radio[/url] mod. Three years I've been chewing on this idea. The problem was always the same: doing it properly meant nightmare DLL injections that crash the game the moment you look at them funny. This works instead.

[hr][/hr]
[h2]⚠ READ THIS BEFORE SUBSCRIBING[/h2]

[b]This Workshop item is only the tiny IN-GAME half.[/b]

On its own it makes exactly zero sound. All it does is watch your screens and quietly report what's happening. The actual music comes from a companion desktop app, and you need both:

[url=https://github.com/emzakit/xcom_anarchyfm/releases]➜ Download the desktop app here[/url]

As of v2.2 the app now has an updater to pull from GitHub (with your permission).

[h3]Setup — about two minutes[/h3]
[list]
[*] [b]1.[/b] Subscribe to this mod [b]and[/b] to [url=https://steamcommunity.com/sharedfiles/filedetails/?id=757398474]Music Modding System[/url]. MMS does the heavy lifting of silencing the vanilla soundtrack — nothing here works without it.
[*] [b]2.[/b] Add [b]-forcelogflush[/b] to XCOM 2's launch options. In Steam: right-click XCOM 2 → Properties → Launch Options. Using a mod launcher? Put it in that launcher's arguments field.
[*] [b]3.[/b] Grab the ZIP from [url=https://github.com/emzakit/xcom_anarchyfm/releases]GitHub Releases[/url].
[*] [b]4.[/b] Unzip it anywhere you like and run the exe. A setup wizard walks you through the rest.
[*] [b]5.[/b] [i](Optional but recommended)[/i] Use the [url=https://github.com/X2CommunityCore/xcom2-launcher]Alternative Mod Launcher[/url].
[/list]

[h3]⚠ Why -forcelogflush is not optional[/h3]
The app works out what you're doing by reading XCOM's log, and XCOM buffers that file rather than writing it as it goes. A cinematic writes nothing at all while it plays, so there's nothing to push the buffer out and the app can hear about a film up to 27 seconds after it began — long after it finished. That switch turns the buffering off. Without it, music plays straight over your cinematics.

[h3]Do I still need to set Music volume to 0?[/h3]
[b]No — not as of v2.3.[/b] That was the workaround for XCOM's own soundtrack playing underneath everything, and that's now fixed properly. Turn it back up: muting it also silences MMS and any music packs you're running, so screens you've handed to a pack would go quiet.

[i]Don't trust a random exe off the internet? Good instinct. It's all open source —[/i] [url=https://github.com/emzakit/xcom_anarchyfm/blob/main/BUILDING.md]build it yourself[/url].

[h3]Can I use this with MMS packs?[/h3]

Yes — and as of v2.3 it works properly rather than by luck.

Ownership is per screen. Put music in a folder and switch that screen on, and this takes it. Leave a folder empty or switch the screen off, and your MMS pack keeps it. The app reads which mods you actually have enabled and steps the pack aside only on the screens it's covering, so the two aren't fighting over the same one.

Before v2.3 that was genuinely a coin flip — MMS picks at random between two things that both claim a screen, which is why the vanilla soundtrack kept turning up. Fixed.

Empty folders = MMS music. No MMS pack either = the in-game soundtrack, if you have the fallback option turned on in MMS.

Rare exception: a few packs are built the same stubborn way this mod is, and when two of those want the same screen, the game just picks one at random each time you play. You'd notice it as a screen that plays your music some sessions and the pack's music others. Fix is easy — switch that screen off in the app and the pack keeps it for good.

[hr][/hr]
[h2]How you organise it[/h2]

Two ways, and you can mix them:

[list]
[*] [b]A folder per screen[/b] — drop tracks into STATE_AVENGER/, STATE_GEOSCAPE/, STATE_MISSION_COMBAT/ and so on. Each screen gets its own vibe.
[*] [b]One big station[/b] — chuck everything into STATE_RESISTANCE_RADIO/ and hit [b]Radio Mode[/b]. More on that in a second, because it's the good bit.
[/list]

Leave a folder empty and that screen just keeps the game's own music. Fill in as much or as little as you fancy.

[h3]📻 Radio Mode — the good bit[/h3]

One button. Switch it on and the Avenger tunes into a station, with [b]every track starting at a random point[/b]. Not from the top — from wherever the broadcast happens to be. Nothing ever feels like a playlist looping round; it feels like a signal that was already running before you walked in.

[b]Pro tip that will sell you on this instantly:[/b] download a few hour-long GTA radio station rips — DJ banter, fake adverts, the lot — and drop them in. Every time you come back to the Avenger you land mid-song, mid-advert or mid-DJ-ramble. It is ridiculous and I love it.

[b]It only affects the Avenger, deliberately.[/b] Long radio content is perfect for pottering around the ship and awful everywhere else. On the main menu it fights the game's own music, and a DJ cracking a joke halfway through a firefight murders the tension stone dead.

Three buttons pick where it draws from:
[list]
[*] [b]Radio Only[/b] — just STATE_RESISTANCE_RADIO/.
[*] [b]Avenger Only[/b] — just STATE_AVENGER/. Your normal Avenger music with the random-start treatment. No radio folder needed — this one's a sleeper hit.
[*] [b]Mix Both[/b] — both pooled together. When a track ends, the next could come from either.
[/list]

Small print, because it matters:
[list]
[*] Off by default, and it remembers itself — the switch and your source choice survive between sessions.
[*] While it's on it overrides STATE_AVENGER_LOOP/ and the Loop Track setting. A station that repeats one song forever isn't a station. Switch it off and your loop track comes straight back.
[*] Station rips run to an hour, so it loads a slice at a time (10 minutes by default) and re-tunes when that ends. Loading a full hour costs a few hundred MB and a real pause before the first note. Set it in the wizard, change it in Options.
[/list]

[h3]Effects[/h3]
There's a whole rack of them. Want your Avenger tracks to sound like they're coming through a beaten-up field radio? Easy.

[h3]Music Addons[/h3]
If someone builds an addon for this, you will be able to subscribe to the music pack on the Workshop and it just turns up in your library, mixed in alongside your own stuff. The [b]Music Addons[/b] button lists everything you're subscribed to and you can switch them on / off.

[list]
[*] Nothing gets copied to your drive. Pack audio plays straight out of the workshop folder, which is what makes the on/off switch possible in the first place. A big station pack can be gigabytes, you don't want a second copy of that.
[*] Sort by name, genre or track count. Filter to a single genre.
[*] Your own music always wins a filename clash.
[*] [b]Want to make one?[/b] Hit [b]Create Mod[/b] in the app and it stamps out a complete, ready-to-publish ModBuddy project — folders, config, descriptor, the lot. Fill it with music and hit publish.
[/list]

[h3]Spotify (experimental)[/h3]
Pin a Spotify playlist to each game state. Needs Premium, needs the desktop app open, needs your own API keys. It drives your account through your own registration, so it's very much an at-your-own-risk toy

[url=https://github.com/emzakit/xcom_anarchyfm/blob/main/SPOTIFY_SETUP.md]Setup guide here[/url].

[h3]Changing tracks[/h3]
On-screen menus caused more headaches than they solved, so:
[list]
[*] [b]The lazy way:[/b] dip in and out of the Geoscape. Every trip back reshuffles.
[*] [b]The proper way:[/b] open the Mod Config Menu (MCM) in game — Play / Pause / Next / Back, wired straight to the player.
[/list]

[url=https://github.com/emzakit/xcom_anarchyfm/blob/main/music/music_readme.md]➜ Full guide to the music folders[/url]

[hr][/hr]
[h2]Known bugs: report them here[/h2]
[list]
I won't be able to test everything because life is busy. So I'm relying on ya'll to tell me when this goes totally wrong.

https://github.com/emzakit/xcom_anarchyfm/issues

[hr][/hr]
[h2]Change log[/h2]
[list]

https://github.com/emzakit/xcom_anarchyfm/wiki/Changelog
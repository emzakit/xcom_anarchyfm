[h1]Anarchy Radio FM[/h1]

[b]Anarchy Radio FM replaces XCOM 2's soundtrack with local files![/b]

Drop in .mp3, .ogg, .wav, .flac, .m4a or .opus and it plays in sync with the game. No need to learn how to create those scary gigantic upk files anymore.

Hans Zimmer scoring your Geoscape while the world quietly falls apart? Go on then. Slipknot the second the shooting starts? Absolutely. The Spice Girls playing over an ADVENT ambush because you thought it would be funny and now it's canon? Nobody here is going to stop you. GTA radio playing over the Avengers so you can have a laugh at Chatterbox FM? Sure!

[b]Watch it in action:[/b] https://youtu.be/y4coRhi1n3w

You will see the current primary bug, backing out to the menu keeps playing whatever was playing. Yeah, yeah, I'm on it.

This is the follow-up to my [url=https://steamcommunity.com/sharedfiles/filedetails/?id=2863096697]Resistance Radio[/url] mod. Three years I've been chewing on this idea. The problem was always the same: doing it properly meant nightmare DLL injections that crash the game the moment you look at them funny. So I stopped trying to do it properly. This works instead.

[hr][/hr]
[h2]⚠ READ THIS BEFORE SUBSCRIBING[/h2]

[b]This Workshop item is only the tiny IN-GAME half.[/b]

On its own it makes exactly zero sound. All it does is watch your screens and quietly report what's happening. The actual music comes from a companion desktop app, and you need both:

[url=https://github.com/emzakit/xcom_anarchyfm/releases]➜ Download the desktop app here[/url]

[h3]Setup — about two minutes[/h3]
[list]
[*] [b]1.[/b] Subscribe to this mod [b]and[/b] to [url=https://steamcommunity.com/sharedfiles/filedetails/?id=757398474]Music Modding System[/url]. MMS does the heavy lifting of silencing the vanilla soundtrack — nothing here works without it.
[*] [b]2.[/b] Grab the ZIP from [url=https://github.com/emzakit/xcom_anarchyfm/releases]GitHub Releases[/url].
[*] [b]3.[/b] Unzip it anywhere you like and run the exe. A setup wizard walks you through the rest.
[*] [b]4.[/b] [i](Optional but recommended)[/i] Use the [url=https://github.com/X2CommunityCore/xcom2-launcher]Alternative Mod Launcher[/url].
[/list]

[h3]⚠ One setting you really do need to change if you toggle states other than the Avenger[/h3]
In game: [b]Options → Audio → Music → 0[/b].

MMS silences most of XCOM's own soundtrack, but not every screen and not every moment — and those gaps are exactly where you'll hear two soundtracks wrestling each other. Turn it to zero and 90% of "weird audio" problems never happen.

(The app can't do this for you. XCOM keeps audio settings in a binary profile save that also holds your character pool, and I'm not writing to that on your behalf.)

[i]Don't trust a random exe off the internet? Good instinct. It's all open source —[/i] [url=https://github.com/emzakit/xcom_anarchyfm/wiki/Building-the-exe]build it yourself[/url].

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
There's a whole rack of them — radio filter, reverb, bass, chorus, bitcrush, echo — plus per-state presets. Want your Avenger tracks to sound like they're coming through a beaten-up field radio? That's two clicks.

[h3]Music Addons[/h3]
If someone builds an addon for this, you will be able to subscribe to the music pack on the Workshop and it just turns up in your library, mixed in alongside your own stuff. The [b]Music Addons[/b] button lists everything you're subscribed to — author, genre tags, description, track count — with a switch for each.

[list]
[*] Nothing gets copied to your drive. Pack audio plays straight out of the workshop folder, which is what makes the on/off switch possible in the first place. A big station pack can be gigabytes — you don't want a second copy of that.
[*] Sort by name, genre or track count. Filter to a single genre.
[*] Your own music always wins a filename clash. A pack can never shadow a track you put there yourself.
[*] [b]Want to make one?[/b] Hit [b]Create Mod[/b] in the app and it stamps out a complete, ready-to-publish ModBuddy project — folders, config, descriptor, the lot. Fill it with music and hit publish.
[/list]

[h3]Spotify (experimental)[/h3]
Pin a Spotify playlist to each game state. Needs Premium, needs the desktop app open, needs your own API keys — it drives your account through your own registration, so it's very much an at-your-own-risk toy. But when it works it's great. [url=https://github.com/emzakit/xcom_anarchyfm/wiki/Spotify-setup]Setup guide here[/url].

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
https://github.com/emzakit/xcom_anarchyfm/issues
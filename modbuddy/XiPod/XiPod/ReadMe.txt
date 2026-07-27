[h1]Anarchy Radio FM[/h1]

Alright folks, here it is: the follow-up to my [url=https://steamcommunity.com/sharedfiles/filedetails/?id=2863096697]Resistance Radio Mod[/url]. I've been poking at this idea for about three years. After a year of messing around (and getting some handy AI help, sue me!), I finally figured out a way to pull this off without using nightmare DLL injections that just cause the game to crash.

Anarchy Radio FM lets you replace XCOM 2's soundtrack with your [b]OWN[/b] local music. It supports .mp3, .ogg, .flac, .m4a and .wav files and plays them perfectly in sync with the game. You get your own title music on the menu, chill tunes on the Avenger, and something loud when the shooting starts. It even has experimental support for Spotify!

[hr][/hr]
[h2]READ THIS BEFORE SUBSCRIBING[/h2]

[b]This Workshop item is only the tiny IN-GAME half of the project.[/b]

It simply watches the game's screens and quietly reports what's happening. On its own, this mod does absolutely nothing audible! To actually play your music, you [b]must[/b] download the companion Anarchy Radio FM desktop app:

https://github.com/emzakit/xcom_anarchyfm

There are two ways to organise your music, and you can mix them:
[list]
[*] [b]Per-state folders[/b] (the default) — drop tracks into STATE_AVENGER/, STATE_GEOSCAPE/ and so on, and each screen gets its own music.
[*] [b]One station[/b] — drop everything into STATE_RESISTANCE_RADIO/ and hit the [b]Radio Mode[/b] button in the desktop app. The Avenger then plays from that folder, with random start points. (Radio Mode is Avenger-only — see below.)
[/list]

[h3]Setup Instructions[/h3]
[list]
[*] [b]Step 1:[/b] Subscribe to this mod and the required [url=https://steamcommunity.com/sharedfiles/filedetails/?id=757398474]Music Modding System[/url]. This mod leans entirely on MMS to silence the game's vanilla music:
[*] [b]Step 2:[/b] Download the latest ZIP release of the desktop app here: [url=https://github.com/emzakit/xcom_anarchyfm/releases]GitHub Releases[/url]
[*] [b]Step 3:[/b] Unzip it to a folder of your choice and run the executable.
[*] [b]Step 4:[/b] (Optional) Use the Alternative Mod Launcher for the best experience: [url=https://github.com/X2CommunityCore/xcom2-launcher]AML GitHub[/url]
[/list]

[i]If you don't trust the executable (smart), the entire project is open-source, and you can rebuild it yourself:[/i] [url=https://github.com/emzakit/xcom_anarchyfm/blob/main/BUILDING.md]Build instructions[/url]

[hr][/hr]
[h2]Features & How to Play[/h2]

[h3]Sound Effects[/h3]
There are plenty of sound effects for you to play around with to try and get the right sound!

[h3]Radio Mode (Avenger only)[/h3]
One button in the desktop app. Switch it on and the Avenger tunes into a station, with every track starting at a new random spot. It feels exactly like tuning into a live broadcast you're ducking in and out of while you potter around the ship.

[b]It only affects the Avenger, on purpose.[/b] Long radio mixes are perfect for downtime and terrible everywhere else — on the main menu they fight the game's own music, and a DJ cracking jokes halfway through a firefight ruins the tension. Every other screen is left completely alone.

Three buttons decide where the Avenger pulls from:
[list]
[*] [b]Radio Only[/b] — STATE_RESISTANCE_RADIO/ only.
[*] [b]Avenger Only[/b] — STATE_AVENGER/ only. Your normal Avenger music, but with the random start points. No radio folder needed!
[*] [b]Mix Both[/b] — both folders pooled. When a track ends, the next one can come from either.
[/list]

[list]
[*][b]Pro-Tip:[/b] Download some long GTA radio stations (complete with DJ banter and fake ads) and drop them into STATE_RESISTANCE_RADIO/. Every time you return to the Avenger, you'll land mid-song, mid-ad, or mid-DJ ramble!
[*] Radio Mode overrides the STATE_AVENGER_LOOP/ folder and the Loop Track setting while it's on — otherwise you'd be stuck hearing one track on repeat instead of a station. Switch it off and your loop track comes right back.
[*] It's off by default, and it leaves your per-state Effects settings alone — switch it back off and everything is exactly as you left it. Once you turn it on it stays on: the switch and your source choice are remembered between sessions.
[*] Station rips are usually an hour long, so Radio Mode loads a slice at a time (10 minutes by default) and re-tunes to a fresh random spot when it ends. Loading a whole hour costs a few hundred MB and a real pause before the first note. You pick this in the setup wizard and can change it in Options.
[/list]

[h3]Music Addons[/h3]
Subscribe to an Anarchy Radio FM music pack on the Workshop and it just turns up in your library, mixed in alongside your own tracks. The [b]Music Addons[/b] button in the desktop app lists everything you're subscribed to — author, genre tags, description, track count — with a switch to turn each one on or off.

[list]
[*] Nothing is copied to your drive. Pack audio plays straight from the workshop folder, which is what makes the on/off switch possible. A big station pack can be gigabytes; you don't want a second copy of that.
[*] Sort by name, genre or track count, and filter to a single genre.
[*] Your own music always wins a filename clash, so a pack can never shadow a track you put there yourself.
[*] Want to make one? Hit [b]Create Mod[/b] in the app — it stamps out a complete, ready-to-publish ModBuddy project with all the folders and files already wired up.
[/list]

[h3]Changing Stations[/h3]
On-screen menus caused too many headaches, so I stripped them out.
[list]
[*] [b]The Hacky Way:[/b] Just dip IN AND OUT of the Geoscape. Every time you come back, the playlist reshuffles.
[*] [b]The Button Way:[/b] Open the Mod Config Menu (MCM) in-game. Under Anarchy Radio FM, you'll find Play / Pause / Next / Back buttons that control the desktop player instantly.
[/list]

[h3]Adding Your Music & Spotify[/h3]
[list]
[*] [b]Local Folders Setup:[/b] [url=https://github.com/emzakit/xcom_anarchyfm/blob/main/music/music_readme.md]Music Guide[/url]
[*] [b]Spotify Setup:[/b] [url=https://github.com/emzakit/xcom_anarchyfm/blob/main/SPOTIFY_SETUP.md]Spotify Guide[/url]
[/list]

[hr][/hr]
[h2]Good to Know[/h2]
[list]
[*] [b]Polished Experience:[/b] The Avenger and Squad Select screens are the polished, intended core of this mod.
[*] [b]Experimental Combat:[/b] The tactical/combat states are currently in beta and might be a bit rough around the edges. MMS music packs are great for this, and Anarchy Radio FM is happy to run alongside them to cover the gaps!
[*] [b]Zero In-Game Setup:[/b] Everything is configured directly inside the desktop app. Nothing in the game itself needs tweaking.
[*] [b]No ffmpeg install:[/b] As of v2 the audio decoder is bundled, so .mp3 / .ogg / .flac / .m4a all just work. Older versions made you install ffmpeg and put it on your PATH — that step is gone.
[*] [b]No bundled browser:[/b] v1 shipped an embedded Chromium (a Web Player for streaming YouTube). It's been removed — it was 360 MB of the download and a browser engine is a lot of security surface to staple onto a music mod. Streaming per state lives in the Spotify feature, which drives the real Spotify desktop app instead. The download is about a third of the size as a result.
[/list]

If you prefer a curated, hassle-free experience with absolutely zero setup, my original [b]Resistance Radio[/b] mod is still up and running perfectly: [url=https://steamcommunity.com/sharedfiles/filedetails/?id=2863096697]Resistance Radio on Steam[/url]

Happy hunting, Commander!
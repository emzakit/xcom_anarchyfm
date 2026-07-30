Pre-requisites: install the XCOM 2 SDK (Not War of the Chosen, we won't need it for this).

But, I'm only playing on WOTC!?

That's okay, the mod is compatible. So, don't fret, it's designed to work with WOTC and vanilla. The XCOM 2 SDK is far easier to set up than the WOTC one, trust me. Use the XCOM 2 SDK if you don't want a headache.

Follow this guide to set things up:

https://steamcommunity.com/sharedfiles/filedetails/?id=956935800

Download the following files in addon_template folder in this repo:

MusicMod.zip
RenameMeToModName_xipod.json

Music template was created by E3245 from the mammoth guide they wrote here... yeah, it's as fiddly and nightmarish as it looks, but if it wasn't for robojumper and the excellent modders out there, this mod wouldn't exist! They're rockstars for putting this together. My aim was to just make things a little easier...

https://docs.google.com/document/d/1qWKWoiinOu-A4u4W6L9g7gUdWPabb5_vkd0zHO6egSw/edit?tab=t.0

1) Place musicmod.zip template in:

\SteamLibrary\steamapps\common\XCOM 2 SDK\Binaries\Win32\ModBuddy\Extensions\Application\ProjectTemplates\XCOM2Mod\1033

2) Go to tools > options and set up your paths

Set the projects locations to addon_projects (or wherever you want to store your project files)

addon_tests in the folder is for built mods, which you can set to under tools > options > xcom2 > general

Alternatively just copy them there when you've built them (more on that later)

img_addon_01.png

3) Create a new mod and choose the MusicMod template

Choose an easy name and DontUseSpaces or special characters

img_addon_02.png

4) Delete these files:

Files to delete inside config folder:
XComShellSound.ini
XComSkyrangerSound.ini
XComStrategySound.ini
XComTacticalSound.ini

Delete Localization folder

Delete Src folder to prevent later grief, you won't need it.

img_addon_03

Sometimes you might have to go into the project folder and delete them manually as well, the SDK is annoying like that.

img_addon_03b

5) Place the template json file in your mod folder and rename it to match your mod, but you must keep _xipod.json

That's the identifier for the mod

img_addon_04

6) Inside ModBuddy right click on your parent mod name, under solution > add > existing item > choose the json file

img_addon_05

Or you can create a text file yourself using notepad and paste what shows up in the section below into it and save as .json

7) Edit the json file to match your mod name etc.

It'll look like this:

{
    "name": "Name of Anarchy FM addon",
    "author": "Your name",
    "description": "what kind of addon is it",
    "genres": ["separate", "genres", "with", "commas"],
    "folders": {
        "STATE_SHELL_MENU": "Content/",
        "STATE_AVENGER": "Content/",
        "STATE_GEOSCAPE": "Content/",
        "STATE_SQUADSELECT": "Content/",
        "STATE_MISSION_EXPLORE": "Content/",
        "STATE_MISSION_COMBAT": "Content/",
        "STATE_AVENGER_LOOP": "Content/",
        "STATE_GEOSCAPE_LOOP": "Content/",
        "STATE_MISSION_COMBAT_LOOP": "Content/",
        "STATE_MISSION_EXPLORE_LOOP": "Content/",
        "STATE_SHELL_MENU_LOOP": "Content/",
        "STATE_SQUADSELECT_LOOP": "Content/",
        "STATE_VICTORY": "Content/",
        "STATE_DEFEAT": "Content/",
        "STATE_RESISTANCE_RADIO": "Content/"
    }
}

You can remove all the stuff you won't be using, so in this one we only want the resistance radio folder

img_addon_06

8) right click on content folder > add new folder > give it an appropriate name > in this example it's GTARadio

img_addon_07

9) Now we need to point the folder IDs inside the json file to the folder(s) you created

In this example we are pointing STATE_RESISTANCE_RADIO > GTARadio

"STATE_RESISTANCE_RADIO": "Content/GTARadio/"

img_addon_08

10) Place your audio files in the folder(s) you created

11) Just like we did with the json file, right click on each folder inside the SDK and then add > existing item > select your music files folder by folder:

img_addon_09

12) Open up the ini files in the config folder and make sure all the names are the same as your project name:

img_addon_10

13) Let's run a test build under build > build solution

(When you do another build, clean the solution first)

img_addon_11

If it worked then you're ready to test it.

It will output to: \steamapps\common\XCOM 2 SDK\Binaries\Win32\ModBuddy\Mods

You can change that in tools > options > XCOM 2 > general > change user path

img_addon_12

Copy the built in there to your addon_test folder
You can also copy it to your Steam Workshop folder instead, up to you really, either should work:

\SteamLibrary\steamapps\workshop\content\268500

14) Open up Anarchy FM it should show up under music addons to tick on / off

15) give it a test in game, if it plays, great. All done. Go back to the SDK and then tools > publish mod:

img_addon_14
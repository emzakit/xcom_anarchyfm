"""Music Mod Scaffolding — stamp out a publishable Workshop addon project.

Copies the bundled ModBuddy template (addon_template/ModName_xipod) and
renames it into a real project the user can open, fill with music and publish.

This is the Python equivalent of addon_template/anarchy_addon_setup.bat, with
three fixes the batch version doesn't make:

  * It COPIES rather than renaming in place, so the template survives and you
    can stamp out as many mods as you like. The batch script renames its own
    template away and can only ever be run once.
  * It rewrites the .XCOM_sln and .x2proj *contents*. Renaming the files alone
    leaves the solution pointing at "My XCOM2 Mod1\\My XCOM2 Mod1.x2proj",
    a path that no longer exists — ModBuddy won't open it.
  * It adds the music/ folders and the _xipod.json descriptor to the .x2proj.
    They're absent from the template, so ModBuddy wouldn't package the two
    things that actually make it an Anarchy Radio FM addon.
"""

import json
import os
import re
import shutil
import uuid

from library import STATE_FOLDERS_FOR_MODS
from paths import resource_path

TEMPLATE_NAME = "ModName_xipod"

# ModBuddy leaves these behind; they're per-user state, not project content.
_IGNORE = shutil.ignore_patterns("*.XCOM_suo", "*.user", "obj", "bin")


def safe_mod_name(raw):
    """Turn user input into something usable as a folder and UnrealScript
    class suffix. Unreal identifiers can't contain spaces or punctuation."""
    cleaned = re.sub(r"[^0-9A-Za-z_]+", "_", (raw or "").strip()).strip("_")
    return cleaned or "MyMusicPack"


def scaffold_music_mod(dest_dir, mod_name):
    """Create <dest_dir>/<name>_xipod/ from the template. Returns its path."""
    name = safe_mod_name(mod_name)
    full = f"{name}_xipod"

    template = resource_path("addon_template", TEMPLATE_NAME)
    if not os.path.isdir(template):
        raise FileNotFoundError(
            f"Mod template missing: {template}\n"
            "It should ship alongside the app — see AnarchyRadioFM.spec."
        )

    outer = os.path.join(dest_dir, full)
    if os.path.exists(outer):
        raise FileExistsError(f"'{full}' already exists in that folder.")

    shutil.copytree(template, outer, ignore=_IGNORE)

    # --- rename the pieces the template names after itself ---
    inner_old = os.path.join(outer, TEMPLATE_NAME)
    inner = os.path.join(outer, full)
    _rename(inner_old, inner)

    _rename(os.path.join(outer, f"{TEMPLATE_NAME}.XCOM_sln"),
            os.path.join(outer, f"{full}.XCOM_sln"))
    _rename(os.path.join(inner, f"{TEMPLATE_NAME}.json"),
            os.path.join(inner, f"{full}.json"))
    _rename(os.path.join(inner, f"{TEMPLATE_NAME}.x2proj"),
            os.path.join(inner, f"{full}.x2proj"))
    _rename(os.path.join(inner, "Src", TEMPLATE_NAME),
            os.path.join(inner, "Src", full))

    music_dir = os.path.join(inner, "music")
    classes_dir = os.path.join(inner, "Src", full, "Classes")
    config_dir = os.path.join(inner, "Config")
    for d in (music_dir, classes_dir, config_dir):
        os.makedirs(d, exist_ok=True)

    _write_descriptor(os.path.join(inner, f"{full}.json"), name, music_dir)
    _write_configs(config_dir, full, name)
    _write_dlc_class(classes_dir, name)
    _fix_project_file(os.path.join(inner, f"{full}.x2proj"), full, music_dir)
    _fix_solution_file(os.path.join(outer, f"{full}.XCOM_sln"), full)
    _write_readme(inner, full, music_dir)

    return outer


def _rename(src, dst):
    if os.path.exists(src) and not os.path.exists(dst):
        os.rename(src, dst)


def _state_dirs(music_dir):
    """The STATE_* folders actually present in the template's music/."""
    try:
        present = {d.upper() for d in os.listdir(music_dir)
                   if os.path.isdir(os.path.join(music_dir, d))}
    except OSError:
        present = set()
    return [s for s in STATE_FOLDERS_FOR_MODS if s in present]


def _write_descriptor(path, name, music_dir):
    states = _state_dirs(music_dir)
    if not states:
        # Template had no music folders — create the standard set so the
        # descriptor isn't pointing at nothing.
        for s in STATE_FOLDERS_FOR_MODS:
            os.makedirs(os.path.join(music_dir, s), exist_ok=True)
        states = list(STATE_FOLDERS_FOR_MODS)

    descriptor = {
        "name": name,
        "author": "Your name",
        "description": "One or two sentences about your pack.",
        "genres": ["Rock", "Orchestral"],
        "folders": {s: f"music/{s}" for s in states},
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(descriptor, f, indent=4)


def _write_configs(config_dir, full, name):
    with open(os.path.join(config_dir, "XComEditor.ini"), "w", encoding="utf-8") as f:
        f.write(f"[ModPackages]\n+ModPackages={full}\n")
    with open(os.path.join(config_dir, "XComEngine.ini"), "w", encoding="utf-8") as f:
        f.write(f"[Engine.ScriptPackages]\n+NonNativePackages={full}\n")
    with open(os.path.join(config_dir, "XComGame.ini"), "w", encoding="utf-8") as f:
        f.write(f"[{full}.X2DownloadableContentInfo_{name}]\n"
                f'DLCIdentifier="{full}"\n')


def _write_dlc_class(classes_dir, name):
    path = os.path.join(classes_dir, f"X2DownloadableContentInfo_{name}.uc")
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            "//---------------------------------------------------------------------------------------\n"
            f"//  FILE:   X2DownloadableContentInfo_{name}.uc\n"
            "//\n"
            "//  An Anarchy Radio FM music addon needs no script to work — the desktop app reads\n"
            "//  the _xipod.json descriptor directly. This class exists so ModBuddy has\n"
            "//  something to compile and the mod registers cleanly with the game.\n"
            "//---------------------------------------------------------------------------------------\n"
            "\n"
            f"class X2DownloadableContentInfo_{name} extends X2DownloadableContentInfo;\n"
        )


def _fix_project_file(path, full, music_dir):
    """Rename the project's identity and register the music + descriptor.

    The template's .x2proj still calls itself "My XCOM2 Mod1" and lists
    neither the music folders nor the .json — so without this, ModBuddy would
    publish a mod containing none of the actual content.
    """
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8-sig") as f:
        xml = f.read()

    xml = re.sub(r"<Name>.*?</Name>", f"<Name>{full}</Name>", xml, count=1)
    xml = re.sub(r"<Description>.*?</Description>",
                 f"<Description>Anarchy Radio FM music addon: {full}</Description>",
                 xml, count=1)
    xml = re.sub(r"<AssemblyName>.*?</AssemblyName>",
                 f"<AssemblyName>{full}</AssemblyName>", xml, count=1)
    xml = re.sub(r"<RootNamespace>.*?</RootNamespace>",
                 f"<RootNamespace>{full}</RootNamespace>", xml, count=1)
    # A fresh Guid per mod — every copy of the template shares the original.
    xml = re.sub(r"<Guid>.*?</Guid>", f"<Guid>{uuid.uuid4()}</Guid>", xml, count=1)

    states = _state_dirs(music_dir)
    entries = ['    <Folder Include="music\\" />']
    entries += [f'    <Folder Include="music\\{s}\\" />' for s in states]
    entries.append(f'    <Content Include="{full}.json" />')
    block = "  <ItemGroup>\n" + "\n".join(entries) + "\n  </ItemGroup>\n"

    xml = xml.replace("</Project>", block + "</Project>")

    with open(path, "w", encoding="utf-8") as f:
        f.write(xml)


def _fix_solution_file(path, full):
    """Point the solution at the renamed project.

    Renaming the .XCOM_sln file alone leaves it referencing
    "My XCOM2 Mod1\\My XCOM2 Mod1.x2proj" — a path that no longer exists, so
    ModBuddy can't open it. This rewrites the project name, its path and its
    GUID so the solution actually loads.
    """
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8-sig") as f:
        sln = f.read()

    project_guid = "{" + str(uuid.uuid4()).upper() + "}"
    old_guid = None
    m = re.search(r'Project\("\{[^}]+\}"\)\s*=\s*"([^"]+)",\s*"([^"]+)",\s*"(\{[^}]+\})"', sln)
    if m:
        old_guid = m.group(3)
        sln = sln.replace(m.group(1), full)
        sln = sln.replace(m.group(2), f"{full}\\{full}.x2proj")
    if old_guid:
        sln = sln.replace(old_guid, project_guid)

    with open(path, "w", encoding="utf-8") as f:
        f.write(sln)


def _write_readme(inner, full, music_dir):
    states = _state_dirs(music_dir)
    path = os.path.join(inner, "ReadMe.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{full} — an Anarchy Radio FM music addon\n")
        f.write("=" * 52 + "\n\n")
        f.write("1. Drop audio files into the music/STATE_* folders below.\n")
        f.write("   Supported: .mp3 .ogg .wav .flac .m4a .opus .wma\n\n")
        f.write(f"2. Edit {full}.json — set your name, author, description and\n")
        f.write("   genre tags. Those show up in the app's Music Addons panel,\n")
        f.write("   where players can sort and filter by them.\n\n")
        f.write("3. Publish from ModBuddy. Players who subscribe get your tracks\n")
        f.write("   merged into their library automatically — nothing is copied\n")
        f.write("   to their drive, it plays straight from the workshop folder.\n\n")
        f.write("Folder reference:\n")
        for s in states:
            nice = s.replace("STATE_", "").replace("_", " ").title()
            f.write(f"  music/{s}/  ->  {nice}\n")
        f.write("\nLeave folders empty for states you don't want to score.\n")
        f.write("Give your files distinctive names — if two packs ship the same\n")
        f.write("filename for the same state, only one of them survives.\n")

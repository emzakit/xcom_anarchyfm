// ============================================================
// XiPod_MCMListener — Mod Config Menu integration.
// Registers with MCM and builds the Anarchy Radio FM settings page
// with toggles, volumes, per-state FX presets, and sliders.
// ============================================================
class XiPod_MCMListener extends UIScreenListener;

// ================================================================
// MCM REGISTRATION
// ================================================================

event OnInit(UIScreen Screen)
{
    // Inline of `MCM_API_Register macro — avoids .uci include path issues
    if (MCM_API(Screen) != none)
    {
        MCM_API(Screen).RegisterClientMod(1, 0, ClientModCallback);
    }
}

// ================================================================
// PAGE SETUP
// ================================================================

simulated function ClientModCallback(MCM_API_Instance ConfigAPI, int GameMode)
{
    local MCM_API_SettingsPage Page;
    local MCM_API_SettingsGroup Grp;
    local array<string> PresetOptions;

    Page = ConfigAPI.NewSettingsPage("Anarchy Radio FM");
    Page.SetPageTitle("Anarchy Radio FM Music Engine");
    Page.SetSaveHandler(OnPageSaved);

    // Preset option names for spinner controls
    PresetOptions.AddItem("Custom");
    PresetOptions.AddItem("Clean");
    PresetOptions.AddItem("Field Radio");
    // User preset slots — always shown so players can assign states to them
    PresetOptions.AddItem("User Preset 1");
    PresetOptions.AddItem("User Preset 2");
    PresetOptions.AddItem("User Preset 3");

    // ---- Group: Playback Controls (click to control the desktop player) ----
    // Fire immediately on click (the log line reaches the desktop app right
    // away). Handy since there's no on-screen player tab.
    Grp = Page.AddGroup('GrpPlayback', "Playback Controls");
    Grp.AddButton('BtnPlay',  "Play",  "Resume or start playback in the Anarchy Radio FM desktop app.", "Play",  OnPlayClicked);
    Grp.AddButton('BtnPause', "Pause", "Pause playback in the Anarchy Radio FM desktop app.",           "Pause", OnPauseClicked);
    Grp.AddButton('BtnNext',  "Next",  "Skip to the next track.",                                        "Next",  OnNextClicked);
    Grp.AddButton('BtnBack',  "Back",  "Go back to the previous track.",                                 "Back",  OnBackClicked);

    // ---- Group: Music Overrides (enable/disable per state) ----
    Grp = Page.AddGroup('GrpEnable', "Music Overrides");
    Grp.AddCheckbox('ChkShell',   "Menu Music",         "Replace main menu music with Anarchy Radio FM tracks. Uncheck to let MMS play its music instead. Anarchy Radio FM stops immediately; MMS takes over on next game restart.",
        class'XiPod_Settings'.static.IsStateEnabled("SHELL_MENU"),    OnEnableSave);
    Grp.AddCheckbox('ChkAvenger', "Avenger Music",      "Replace Avenger base music with Anarchy Radio FM tracks. Uncheck to let MMS play. Anarchy Radio FM stops immediately; MMS takes over on next game restart.",
        class'XiPod_Settings'.static.IsStateEnabled("AVENGER"),       OnEnableSave);
    Grp.AddCheckbox('ChkBattle',  "Mission Music",      "Replace tactical mission music (explore + combat) with Anarchy Radio FM tracks. Uncheck to let MMS play. Anarchy Radio FM stops immediately; MMS takes over on next game restart.",
        class'XiPod_Settings'.static.IsStateEnabled("BATTLE"),        OnEnableSave);
    Grp.AddCheckbox('ChkSqd',     "Squad Select Music", "Replace squad select music with Anarchy Radio FM tracks. Uncheck to let MMS play. Anarchy Radio FM stops immediately; MMS takes over on next game restart.",
        class'XiPod_Settings'.static.IsStateEnabled("SQUADSELECT"),   OnEnableSave);
    Grp.AddCheckbox('ChkVictory', "Victory Music",      "Play a custom victory stinger. Uncheck to let MMS/default play. Anarchy Radio FM stops immediately; MMS takes over on next game restart.",
        class'XiPod_Settings'.static.IsStateEnabled("VICTORY"),       OnEnableSave);
    Grp.AddCheckbox('ChkDefeat',  "Defeat Music",       "Play a custom defeat stinger. Uncheck to let MMS/default play. Anarchy Radio FM stops immediately; MMS takes over on next game restart.",
        class'XiPod_Settings'.static.IsStateEnabled("DEFEAT"),        OnEnableSave);

    // ---- Group: Per-State Volume ----
    Grp = Page.AddGroup('GrpVolume', "Per-State Volume");
    Grp.AddSlider('VolShell',   "Menu Volume",         "How loud custom music plays on the main menu (0 = silent, 100 = full volume).",
        0, 100, 10, class'XiPod_Settings'.static.GetStateVolume("SHELL_MENU"),    OnVolumeSave);
    Grp.AddSlider('VolAvenger', "Avenger Volume",      "How loud custom music plays aboard the Avenger (0 = silent, 100 = full volume).",
        0, 100, 10, class'XiPod_Settings'.static.GetStateVolume("AVENGER"),       OnVolumeSave);
    Grp.AddSlider('VolBattle',  "Mission Volume",      "How loud custom music plays during tactical missions — covers both explore and combat (0 = silent, 100 = full volume).",
        0, 100, 10, class'XiPod_Settings'.static.GetStateVolume("BATTLE"),        OnVolumeSave);
    Grp.AddSlider('VolSqd',     "Squad Select Volume", "How loud custom music plays on the squad select screen (0 = silent, 100 = full volume).",
        0, 100, 10, class'XiPod_Settings'.static.GetStateVolume("SQUADSELECT"),   OnVolumeSave);
    Grp.AddSlider('VolVictory', "Victory Volume",      "Volume for the victory stinger (0 = silent, 100 = full volume).",
        0, 100, 10, class'XiPod_Settings'.static.GetStateVolume("VICTORY"),       OnVolumeSave);
    Grp.AddSlider('VolDefeat',  "Defeat Volume",       "Volume for the defeat stinger (0 = silent, 100 = full volume).",
        0, 100, 10, class'XiPod_Settings'.static.GetStateVolume("DEFEAT"),        OnVolumeSave);

    // ---- Group: FX Presets (per-state) ----
    Grp = Page.AddGroup('GrpPresets', "Audio FX Presets");
    Grp.AddSpinner('PreShell',   "Menu FX",         "Audio effect preset for main menu music. 'Custom' uses the radio/reverb checkboxes and sliders below.",
        PresetOptions, class'XiPod_Settings'.static.GetPresetName("SHELL_MENU"),    OnPresetSave);
    Grp.AddSpinner('PreAvenger', "Avenger FX",      "Audio effect preset for Avenger music.",
        PresetOptions, class'XiPod_Settings'.static.GetPresetName("AVENGER"),       OnPresetSave);
    Grp.AddSpinner('PreBattle',  "Mission FX",      "Audio effect preset for tactical mission music. 'Field Radio' simulates comms chatter.",
        PresetOptions, class'XiPod_Settings'.static.GetPresetName("BATTLE"),        OnPresetSave);
    Grp.AddSpinner('PreSqd',     "Squad Select FX", "Audio effect preset for squad select music.",
        PresetOptions, class'XiPod_Settings'.static.GetPresetName("SQUADSELECT"),   OnPresetSave);

    // ---- Group: User Presets — Save/Load custom FX settings ----
    Grp = Page.AddGroup('GrpUserPresets', "User Presets (Save/Load Custom FX)");
    Grp.AddCheckbox('SaveSlot1', "Save to User Preset 1", "Snapshot your current Custom FX slider values into User Preset 1. It will then appear in the FX Preset dropdown above.",
        false, OnSaveUserPreset);
    Grp.AddCheckbox('SaveSlot2', "Save to User Preset 2", "Snapshot your current Custom FX slider values into User Preset 2.",
        false, OnSaveUserPreset);
    Grp.AddCheckbox('SaveSlot3', "Save to User Preset 3", "Snapshot your current Custom FX slider values into User Preset 3.",
        false, OnSaveUserPreset);
    Grp.AddCheckbox('ClearSlot1', "Clear User Preset 1", "Remove User Preset 1 from the FX Preset dropdown.",
        false, OnClearUserPreset);
    Grp.AddCheckbox('ClearSlot2', "Clear User Preset 2", "Remove User Preset 2.",
        false, OnClearUserPreset);
    Grp.AddCheckbox('ClearSlot3', "Clear User Preset 3", "Remove User Preset 3.",
        false, OnClearUserPreset);

    // ---- Group: Resistance Radio — plays from state_resistance_radio folder ----
    Grp = Page.AddGroup('GrpRadio', "Resistance Radio (shared radio station)");
    Grp.AddCheckbox('RadShell',   "Menu",         "Switch to Resistance Radio for the main menu. Plays from the state_resistance_radio folder with random start positions. If the radio folder is empty, falls back to the state's own tracks but still uses a random starting position.",
        class'XiPod_Settings'.static.IsRadioEnabled("SHELL_MENU"),    OnRadioSave);
    Grp.AddCheckbox('RadAvenger', "Avenger",      "Switch to Resistance Radio while aboard the Avenger. Tunes into the shared radio station instead of the Avenger playlist. If the radio folder is empty, falls back to Avenger tracks with a random starting position.",
        class'XiPod_Settings'.static.IsRadioEnabled("AVENGER"),       OnRadioSave);
    Grp.AddCheckbox('RadBattle',  "Mission",      "Switch to Resistance Radio during tactical missions. If the radio folder is empty, falls back to mission tracks with a random starting position.",
        class'XiPod_Settings'.static.IsRadioEnabled("BATTLE"),        OnRadioSave);
    Grp.AddCheckbox('RadSqd',     "Squad Select", "Switch to Resistance Radio on the squad select screen. If the radio folder is empty, falls back to squad select tracks with a random starting position.",
        class'XiPod_Settings'.static.IsRadioEnabled("SQUADSELECT"),   OnRadioSave);

    Grp = Page.AddGroup('GrpReverb', "Custom FX: Reverb (only when preset = Custom)");
    Grp.AddCheckbox('RevShell',   "Menu",         "Add reverb to menu music for a spacious, atmospheric sound.",
        class'XiPod_Settings'.static.IsReverbEnabled("SHELL_MENU"),    OnReverbSave);
    Grp.AddCheckbox('RevAvenger', "Avenger",      "Add reverb to Avenger music — echoing through the ship's corridors.",
        class'XiPod_Settings'.static.IsReverbEnabled("AVENGER"),       OnReverbSave);
    Grp.AddCheckbox('RevBattle',  "Mission",      "Add reverb to mission music. Atmospheric battlefield ambience.",
        class'XiPod_Settings'.static.IsReverbEnabled("BATTLE"),        OnReverbSave);
    Grp.AddCheckbox('RevSqd',     "Squad Select", "Add reverb to squad select music.",
        class'XiPod_Settings'.static.IsReverbEnabled("SQUADSELECT"),   OnReverbSave);

    // ---- Group: Loop Tracks ----
    Grp = Page.AddGroup('GrpLoop', "Loop Tracks");
    Grp.AddCheckbox('LoopShell',   "Menu",           "ON: Repeat the current track until you leave the menu. OFF: Shuffle through all menu tracks.",
        class'XiPod_Settings'.static.IsLoopEnabled("SHELL_MENU"),    OnLoopSave);
    Grp.AddCheckbox('LoopAvenger', "Avenger",        "ON: Repeat the current track while aboard the Avenger. OFF: Shuffle through all Avenger tracks automatically.",
        class'XiPod_Settings'.static.IsLoopEnabled("AVENGER"),       OnLoopSave);
    Grp.AddCheckbox('LoopBattle',  "Mission",        "ON: Repeat the current track during the mission. OFF: Shuffle through mission tracks.",
        class'XiPod_Settings'.static.IsLoopEnabled("BATTLE"),        OnLoopSave);
    Grp.AddCheckbox('LoopExplore', "Mission Explore", "ON: Repeat the explore track during concealment. OFF: Shuffle explore tracks.",
        class'XiPod_Settings'.static.IsLoopEnabled("EXPLORE"),       OnLoopSave);
    Grp.AddCheckbox('LoopCombat',  "Mission Combat",  "ON: Repeat the combat track during firefights. OFF: Shuffle combat tracks.",
        class'XiPod_Settings'.static.IsLoopEnabled("COMBAT"),        OnLoopSave);
    Grp.AddCheckbox('LoopSqd',     "Squad Select",   "ON: Repeat the current track on squad select. OFF: Shuffle through squad select tracks.",
        class'XiPod_Settings'.static.IsLoopEnabled("SQUADSELECT"),   OnLoopSave);

    // ---- Group: Random Start — "Radio Tuning" mode ----
    Grp = Page.AddGroup('GrpRandomStart', "Random Start (Radio Tuning)");
    Grp.AddCheckbox('RndShell',   "Menu",           "Start menu tracks from a random position — like tuning into a station that's always playing.",
        class'XiPod_Settings'.static.IsRandomStartEnabled("SHELL_MENU"),    OnRandomStartSave);
    Grp.AddCheckbox('RndAvenger', "Avenger",        "Start Avenger tracks mid-way. Perfect for a GTA radio station vibe on the ship.",
        class'XiPod_Settings'.static.IsRandomStartEnabled("AVENGER"),       OnRandomStartSave);
    Grp.AddCheckbox('RndBattle',  "Mission",        "Start mission tracks from a random position.",
        class'XiPod_Settings'.static.IsRandomStartEnabled("BATTLE"),        OnRandomStartSave);
    Grp.AddCheckbox('RndExplore', "Mission Explore", "Start explore tracks from a random position.",
        class'XiPod_Settings'.static.IsRandomStartEnabled("EXPLORE"),       OnRandomStartSave);
    Grp.AddCheckbox('RndCombat',  "Mission Combat",  "Start combat tracks from a random position.",
        class'XiPod_Settings'.static.IsRandomStartEnabled("COMBAT"),        OnRandomStartSave);
    Grp.AddCheckbox('RndSqd',     "Squad Select",   "Start squad select tracks from a random position.",
        class'XiPod_Settings'.static.IsRandomStartEnabled("SQUADSELECT"),   OnRandomStartSave);

    // ---- Group: Custom FX Parameters (global sliders, used when preset = Custom) ----
    Grp = Page.AddGroup('GrpFxParams', "Custom FX Parameters (when preset = Custom)");
    Grp.AddSlider('FxHighpass',    "Radio Highpass (Hz)",     "Cuts bass frequencies below this value. Higher = thinner, more tinny. Default: 450 Hz.",
        100, 800, 50, class'XiPod_Settings'.static.GetFxParam("RADIOHIGHPASS"),   OnFxParamSave);
    Grp.AddSlider('FxLowpass',     "Radio Lowpass (Hz)",      "Cuts treble above this value. Lower = more muffled, old-radio. Default: 3000 Hz.",
        1500, 8000, 500, class'XiPod_Settings'.static.GetFxParam("RADIOLOWPASS"), OnFxParamSave);
    Grp.AddSlider('FxRoomSize',    "Reverb Room Size (%)",    "Virtual room size. 0% = closet, 100% = cathedral. Default: 80%.",
        0, 100, 10, class'XiPod_Settings'.static.GetFxParam("REVERBROOMSIZE"),    OnFxParamSave);
    Grp.AddSlider('FxWet',         "Reverb Wet Level (%)",    "Reverb mix. 0% = dry, 100% = drenched in echo. Default: 20%.",
        0, 100, 10, class'XiPod_Settings'.static.GetFxParam("REVERBWET"),         OnFxParamSave);
    Grp.AddSlider('FxBassBoost',   "Bass Boost (dB)",         "Low-end shelf boost at 200Hz. 0 = off, 12 = maximum thump. Great for combat music.",
        0, 12, 1, class'XiPod_Settings'.static.GetFxParam("BASSBOOST"),           OnFxParamSave);
    Grp.AddSlider('FxChorusDepth', "Chorus Depth (%)",        "How much the chorus effect widens the sound. 0 = off, 100 = full shimmer.",
        0, 100, 5, class'XiPod_Settings'.static.GetFxParam("CHORUSDEPTH"),        OnFxParamSave);
    Grp.AddSlider('FxChorusRate',  "Chorus Rate",             "Speed of the chorus sweep. 10 = slow drift, 50 = fast shimmer. Default: 10.",
        10, 50, 5, class'XiPod_Settings'.static.GetFxParam("CHORUSRATE"),         OnFxParamSave);
    Grp.AddSlider('FxBitcrush',    "Bitcrush (bits)",         "Reduces audio resolution. 16 = clean (off), 8 = retro lo-fi, 4 = extreme crunch.",
        4, 16, 1, class'XiPod_Settings'.static.GetFxParam("BITCRUSH"),            OnFxParamSave);
    Grp.AddSlider('FxEchoDelay',   "Echo Delay (ms)",         "Time between echo repeats. 0 = off. 100-300ms for subtle depth, 400-500ms for big spacey echoes.",
        0, 500, 25, class'XiPod_Settings'.static.GetFxParam("ECHODELAY"),         OnFxParamSave);
    Grp.AddSlider('FxEchoMix',     "Echo Mix (%)",            "How loud the echo repeats are. 0% = no echo, 100% = equal to original signal. Default: 10%.",
        0, 100, 5, class'XiPod_Settings'.static.GetFxParam("ECHOMIX"),            OnFxParamSave);

    Page.ShowSettings();
}

// ================================================================
// PLAYBACK BUTTON HANDLERS — fire immediately on click
// ================================================================

simulated function OnPlayClicked(MCM_API_Setting Setting)
{
    `log("XIPOD: PLAY");
}

simulated function OnPauseClicked(MCM_API_Setting Setting)
{
    `log("XIPOD: PAUSE");
}

simulated function OnNextClicked(MCM_API_Setting Setting)
{
    `log("XIPOD: NEXT");
}

simulated function OnBackClicked(MCM_API_Setting Setting)
{
    `log("XIPOD: PREV");
}

// ================================================================
// SAVE HANDLERS — called when user clicks "Save and Exit"
// ================================================================

simulated function OnEnableSave(MCM_API_Setting Setting, bool Value)
{
    local string StateName, LogValue;

    StateName = EnableNameFromSetting(Setting.GetName());
    if (StateName == "") return;

    class'XiPod_Settings'.static.SetToggle(StateName, Value);

    LogValue = "ON";
    if (!Value) LogValue = "OFF";
    `log("XIPOD: TOGGLE" @ StateName @ LogValue);
}

simulated function OnVolumeSave(MCM_API_Setting Setting, float Value)
{
    local string StateName;
    local int IntVal;

    StateName = VolumeNameFromSetting(Setting.GetName());
    if (StateName == "") return;

    IntVal = int(Value);
    class'XiPod_Settings'.static.SetStateVolume(StateName, IntVal);
    `log("XIPOD: STATEVOL" @ StateName @ IntVal);
}

simulated function OnSaveUserPreset(MCM_API_Setting Setting, bool Value)
{
    local name N;
    local int Slot;

    if (!Value) return;  // Only act on check, not uncheck

    N = Setting.GetName();
    if (N == 'SaveSlot1')      Slot = 1;
    else if (N == 'SaveSlot2') Slot = 2;
    else if (N == 'SaveSlot3') Slot = 3;
    else return;

    `log("XIPOD: SAVEPRESET" @ string(Slot));
}

simulated function OnClearUserPreset(MCM_API_Setting Setting, bool Value)
{
    local name N;
    local int Slot;

    if (!Value) return;

    N = Setting.GetName();
    if (N == 'ClearSlot1')      Slot = 1;
    else if (N == 'ClearSlot2') Slot = 2;
    else if (N == 'ClearSlot3') Slot = 3;
    else return;

    `log("XIPOD: CLEARPRESET" @ string(Slot));
}

simulated function OnPresetSave(MCM_API_Setting Setting, string Value)
{
    local string StateName, PresetKey;
    local int PresetIdx;

    StateName = PresetNameFromSetting(Setting.GetName());
    if (StateName == "") return;

    PresetIdx = PresetIndexFromName(Value);
    PresetKey = PresetKeyFromIndex(PresetIdx);

    class'XiPod_Settings'.static.SetPreset(StateName, PresetIdx);
    `log("XIPOD: PRESET" @ StateName @ PresetKey);
}

simulated function OnRadioSave(MCM_API_Setting Setting, bool Value)
{
    local string StateName, LogValue;

    StateName = RadioNameFromSetting(Setting.GetName());
    if (StateName == "") return;

    class'XiPod_Settings'.static.SetRadio(StateName, Value);

    LogValue = "ON";
    if (!Value) LogValue = "OFF";
    `log("XIPOD: STATERADIO" @ StateName @ LogValue);
}

simulated function OnReverbSave(MCM_API_Setting Setting, bool Value)
{
    local string StateName, LogValue;

    StateName = ReverbNameFromSetting(Setting.GetName());
    if (StateName == "") return;

    class'XiPod_Settings'.static.SetReverb(StateName, Value);

    LogValue = "ON";
    if (!Value) LogValue = "OFF";
    `log("XIPOD: STATEREVERB" @ StateName @ LogValue);
}

simulated function OnLoopSave(MCM_API_Setting Setting, bool Value)
{
    local string StateName, LogValue;

    StateName = LoopNameFromSetting(Setting.GetName());
    if (StateName == "") return;

    class'XiPod_Settings'.static.SetLoop(StateName, Value);

    LogValue = "ON";
    if (!Value) LogValue = "OFF";
    `log("XIPOD: STATELOOP" @ StateName @ LogValue);
}

simulated function OnRandomStartSave(MCM_API_Setting Setting, bool Value)
{
    local string StateName, LogValue;

    StateName = RandomStartNameFromSetting(Setting.GetName());
    if (StateName == "") return;

    class'XiPod_Settings'.static.SetRandomStart(StateName, Value);

    LogValue = "ON";
    if (!Value) LogValue = "OFF";
    `log("XIPOD: STATERANDOMSTART" @ StateName @ LogValue);
}

simulated function OnFxParamSave(MCM_API_Setting Setting, float Value)
{
    local string ParamName;
    local int IntVal;

    ParamName = FxParamNameFromSetting(Setting.GetName());
    if (ParamName == "") return;

    IntVal = int(Value);
    class'XiPod_Settings'.static.SetFxParam(ParamName, IntVal);
    `log("XIPOD: FXPARAM" @ ParamName @ IntVal);
}

// Page-level save handler (fires after all individual saves).
simulated function OnPageSaved(MCM_API_SettingsPage Page)
{
    `log("XIPOD: MCM settings saved. Toggle changes take effect on next state transition.");
}

// ================================================================
// NAME MAPPING — Setting name -> State/Param name
// ================================================================

simulated function string EnableNameFromSetting(name N)
{
    if (N == 'ChkShell')   return "SHELL_MENU";
    if (N == 'ChkAvenger') return "AVENGER";
    if (N == 'ChkGeo')     return "GEOSCAPE";
    if (N == 'ChkBattle')  return "BATTLE";
    if (N == 'ChkSqd')     return "SQUADSELECT";
    if (N == 'ChkVictory') return "VICTORY";
    if (N == 'ChkDefeat')  return "DEFEAT";
    return "";
}

simulated function string VolumeNameFromSetting(name N)
{
    if (N == 'VolShell')   return "SHELL_MENU";
    if (N == 'VolAvenger') return "AVENGER";
    if (N == 'VolGeo')     return "GEOSCAPE";
    if (N == 'VolBattle')  return "BATTLE";
    if (N == 'VolSqd')     return "SQUADSELECT";
    if (N == 'VolVictory') return "VICTORY";
    if (N == 'VolDefeat')  return "DEFEAT";
    return "";
}

simulated function string PresetNameFromSetting(name N)
{
    if (N == 'PreShell')   return "SHELL_MENU";
    if (N == 'PreAvenger') return "AVENGER";
    if (N == 'PreGeo')     return "GEOSCAPE";
    if (N == 'PreBattle')  return "BATTLE";
    if (N == 'PreSqd')     return "SQUADSELECT";
    return "";
}

simulated function string RadioNameFromSetting(name N)
{
    if (N == 'RadShell')   return "SHELL_MENU";
    if (N == 'RadAvenger') return "AVENGER";
    if (N == 'RadGeo')     return "GEOSCAPE";
    if (N == 'RadBattle')  return "BATTLE";
    if (N == 'RadSqd')     return "SQUADSELECT";
    return "";
}

simulated function string ReverbNameFromSetting(name N)
{
    if (N == 'RevShell')   return "SHELL_MENU";
    if (N == 'RevAvenger') return "AVENGER";
    if (N == 'RevGeo')     return "GEOSCAPE";
    if (N == 'RevBattle')  return "BATTLE";
    if (N == 'RevSqd')     return "SQUADSELECT";
    return "";
}

simulated function string LoopNameFromSetting(name N)
{
    if (N == 'LoopShell')   return "SHELL_MENU";
    if (N == 'LoopAvenger') return "AVENGER";
    if (N == 'LoopGeo')     return "GEOSCAPE";
    if (N == 'LoopBattle')  return "BATTLE";
    if (N == 'LoopExplore') return "EXPLORE";
    if (N == 'LoopCombat')  return "COMBAT";
    if (N == 'LoopSqd')     return "SQUADSELECT";
    return "";
}

simulated function string RandomStartNameFromSetting(name N)
{
    if (N == 'RndShell')   return "SHELL_MENU";
    if (N == 'RndAvenger') return "AVENGER";
    if (N == 'RndGeo')     return "GEOSCAPE";
    if (N == 'RndBattle')  return "BATTLE";
    if (N == 'RndExplore') return "EXPLORE";
    if (N == 'RndCombat')  return "COMBAT";
    if (N == 'RndSqd')     return "SQUADSELECT";
    return "";
}

simulated function string FxParamNameFromSetting(name N)
{
    if (N == 'FxHighpass')    return "RADIOHIGHPASS";
    if (N == 'FxLowpass')     return "RADIOLOWPASS";
    if (N == 'FxRoomSize')    return "REVERBROOMSIZE";
    if (N == 'FxWet')         return "REVERBWET";
    if (N == 'FxBassBoost')   return "BASSBOOST";
    if (N == 'FxChorusDepth') return "CHORUSDEPTH";
    if (N == 'FxChorusRate')  return "CHORUSRATE";
    if (N == 'FxBitcrush')    return "BITCRUSH";
    if (N == 'FxEchoDelay')   return "ECHODELAY";
    if (N == 'FxEchoMix')     return "ECHOMIX";
    return "";
}

// ================================================================
// PRESET HELPERS
// ================================================================

// Convert display name to index (matches PRESET_KEYS in Python)
simulated function int PresetIndexFromName(string DisplayName)
{
    if (DisplayName == "Custom")           return 0;
    if (DisplayName == "Clean")            return 1;
    if (DisplayName == "Field Radio")      return 2;
    if (DisplayName == "User Preset 1")    return 3;
    if (DisplayName == "User Preset 2")    return 4;
    if (DisplayName == "User Preset 3")    return 5;
    return 0;
}

// Convert index to internal key (for log command)
simulated function string PresetKeyFromIndex(int Idx)
{
    if (Idx == 0) return "CUSTOM";
    if (Idx == 1) return "CLEAN";
    if (Idx == 2) return "FIELD_RADIO";
    if (Idx == 3) return "USER_1";
    if (Idx == 4) return "USER_2";
    if (Idx == 5) return "USER_3";
    return "CUSTOM";
}

defaultproperties
{
    ScreenClass = none
}

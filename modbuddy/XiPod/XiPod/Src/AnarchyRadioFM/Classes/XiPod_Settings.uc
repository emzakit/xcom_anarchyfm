// ============================================================
// XiPod_Settings — Single source of truth for persistent config.
// Stored in XComXiPod.ini under [AnarchyRadioFM.XiPod_Settings]
// ============================================================
class XiPod_Settings extends Object config(XiPod);

var config int  SavedVolume;
var config bool bEnableShellMenu;
var config bool bEnableAvenger;
var config bool bEnableGeoscape;
var config bool bEnableBattle;
var config bool bEnableSquadSelect;
var config bool bEnableVictory;
var config bool bEnableDefeat;

// Per-state volumes (0-100)
var config int VolumeShellMenu;
var config int VolumeAvenger;
var config int VolumeGeoscape;
var config int VolumeBattle;
var config int VolumeSquadSelect;
var config int VolumeVictory;
var config int VolumeDefeat;

// Per-state audio effects
var config bool bRadioShellMenu;
var config bool bRadioAvenger;
var config bool bRadioGeoscape;
var config bool bRadioBattle;
var config bool bRadioSquadSelect;

var config bool bReverbShellMenu;
var config bool bReverbAvenger;
var config bool bReverbGeoscape;
var config bool bReverbBattle;
var config bool bReverbSquadSelect;

// Per-state loop toggle (ON = repeat single track, OFF = shuffle through playlist)
var config bool bLoopShellMenu;
var config bool bLoopAvenger;
var config bool bLoopGeoscape;
var config bool bLoopBattle;
var config bool bLoopSquadSelect;
var config bool bLoopExplore;
var config bool bLoopCombat;

// Per-state random start — "radio tuning" mode.
// When ON, tracks start from a random position as if the station was always playing.
var config bool bRandomStartShellMenu;
var config bool bRandomStartAvenger;
var config bool bRandomStartGeoscape;
var config bool bRandomStartBattle;
var config bool bRandomStartSquadSelect;
var config bool bRandomStartExplore;
var config bool bRandomStartCombat;

// Per-state FX preset index (indexes into preset name array)
// 0=Custom, 1=Clean, 2=Field Radio, 3-5=User Presets
var config int PresetShellMenu;
var config int PresetAvenger;
var config int PresetGeoscape;
var config int PresetBattle;
var config int PresetSquadSelect;

// Global FX parameters (used when a state's preset is "Custom")
var config int RadioHighpass;    // Hz, default 500
var config int RadioLowpass;     // Hz, default 4500
var config int ReverbRoomSize;   // 0-100, maps to 0.0-1.0, default 90
var config int ReverbWet;        // 0-100, maps to 0.0-1.0, default 30
var config int BassBoost;        // 0-12 dB, default 0
var config int ChorusDepth;      // 0-100%, default 0
var config int ChorusRate;       // 10-50 (maps to 1.0-5.0 Hz), default 15
var config int Bitcrush;     // 4-16 bits (16 = clean/off), default 16
var config int EchoDelay;        // 0-500 ms, default 0
var config int EchoMix;          // 0-100%, default 25

// User preset slots — opaque pipe-delimited FX strings written by the
// Anarchy Radio FM desktop app (e.g. "bassboost:3|radio:True"). Declared as config
// vars ONLY so SaveConfig() preserves them when rewriting XComXiPod.ini;
// UnrealScript never parses them.
var config string UserPreset1;
var config string UserPreset2;
var config string UserPreset3;

// Tracks which game screen is currently active (runtime state).
var config string CurrentScreenType;

// --- Read helpers ---

static function bool IsStateEnabled(string StateName)
{
    if (StateName == "SHELL_MENU")   return default.bEnableShellMenu;
    if (StateName == "AVENGER")      return default.bEnableAvenger;
    if (StateName == "GEOSCAPE")     return default.bEnableGeoscape;
    if (StateName == "BATTLE")       return default.bEnableBattle;
    if (StateName == "SQUADSELECT")  return default.bEnableSquadSelect;
    if (StateName == "VICTORY")      return default.bEnableVictory;
    if (StateName == "DEFEAT")       return default.bEnableDefeat;
    return true;
}

static function int GetVolume()
{
    return default.SavedVolume;
}

static function int GetStateVolume(string StateName)
{
    if (StateName == "SHELL_MENU")   return default.VolumeShellMenu;
    if (StateName == "AVENGER")      return default.VolumeAvenger;
    if (StateName == "GEOSCAPE")     return default.VolumeGeoscape;
    if (StateName == "BATTLE")       return default.VolumeBattle;
    if (StateName == "SQUADSELECT")  return default.VolumeSquadSelect;
    if (StateName == "VICTORY")      return default.VolumeVictory;
    if (StateName == "DEFEAT")       return default.VolumeDefeat;
    return 50;
}

static function bool IsRadioEnabled(string StateName)
{
    if (StateName == "SHELL_MENU")   return default.bRadioShellMenu;
    if (StateName == "AVENGER")      return default.bRadioAvenger;
    if (StateName == "GEOSCAPE")     return default.bRadioGeoscape;
    if (StateName == "BATTLE")       return default.bRadioBattle;
    if (StateName == "SQUADSELECT")  return default.bRadioSquadSelect;
    return false;
}

static function bool IsReverbEnabled(string StateName)
{
    if (StateName == "SHELL_MENU")   return default.bReverbShellMenu;
    if (StateName == "AVENGER")      return default.bReverbAvenger;
    if (StateName == "GEOSCAPE")     return default.bReverbGeoscape;
    if (StateName == "BATTLE")       return default.bReverbBattle;
    if (StateName == "SQUADSELECT")  return default.bReverbSquadSelect;
    return false;
}

static function bool IsLoopEnabled(string StateName)
{
    if (StateName == "SHELL_MENU")   return default.bLoopShellMenu;
    if (StateName == "AVENGER")      return default.bLoopAvenger;
    if (StateName == "GEOSCAPE")     return default.bLoopGeoscape;
    if (StateName == "BATTLE")       return default.bLoopBattle;
    if (StateName == "SQUADSELECT")  return default.bLoopSquadSelect;
    if (StateName == "EXPLORE")      return default.bLoopExplore;
    if (StateName == "COMBAT")       return default.bLoopCombat;
    return true;
}

static function bool IsRandomStartEnabled(string StateName)
{
    if (StateName == "SHELL_MENU")   return default.bRandomStartShellMenu;
    if (StateName == "AVENGER")      return default.bRandomStartAvenger;
    if (StateName == "GEOSCAPE")     return default.bRandomStartGeoscape;
    if (StateName == "BATTLE")       return default.bRandomStartBattle;
    if (StateName == "SQUADSELECT")  return default.bRandomStartSquadSelect;
    if (StateName == "EXPLORE")      return default.bRandomStartExplore;
    if (StateName == "COMBAT")       return default.bRandomStartCombat;
    return false;
}

static function string GetPresetName(string StateName)
{
    local int Idx;

    if (StateName == "SHELL_MENU")        Idx = default.PresetShellMenu;
    else if (StateName == "AVENGER")      Idx = default.PresetAvenger;
    else if (StateName == "GEOSCAPE")     Idx = default.PresetGeoscape;
    else if (StateName == "BATTLE")       Idx = default.PresetBattle;
    else if (StateName == "SQUADSELECT")  Idx = default.PresetSquadSelect;
    else return "Custom";

    if (Idx == 0) return "Custom";
    if (Idx == 1) return "Clean";
    if (Idx == 2) return "Field Radio";
    if (Idx == 3) return "User Preset 1";
    if (Idx == 4) return "User Preset 2";
    if (Idx == 5) return "User Preset 3";
    return "Custom";
}

static function int GetFxParam(string ParamName)
{
    if (ParamName == "RADIOHIGHPASS")  return default.RadioHighpass;
    if (ParamName == "RADIOLOWPASS")   return default.RadioLowpass;
    if (ParamName == "REVERBROOMSIZE") return default.ReverbRoomSize;
    if (ParamName == "REVERBWET")      return default.ReverbWet;
    if (ParamName == "BASSBOOST")      return default.BassBoost;
    if (ParamName == "CHORUSDEPTH")    return default.ChorusDepth;
    if (ParamName == "CHORUSRATE")     return default.ChorusRate;
    if (ParamName == "BITCRUSH")       return default.Bitcrush;
    if (ParamName == "ECHODELAY")      return default.EchoDelay;
    if (ParamName == "ECHOMIX")        return default.EchoMix;
    return 0;
}

// --- Write helpers ---

static function SetToggle(string StateName, bool bValue)
{
    local XiPod_Settings S;

    if (StateName == "SHELL_MENU")        default.bEnableShellMenu = bValue;
    else if (StateName == "AVENGER")      default.bEnableAvenger = bValue;
    else if (StateName == "GEOSCAPE")     default.bEnableGeoscape = bValue;
    else if (StateName == "BATTLE")       default.bEnableBattle = bValue;
    else if (StateName == "SQUADSELECT")  default.bEnableSquadSelect = bValue;
    else if (StateName == "VICTORY")      default.bEnableVictory = bValue;
    else if (StateName == "DEFEAT")       default.bEnableDefeat = bValue;

    S = new class'XiPod_Settings';
    S.SaveConfig();
}

static function SetVolume(int NewVolume)
{
    local XiPod_Settings S;
    default.SavedVolume = NewVolume;
    S = new class'XiPod_Settings';
    S.SaveConfig();
}

static function SetStateVolume(string StateName, int Volume)
{
    local XiPod_Settings S;

    if (StateName == "SHELL_MENU")        default.VolumeShellMenu = Volume;
    else if (StateName == "AVENGER")      default.VolumeAvenger = Volume;
    else if (StateName == "GEOSCAPE")     default.VolumeGeoscape = Volume;
    else if (StateName == "BATTLE")       default.VolumeBattle = Volume;
    else if (StateName == "SQUADSELECT")  default.VolumeSquadSelect = Volume;
    else if (StateName == "VICTORY")      default.VolumeVictory = Volume;
    else if (StateName == "DEFEAT")       default.VolumeDefeat = Volume;

    S = new class'XiPod_Settings';
    S.SaveConfig();
}

static function SetRadio(string StateName, bool bValue)
{
    local XiPod_Settings S;

    if (StateName == "SHELL_MENU")        default.bRadioShellMenu = bValue;
    else if (StateName == "AVENGER")      default.bRadioAvenger = bValue;
    else if (StateName == "GEOSCAPE")     default.bRadioGeoscape = bValue;
    else if (StateName == "BATTLE")       default.bRadioBattle = bValue;
    else if (StateName == "SQUADSELECT")  default.bRadioSquadSelect = bValue;

    S = new class'XiPod_Settings';
    S.SaveConfig();
}

static function SetReverb(string StateName, bool bValue)
{
    local XiPod_Settings S;

    if (StateName == "SHELL_MENU")        default.bReverbShellMenu = bValue;
    else if (StateName == "AVENGER")      default.bReverbAvenger = bValue;
    else if (StateName == "GEOSCAPE")     default.bReverbGeoscape = bValue;
    else if (StateName == "BATTLE")       default.bReverbBattle = bValue;
    else if (StateName == "SQUADSELECT")  default.bReverbSquadSelect = bValue;

    S = new class'XiPod_Settings';
    S.SaveConfig();
}

static function SetLoop(string StateName, bool bValue)
{
    local XiPod_Settings S;

    if (StateName == "SHELL_MENU")        default.bLoopShellMenu = bValue;
    else if (StateName == "AVENGER")      default.bLoopAvenger = bValue;
    else if (StateName == "GEOSCAPE")     default.bLoopGeoscape = bValue;
    else if (StateName == "BATTLE")       default.bLoopBattle = bValue;
    else if (StateName == "SQUADSELECT")  default.bLoopSquadSelect = bValue;
    else if (StateName == "EXPLORE")      default.bLoopExplore = bValue;
    else if (StateName == "COMBAT")       default.bLoopCombat = bValue;

    S = new class'XiPod_Settings';
    S.SaveConfig();
}

static function SetRandomStart(string StateName, bool bValue)
{
    local XiPod_Settings S;

    if (StateName == "SHELL_MENU")        default.bRandomStartShellMenu = bValue;
    else if (StateName == "AVENGER")      default.bRandomStartAvenger = bValue;
    else if (StateName == "GEOSCAPE")     default.bRandomStartGeoscape = bValue;
    else if (StateName == "BATTLE")       default.bRandomStartBattle = bValue;
    else if (StateName == "SQUADSELECT")  default.bRandomStartSquadSelect = bValue;
    else if (StateName == "EXPLORE")      default.bRandomStartExplore = bValue;
    else if (StateName == "COMBAT")       default.bRandomStartCombat = bValue;

    S = new class'XiPod_Settings';
    S.SaveConfig();
}

static function SetPreset(string StateName, int PresetIndex)
{
    local XiPod_Settings S;

    if (StateName == "SHELL_MENU")        default.PresetShellMenu = PresetIndex;
    else if (StateName == "AVENGER")      default.PresetAvenger = PresetIndex;
    else if (StateName == "GEOSCAPE")     default.PresetGeoscape = PresetIndex;
    else if (StateName == "BATTLE")       default.PresetBattle = PresetIndex;
    else if (StateName == "SQUADSELECT")  default.PresetSquadSelect = PresetIndex;

    S = new class'XiPod_Settings';
    S.SaveConfig();
}

static function SetFxParam(string ParamName, int Value)
{
    local XiPod_Settings S;

    if (ParamName == "RADIOHIGHPASS")       default.RadioHighpass = Value;
    else if (ParamName == "RADIOLOWPASS")   default.RadioLowpass = Value;
    else if (ParamName == "REVERBROOMSIZE") default.ReverbRoomSize = Value;
    else if (ParamName == "REVERBWET")      default.ReverbWet = Value;
    else if (ParamName == "BASSBOOST")      default.BassBoost = Value;
    else if (ParamName == "CHORUSDEPTH")    default.ChorusDepth = Value;
    else if (ParamName == "CHORUSRATE")     default.ChorusRate = Value;
    else if (ParamName == "BITCRUSH")       default.Bitcrush = Value;
    else if (ParamName == "ECHODELAY")      default.EchoDelay = Value;
    else if (ParamName == "ECHOMIX")        default.EchoMix = Value;

    S = new class'XiPod_Settings';
    S.SaveConfig();
}

// --- Current screen tracking ---

static function SetCurrentScreen(string ScreenType)
{
    default.CurrentScreenType = ScreenType;
}

static function string GetCurrentScreen()
{
    return default.CurrentScreenType;
}

defaultproperties
{
}

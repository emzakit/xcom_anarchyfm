// ============================================================
// XiPod_UI — In-game music player with track browser.
//
// Layout:
//   Main panel (centered):
//     Left col:  "Playlists" header + state filter buttons
//     Right col: Scrollable track list (click to play)
//
//   Right side tab: "Controls" header + Back/Pause/Play/Next/
//                    Refresh Library/Close stacked vertically
//
// All settings live in MCM (Options > Mod Settings > Anarchy Radio FM).
// ============================================================
class XiPod_UI extends UIScreen config(XiPod);

// Track manifest populated by Python into XComXiPod.ini
var config array<string> TrackList;

// Main panel
var UIPanel   MainPanel;
var UIBGBox   MainBG;

// Controls side tab
var UIPanel   ControlsPanel;
var UIBGBox   ControlsBG;

// State filter buttons
var array<UIButton> StateButtons;
var string          ActiveStateFilter;

// Track list
var UIList    TrackListUI;

// Filtered track data
var array<string> FilteredTrackIDs;
var array<string> FilteredTrackNames;

// Now-playing toast
var UIText ToastText;

// Layout constants
const MAIN_W = 850;
const MAIN_H = 620;

const SIDEBAR_W    = 280;
const TRACK_LIST_X = 290;

const CTRL_W = 180;
const CTRL_GAP = 15;

const BTN_H   = 30;
const BTN_GAP = 4;

// ================================================================
// INIT
// ================================================================

simulated function OnInit()
{
    local int MainX, MainY, CtrlX;

    super.OnInit();
    `log("XIPOD_DEBUG: XiPod_UI.OnInit");

    // Center the combined layout (main + gap + controls)
    MainX = (1920 - MAIN_W - CTRL_GAP - CTRL_W) / 2;
    MainY = (1080 - MAIN_H) / 2;
    CtrlX = MainX + MAIN_W + CTRL_GAP;

    // ---- Main panel with XCOM border ----
    MainPanel = Spawn(class'UIPanel', self).InitPanel('XiPodMain');
    MainPanel.SetPosition(MainX, MainY);
    MainPanel.SetSize(MAIN_W, MAIN_H);

    MainBG = Spawn(class'UIBGBox', MainPanel).InitBG('MainBG', 0, 0, MAIN_W, MAIN_H);

    // ---- XCOM-style title header ----
    Spawn(class'UIX2PanelHeader', MainPanel).InitPanelHeader('XiPodHeader', "ANARCHY RADIO FM", "Music Player");

    // ---- "Playlists" header ----
    BuildPlaylistsSide();

    // ---- Vertical divider ----
    Spawn(class'UIBGBox', MainPanel).InitBG('VDiv', SIDEBAR_W, 50, 2, MAIN_H - 60);

    // ---- Track list ----
    TrackListUI = Spawn(class'UIList', MainPanel);
    TrackListUI.InitList('TrackList', TRACK_LIST_X, 55, MAIN_W - TRACK_LIST_X - 15, MAIN_H - 70);
    TrackListUI.OnItemClicked = OnTrackClicked;

    // ---- Controls side tab ----
    BuildControlsTab(CtrlX, MainY);

    // ---- Load tracks ----
    ActiveStateFilter = GetCurrentStateFilter();
    PopulateFilteredTracks(ActiveStateFilter);
}

// ================================================================
// LEFT SIDE: PLAYLISTS
// ================================================================

simulated function BuildPlaylistsSide()
{
    local int BtnY;
    local UIText Header;
    local string CurrentScreen;

    // Header
    Header = Spawn(class'UIText', MainPanel).InitText('PlaylistsHeader');
    Header.SetPosition(10, 50);
    Header.SetSize(SIDEBAR_W - 20, 30);
    Header.SetHTMLText("<p align='center'><font size='16' color='#a8e8d8'><b>Playlists</b></font></p>");

    BtnY = 78;
    CurrentScreen = class'XiPod_Settings'.static.GetCurrentScreen();

    // Show only playlists relevant to the current game state.
    // Prevents cross-state confusion (e.g. playing menu music on Avenger).
    if (CurrentScreen == "SHELL_MENU")
    {
        BtnY = AddPlaylistBtn(BtnY, "Main Menu",        "SHELL_MENU",      "state_shell_menu|",      "Shuffle playlist for the Main Menu");
        BtnY = AddPlaylistBtn(BtnY, "Main Menu [Loop]", "SHELL_MENU_LOOP", "state_shell_menu_loop",  "Looping tracks for the Main Menu");
    }
    else if (CurrentScreen == "AVENGER")
    {
        BtnY = AddPlaylistBtn(BtnY, "Avenger",        "AVENGER",      "state_avenger|",      "Shuffle playlist for the Avenger base");
        BtnY = AddPlaylistBtn(BtnY, "Avenger [Loop]", "AVENGER_LOOP", "state_avenger_loop",  "Looping tracks for the Avenger");
    }
    else if (CurrentScreen == "SQUADSELECT")
    {
        BtnY = AddPlaylistBtn(BtnY, "Squad Select",        "SQUADSELECT",      "state_squadselect|",      "Shuffle playlist for Squad Select");
        BtnY = AddPlaylistBtn(BtnY, "Squad Select [Loop]", "SQUADSELECT_LOOP", "state_squadselect_loop",  "Looping tracks for Squad Select");
    }
    else if (CurrentScreen == "TACTICAL")
    {
        BtnY = AddPlaylistBtn(BtnY, "Mission Explore",        "MISSION_EXPLORE",      "state_mission_explore|",      "Shuffle playlist for stealth/concealment");
        BtnY = AddPlaylistBtn(BtnY, "Mission Explore [Loop]", "MISSION_EXPLORE_LOOP", "state_mission_explore_loop",  "Looping tracks for stealth missions");
        BtnY = AddPlaylistBtn(BtnY, "Mission Combat",         "MISSION_COMBAT",       "state_mission_combat|",       "Shuffle playlist for combat");
        BtnY = AddPlaylistBtn(BtnY, "Mission Combat [Loop]",  "MISSION_COMBAT_LOOP",  "state_mission_combat_loop",   "Looping tracks for combat");
    }
    else if (CurrentScreen == "VICTORY")
    {
        BtnY = AddPlaylistBtn(BtnY, "Victory", "VICTORY", "state_victory", "Victory stinger tracks");
    }
    else if (CurrentScreen == "DEFEAT")
    {
        BtnY = AddPlaylistBtn(BtnY, "Defeat", "DEFEAT", "state_defeat", "Defeat stinger tracks");
    }
    else
    {
        // Fallback — show avenger
        BtnY = AddPlaylistBtn(BtnY, "Avenger",        "AVENGER",      "state_avenger|",      "Shuffle playlist for the Avenger base");
        BtnY = AddPlaylistBtn(BtnY, "Avenger [Loop]", "AVENGER_LOOP", "state_avenger_loop",  "Looping tracks for the Avenger");
    }

    // Resistance Radio is always available — shared station across states
    BtnY = AddPlaylistBtn(BtnY, "Resistance Radio", "RADIO", "state_resistance_radio", "Shared radio station — plays across all states");
}

// Helper: adds one playlist button and returns the next Y position.
simulated function int AddPlaylistBtn(int BtnY, string Label, string StateName, string TrackPrefix, string Tooltip)
{
    local UIButton Btn;
    local int Count;
    local string BtnLabel;

    Count = CountTracksForPrefix(TrackPrefix);
    BtnLabel = Label @ "(" $ string(Count) $ ")";

    Btn = Spawn(class'UIButton', MainPanel);
    Btn.InitButton(name("StateBtn_" $ StateName), "", OnStateFilterClicked);
    Btn.SetResizeToText(false);
    Btn.SetPosition(10, BtnY);
    Btn.SetWidth(SIDEBAR_W - 25);
    Btn.SetText("<p align='center'><font size='12'>" $ BtnLabel $ "</font></p>");
    Btn.SetTooltipText(Tooltip);
    StateButtons.AddItem(Btn);

    return BtnY + BTN_H + BTN_GAP;
}

simulated function int CountTracksForPrefix(string Prefix)
{
    local int i, Pipe1, Pipe2, Count;
    local string TrackData, TrackState, MatchState;
    local bool bExact;

    bExact = (Right(Prefix, 1) == "|");
    if (bExact)
        MatchState = Left(Prefix, Len(Prefix) - 1);
    else
        MatchState = Prefix;

    Count = 0;
    for (i = 0; i < TrackList.Length; i++)
    {
        TrackData = TrackList[i];
        Pipe1 = InStr(TrackData, "|");
        TrackData = Mid(TrackData, Pipe1 + 1);
        Pipe2 = InStr(TrackData, "|");
        TrackState = Left(TrackData, Pipe2);

        if (TrackState == MatchState)
            Count++;
    }
    return Count;
}

// ================================================================
// RIGHT SIDE TAB: CONTROLS
// ================================================================

simulated function BuildControlsTab(int PosX, int PosY)
{
    local int BtnY;
    local UIText Header;
    local UIButton Btn;
    local int TabH;

    // Height: header + 6 buttons + spacing
    TabH = 40 + (BTN_H + BTN_GAP) * 6 + 10;

    ControlsPanel = Spawn(class'UIPanel', self).InitPanel('XiPodControls');
    ControlsPanel.SetPosition(PosX, PosY);
    ControlsPanel.SetSize(CTRL_W, TabH);

    ControlsBG = Spawn(class'UIBGBox', ControlsPanel).InitBG('CtrlBG', 0, 0, CTRL_W, TabH);

    // Header
    Header = Spawn(class'UIText', ControlsPanel).InitText('ControlsHeader');
    Header.SetPosition(10, 8);
    Header.SetSize(CTRL_W - 20, 30);
    Header.SetHTMLText("<font size='16' color='#a8e8d8'><b>Controls</b></font>");

    BtnY = 40;

    Btn = Spawn(class'UIButton', ControlsPanel).InitButton('BtnBack', "Back", OnBackClicked);
    Btn.SetPosition(10, BtnY);
    Btn.SetWidth(CTRL_W - 20);
    Btn.SetTooltipText("Skip to the previous track");
    BtnY += BTN_H + BTN_GAP;

    Btn = Spawn(class'UIButton', ControlsPanel).InitButton('BtnPause', "Pause", OnPauseClicked);
    Btn.SetPosition(10, BtnY);
    Btn.SetWidth(CTRL_W - 20);
    Btn.SetTooltipText("Pause the currently playing track");
    BtnY += BTN_H + BTN_GAP;

    Btn = Spawn(class'UIButton', ControlsPanel).InitButton('BtnPlay', "Play", OnPlayClicked);
    Btn.SetPosition(10, BtnY);
    Btn.SetWidth(CTRL_W - 20);
    Btn.SetTooltipText("Resume playback or start a new track");
    BtnY += BTN_H + BTN_GAP;

    Btn = Spawn(class'UIButton', ControlsPanel).InitButton('BtnNext', "Next", OnNextClicked);
    Btn.SetPosition(10, BtnY);
    Btn.SetWidth(CTRL_W - 20);
    Btn.SetTooltipText("Skip to the next track");
    BtnY += BTN_H + BTN_GAP;

    Btn = Spawn(class'UIButton', ControlsPanel).InitButton('BtnRescan', "Refresh Library", OnRescanClicked);
    Btn.SetPosition(10, BtnY);
    Btn.SetWidth(CTRL_W - 20);
    Btn.SetTooltipText("Rescan the music folder for new or removed tracks");
    BtnY += BTN_H + BTN_GAP;

    Btn = Spawn(class'UIButton', ControlsPanel).InitButton('BtnClose', "Close", OnCloseClicked);
    Btn.SetPosition(10, BtnY);
    Btn.SetWidth(CTRL_W - 20);
    Btn.SetTooltipText("Close the Anarchy Radio FM player (music keeps playing)");
}

// ================================================================
// TRACK LIST
// ================================================================

simulated function PopulateFilteredTracks(string StateFilter)
{
    local string StatePrefix, TrackData, TrackID, TrackState, TrackName;
    local int Pipe1, Pipe2, i;
    local bool bExactMatch;
    local UIMechaListItem ListItem;

    // Map filter name to prefix. Pipe suffix = exact match (don't include _loop tracks)
    if (StateFilter == "SHELL_MENU")                StatePrefix = "state_shell_menu|";
    else if (StateFilter == "SHELL_MENU_LOOP")      StatePrefix = "state_shell_menu_loop";
    else if (StateFilter == "AVENGER")              StatePrefix = "state_avenger|";
    else if (StateFilter == "AVENGER_LOOP")         StatePrefix = "state_avenger_loop";
    else if (StateFilter == "GEOSCAPE")             StatePrefix = "state_geoscape|";
    else if (StateFilter == "GEOSCAPE_LOOP")        StatePrefix = "state_geoscape_loop";
    else if (StateFilter == "SQUADSELECT")          StatePrefix = "state_squadselect|";
    else if (StateFilter == "SQUADSELECT_LOOP")     StatePrefix = "state_squadselect_loop";
    else if (StateFilter == "MISSION_EXPLORE")      StatePrefix = "state_mission_explore|";
    else if (StateFilter == "MISSION_EXPLORE_LOOP") StatePrefix = "state_mission_explore_loop";
    else if (StateFilter == "MISSION_COMBAT")       StatePrefix = "state_mission_combat|";
    else if (StateFilter == "MISSION_COMBAT_LOOP")  StatePrefix = "state_mission_combat_loop";
    else if (StateFilter == "VICTORY")              StatePrefix = "state_victory";
    else if (StateFilter == "DEFEAT")               StatePrefix = "state_defeat";
    else if (StateFilter == "RADIO")                StatePrefix = "state_resistance_radio";
    else                                            StatePrefix = "state_avenger|";

    // Check if this is an exact-match prefix (ends with |)
    bExactMatch = (Right(StatePrefix, 1) == "|");
    if (bExactMatch)
        StatePrefix = Left(StatePrefix, Len(StatePrefix) - 1);

    TrackListUI.ClearItems();
    FilteredTrackIDs.Length   = 0;
    FilteredTrackNames.Length = 0;

    for (i = 0; i < TrackList.Length; i++)
    {
        TrackData = TrackList[i];

        Pipe1     = InStr(TrackData, "|");
        TrackID   = Left(TrackData, Pipe1);
        TrackData = Mid(TrackData, Pipe1 + 1);

        Pipe2      = InStr(TrackData, "|");
        TrackState = Left(TrackData, Pipe2);
        TrackName  = Mid(TrackData, Pipe2 + 1);

        if ((bExactMatch && TrackState == StatePrefix) ||
            (!bExactMatch && TrackState == StatePrefix))
        {
            ListItem = Spawn(class'UIMechaListItem', TrackListUI.ItemContainer);
            ListItem.InitListItem();
            ListItem.SetWidth(MAIN_W - TRACK_LIST_X - 15);
            ListItem.UpdateDataDescription(TrackName, "");
            FilteredTrackIDs.AddItem(TrackID);
            FilteredTrackNames.AddItem(TrackName);
        }
    }
}

// ================================================================
// CALLBACKS
// ================================================================

simulated function OnPlayClicked(UIButton Button)
{
    `log("XIPOD: PLAY");
    if (FilteredTrackNames.Length > 0)
        ShowToast(FilteredTrackNames[0]);
}

simulated function OnPauseClicked(UIButton Button)
{
    `log("XIPOD: PAUSE");
}

simulated function OnNextClicked(UIButton Button)
{
    `log("XIPOD: NEXT");
}

simulated function OnBackClicked(UIButton Button)
{
    `log("XIPOD: PREV");
}

simulated function OnCloseClicked(UIButton Button)
{
    CloseScreen();
}

simulated function OnStateFilterClicked(UIButton Button)
{
    local string BtnName;

    // Button names are "StateBtn_AVENGER", "StateBtn_RADIO", etc.
    BtnName = string(Button.MCName);
    if (Left(BtnName, 9) == "StateBtn_")
    {
        ActiveStateFilter = Mid(BtnName, 9);
        PopulateFilteredTracks(ActiveStateFilter);
    }
}

simulated function OnTrackClicked(UIList ListCtrl, int Index)
{
    if (Index >= 0 && Index < FilteredTrackIDs.Length)
    {
        `log("XIPOD: PLAY_ID" @ FilteredTrackIDs[Index]);
        ShowToast(FilteredTrackNames[Index]);
    }
}

simulated function OnRescanClicked(UIButton Button)
{
    `log("XIPOD: RESCAN");
}

// ================================================================
// INPUT
// ================================================================

simulated function bool OnUnrealCommand(int cmd, int arg)
{
    if (cmd == class'UIUtilities_Input'.const.FXS_KEY_ESCAPE)
    {
        CloseScreen();
        return true;
    }
    return super.OnUnrealCommand(cmd, arg);
}

// ================================================================
// NOW PLAYING TOAST
// ================================================================

simulated function ShowToast(string TrackName)
{
    if (ToastText == none)
    {
        ToastText = Spawn(class'UIText', self).InitText('NowPlayingToast');
        ToastText.SetPosition(10, 10);
        ToastText.SetSize(600, 30);
    }

    ToastText.SetHTMLText("<font size='14' color='#a8e8d8'>Now Playing: " $ TrackName $ "</font>");
    ToastText.Show();
    ToastText.SetAlpha(100);
    SetTimer(3.0, false, 'HideToast');
}

simulated function HideToast()
{
    if (ToastText != none)
    {
        ToastText.Hide();
    }
}

// ================================================================
// HELPERS
// ================================================================

simulated function string GetCurrentStateFilter()
{
    local string S;
    S = class'XiPod_Settings'.static.GetCurrentScreen();
    if (S == "")
        return "AVENGER";
    // Tactical screen shows explore/combat — default filter to explore
    if (S == "TACTICAL")
        return "MISSION_EXPLORE";
    return S;
}

defaultproperties
{
    bConsumeMouseEvents=true
    InputState=eInputState_Consume
}

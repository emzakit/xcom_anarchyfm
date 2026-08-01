// ============================================================
// XiPod_UISL_PostMission — Victory/Defeat state detection.
//
// Determines post-mission outcome on UIAfterAction init.
// On removal, transitions to AVENGER state.
// ============================================================
// Matched with IsA rather than ScreenClass, because XCOM 2 binds a listener
// to an EXACT class and other mods replace this screen with a subclass —
// Long War of the Chosen swaps in UIAfterAction_LW, which extends
// UIAfterAction. Bound the direct way, this listener simply never fires for
// those players and their post-mission music silently stops working. IsA
// walks the hierarchy, so a replacement still matches.
//
// It also keeps us out of the Alternative Mod Launcher's conflict list, where
// a shared ScreenClass reads as an incompatibility even when it isn't one.
class XiPod_UISL_PostMission extends UIScreenListener;

simulated function bool IsAfterActionScreen(UIScreen Screen)
{
    return Screen != none && Screen.IsA('UIAfterAction');
}

event OnInit(UIScreen Screen)
{
    local XComGameState_BattleData BattleData;

    if (!IsAfterActionScreen(Screen))
        return;

    BattleData = XComGameState_BattleData(`XCOMHISTORY.GetSingleGameStateObjectForClass(class'XComGameState_BattleData'));

    if (BattleData != none && BattleData.bLocalPlayerWon)
    {
        class'XiPod_Settings'.static.SetCurrentScreen("VICTORY");
        `log("XIPOD: STATE_VICTORY");
    }
    else
    {
        class'XiPod_Settings'.static.SetCurrentScreen("DEFEAT");
        `log("XIPOD: STATE_DEFEAT");
    }
}

event OnRemoved(UIScreen Screen)
{
    local string Current;

    if (!IsAfterActionScreen(Screen))
        return;

    Current = class'XiPod_Settings'.static.GetCurrentScreen();

    // After-action report dismissed → transition to avenger music.
    if (Current == "VICTORY" || Current == "DEFEAT")
    {
        class'XiPod_Settings'.static.SetCurrentScreen("AVENGER");
        `log("XIPOD: STATE_AVENGER");
    }
}

defaultproperties
{
    ScreenClass = none
}

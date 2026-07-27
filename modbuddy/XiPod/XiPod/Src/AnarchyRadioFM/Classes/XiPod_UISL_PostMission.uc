// ============================================================
// XiPod_UISL_PostMission — Victory/Defeat state detection.
//
// Determines post-mission outcome on UIAfterAction init.
// On removal, transitions to AVENGER state.
// ============================================================
class XiPod_UISL_PostMission extends UIScreenListener;

event OnInit(UIScreen Screen)
{
    local XComGameState_BattleData BattleData;

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
    ScreenClass = class'UIAfterAction'
}

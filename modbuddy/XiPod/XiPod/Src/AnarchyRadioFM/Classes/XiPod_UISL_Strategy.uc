// ============================================================
// XiPod_UISL_Strategy — Avenger HUD state detection.
//
// Handles the AVENGER state and the squad-select-to-avenger
// delayed transition (mission cancel vs launch race condition).
// ============================================================
class XiPod_UISL_Strategy extends UIScreenListener;

event OnInit(UIScreen Screen)
{
    local string Current;

    Current = class'XiPod_Settings'.static.GetCurrentScreen();

    if (Current == "SQUADSELECT")
    {
        // Could be mission launch (tactical takes over) or cancel (we emit avenger).
        // Delay so UITacticalHUD can claim TACTICAL first if launching.
        Screen.SetTimer(2.0, false, 'DoDelayedAvengerEmit', self);
    }
    else if (Current != "AVENGER")
    {
        class'XiPod_Settings'.static.SetCurrentScreen("AVENGER");
        `log("XIPOD: STATE_AVENGER");
    }
}

event OnReceiveFocus(UIScreen Screen)
{
    local string Current;

    Current = class'XiPod_Settings'.static.GetCurrentScreen();

    if (Current == "SQUADSELECT")
    {
        Screen.SetTimer(2.0, false, 'DoDelayedAvengerEmit', self);
    }
    else if (Current != "AVENGER")
    {
        class'XiPod_Settings'.static.SetCurrentScreen("AVENGER");
        `log("XIPOD: STATE_AVENGER");
    }
}

function DoDelayedAvengerEmit()
{
    if (class'XiPod_Settings'.static.GetCurrentScreen() == "SQUADSELECT")
    {
        class'XiPod_Settings'.static.SetCurrentScreen("AVENGER");
        `log("XIPOD: STATE_AVENGER");
    }
}

defaultproperties
{
    ScreenClass = class'UIAvengerHUD'
}

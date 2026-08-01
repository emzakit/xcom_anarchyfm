// ============================================================
// XiPod_UISL_Strategy — Avenger HUD state detection.
//
// Handles the AVENGER state and the squad-select-to-avenger
// delayed transition (mission cancel vs launch race condition).
// ============================================================
// Matched with IsA rather than ScreenClass — see XiPod_UISL_PostMission for
// the full reasoning. Long War of the Chosen puts several of its own
// listeners on UIAvengerHUD and other packs replace it outright, so binding
// to the exact class is a silent failure waiting to happen.
class XiPod_UISL_Strategy extends UIScreenListener;

simulated function bool IsAvengerHUD(UIScreen Screen)
{
    return Screen != none && Screen.IsA('UIAvengerHUD');
}

// Emission is deliberately UNCONDITIONAL (bar the squad-select race below).
// There used to be an `else if (Current != "AVENGER")` guard here to avoid
// repeat log lines, but the desktop app already ignores a state it's already
// playing — switch_state() returns early on the same state — so the guard
// bought nothing and cost everything when CurrentScreenType went stale.
// MMS logs every event unconditionally for the same reason: a duplicate line
// is free, a missing one is a silent failure.

event OnInit(UIScreen Screen)
{
    local string Current;

    if (!IsAvengerHUD(Screen))
        return;

    Current = class'XiPod_Settings'.static.GetCurrentScreen();

    if (Current == "SQUADSELECT")
    {
        // Could be mission launch (tactical takes over) or cancel (we emit avenger).
        // Delay so UITacticalHUD can claim TACTICAL first if launching.
        Screen.SetTimer(2.0, false, 'DoDelayedAvengerEmit', self);
    }
    else
    {
        class'XiPod_Settings'.static.SetCurrentScreen("AVENGER");
        `log("XIPOD: STATE_AVENGER");
    }
}

event OnReceiveFocus(UIScreen Screen)
{
    local string Current;

    if (!IsAvengerHUD(Screen))
        return;

    Current = class'XiPod_Settings'.static.GetCurrentScreen();

    if (Current == "SQUADSELECT")
    {
        Screen.SetTimer(2.0, false, 'DoDelayedAvengerEmit', self);
    }
    else
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
    ScreenClass = none
}

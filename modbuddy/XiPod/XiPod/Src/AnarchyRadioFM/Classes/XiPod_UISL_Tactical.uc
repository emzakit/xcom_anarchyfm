// ============================================================
// XiPod_UISL_Tactical — Tactical mission state detection.
//
// Sets the screen type for the playlist UI. Explore/combat
// sub-state detection is handled by MMS — Python listens
// for MMS log lines ("Transition to explore/Combat").
// ============================================================
class XiPod_UISL_Tactical extends UIScreenListener;

event OnInit(UIScreen Screen)
{
    class'XiPod_Settings'.static.SetCurrentScreen("TACTICAL");
    `log("XIPOD: STATE_TACTICAL");
}

event OnReceiveFocus(UIScreen Screen)
{
    `log("XIPOD: STATE_TACTICAL");
}

defaultproperties
{
    ScreenClass = class'UITacticalHUD'
}

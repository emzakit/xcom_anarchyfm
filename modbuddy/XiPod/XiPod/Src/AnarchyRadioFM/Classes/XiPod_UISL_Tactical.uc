// ============================================================
// XiPod_UISL_Tactical — Tactical mission state detection.
//
// Sets the screen type for the playlist UI. Explore/combat
// sub-state detection is handled by MMS — the desktop app listens for MMS's
// own log output. Note MMS never logs a "Transition to explore" line: explore
// is picked up from "Starting Ambience" at mission start, and combat from
// "Transition to Combat!".
// ============================================================
// Matched with IsA rather than ScreenClass — see XiPod_UISL_PostMission for
// the full reasoning. Nothing common replaces UITacticalHUD today, but the
// cost of being robust is one name comparison and the failure mode is silent.
class XiPod_UISL_Tactical extends UIScreenListener;

event OnInit(UIScreen Screen)
{
    if (Screen == none || !Screen.IsA('UITacticalHUD'))
        return;

    class'XiPod_Settings'.static.SetCurrentScreen("TACTICAL");
    `log("XIPOD: STATE_TACTICAL");
}

event OnReceiveFocus(UIScreen Screen)
{
    if (Screen == none || !Screen.IsA('UITacticalHUD'))
        return;

    `log("XIPOD: STATE_TACTICAL");
}

defaultproperties
{
    ScreenClass = none
}

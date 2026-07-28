// ============================================================
// XiPod_UISL_Tactical — Tactical mission state detection.
//
// Sets the screen type for the playlist UI. Explore/combat
// sub-state detection is handled by MMS — the desktop app listens for MMS's
// own log output. Note MMS never logs a "Transition to explore" line: explore
// is picked up from "Starting Ambience" at mission start, and combat from
// "Transition to Combat!".
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

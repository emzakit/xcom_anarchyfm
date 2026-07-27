// ============================================================
// XiPod_UISL_Shell — Shell/main menu state detection.
//
// Native shell music suppression is handled by MMS — Anarchy Radio FM
// feeds MMS a silent SoundCue via XComShellSound.ini config.
// This listener just handles state detection for Python.
// ============================================================
class XiPod_UISL_Shell extends UIScreenListener;

event OnInit(UIScreen Screen)
{
    class'XiPod_Settings'.static.SetCurrentScreen("SHELL_MENU");
    `log("XIPOD: STATE_SHELL_MENU");
}

event OnReceiveFocus(UIScreen Screen)
{
    // Shell regains focus — player backed out of new game setup,
    // or returned to main menu from strategy.
    `log("XIPOD: STATE_SHELL_MENU");
}

defaultproperties
{
    ScreenClass = class'UIShell'
}

// ============================================================
// XiPod_UISL_Shell — Shell/main menu state detection.
//
// Native shell music suppression is handled by MMS — Anarchy Radio FM
// feeds MMS a silent SoundCue via XComShellSound.ini config.
// This listener just handles state detection for Python.
// ============================================================
class XiPod_UISL_Shell extends UIScreenListener;

// This listener had never fired once, in any log we have. It asked for
// ScreenClass = UIShell, but the screen the game actually opens is
// UIFinalShell, and XCOM 2 matches listeners on the EXACT class rather than
// walking the hierarchy — so a subclass never matches its parent. The menu
// therefore had no state signal at all, which is why music carried on playing
// when you backed out to it.
//
// Matching on `none` plus an IsA test is the way round it, and it is what MMS
// does in its own shell listener. UIMPShell_Base is included for the same
// reason MMS includes it: the multiplayer shell is a menu too.
simulated function bool IsShellScreen(UIScreen Screen)
{
    return Screen != none
        && (Screen.IsA('UIFinalShell') || Screen.IsA('UIMPShell_Base'));
}

event OnInit(UIScreen Screen)
{
    if (!IsShellScreen(Screen))
        return;

    class'XiPod_Settings'.static.SetCurrentScreen("SHELL_MENU");
    `log("XIPOD: STATE_SHELL_MENU");
}

event OnReceiveFocus(UIScreen Screen)
{
    // Shell regains focus — player backed out of new game setup,
    // or returned to main menu from strategy.
    if (!IsShellScreen(Screen))
        return;

    `log("XIPOD: STATE_SHELL_MENU");
}

defaultproperties
{
    ScreenClass = none
}

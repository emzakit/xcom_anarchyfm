// ============================================================
// XiPod_UISL_EdgeTab — Global screen-event glue (ScreenClass=none).
//
// The on-screen edge tab has been REMOVED. In-game, you change "stations"
// simply by dipping in and out of the Geoscape (a fresh reshuffle, just
// like the original Resistance Radio); the XiPodPlay / XiPodPause /
// XiPodNext / XiPodPrev console commands are there if you want keybinds.
//
// This listener still handles two global behaviours:
//   - UIStrategyMap first-load AVENGER fallback (kick music off on load)
//   - UIShellNarrativeContent preemptive PAUSE before shell cinematics
//
// (Class/file name kept as-is for build stability — it's just a global
//  UIScreenListener now, no tab.)
// ============================================================
class XiPod_UISL_EdgeTab extends UIScreenListener;

event OnInit(UIScreen Screen)
{
    // UIStrategyMap isn't a music state on its own — Avenger music plays
    // through it. On the first strategy load (fresh game or loaded save)
    // emit AVENGER so something starts playing.
    if (Screen.IsA('UIStrategyMap'))
    {
        if (class'XiPod_Settings'.static.GetCurrentScreen() == "" ||
            class'XiPod_Settings'.static.GetCurrentScreen() == "SHELL_MENU")
        {
            class'XiPod_Settings'.static.SetCurrentScreen("AVENGER");
            `log("XIPOD: STATE_AVENGER");
        }
    }
}

event OnRemoved(UIScreen Screen)
{
    // UIShellNarrativeContent fires BEFORE the Bink cinematic starts.
    // ConfirmNarrativeContent pops this screen, OnRemoved fires, THEN
    // the movie starts. This preemptive PAUSE reaches the player before
    // the video buffers log lines. Also fires on Back — UIShell then
    // re-emits STATE_SHELL_MENU.
    if (Screen.IsA('UIShellNarrativeContent'))
    {
        `log("XIPOD: PAUSE");
    }
}

defaultproperties
{
    ScreenClass = none
}

// ============================================================
// XiPod_UISL_SquadSelect — Squad select state detection.
// ============================================================
// Matched with IsA rather than ScreenClass — see XiPod_UISL_PostMission for
// the full reasoning. Squad select is replaced outright by robojumper's Squad
// Select (robojumper_UISquadSelect extends UISquadSelect), which is popular
// enough that binding to the exact class would leave a lot of people with no
// squad select music and no clue why.
class XiPod_UISL_SquadSelect extends UIScreenListener;

event OnInit(UIScreen Screen)
{
    if (Screen == none || !Screen.IsA('UISquadSelect'))
        return;

    class'XiPod_Settings'.static.SetCurrentScreen("SQUADSELECT");
    `log("XIPOD: STATE_SQUADSELECT");
}

defaultproperties
{
    ScreenClass = none
}

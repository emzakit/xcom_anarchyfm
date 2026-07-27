// ============================================================
// XiPod_UISL_SquadSelect — Squad select state detection.
// ============================================================
class XiPod_UISL_SquadSelect extends UIScreenListener;

event OnInit(UIScreen Screen)
{
    class'XiPod_Settings'.static.SetCurrentScreen("SQUADSELECT");
    `log("XIPOD: STATE_SQUADSELECT");
}

defaultproperties
{
    ScreenClass = class'UISquadSelect'
}

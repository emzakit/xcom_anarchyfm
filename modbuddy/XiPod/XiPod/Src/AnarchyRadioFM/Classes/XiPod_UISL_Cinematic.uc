// ============================================================
// XiPod_UISL_Cinematic — keeps a XiPod_CinematicWatcher alive.
//
// UIScreenListeners don't tick, so the watcher has to be a real Actor. It is
// owned by the presentation layer and dies with the map, so it needs
// respawning on each new one.
//
// CRITICAL: this class must never store the watcher in a variable.
//
// XCOM 2 runs a UIScreenListener as its CLASS DEFAULT OBJECT, which is
// rooted and never garbage collected. A var here holding an Actor is
// therefore a permanent hard reference into that Actor's World, and the next
// map load dies on:
//
//   World XPACK_Shell_Xenoform.TheWorld not cleaned up by garbage collection!
//     XiPod_UISL_Cinematic AnarchyRadioFM.Default__XiPod_UISL_Cinematic
//     (ObjectProperty AnarchyRadioFM.XiPod_UISL_Cinematic:Watcher)
//
// which is a hard CTD, not a warning. An earlier version of this file did
// exactly that. So the "is one already running" test searches the world
// instead of remembering an answer.
// ============================================================
class XiPod_UISL_Cinematic extends UIScreenListener;

event OnInit(UIScreen Screen)
{
    local XComPresentationLayerBase Pres;
    local XiPod_CinematicWatcher Existing;
    local bool bAlreadyWatching;

    // Only the persistent per-map HUDs. Screens init constantly — every
    // popup and tooltip — and the AllActors search below is O(all actors),
    // which is not something to run on each of them in tactical.
    if (Screen == none)
        return;
    if (!Screen.IsA('UIAvengerHUD') && !Screen.IsA('UITacticalHUD')
        && !Screen.IsA('UIFinalShell'))
    {
        return;
    }

    if (Screen.Movie == none)
        return;

    Pres = Screen.Movie.Pres;
    if (Pres == none)
        return;

    foreach Screen.WorldInfo.AllActors(class'XiPod_CinematicWatcher', Existing)
    {
        if (!Existing.bDeleteMe)
        {
            bAlreadyWatching = true;
            break;
        }
    }

    if (bAlreadyWatching)
        return;

    // Deliberately a local. See the note at the top of this file.
    Existing = Pres.Spawn(class'XiPod_CinematicWatcher', Pres);

    // BeginWatching logs the CINE_WATCH line itself, so that it can report
    // the config values it resolved.
    if (Existing != none)
        Existing.BeginWatching();
}

defaultproperties
{
    ScreenClass = none
}

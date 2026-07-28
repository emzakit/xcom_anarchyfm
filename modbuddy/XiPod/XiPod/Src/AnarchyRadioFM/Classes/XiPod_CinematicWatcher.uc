// ============================================================
// XiPod_CinematicWatcher — polls for cinematics and announces them
// BEFORE the film starts.
//
// Why this exists: the desktop app used to learn about cinematics from the
// game's own "Movie Started Event" log line, and for half of them that line
// arrives far too late to act on. UIPlayMovie calls XENGINE.WaitForMovie(),
// which blocks the script thread for the entire runtime of the film — so
// nothing at all is written to the log between "Movie Started" and "Movie
// Finished" (verified: a 98-second Resistance Council scene produced zero
// intervening lines), and whatever is sitting in the engine's log buffer
// stays there until the film ends. By then the music has already played
// over the whole thing.
//
// Naming every cinematic in the app's defaults file did not help, because
// that table is only consulted AFTER the log line arrives. The problem was
// never the vocabulary, it was the timing.
//
// So instead of waiting to be told, we watch for a cinematic coming. A
// queued narrative moment carrying a Bink is visible before UIPlayMovie
// blocks, and a `log() from script during that window does reach the app in
// time — the existing pre-cinematic PAUSE hook proves a ~0.75s lead is
// enough.
//
// KNOWN GAP: this catches narrative-driven cinematics. Kismet-driven ones
// (the Lost and Abandoned rendezvous, in-mission story beats) are NOT caught
// yet — a real capture showed the queue never filling for them. bVerbose
// below exists to find out what does catch them.
// ============================================================
class XiPod_CinematicWatcher extends Actor config(Game);

// How often to check. The narrative queue for a Kismet-triggered cinematic
// can be filled and drained inside a fraction of a second — the Lost and
// Abandoned rendezvous went from "Start of XCom Turn" to Movie Started in
// 0.18s — so this is deliberately faster than the reaction time we need.
// The check itself is a few native calls and a walk over an array that is
// almost always empty.
var float PollInterval;

// Last announced state, so we only log on a change rather than every tick.
var bool bCinematicActive;

// Diagnostic. Logs every candidate predicate whenever any of them changes,
// so a play session can show which one (if any) goes true BEFORE the film
// starts. Set to false in XComGame.ini once detection is settled.
var config bool bVerbose;

// Promotes "the game is in cinematic mode" from a diagnostic reading to an
// actual trigger. OFF by default and deliberately so: cinematic mode is set
// for plenty of things that are not films, and a false positive mutes the
// player's music mid-mission — worse than the bug being fixed. If a capture
// shows cinemode leading the Kismet-driven films cleanly, flip this on in
// XComGame.ini to enable it without waiting for a rebuild.
var config bool bUseCinematicMode;

// Previous diagnostic sample, so verbose mode also only logs on change.
var int  LastConvCount;
var int  LastPendCount;
var bool bLastBink;
var bool bLastMovie;
var bool bLastCineMode;

simulated function BeginWatching()
{
    bCinematicActive = false;
    LastConvCount = -1;
    LastPendCount = -1;
    SetTimer(PollInterval, true, 'PollCinematic');

    // Reports the settings it actually resolved, because both are config-only
    // now and a config section that failed to merge would otherwise disable
    // the diagnostic silently — costing a whole play session to discover.
    // verbose=0 here means XComGame.ini was not picked up.
    `log("XIPOD: CINE_WATCH verbose=" $ (bVerbose ? 1 : 0)
         $ " usecinemode=" $ (bUseCinematicMode ? 1 : 0)
         $ " poll=" $ PollInterval);
}

simulated function StopWatching()
{
    ClearTimer('PollCinematic');
}

simulated function PollCinematic()
{
    local XComPlayerController PC;
    local UINarrativeMgr NarrMgr;
    local int nConv, nPend;
    local bool bBink, bMovie, bCineMode, bNow;

    PC = GetLocalPC();
    NarrMgr = GetNarrativeMgr(PC);

    if (NarrMgr != none)
    {
        nConv = NarrMgr.m_arrConversations.Length;
        nPend = NarrMgr.PendingConversations.Length;
        bBink = HasPendingBink(NarrMgr);
    }

    // Loading movies are deliberately excluded: they play on every map
    // change, and silencing for each one would cut the track every time the
    // player enters a mission.
    bMovie = class'XComEngine'.static.IsAnyMoviePlaying()
             && !class'XComEngine'.static.IsLoadingMoviePlaying();

    bCineMode = IsGameInCinematicMode(PC);

    if (bVerbose)
        ReportState(nConv, nPend, bBink, bMovie, bCineMode);

    // A Bink-carrying narrative moment or an actual full-screen film always
    // drives the lock. Cinematic mode only joins in if it has been opted
    // into — see bUseCinematicMode.
    bNow = bBink || bMovie || class'XComEngine'.static.IsWaitingForMovie()
           || (bUseCinematicMode && bCineMode);

    if (bNow == bCinematicActive)
        return;

    bCinematicActive = bNow;

    if (bNow)
        `log("XIPOD: CINE_ON");
    else
        `log("XIPOD: CINE_OFF");
}

simulated function ReportState(int nConv, int nPend, bool bBink, bool bMovie,
                               bool bCineMode)
{
    if (nConv == LastConvCount && nPend == LastPendCount
        && bBink == bLastBink && bMovie == bLastMovie
        && bCineMode == bLastCineMode)
    {
        return;
    }

    LastConvCount = nConv;
    LastPendCount = nPend;
    bLastBink = bBink;
    bLastMovie = bMovie;
    bLastCineMode = bCineMode;

    `log("XIPOD: CINE_DBG conv=" $ nConv $ " pend=" $ nPend
         $ " bink=" $ (bBink ? 1 : 0)
         $ " movie=" $ (bMovie ? 1 : 0)
         $ " cinemode=" $ (bCineMode ? 1 : 0));
}

// Resolved a step at a time rather than through `PRESBASE: that macro chains
// a cast straight into .Pres, and a miss during a map transition would log
// an accessed-none. At twenty polls a second that would bury the log we are
// trying to keep readable.
simulated function XComPlayerController GetLocalPC()
{
    local WorldInfo WI;

    WI = class'WorldInfo'.static.GetWorldInfo();
    if (WI == none)
        return none;

    return XComPlayerController(WI.GetALocalPlayerController());
}

simulated function UINarrativeMgr GetNarrativeMgr(XComPlayerController PC)
{
    if (PC == none || PC.Pres == none)
        return none;

    return PC.Pres.m_kNarrativeUIMgr;
}

simulated function bool IsGameInCinematicMode(XComPlayerController PC)
{
    local XComTacticalController TC;
    local XComHeadquartersController HC;

    TC = XComTacticalController(PC);
    if (TC != none)
        return TC.m_bInCinematicMode;

    HC = XComHeadquartersController(PC);
    if (HC != none)
        return HC.m_bInCinematicMode;

    return false;
}

// A conversation only counts if it carries a film. Narrative moments are
// also used for plain voice-over — Central over the radio, Tygan chiming in
// mid-mission — and pausing the player's music for those would be far more
// annoying than the bug this class exists to fix.
simulated function bool HasPendingBink(UINarrativeMgr NarrMgr)
{
    local int i;

    for (i = 0; i < NarrMgr.m_arrConversations.Length; i++)
    {
        if (NarrMgr.m_arrConversations[i].NarrativeMoment != none
            && NarrMgr.m_arrConversations[i].NarrativeMoment.strBink != "")
        {
            return true;
        }
    }

    for (i = 0; i < NarrMgr.PendingConversations.Length; i++)
    {
        if (NarrMgr.PendingConversations[i].NarrativeMoment != none
            && NarrMgr.PendingConversations[i].NarrativeMoment.strBink != "")
        {
            return true;
        }
    }

    return false;
}

// NOTE: bVerbose and bUseCinematicMode are `config` and so must NOT appear
// here — the compiler rejects a default for a config property ("Import
// failed ... property is config"). Their values come from XComGame.ini.
defaultproperties
{
    PollInterval=0.05
    bCinematicActive=false
}

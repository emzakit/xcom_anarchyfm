//---------------------------------------------------------------------------------------
//  X2DownloadableContentInfo_AnarchyRadioFM.uc
//  Anarchy Radio FM - External Music Engine for XCOM 2
//---------------------------------------------------------------------------------------

class X2DownloadableContentInfo_AnarchyRadioFM extends X2DownloadableContentInfo;

static event OnLoadedSavedGame()
{}

static event InstallNewCampaign(XComGameState StartState)
{}

// --- XIPOD CONSOLE COMMANDS ---

exec function XiPodPlay()
{
    `log("XIPOD: PLAY");
}

exec function XiPodPause()
{
    `log("XIPOD: PAUSE");
}

exec function XiPodNext()
{
    `log("XIPOD: NEXT");
}

exec function XiPodPrev()
{
    `log("XIPOD: PREV");
}

exec function OpenXiPod()
{
    local XComPresentationLayerBase Pres;
    local XiPod_UI MyUI;

    Pres = `PRESBASE;

    if (Pres != none)
    {
        MyUI = Pres.Spawn(class'XiPod_UI', Pres);
        Pres.ScreenStack.Push(MyUI);
    }
}

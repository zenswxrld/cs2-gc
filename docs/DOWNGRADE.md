# Download the supported CS2 version

This mod candidate supports **Steam build 25966348**, released 15 October 2026 UTC. Its game version is **1.41.9.1**, client **2000933**.

A version label alone is insufficient: the named Steam beta branch currently points at a different build. The newest public build is also not interchangeable. The launcher checks the engine, client DLL and VPK directory hashes from the tested installation.

## Recommended: download a separate copy

Use [DepotDownloader's Windows x64 release](https://github.com/SteamRE/DepotDownloader/releases/latest), from the tool's own GitHub repository. Extract it and open PowerShell in that extracted folder.

Run these **one at a time**. Replace `YOUR_STEAM_USERNAME` and the destination if necessary. Both commands must use the **same destination**.

Common game content, maps and textures:

```powershell
.\DepotDownloader.exe -app 730 -depot 2347770 -manifest 2520908610273941189 -username YOUR_STEAM_USERNAME -dir "G:\CS2-GC-25966348"
```

Windows executable and DLLs:

```powershell
.\DepotDownloader.exe -app 730 -depot 2347771 -manifest 8766757721818354077 -username YOUR_STEAM_USERNAME -dir "G:\CS2-GC-25966348"
```

Enter your password/Steam Guard approval in DepotDownloader locally; do not put credentials in a script or send them to anyone. The tool supports interactive authentication and downloads from Steam. See its [usage documentation](https://github.com/SteamRE/DepotDownloader#usage).

Wait for both downloads to complete successfully. Then extract the whole mod ZIP over `G:CS2-GC-25966348` and open **Launch CS2 GC.exe**.

These are the runtime/content depots used for the supported Windows game. The second manifest predates the common-content hotfix because the Windows binaries did not change in that hotfix. Workshop Tools and optional low-violence content are not needed for this mod's normal setup.

Manifest references:

- [Build 25966348](https://steamdb.info/patchnotes/25966348/)
- [Common content, depot 2347770](https://steamdb.info/depot/2347770/manifests/)
- [Windows binaries, depot 2347771](https://steamdb.info/depot/2347771/manifests/)

SteamDB is a third-party index; DepotDownloader and your Steam account obtain the actual files from Steam. Historical download availability is controlled by Steam. If a download returns access denied or manifest unavailable, retain the exact error. No unverified manifest or third-party game-file mirror is a substitute.

## Steam beta selection

Steam exposes version branches under **CS2 → Properties → Game Versions & Betas**. The 1.41.9.1 branch was listed at build 25947352 when checked, while the supported tested hotfix is 25966348. Do not assume selecting that branch produces the exact supported files.

[Valve's branch instructions](https://partner.steamgames.com/doc/store/application/branches).

## Keeping the mod copy stable

Download to a folder outside Steam's managed `steamapps/common` folders. Keep Steam open for account services, but launch **Launch CS2 GC.exe in the separate copy**. The launcher starts the adjacent game executable directly.

A Steam library move or “only update on launch” preference does not freeze a game version. Keep your normal Steam installation separate if you want current official matchmaking.

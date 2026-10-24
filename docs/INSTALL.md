# Installing the complete ZIP

## Requirements

- Windows x64 and Steam installed, signed into an account that owns CS2.
- The exact supported game files: Steam build **25966348**, client **2000933**. [Download instructions](DOWNGRADE.md).
- A writable CS2 folder. A separate copy outside Steam's library is recommended.
- Space for the game, mod and generated material packs.

Python, a compiler, .NET and manual console commands are not installation requirements. The ZIP includes a private Python runtime.

## Fresh installation

1. Finish both supported depot downloads into one separate folder, for example `G:\CS2-GC-25966348`.
2. Extract the whole mod ZIP directly into that folder. The result must include:
```text
CS2-GC-25966348/
  Launch CS2 GC.exe
  README.md
  README-INSTALL.md
  README-DOWNGRADE.md
  game/
    bin/win64/
      cs2.exe                         (from Steam)
      steam_api64.dll                  (original before first launch)
      cs2_gc_payload/steam_api64.dll   (mod payload)
      cs2_gc_python/python.exe         (private runtime)
      cs2_gc_profile.exe
      launch_setup.py
      gold_pools.txt
      collection_icons/
      weapon_patterns/
      ...remaining mod helpers and assets
```
3. Open **Launch CS2 GC.exe**. It opens Steam if needed, prepares the local copy and launches that executable directly. It never uses Steam's app-launch command to select a different installation.
4. Allow the first preparation to finish; it can take several minutes. An unchanged later launch should use the cache.

The first profile initialization requires Steam online. The bootstrap requests a welcome, Store data and a mission schema using your account's Steam session. It sends no purchases, equips, case openings or inventory modifications to the real GC. Those recordings stay local. This new first-run path still needs live validation on a clean installation; failures stop with a diagnostic rather than opening an empty local profile.

The launcher automatically preserves the original Steam library, installs the mod proxy, writes the local App ID file and extracts the schema. Do not rename DLLs or copy a schema from another game version manually.

## Included bot mods

Bot skins and the Bot Improver/difficulty integration are already part of CS2 GC. This ZIP carries the same pinned **Bot Improver v1.4.6** release as the working copy, including BotRandomizer, Metamod, CounterStrikeSharp with its runtime, and Low/Medium/High skill presets. The launcher installs these from the local payload; it does not fetch the latest plugins during setup.

The local Premier rating selects the presets and stock difficulty. Bot cosmetic loadouts are curated against the installed schema. Existing owned installations are reused; unrelated addons are never silently replaced. Your own mode server configs are preserved; if you customized one, setup logs which bot config it needs to execute.

The bundled bot plugins still need a fresh-gameplay check with the new ZIP. Installation checks alone do not prove every AI behaviour.

To disable the bot plugins, close CS2 and run the bundled bot removal helper using its private runtime:

```text
game\bin\win64\cs2_gc_python\python.exe -B game\bin\win64\bot_skins.py uninstall
```

This also saves a disabled preference so later launches and ZIP upgrades do not reinstall them. To enable the bundled version again, remove `game/bin/win64/cs2_gc_bot_plugins_disabled` with CS2 closed, then open the root launcher.

## Upgrading an existing installation

1. Close CS2 and let its rewards helper exit.
2. Back up your saved state.
3. Extract the complete newer ZIP over the same CS2 root folder, replacing the mod files.
4. Open **Launch CS2 GC.exe**.

The archive deliberately omits player inventory, active config files, replay recordings and generated ID/history maps. Existing files remain in place. It also keeps the replacement proxy under `cs2_gc_payload` until the launcher has checked and preserved the original library.

If upgrading an old mod folder that already contains the proxy but has lost `steam_api64_real.dll`, restore the original Steam DLL from the supported Windows depot first. The launcher refuses to save a proxy as the original.

## Moving your existing profile

Copy these **from your own old installation**, with CS2 closed:

- `cs2_gc_inventory.txt`
- `cs2_gc_finish_ids.json`
- `cs2_gc_gun_collections.json` (when present; includes collection history)
- `cs2_gc.cfg` and `cs2_gc_gameplay.cfg` (when present)
- `cs2_gc_gsi_state.json`, `cs2_gc_rewards.txt` and `cs2_gc_matches.txt` (when present; keep the helper cursors together)
- The complete `cs2_gc_replay` folder.

Place them in the new `game/bin/win64` folder. Copy your profile before the first launch of a new folder. Do not import another person's replay or inventory. Optional own preset/name files may also be copied.

## Steam-managed installation

The same ZIP layout can be extracted over a Steam-managed installation **only if its files match the supported build**. Steam updates and integrity verification may replace mod files or native mounts. Moving a game to another Steam library does not stop Steam updating it.

Use a separate supported copy for the mod and keep the normal Steam installation unmodified for online play. Changing Steam's update preference to “only update when launched” is not a version lock.

## Troubleshooting

| Problem | Action |
| --- | --- |
| Unsupported build | Use both exact depot manifests in the downgrade guide. Do not mix DLLs from the newest build with old VPKs. |
| Missing/changed mod file | Re-extract the complete ZIP. Partial helper ZIPs are insufficient for a fresh install. |
| Native preparation failed | Read `game/bin/win64/cs2_gc_prepare.log`; the dialog now includes the setup error. Preserve inventory and finish IDs. |
| Steam asks to install the game | Use the new root launcher. An old debug launcher may still use Steam's registered app path. |
| Missing engine2 / exit 0x7e | Check the Windows depot completed and both the active proxy and original Steam DLL are present. Do not install random DLL downloads. |
| Empty profile | Check `cs2_gc_profile.log` and `cs2_gc_log.txt`; the personal welcome/Store recordings must exist. |
| Launcher closes early | The launcher reports the exit code. Check `cs2_gc_launcher.log` and `cs2_gc_log.txt`. |
| XP/rewards do not advance | Check `cs2_gc_rewards.log`. A first-time GSI configuration can require one game restart. |
| Long first launch | Material generation is expected; later launches should use the cache. Do not replace generated VPKs while CS2 is running. |

## Removal

Close CS2. Remove the bot plugins using the bundled helper above, then keep a backup of your own saved files. Restore the original `steam_api64_real.dll` as `steam_api64.dll` and disable the owned VPK mounts using the bundled disable helper. The native resource tools keep backups of edited game information. For an ordinary Steam copy, verifying files restores Valve-managed files but does not remove every extra mod file.

Do not delete the entire game folder to remove the mod. Full owned-file cleanup and a polished removal flow remain future work.

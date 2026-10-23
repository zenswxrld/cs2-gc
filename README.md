# CS2 GC

A local inventory and progression mod for **Counter-Strike 2**, descended from [CSOffline](https://github.com/zenswxrld/CSOffline). It uses CS2's native inventory, loadout, Store and Armory pages for offline/bot play.

Items, stars, ratings and rewards belong to this local mod. They do not create real Steam items or change your Steam wallet. Launches use `-insecure`; use an unmodified Steam installation for official matchmaking.

## Download and install

**Supported game: Windows x64, Steam build `25966348` (game version 1.41.9.1, client 2000933).** The newest Steam build is not automatically supported. The launcher checks the actual client/engine/VPK fingerprints, not just the version label.

1. Obtain the supported CS2 files. [Exact downgrade instructions](docs/DOWNGRADE.md).
2. Extract the **entire** `CS2GC-Portable-25966348.zip` into the CS2 root folder, the folder containing `game`.
3. Open **Launch CS2 GC.exe**. No installer, separate Python installation, PowerShell commands or Steam launch-option edits are needed.

Keep Steam installed and sign in to an account that owns CS2. The ZIP contains the mod and its private Python runtime; it does not contain Valve's game files or anyone's account recordings.

Use a separate game folder outside Steam's managed library so Steam does not replace the mod or update that copy. [Installation, upgrades and removal](docs/INSTALL.md).

Complete ZIP candidates are built by the [portable ZIP workflow](https://github.com/zenswxrld/cs2-gc/actions/workflows/portable-release.yml). Download the artifact named **CS2GC-Portable-25966348**, then extract the ZIP inside it. Actions artifact downloads require GitHub sign-in. Partial helper-update ZIPs are not fresh installations.

## What the launcher handles

- Starts the CS2 executable in **this copy of the game**, with its working directory set correctly.
- Checks the supported game files and the complete mod payload.
- Saves the original Steam DLL as `steam_api64_real.dll` before activating the mod.
- Extracts the matching `items_game.txt` from the installed VPK, including schemas larger than 8 MiB.
- Initializes missing own-account welcome/Store recordings through Steam; never distributes personal recordings.
- Prepares the native resources before CS2 opens them, then reuses the preparation cache.
- Preserves existing inventory, settings, finish IDs and replay files during ZIP upgrades.
- Shows preparation failures and early game exit codes instead of silently closing.

The first preparation can take several minutes. Later unchanged launches use the cache.

## Current status

| Area | Status |
| --- | --- |
| Local inventory, saved items/loadouts and case opening | User-tested in earlier builds |
| Native Armory rotation, stars, selling, souvenirs and custom knife/glove cases | User-tested; individual economy and finish issues remain |
| Profile XP, local Premier-style rating and bot-match rewards | Working baseline; mode-specific behaviour still needs coverage |
| Care packages | Claims and case rewards user-confirmed after the favourite-message fix; packages default to profile level-ups |
| Bot names, scoreboard labels and mission-to-bot-match launching | Working baseline; not every language/HUD location is verified |
| Custom gun collections and colour families | Implemented; visual quality, distribution, duplicate and trade-up review ongoing |
| Mission progress and tier rewards | Implemented; live validation still needed |
| Complete ZIP and direct launcher | Implemented in the packaging branch; fresh-install/profile bootstrap and upgrade smoke tests required in the target client |
| Career UI, achievements and advanced bot behaviour | Future work |

See [feature details and known issues](docs/FEATURES.md) and [future plans](docs/FEATURE-ROADMAP.md). “Implemented” and passing automated tests do not establish live-client correctness.

## Your saved files

All mod state is currently in `game/bin/win64`. Back up these before moving installations:

- `cs2_gc_inventory.txt` — inventory, loadouts and saved progression.
- `cs2_gc_finish_ids.json` and `cs2_gc_gun_collections.json` — stable custom finish IDs and generated collection history.
- `cs2_gc.cfg`, `cs2_gc_gameplay.cfg` and `cs2_gc_gsi_state.json` — settings and helper progression.
- `cs2_gc_replay` — personal protocol recordings; keep private.

The release ZIP includes no inventory, settings or finish-ID map to overwrite yours.

## Troubleshooting

Start with [the installation guide](docs/INSTALL.md#troubleshooting). Useful logs in `game/bin/win64` are `cs2_gc_prepare.log`, `cs2_gc_launcher.log`, `cs2_gc_profile.log`, `cs2_gc_log.txt` and `cs2_gc_rewards.log`.

Never fix startup by deleting your inventory or finish-ID map. Do not share the replay folder or raw account data.

## Development

The active C++20 source is in `cs2_gc/`; Python helpers and owned artwork are in `tools/`. `legacy/` is a separate CS:GO reference project, not an installable CS2 binary.

Core checks:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON
cmake --build build --config Release
ctest --test-dir build -C Release --output-on-failure
```

The portable workflow also builds the Windows proxy, launcher, profile bootstrap and texture decoder, checks export forwarding, and smoke-tests the assembled ZIP with its private runtime. Builds and tests run in GitHub Actions.

## Credits

Original BSD license and upstream credits are retained. The package includes the project's license, the gold-pool data attribution, BCDEC's license and the embedded Python runtime's own license. Game assets are read from the user's own CS2 installation.

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
- Installs the bundled bot skins and Bot Improver plugins/presets, preserving owned installations and refusing unrelated addons.
- Prepares the native resources before CS2 opens them, then reuses the preparation cache.
- Preserves existing inventory, settings, finish IDs and replay files during ZIP upgrades.
- Shows preparation failures and early game exit codes instead of silently closing.

> [!IMPORTANT]
> **The first launch is slow. Let it finish.** Before CS2 opens, the launcher builds every custom-collection skin
> (thousands of recoloured textures) and packs them into the game. This happens once; later launches reuse the
> cache and start in seconds to a minute. Progress is written to `game\bin\win64\cs2_gc_prepare.log`.
>
> | Drive the game is on | Rough first-launch time |
> | --- | --- |
> | NVMe SSD | 15–30 minutes |
> | SATA SSD | 20–40 minutes |
> | Hard drive (HDD) | 45–90+ minutes |
>
> These are rough estimates; CPU speed matters too. A full rebuild also happens once after an update that changes
> how skins are made. Closing the launcher mid-way is safe for your game and inventory, but the next launch starts
> preparing again, so it is quickest to leave it running. Keep plenty of free space on that drive while it runs; once done, duplicate copies are removed and
> only the packed skins remain.
>
> **Short on time or disk space?** Before the first launch, create `game\bin\win64\cs2_gc_gameplay.cfg` (a plain
> text file) containing the line `custom_cases = 0`, or set it later with **CS2 GC Settings\Edit Settings.cmd**. Only the
> knife and glove recolours are built, and the Black Market and Gauntlet cases stay in the Armory; the custom gun
> collections leave the Armory rotation, drops and trade-ups. It is meant for new installs: custom-collection skins
> you already own will not display correctly while it is off, and setting it back to `1` brings them back.

## Features

Status key: **confirmed** = checked by the user in the supported client; **implemented** = built and covered by automated offline tests, still waiting for an in-game check. Passing tests alone never proves the live client.

### Inventory, loadouts and opening

| Feature | Status |
| --- | --- |
| Local inventory, loadouts and equipped items (knives, gloves, agents, stickers, charms) | Confirmed |
| Case, capsule and souvenir opening, with free matching keys and the key picker skipped | Confirmed |
| Native trade-ups, including mixed StatTrak and all-Souvenir contracts | Confirmed baseline |
| Custom-collection trade-ups: custom skins are listed in the Trade Up screen under their collection, and the result is one of the next tier's colours | Confirmed |
| Sell for stars from the item's right-click menu | Confirmed |
| Multi-sell: **Sell multiple for stars...** opens CS2's own storage-unit picker; only sellable items are listed, the button shows the total, and a confirmation is required | Confirmed |

### Armory and stars

| Feature | Status |
| --- | --- |
| Native Armory page with category tabs, pagination and a rotation timer, plus a **REFRESH ARMORY** button | Confirmed |
| Rotating collections, charms, stickers, capsules, cases, souvenirs, terminals and limited items | Confirmed |
| Collection tiles with their own emblems and 3D model previews | Confirmed |
| Black Market Case (knives) and Gauntlet Case (gloves) with custom recolours | Confirmed |
| Agent tile: rotating collections of Shattered Web, Broken Fang and Riptide agents with each operation's emblem, 25 stars | Implemented |
| Star economy balanced so no buy, open or sell route returns more stars than it costs (`sell_max_return_percent`) | Implemented |
| Armory passes renew themselves when full (`armory_pass_auto_renew`) | Implemented |

### Custom collections

| Feature | Status |
| --- | --- |
| 36 custom gun collections built from every gun finish, with themed palettes and detail-preserving recolours | Confirmed; visual review ongoing |
| Colour families: one listed skin can roll several named colours | Confirmed |
| Owned custom skins keep their IDs and keep rendering after regeneration | Confirmed |

### Progression and rewards

| Feature | Status |
| --- | --- |
| Profile XP and stars from bot matches in any mode: kills, headshots, MVPs and finishing the match | Confirmed |
| Local Premier-style rating with placement matches | Confirmed baseline |
| Care packages: on a level-up choose 3 of 4 rewards; claimed rewards stay labelled until the next package | Confirmed |
| Missions served locally; the mission tile shows | Confirmed |
| Mission progress, step XP and stars; a mission stays until completed, then a new one is generated straight away (not tied to the Armory) | Implemented; the last live test predated the fix |

### Bots

| Feature | Status |
| --- | --- |
| Random player-style bot names and scoreboard labels without the BOT prefix | Confirmed |
| Mission cards launch the matching bot mode and map | Confirmed |
| Bot skins: popular gun skins, knives, gloves, sticker crafts and charms (BotRandomizer) | Implemented (bundled) |
| Bot Improver plugins: aim, grenades and utility, movement, AI and buying | Implemented (bundled) |
| Bot skill follows your local rating: Low preset below 10,000, Medium to 29,999, High from 30,000, plus stock difficulty easy/normal/hard/expert at 5k/10k/20k | Implemented |
| Bot settings run from owned `gamemode_<mode>_server.cfg` files; stock mode configs, key binds and other addons are never replaced | Implemented |

### Launcher and setup

| Feature | Status |
| --- | --- |
| Complete drag-and-drop ZIP with a private Python runtime and root launcher | Implemented; fresh-install check pending |
| Preparation cache for fast repeat launches | Confirmed |
| Owned search paths in `gameinfo.gi`, backed up first, with other addons preserved | Confirmed |

### Planned

Career/statistics page, achievements, more missions, bot chat and personalities, wider language coverage, a game-folder cleanup tool and support for newer CS2 builds. These are plans, not included features.

More detail: [features and known issues](docs/FEATURES.md) and [roadmap](docs/FEATURE-ROADMAP.md).

### Useful settings (`cs2_gc_gameplay.cfg`)

| Setting | Default | Effect |
| --- | --- | --- |
| `armory_rotation_seconds` | 900 | How often the Armory rotates |
| `armory_agent_price` | 25 | Agent collection tile price |
| `armory_pass_auto_renew` | 1 | Full passes restart on their own |
| `sell_max_return_percent` | 90 | Highest share of a purchase that selling can return |
| `custom_cases` | 1 | 0 turns the custom gun collections off: no Armory tiles, drops or trade-ups, and their skins are not built. Knife and glove cases stay |
| `custom_collection_tradeups` | 1 | Custom collections count in the Trade Up screen |
| `care_packages_from_matches` | 0 | 1 also gives a package per match |

Open **CS2 GC Settings\Edit Settings.cmd** in the game folder. It opens `game\bin\win64\cs2_gc_gameplay.cfg` in Notepad (the launcher creates it on its first run) with every setting listed at its default behind a `#`. Delete the `# ` in front of a setting to change it, then restart the launcher. The complete annotated list is in [examples/cs2_gc_gameplay.cfg](examples/cs2_gc_gameplay.cfg).

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

Original BSD license and upstream credits are retained. The package includes the project's license, the gold-pool data attribution, BCDEC's license, the embedded Python runtime's own license, and the bundled bot components' notices and source snapshots. Game assets are read from the user's own CS2 installation.

# Codex test build 2026-10-20-15

Built on Claude's `schema-loader` commit `e6f93092f28f0664e479fd5b29080abdc876b44d`.
Working mixed trade-ups, held skins, native resource mounting and existing inventory are preserved.
New features below are verified offline; target-client checks remain necessary.

## Install

1. Fully close CS2. Back up your proxy DLL, inventory and gameplay config.
2. Copy this ZIP into `game/bin/win64`. Keep your original `steam_api64_real.dll`, `items_game.txt`, replay folder, proxy config and inventory.
3. Merge desired gameplay settings into your existing `cs2_gc_gameplay.cfg`, or use the supplied defaults. The DLL and Python helpers must be updated together.
4. Launch `cs2_gc_debug.exe`, wait for preparation, then fully close CS2 and launch once more to mount the new native overrides.

Python 3 must already be installed. The helper starts quietly and closes with CS2.
This is the debug test package; normal release builds disable test console controls.

## Changes to check

- **Expanded Armory:** 3 collection groups, 2 charm groups, 2 sticker groups, 2 cases, 2 capsules, 1 limited offer and 1 random-agent offer by default. All rotate on the shared 15-minute cycle. Counts are configurable.
- **Agents:** random choice from the 63 eligible official agents in the inspected schema; default cost 50 stars.
- **Capsules:** 56 curated capsule options, including the historical team capsules used in OfflineCS. These are a curated selection, not a live popularity ranking.
- **Tiles:** actual limited-item image replaces the stock hardcoded weapon carousel; short preview lists wrap safely; nav images fall back to actual items; reused tile/nav callbacks bind to the current offer.
- **Main-page timer:** countdown also appears below the credit balance.
- **Limited certificates:** limited Armory purchases, including Howl, receive the existing Original Owner Certificate attribute. Existing terminal certificate behavior remains.
- **Weapon reward pool:** match and level weapons default to the five schema `set_timed_drops_*` collections. The inspected schema supplies 40 blue-or-better eligible finishes. Case skins are excluded. Three rewards and the independent 50% case / 50% weapon split remain.
- **Selling:** inventory context menu offers Sell for Stars through the native deletion request, with confirmation. Item removal and stars persist together; repeat, malformed or overflowing requests do not pay. Equipped sales clear the saved loadout reference. Stored items, storage units with contents, pending terminal offers and temporary items are excluded.
- **Premier variation:** win/loss gains vary by up to 79 rating around configured values; win gains remain positive and loss gains negative. Bot badges use stable individual offsets up to 1,200 from your displayed rating. Placements still hide the rating until the configured wins.
- **Native results tab:** REWARDS & RATING joins CS2's end-of-match sequence after the victory card for offline matches. It reads actual cached rating, profile level and new unacknowledged reward items. It does not grant or acknowledge rewards.

The results tab needs live verification. It requires an inventory baseline before rewards arrive and cannot reconstruct drops already acknowledged elsewhere. The stock XP progress animation still depends on engine-owned data-ready flags; this build displays the current profile level rather than claiming that animation is fixed.

## OfflineCS sale values

| Item | Stars |
| --- | ---: |
| Consumer / Industrial / Mil-Spec | 1 / 2 / 5 |
| Restricted / Classified / Covert | 10 / 25 / 50 |
| Knife or gloves | 150 |
| Sticker, patch, graffiti or charm | 50% of rarity value, minimum 1 |
| Music kit | 10 |
| Eligible container | 30% of its local Armory price, minimum 1 |
| Agent | 50% of configured agent price, normally 25 |

No StatTrak premium or attached-sticker/charm refund, matching OfflineCS. Contraband has no default rarity sale value. Container prices use this CS2 Armory's 2-star case / 1-star capsule costs to avoid a buy/sell profit loop. All sale prices and percentages are configurable.

## Suggested live test

1. Check `cs2_gc_log.txt` says `test build: codex-20261020-15` and the gameplay config loaded.
2. After the restart, check the Armory's extra groups, balance timer, limited artwork and random-agent preview. Redeem one agent and one limited item; verify stars and certificate.
3. Right-click a spare blue skin, cancel its sale, then confirm its sale. Expect +5 stars. Restart and confirm the skin is gone and the balance remains.
4. Complete a competitive bot match. Look for REWARDS & RATING after the victory card, current profile level, actual drops, and rating or placement count. Check bot scoreboard ratings differ and remain stable while the scoreboard refreshes.
5. Confirm weapon rewards belong to the weekly collections, and cases still drop. Match and level rewards can both occur at one completion.
6. Send both logs if any native feature is skipped or the tab does not appear. The console echo/log transport for give-stars and forced rotation is still unresolved in the last live report; do not assume those commands work from offline tests.

## Validation

15 automated suites pass, including native sale confirmation/cancellation, repeat-sale protection, saved balance/loadout handling, weekly pool exclusion and real-cache results rendering. All 120 generated real-schema Armory goods redeem in a separate integration check; all 5 limited offers carry certificates. Patched actual xpshop, endofmatch and inventory-context scripts pass Node syntax checks. Windows debug and release builds are cross-compiled; live CS2 behavior is not verified here.

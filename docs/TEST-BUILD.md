# Codex test build 2026-10-20-05

## Install

1. Fully close CS2 and back up `steam_api64.dll`, `cs2_gc_inventory.txt` and your gameplay config.
2. Copy the ZIP contents into `game/bin/win64`, keeping your existing original `steam_api64_real.dll`, `items_game.txt`, replay folder and proxy/account config. Keep Python 3 installed and every bundled helper beside the DLL. Preserve custom gameplay settings when copying the example config.
3. Launch local CS2 with `-insecure -condebug`. The hidden rewards helper starts/stops with CS2; no rewards window is needed.
4. Wait for native preparation messages in `cs2_gc_rewards.log`, fully close CS2, then launch again. Schema and Panorama changes need this extra restart. Unsupported/missing assets are logged and skipped without stopping XP.
5. Open the native Armory. Check its timer and six category slots, buy one active item, and equip skins for both teams. Restart again to check saved loadouts.

`grant_test_items.cmd` is an optional additive test-inventory tool, used with CS2 closed. It backs up first and adds 229 schema-validated items, including all skin tiers, StatTrak, cases/keys, capsules, terminals and passes. Each run adds another batch. It is not required for gameplay.

## New in build 05

- Equipped loadout slots now save in the inventory, restore into client/server item state, and save immediately after native equip requests. Older saves have no stored choices to recover; equip again after installing.
- Installed Panorama lookup accepts the actual `.js`, `.vjs`, `.js_c` or `.vjs_c` filename and slash representation. Raw JS stays raw. This addresses build 04's logged missing `.vjs_c` assets; the target game must still confirm loading.
- Native mixed-recipe override now mounts through both `Game` and `Mod`. This is a new mounting test, **not a verified fix** for the user's still-segregated normal/StatTrak picker. The backend already accepts mixed contracts and uses their StatTrak fraction.
- Armory catalogue and UI preparation now run automatically. Catalogue rows refer only to existing official items/loot lists; no custom cases, skins or paint kits. The GC validates source/output CRCs and the owned mount before loading that same generated schema on the next launch.
- All six Armory category pools rotate independently every 15 minutes, with a visible countdown. One active entry per pool; previous selections expire without spending stars. A stale inspect screen returns to the main tiles when the cycle changes.

| Slot | Pool in supplied build 25966348 | Default price |
| --- | --- | ---: |
| Cases | 42 standard keyed weapon cases | 2 stars |
| Capsules | 34 curated sticker/team capsules | 1 star |
| Weapon collections | 6 current/previous Armory collections | 4 stars |
| Sticker sheets | 6 Armory sticker collections | 1 star |
| Charms | 4 Armory charm collections | 3 stars |
| Limited Edition Item | Heat Treated, XM1014 Solitude, M4A1-S Solitude, AK-47 Aphrodite, Howl | 25 stars; Howl 40 |

The capsule selection includes team capsules from Katowice/Cologne 2014, Katowice/Cologne 2015, Stockholm, Antwerp, Paris, Copenhagen, Shanghai, Austin and Budapest where their group capsules exist in the installed schema, plus CS20, CS:GO 10, Halo, Half-Life Alyx and Skill Groups. This is a curated pool, not a live market popularity ranking. No individual team envelopes, coupons, souvenirs or music capsules enter it. Missing schema entries are omitted. Charms and sticker sheets use existing Armory pack loot lists; unrelated weapon collections do not enter the collection pool.

Limited items share the existing limited-style native tile flow. Howl uses the existing single-Howl `removed_items` list, retaining Contraband rarity. New catalogue rows create actual native shop indexes; there are no invented redeem indexes. Live rendering/redemption remains to be checked after the restart.

## In-game test commands

With `-condebug` added to your launch options, wait for the helper to start, then enter once per game launch:

```
exec cs2_gc_console
```

Then use:

```
cs2_gc_give_stars
cs2_gc_give_stars_1000
cs2_gc_force_rotation
```

The first adds 100 stars; the second adds 1,000. They add to the saved balance without advancing XP or passes. Force rotation advances every category pool; wait two seconds before buying. It advances the selection while retaining the normal quarter-hour timer. No BAT file is involved. Do not re-execute the setup CFG mid-session: it initializes the UI rotation offset. A helper restart regenerates aliases; execute the setup again if it restarts.

These are console aliases using normal echo/user-info commands and the game's local console log. The helper reads new, exact session-marked lines; the proxy applies a cumulative star cursor atomically with inventory. Historical console output cannot pay again. The UI reads the same local rotation offset. These new aliases still need live validation on this client.

## Rewards retained

New profiles start at **level 1, zero XP**. Profile levels take 5,000 XP and cap at 40.

| Action | XP |
| --- | ---: |
| Kill | 5 |
| Headshot | +3 |
| MVP | 25 |
| Completed match | 600 |

Up to five active passes advance together at 400 XP/star, 40 stars per pass. No active pass means profile XP only. Plants/defuses are not connected. Bot matches are supported; warmup/spectated-player stats are excluded. The first snapshot is a baseline, not a retrospective payout.

Every observed completed match grants three independent drops, each 50% case / 50% normal blue-through-red weapon. Every newly earned profile level grants three additional drops with the same policy, without a weekly cooldown. No automatic key or gold/Contraband match drop. Cursors and rewards persist together; old saves do not receive invented historical level rewards.

Case/terminal pity starts soft at roll 10, guarantees the target by roll 100 and persists. Random Armory packs have independent saved pity, also 10/100; highest-tier base chance is at least 0.64%, never reducing a higher baseline. Fixed cases/capsules and limited skins do not advance Armory pity. Collection rolls do not get StatTrak.

Local Premier rating uses observed competitive-mode results: start 1,000, +300/win, -100/loss, hidden until ten wins. It is a local model, not Valve's formula. Profile placement display was confirmed at one win / nine remaining. Scoreboard badges still need live verification. The generated `exec cs2_gc_premier_bots` config applies difficulty before spawning bots; automatic skill and end-of-match panels remain pending.

## Known live failures and next checks

**Terminal Buy is still unresolved.** Build-04 logs show its saved offer reload but the Store preparation fails with `Corrupt input data`. This build does not claim to fix that failure. Send `game/bin/win64/cs2_gc_replay/2501.bin` with both logs so the actual recorded price-sheet compression can be inspected. Use the native laptop; no terminal-purchase BAT is bundled.

**Mixed native trade-up selection still failed in build 04**, after restarting. Test normal-first and StatTrak-first again after this build's additional Mod mount. Backend acceptance/probability tests do not prove the native inventory filter changed.

**End-of-match drop, XP and rank screens are not implemented.** The user confirmed actual drops, earned stars, star persistence and the profile XP bar; these are separate from match presentation.

Check Armory timer/category rendering, two consecutive forced rotations and active/stale redemptions; limited items including Howl; equip/restart/bot-match skins; scoreboard badges; one-click opening/hidden Rent; and per-level drops. Source/JS tests and a Windows cross-build cannot prove the client loaded overrides.

## Configuration and recovery

`cs2_gc_gameplay.cfg` controls XP, drops, mixed contracts, pity, terminals, rotation and Premier rules. Restart once for helper preparation and again to load changed native resources. Unknown/duplicate/out-of-range settings reject. The new category catalogue always enforces its active slots; `armory_rotation_slots` and optional `armory_rotation_enforce` retain their older uncategorised-schema fallback meaning.

To restore homogeneous recipes, set `mixed_stattrak_tradeups=0`. To remove the generated catalogue/UI too, set `armory_rotation_enabled=0`. Launch for the helper to remove its owned mount lines, then restart. Other addons stay intact. Original schema/VPKs stay unchanged; first-edit gameinfo backups and manifest hashes protect external changes.

Keep `cs2_gc_inventory.txt`, GSI state and cumulative cursor files. Deleting history can lose progression; it is not a supported reset. Older lost equip choices and pre-fix spending cannot be reconstructed. If preparation rejects an externally edited addon, inspect it instead of deleting saved inventory.

All offline regression suites and the Windows x64 build are checked separately. Export forwarding preserves all 1,046 supplied proxy exports. No original game DLL, full schema, account data, replay or user log is distributed. Protocol fingerprint hashes still identify the original 25947352 fixture; they were not relabelled as build 25966348.

Send `cs2_gc_rewards.log` and `cs2_gc_log.txt` with the failed action. Avoid publicly sharing GSI state/config because they contain a local identity or token. The remaining OfflineCS feature order is in `FEATURE-ROADMAP.md`.

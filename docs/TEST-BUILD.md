# Codex test build 2026-10-20-01

## Install and test

1. Close CS2. Back up your current proxy `steam_api64.dll` and `cs2_gc_inventory.txt`.
2. Copy the test ZIP's contents to `game/bin/win64`, beside your existing `steam_api64_real.dll`, `items_game.txt`, config and replay directory. Keep those existing files.
3. With CS2 closed, run `grant_test_items.cmd` once (Python 3 required). It adds 229 schema-validated test items and makes a timestamped inventory backup. Existing items, stars, pass progress and rank remain intact. Running it again adds another batch.
4. Run `start_rewards.cmd` and leave its window open. It installs only `game/csgo/cfg/gamestate_integration_cs2_gc.cfg` and starts a loopback game-state receiver. Launch/restart CS2 afterwards so that config is read.
5. Launch CS2 with `-insecure` in local mode. Activate an Armory Pass to earn stars. Play a bot match.

Test items: 20 normal skins at each rarity from Consumer through Classified, 10 normal Coverts, 20 StatTrak skins at each of Mil-Spec/Restricted/Classified, 10 StatTrak Coverts, Fever cases and matching keys, sticker capsules, patch packs, X-Ray packages, both terminals and five Armory Passes. Each rarity/StatTrak group starts in one collection so ten standard inputs (or five Covert inputs) have valid outcomes. Finishes, patterns and wear vary. All names/IDs are checked against the supplied schema, not added as custom items.

## Rewards

New local profiles start at **level 1, zero XP**. The recorded account's profile is replaced in the welcome. Levels take 5,000 XP and cap at 40; passes can continue progressing at that cap.

| Action | Local XP |
| --- | ---: |
| Kill | 5 |
| Headshot | +3 |
| MVP | 25 |
| Completed match | 600 |

Every active pass advances by the earned XP, awarding one star per 400 XP, up to 40 per pass. Up to five passes can progress together. Finished passes can be replaced when another pass is activated. No active pass means profile XP only. Plants/defuses are not yet attributed by this helper. Warmup, spectated players and controlled bots with a different Steam ID are ignored. The first snapshot establishes a baseline rather than paying old scoreboard stats.

The helper commits cumulative XP and its last snapshot to `cs2_gc_gsi_state.json`, then atomically publishes `cs2_gc_rewards.txt`. The proxy applies only XP beyond its saved checkpoint. Keep both helper files; do not delete/reset one to replenish rewards. Stars, pass tracks, rank, XP and the consumed checkpoint save together in the inventory. The config's `armory_credits` seeds an inventory without a saved balance; it no longer refills stars on relaunch. Existing pre-fix spending cannot be reconstructed automatically.

## What this test changes

- Single-item Store coupons grant the actual capsule/package/sticker/charm directly. They do not open the purchased container. Old coupon envelopes still have their old unlock path.
- Armory collection rolls cannot accidentally receive hidden StatTrak. Startup repairs impossible StatTrak flags on known collection-only skins; valid case StatTrak is retained and encoded visibly.
- Five Covert skins can produce golds. StatTrak contracts produce knives only. Missing/incompatible rare-pool data rejects a contract without consuming its inputs. Gold membership comes from the versioned CSGO-API catalogue (see `data/CSGO-API-LICENSE`), validated against the game's schema. The local model chooses supplied collections proportionally and listed outcomes uniformly; this is not a claim of exact Valve phase odds.
- Terminals unseal, retain a saved offer, decline to the next offer, and accept that same offer through the free/local Store. Counter checks prevent stale-request rerolls. Local defaults: five offers and seven-day lifetime; supplied `volatile_limit` is respected up to 100. The displayed purchase price is zero. This does not connect to Steam payments.
- The bot server receives a separate GC welcome/cache queue. Equipped weapon objects include `equipped_state`; server callbacks are routed separately from client callbacks.

## Verification and remaining work

Offline regression suites and Windows x64 cross-compilation pass. The test DLL's export list matches the 1,046 exports in the supplied existing proxy and forwards directly to `steam_api64_real`, not through the previous proxy. It depends only on Windows system runtimes. No original game DLL, schema, replay, account data or uploaded log is distributed.

**Live testing is still required** for held bot-match skins, progression UI refresh, terminal offer messages and Covert results. The old protocol fingerprint still refers to build 25947352; the external schema checks used build 25966348's real schema, but the original fingerprint hashes have not been relabelled as that build.

The extra “Open to Keep” confirmation is Panorama-side and remains in this DLL. `tools/skip_container_confirm.py` prepares a source override for only local-GC item IDs; it must be compiled and mounted with the target game's Panorama toolchain before the confirmation can be removed. No unverified UI override is installed by this ZIP. Existing gaps such as music/patch/graffiti-specific drops and X-Ray package unlocking are not silently declared fixed. Standard case gold drops are separate from the newly added Covert contract support.

Send `cs2_gc_log.txt` from this test and describe which action failed. Avoid sharing the GSI state/config files publicly: they include a local player identifier or token.

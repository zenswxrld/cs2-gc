# Codex test build 2026-10-20-03

## Install and test

1. Close CS2. Back up your current proxy `steam_api64.dll` and `cs2_gc_inventory.txt`.
2. Copy the test ZIP's contents to `game/bin/win64`, beside your existing `steam_api64_real.dll`, `items_game.txt`, config and replay directory. Keep those existing files.
3. `cs2_gc_gameplay.cfg` contains all gameplay options with comments. Defaults match the requests. Close/restart **both CS2 and the helper** after edits. Existing proxy/account configuration is separate and is not replaced. See the limitations below for native UI features.
4. With CS2 closed, run `grant_test_items.cmd` once (Python 3 required). It adds 229 schema-validated test items and makes a timestamped inventory backup. Existing items, stars, pass progress and rank remain intact. Running it again adds another batch.
5. Close any old `start_rewards.cmd` window. Leave the bundled Python helpers beside the DLL. **The DLL now starts the rewards bridge automatically in the background** when local `-insecure` CS2 runs, and the bridge stops when that game closes. Python 3 must remain installed. If GSI has never been configured, the first launch installs its dedicated config; restart CS2 once to load it. No manual helper launch is needed after that.
6. Launch CS2 with `-insecure` in local mode. Activate an Armory Pass to earn stars. Play a bot match.

Test items: 20 normal skins at each rarity from Consumer through Classified, 10 normal Coverts, 20 StatTrak skins at each of Mil-Spec/Restricted/Classified, 10 StatTrak Coverts, Fever cases and matching keys, sticker capsules, patch packs, X-Ray packages, both terminals and five Armory Passes. Each rarity/StatTrak group starts in one collection so ten standard inputs (or five Covert inputs) have valid outcomes. Finishes, patterns and wear vary. All names/IDs are checked against the supplied schema, not added as custom items.

## Rewards

New local profiles start at **level 1, zero XP**. The recorded account's profile is replaced in the welcome. Levels take 5,000 XP and cap at 40; passes can continue progressing at that cap.

| Action | Local XP |
| --- | ---: |
| Kill | 5 |
| Headshot | +3 |
| MVP | 25 |
| Completed match | 600 |

By default every active pass advances by the earned XP, awarding one star per 400 XP (configurable with `armory_xp_per_star`; native progress is scaled), up to 40 per pass. Up to five passes can progress together. Finished passes can be replaced when another pass is activated. No active pass means profile XP only. Plants/defuses are not yet attributed by this helper. Warmup, spectated players and controlled bots with a different Steam ID are ignored. The first snapshot establishes a baseline rather than paying old scoreboard stats.

The helper commits cumulative XP and its last snapshot to `cs2_gc_gsi_state.json`, then atomically publishes `cs2_gc_rewards.txt`. The proxy applies only XP beyond its saved checkpoint. Keep both helper files; do not delete/reset one to replenish rewards. Stars, pass tracks, rank, XP and the consumed checkpoint save together in the inventory. The config's `armory_credits` seeds an inventory without a saved balance; it no longer refills stars on relaunch. Existing pre-fix spending cannot be reconstructed automatically.

## New in build 03

The proxy launches the local rewards bridge from the normal Steam callback loop,
with a hidden Windows process and the actual game PID. It prefers `pyw`/`pythonw`,
with console Python fallback also launched without a console. The bridge retains
a Windows handle to the launching game and exits after that process ends. It
does not run at Windows startup or install a scheduled task/service.

An OS lock prevents duplicate helpers from changing the same reward state. The
HTTP port is claimed before loading/saving state, including conflicts with an
older helper. Startup failures are recorded in `cs2_gc_log.txt`; background
Python diagnostics go to `cs2_gc_rewards.log`, with one previous log retained.
Missing Python or missing bundled scripts is reported. Helper restarts are
limited to three launches per game session. Logs do not include the GSI token or
raw packets. Existing reward cursors keep replayed stats from paying twice.

Automatic startup defaults on. Set `rewards_auto_start = 0` in
`cs2_gc_gameplay.cfg` to use the manual `start_rewards.cmd` diagnostic mode instead.
The manual script is optional; keep its window open only when choosing that mode.
If an old manual helper is already running, close it once before installing this
build so the automatic helper can own its lifecycle.

Regression tests launch a real helper process, send duplicate gameplay snapshots,
verify one reward, reject a second helper, close the parent, and verify clean exit
and saved rewards. Full Windows cross-build and export checks are separate from
live Windows/CS2 testing; that startup/exit flow still needs your in-game check.

## Changes retained from build 02

- Mixed normal/StatTrak contracts use the input fraction for StatTrak probability (3/10 = 30%, 2/5 = 40%). Gold StatTrak outcomes use knives; glove-only pools always stay normal for mixed contracts and refuse all-StatTrak contracts atomically. Intentional contract StatTrak survives startup repair.
- If the native recipe menu filters the other variant, keep CS2 running and run `mixed_tradeup.cmd`, choose a rarity and the printed local IDs, then confirm once. It submits the normal local Craft request; it never edits your inventory file.
- Eligible cases with a validated gold pool can now drop golds. Base chance 0.26%, soft pity begins on the 10th opening, increasing linearly to 100% on the 100th. Gold resets the saved shared case counter. Capsules, trade-ups and Armory purchases do not affect it. Cases with no validated gold pool do not advance pity.
- Terminals have a separate saved pity counter per terminal type, advanced only on a new offer reveal. A top offer resets it even if declined. Dead Hand targets gold gloves (base 0.26%); Genesis targets its highest weapon tier (Covert, base 0.64%). The same configurable soft/hard thresholds apply. Unseal/reconnect/accept/stale requests do not advance it.
- The supplied latest log shows revealed terminal offers but **zero Store PurchaseInit requests** in the build-01 session. Native terminal checkout is still unresolved. Workaround: reveal the offer, keep CS2 running, run `terminal_purchase.cmd`, select the terminal and confirm. It keeps the displayed offer, consumes that terminal, saves and updates your inventory, locally and free. Close the laptop afterwards.
- Every newly observed completed match grants **three items**, each independently 50% a keyed case or 50% a normal weapon skin of rarity blue through red. Drops do not require an Armory Pass. No automatic key, gold or Contraband match drop. Count/chance/minimum rarity are configurable. Completion counters and granted items persist together, so repeated snapshots/restarts do not duplicate drops. No retrospective payout for old matches absent from the bridge history.
- Native match-drop notification messages follow the new inventory objects. Their live presentation still needs testing; receiving inventory items and displaying a match panel are separate checks.
- The GSI window prints first receipt, earned XP, completed matches and waiting/stale-data diagnostics. Your supplied save has five active passes but XP/reward cursor both zero, so none of its gameplay XP reached the coordinator. Build 03 starts it automatically. Check `cs2_gc_rewards.log` for received/waiting/earned messages; if the config was just installed, restart the game once. Send that log with `cs2_gc_log.txt` if XP remains zero.
- `cs2_gc_gameplay.cfg` controls XP events and switches, XP per star, drop count/odds, mixed contracts, pity, terminals, rotation, local rating and Howl offer policy. Saving zero stars, level 1/0 XP defaults and pass caps remain intact. Unknown/duplicate/out-of-range keys are rejected. The helper stops on invalid config; the DLL logs an error and uses documented defaults.

### Local Premier foundation

The GSI bridge records competitive-mode wins/losses/ties only when it observes a live-to-gameover transition with valid final T/CT scores. Numeric rating stays hidden until **10 wins**. Default local formula: start 1,000, win +300, loss -100, tie 0, range 0–35,000. All are configurable. Rating is saved with bridge history, independently of the profile's XP level. This is a local model, not Valve's private formula or online rating.

The helper writes `game/csgo/cfg/cs2_gc_premier_bots.cfg`; execute `exec cs2_gc_premier_bots` in the local server console **before spawning bots**. Current policy maps under 5k/10k/15k/above to normal bot difficulty values 0/1/2/3. Automatic application to spawned bots, the Play-menu control and native Premier rating/placement/rank-change panels remain pending. The public CS2 competitive config confirms `bot_difficulty` exists; this is not proof the UI integration works.

### Armory rotation and Howl

Rotation policy is UTC-aligned **15 minutes**, six active goods, wrapping across all schema Armory goods. Optional local Howl offer defaults to 40 stars and participates in that roster; it resolves the existing CS2 finish and retains Contraband rarity, and is never accepted outside its active window. These backend rules have offline tests. **The current native page does not yet show or sell the new Howl offer.** Its native purchase API takes schema shop indexes; inventing an index will not add a working offer.

`rotate_armory.py` prepares a countdown/visibility SOURCE override from the target client's extracted `xpshop.js`. It needs that game's Panorama compilation and mounting. Set `armory_howl_enabled=0` to generate the base rotation override until a verified native Howl redeem bridge exists; the generator refuses a mismatched roster. Keep `armory_rotation_enforce=0` until the matching UI is mounted. Native rotation/countdown/Howl are **not installed by this DLL**. Changing rotation options requires regenerating the UI override too.

## Earlier changes retained

- Single-item Store coupons grant the actual capsule/package/sticker/charm directly. They do not open the purchased container. Old coupon envelopes still have their old unlock path.
- Armory collection rolls cannot accidentally receive hidden StatTrak. Startup repairs impossible StatTrak flags on known collection-only skins; valid case StatTrak is retained and encoded visibly.
- Five Covert skins can produce golds. All-StatTrak gold contracts produce knives only. Missing/incompatible rare-pool data rejects a contract without consuming its inputs. Gold membership comes from the versioned CSGO-API catalogue (see `data/CSGO-API-LICENSE`), validated against the game's schema. The local model chooses supplied collections proportionally and listed outcomes uniformly; this is not a claim of exact Valve phase odds.
- Terminals unseal, retain a saved offer, decline to the next offer, and accept that same offer through the free/local Store. Counter checks prevent stale-request rerolls. Local defaults: five offers and seven-day lifetime; supplied `volatile_limit` is respected up to 100. The displayed purchase price is zero. This does not connect to Steam payments.
- The bot server receives a separate GC welcome/cache queue. Equipped weapon objects include `equipped_state`; server callbacks are routed separately from client callbacks.

## Verification and remaining work

Offline regression suites and Windows x64 cross-compilation pass. The test DLL's export list matches the 1,046 exports in the supplied existing proxy and forwards directly to `steam_api64_real`, not through the previous proxy. It depends only on Windows system runtimes. No original game DLL, schema, replay, account data or uploaded log is distributed.

**Live testing is still required** for held bot-match skins, XP/star delivery, mixed-contract UI/helper behavior, terminal helper acceptance, case/terminal pity, match-drop presentation and Covert results. A native bot-match XP/skill-rank panel is not implemented yet; profile updates alone do not open it. The old protocol fingerprint still refers to build 25947352; the external schema checks used build 25966348's real schema, but the original fingerprint hashes have not been relabelled as that build.

The extra “Open to Keep” confirmation is Panorama-side and remains in this DLL. `tools/skip_container_confirm.py` prepares a source override for only local-GC item IDs; it must be compiled and mounted with the target game's Panorama toolchain before the confirmation can be removed. No unverified UI override is installed by this ZIP. Existing gaps such as music/patch/graffiti-specific drops and X-Ray package unlocking are not silently declared fixed. Standard case gold drops and saved pity are now included as described above.

Send `cs2_gc_log.txt` from this test and describe which action failed. Avoid sharing the GSI state/config files publicly: they include a local player identifier or token.

## Helper request recovery

Mixed contracts and terminal helper purchases use pending/processing/result files beside the DLL. Submit once and wait for the matching result token. A `processing` file left after a crash is intentionally not replayed: inspect inventory and the GC log before deleting it or resubmitting. Never edit or delete your saved inventory to clear a helper request.

The wider approved port order and CS2 limitations are in `FEATURE-ROADMAP.md`. The legacy Star Shop, Danger Zone achievements and service-medal achievement rewards are excluded.

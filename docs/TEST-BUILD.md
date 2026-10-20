# Codex test build 2026-10-20-04

## Install and test

1. Close CS2. Back up your current proxy `steam_api64.dll` and `cs2_gc_inventory.txt`.
2. Copy the test ZIP's contents to `game/bin/win64`, beside your existing `steam_api64_real.dll`, `items_game.txt`, config and replay directory. Keep those existing files.
3. `cs2_gc_gameplay.cfg` contains all gameplay options with comments. Defaults match the requests. Close/restart CS2 after edits; its background helper exits with it. Existing proxy/account configuration is separate and is not replaced. See the limitations below for native UI features.
4. With CS2 closed, run `grant_test_items.cmd` once (Python 3 required). It adds 229 schema-validated test items and makes a timestamped inventory backup. Existing items, stars, pass progress and rank remain intact. Running it again adds another batch.
5. Close any old manual rewards window. Leave the bundled Python helpers beside the DLL. **The DLL now starts the rewards bridge automatically in the background** when local `-insecure` CS2 runs, and the bridge stops when that game closes. Python 3 must remain installed. If GSI has never been configured, the first launch installs its dedicated config; restart CS2 once to load it. No manual helper launch is needed after that.
6. Launch CS2 with `-insecure` in local mode. Wait for the rewards log to say `Native trade-up UI: prepared`, then fully close and restart CS2 once. The next launch loads the native shared trade-up recipes. Activate an Armory Pass to earn stars and play a bot match.

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

## New in build 04

- Native Premier rank-cache updates use the saved GSI rating/wins. The supplied
  logs record placement win **1/10**; the profile should now say **9 more wins**
  after that save loads. The rating remains zero until ten wins. Welcome and XP
  profile updates replace stale recorded Premier entries too.
- The native scoreboard override keeps the unranked Premier emblem visible,
  then renders the saved rating after placements. Bot emblems can mirror your
  local badge; these are cosmetic, not independent bot careers. The old server
  scoreboard stats remain the fallback for other players/modes.
- Native terminal reload message **2536**, seen unanswered in your new log, now
  returns the saved terminal and offer followed by the expected notification.
  It never advances pity or rerolls. A generated local Store reply adds missing
  terminal price-sheet entries from your real schema, preserving original
  response fields/currencies and leaving the replay untouched. **Use the laptop's
  normal Buy button; no batch file. Native checkout needs your retest.**
- Every newly earned profile level grants three additional items, independently
  50% case / 50% blue-through-red skin, with **no weekly cooldown**. This is
  separate from three match drops. Multiple level gains remain queued across
  restarts, paying once each. Old saves begin at their current level; no invented
  historical rewards. Default profile cap remains 40. These are direct local
  drops, not an implemented weekly-care-package selection screen.
- Random Armory collections/packs now have independent saved pity counters:
  soft starts roll 10, highest available tier guaranteed by roll 100, reset on
  that tier. Top-tier base chance is at least 0.64%, never reducing a higher
  existing base; lower-tier weights are preserved proportionally. Collections
  with five/six rarity tiers now have nonzero weights for those upper tiers.
  Fixed goods, cases bought from the Armory and limited skins/Howl do not advance
  this counter. Failed/expired/unaffordable purchases do not advance it either.
- One normal Open click can skip the extra Open-to-Keep confirmation and begin
  the animation. Open-to-Rent can be hidden on local containers. Each has a config
  switch; real inventory/rental and X-Ray restricted paths retain their behavior.

The background helper reads only the needed assets from your installed VPKs and
prepares separate scoreboard/confirmation overrides. VPKs stay read-only. The
supported compiled script format is checked before patching; changed layouts
are logged and skipped without stopping rewards. First-edit gameinfo backups
and ownership/hash checks preserve other addons and external edits. **Restart
CS2 once after preparation** to mount these resources; enabling/disabling UI
settings also needs that preparation plus restart. This is new code for testing,
not proof the target engine loaded it successfully. Check `cs2_gc_rewards.log`.

New options include `premier_scoreboard`, `premier_bot_badges`,
`level_drops_enabled`, `level_drop_count`, `skip_container_confirmation`,
`hide_rent_button`, `armory_pity_enabled`, `armory_pity_soft_at`,
`armory_pity_hard_at`, and `armory_top_per_10000`. No game-console stars/grant
command has been registered in this build. Optional developer transports remain
in the repository; the test ZIP does not require or include terminal/trade-up
batch launchers.

### Native mixed trade-ups

Use CS2's normal Trade Up screen. The background helper prepares an override from
`items_game.txt` beside your DLL, then adds one dedicated `Game cs2_gc_native`
search path to your installed `game/csgo/gameinfo.gi`. **Restart CS2 once after
preparation**; the running game cannot reload its recipe schema. No command
window or per-contract helper is required for this test.

Only six normal recipe input-quality values and six duplicate StatTrak recipe
enable flags change. Existing normal recipes accept normal and StatTrak inputs;
duplicate StatTrak recipes are disabled so either first selection can use the
shared recipe. All other schema text, including items, finishes and outputs, is
preserved. The original `items_game.txt` is never edited. A first-edit
`gameinfo.gi.cs2_gc_native_backup` is retained; other addon paths are preserved.

Test the same rarity with **normal first, then StatTrak first**, and try a mixed
five-Covert contract too. The coordinator still rolls StatTrak from its fraction
of actual inputs. Offline checks validate the supplied build-25966348 recipes,
reversible mounting and normal-recipe Craft responses for both selection orders.
**Native selection and mounting still require your live CS2 test.** If unchanged,
send `cs2_gc_rewards.log` and `cs2_gc_log.txt` after the full restart.

Set `mixed_stattrak_tradeups=0`, launch once for the helper to remove its owned
mount line, then restart to restore homogeneous native recipes. It does not
restore an old whole gameinfo over other addons. Refresh your extracted source
schema after game updates; preparation refuses unexpected recipe layouts or an
externally edited override. Setup errors are logged without stopping XP/stars.
Python and all bundled modules, including `native_tradeups.py`, are required.

The user confirmed star persistence and match drops in build 03. Their new logs
confirm **1,314 earned XP**, **three saved match drops**, **one Premier win** and
five passes advancing the star balance **26 -> 41**. The profile XP bar is visible.
The end-of-match drop screen and XP/rank panels are still absent; those panels
are not implemented by build 04. This evidence does not live-validate the new DLL.

## Background rewards retained from build 03

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
The manual script remains available in the repository for diagnostics; keep its window open only when choosing that mode.
If an old manual helper is already running, close it once before installing this
build so the automatic helper can own its lifecycle.

Regression tests launch a real helper process, send duplicate gameplay snapshots,
verify one reward, reject a second helper, close the parent, and verify clean exit
and saved rewards. Full Windows cross-build and export checks are separate from
live Windows/CS2 testing; that startup/exit flow was subsequently confirmed by the supplied build-03 helper log.

## Changes retained from build 02

- Mixed normal/StatTrak contracts use the input fraction for StatTrak probability (3/10 = 30%, 2/5 = 40%). Gold StatTrak outcomes use knives; glove-only pools always stay normal for mixed contracts and refuse all-StatTrak contracts atomically. Intentional contract StatTrak survives startup repair.
- `mixed_tradeup.cmd` remains an optional diagnostic fallback. Build 04 targets the native screen through the recipe override described above; use the native screen for the requested test.
- Eligible cases with a validated gold pool can now drop golds. Base chance 0.26%, soft pity begins on the 10th opening, increasing linearly to 100% on the 100th. Gold resets the saved shared case counter. Capsules, trade-ups and Armory purchases do not affect it. Cases with no validated gold pool do not advance pity.
- Terminals have a separate saved pity counter per terminal type, advanced only on a new offer reveal. A top offer resets it even if declined. Dead Hand targets gold gloves (base 0.26%); Genesis targets its highest weapon tier (Covert, base 0.64%). The same configurable soft/hard thresholds apply. Unseal/reconnect/accept/stale requests do not advance it.
- The supplied latest log shows revealed terminal offers but **zero Store PurchaseInit requests** in the build-01 session. Native terminal checkout is still unresolved. Build 04 adds native reload/price-sheet repairs above; retest the in-game Buy button. The old developer helper remains only in the repository.
- Every newly observed completed match grants **three items**, each independently 50% a keyed case or 50% a normal weapon skin of rarity blue through red. Drops do not require an Armory Pass. No automatic key, gold or Contraband match drop. Count/chance/minimum rarity are configurable. Completion counters and granted items persist together, so repeated snapshots/restarts do not duplicate drops. No retrospective payout for old matches absent from the bridge history.
- Native match-drop notification messages follow the new inventory objects. Their live presentation still needs testing; receiving inventory items and displaying a match panel are separate checks.
- The GSI window prints first receipt, earned XP, completed matches and waiting/stale-data diagnostics. Your supplied save has five active passes but XP/reward cursor both zero, so none of its gameplay XP reached the coordinator. Build 03 starts it automatically. Check `cs2_gc_rewards.log` for received/waiting/earned messages; if the config was just installed, restart the game once. Send that log with `cs2_gc_log.txt` if XP remains zero.
- `cs2_gc_gameplay.cfg` controls XP events and switches, XP per star, drop count/odds, mixed contracts, pity, terminals, rotation, local rating and Howl offer policy. Saving zero stars, level 1/0 XP defaults and pass caps remain intact. Unknown/duplicate/out-of-range keys are rejected. The helper stops on invalid config; the DLL logs an error and uses documented defaults.

### Local Premier foundation

The GSI bridge records competitive-mode wins/losses/ties only when it observes a live-to-gameover transition with valid final T/CT scores. Numeric rating stays hidden until **10 wins**. Default local formula: start 1,000, win +300, loss -100, tie 0, range 0–35,000. All are configurable. Rating is saved with bridge history, independently of the profile's XP level. This is a local model, not Valve's private formula or online rating.

The helper writes `game/csgo/cfg/cs2_gc_premier_bots.cfg`; execute `exec cs2_gc_premier_bots` in the local server console **before spawning bots**. Current policy maps under 5k/10k/15k/above to normal bot difficulty values 0/1/2/3. Build 04 connects profile placement/rating and scoreboard badges for live testing. Automatic application to spawned bots, the Play-menu control and native end-of-match rank-change panels remain pending. The public CS2 competitive config confirms `bot_difficulty` exists; this is not proof the UI integration works.

### Armory rotation and Howl

Rotation policy is UTC-aligned **15 minutes**, six active goods, wrapping across all schema Armory goods. Optional local Howl offer defaults to 40 stars and participates in that roster; it resolves the existing CS2 finish and retains Contraband rarity, and is never accepted outside its active window. These backend rules have offline tests. **The current native page does not yet show or sell the new Howl offer.** Its native purchase API takes schema shop indexes; inventing an index will not add a working offer. The user requested adding Howl alongside usual skins in the existing **Limited Edition Item** slot, with the 15-minute timer; do not create a separate Howl store/category.

`rotate_armory.py` prepares a countdown/visibility SOURCE override from the target client's extracted `xpshop.js`. It needs that game's Panorama compilation and mounting. Set `armory_howl_enabled=0` to generate the base rotation override until a verified native Howl redeem bridge exists; the generator refuses a mismatched roster. Keep `armory_rotation_enforce=0` until the matching UI is mounted. Native rotation/countdown/Howl are **not installed by this DLL**. Changing rotation options requires regenerating the UI override too.

## Earlier changes retained

- Single-item Store coupons grant the actual capsule/package/sticker/charm directly. They do not open the purchased container. Old coupon envelopes still have their old unlock path.
- Armory collection rolls cannot accidentally receive hidden StatTrak. Startup repairs impossible StatTrak flags on known collection-only skins; valid case StatTrak is retained and encoded visibly.
- Five Covert skins can produce golds. All-StatTrak gold contracts produce knives only. Missing/incompatible rare-pool data rejects a contract without consuming its inputs. Gold membership comes from the versioned CSGO-API catalogue (see `data/CSGO-API-LICENSE`), validated against the game's schema. The local model chooses supplied collections proportionally and listed outcomes uniformly; this is not a claim of exact Valve phase odds.
- Terminals unseal, retain a saved offer, decline to the next offer, and accept that same offer through the free/local Store. Counter checks prevent stale-request rerolls. Local defaults: five offers and seven-day lifetime; supplied `volatile_limit` is respected up to 100. The displayed purchase price is zero. This does not connect to Steam payments.
- The bot server receives a separate GC welcome/cache queue. Equipped weapon objects include `equipped_state`; server callbacks are routed separately from client callbacks.

## Verification and remaining work

Offline regression suites and Windows x64 cross-compilation pass. The test DLL's export list matches the 1,046 exports in the supplied existing proxy and forwards directly to `steam_api64_real`, not through the previous proxy. It depends only on Windows system runtimes. No original game DLL, schema, replay, account data or uploaded log is distributed.

**Live testing is still required** for build-04 native mixed-contract selection, scoreboard/placement updates, native terminal checkout, level drops, Armory pity and one-click container opening; held bot-match skins and Covert/gold results also remain checks. Build-03 XP/stars/drops were confirmed as described above. A native bot-match XP/skill-rank panel is not implemented yet; profile updates alone do not open it. The old protocol fingerprint still refers to build 25947352; the external schema checks used build 25966348's real schema, but the original fingerprint hashes have not been relabelled as that build.

The extra “Open to Keep” confirmation is Panorama-side; build 04 now prepares a narrowly scoped native override as described above. `tools/skip_container_confirm.py` restricts the bypass to local-GC item IDs. The background helper prepares a supported compiled resource from the installed archive and mounts a dedicated folder; the ZIP itself ships no proprietary resource. Existing gaps such as music/patch/graffiti-specific drops and X-Ray package unlocking are not silently declared fixed. Standard case gold drops and saved pity are now included as described above.

Send `cs2_gc_log.txt` from this test and describe which action failed. Avoid sharing the GSI state/config files publicly: they include a local player identifier or token.

## Helper request recovery

Mixed contracts and terminal helper purchases use pending/processing/result files beside the DLL. Submit once and wait for the matching result token. A `processing` file left after a crash is intentionally not replayed: inspect inventory and the GC log before deleting it or resubmitting. Never edit or delete your saved inventory to clear a helper request.

The wider approved port order and CS2 limitations are in `FEATURE-ROADMAP.md`. The legacy Star Shop, Danger Zone achievements and service-medal achievement rewards are excluded.

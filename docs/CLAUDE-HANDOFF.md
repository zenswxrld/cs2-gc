# Current handoff: Codex build 17 (21 October 2026 local time)

Follow-up on the same PR #9 branch. User says Armory works but requested visual cleanup: removed the worded category tabs, enlarged/centered arrows/page number/countdown, balanced rows across pages, and pinned the limited offer on the landing page (retained on later pages). Interleaved offer types to keep the page balanced. Agent tile art now sits on the right; agent inspection has up to 8 named cards with its own pager, a smaller title and reserved purchase-bar space, rather than all 63 overlapping. Preview paging does not affect the random recruitment pool.

User additionally requested terminals in the Armory. Added a separate `terminal` rotation slot, default 1 visible at 2 stars, generated from installed volatile terminal definitions (Genesis and Dead Hand in the inspected schema). C++ and native UI use matching counts; purchases grant a closed real terminal and reuse existing unsealing. `terminals_enabled=0` hides the slot. New configurable keys: `armory_terminal_slots`, `armory_terminal_price`. No schema item/loot definitions are created.

Latest user confirmation: bottom Sell for Stars is correctly positioned. Graffiti is broken; user explicitly said to hold that for later. Do not claim graffiti is fixed. Stock XP animation and console log transport remain open. Keep the working pre-launch resource preparation from build 16.

New layout and terminal offers still need target-client verification. See TEST-BUILD.md. Existing notes below are archival.

---

# Current handoff: Codex build 16 (20 October 2026)

Follow-up on PR #9, branch `codex/armory-agents-weekly-drops-and-match-screens`. Full checklist: [TEST-BUILD.md](TEST-BUILD.md).

**Live finding:** user's build-15 helper could not replace mounted `cs2_gc_native`, `cs2_gc_armory` and `cs2_gc_scoreboard` VPKs (Windows error 5). GC loaded 120 offers while the client retained old six-slot UI/rating behavior. `cs2_gc_debug.exe` now runs new `prepare_native.py` to completion **before** starting Steam/CS2, aborting with a log on failure. Keep this order; preparing only after DLL/game load cannot update locked packs.

**Confirmed by user:** native selling, weekly collection drops, Rent-button removal and one-click opening work. Results tab/rating delta appears but was clipped. Existing working mixed inputs, held skins, certificates and rotation remain intact.

**Follow-up changes:** Community Market actions replaced by bottom Sell for Stars; native Armory category filters/countdown/4-3-4 row paging and explicit limited artwork/current-entry routing; stable individual bot ratings using real scoreboard slots rather than an unverified name API; full-height centered results card (stock parent is 300px); detected reward IDs retained through acknowledgement; configurable 20s tab/45s local match delay. Music definitions/id attribute/persistence/guaranteed ST capsule lists now supported. Single guaranteed old Store envelopes migrate in place without new IDs or duplicate items. Unknown/bundled offers and missing historical generic music IDs are left alone.

Validation: 15 suites pass; Windows debug/release cross-builds; complete pre-launch override pipeline using inspected native scripts and version-2 resources, readback/syntax check from built VPKs, identical second-pass VPK bytes. New live validation remains necessary. Stock XP animation, console log transport and terminal price-cap semantics remain open.

---

# Current handoff: Codex build 15 (20 October 2026)

Branch: `codex/armory-agents-weekly-drops-and-match-screens`, based on your `schema-loader` at `e6f93092f28f0664e479fd5b29080abdc876b44d`. See [TEST-BUILD.md](TEST-BUILD.md) for exact behavior and live checklist.

This update adds configurable multi-group rotation, the official random-agent offer, expanded OfflineCS capsule choices, native limited artwork and certificates, a balance-area timer, weekly-only blue+ weapon rewards, varied local/bot Premier ratings, OfflineCS-style native sales and a native offline end-match rewards/rating tab. `item_sales.cpp` owns pricing and validation; the Panorama menu submits existing CMsgDeleteItem 1004, with the same native delete-to-sell approach as OfflineCS. Container refunds use CS2 Armory costs, not higher old shop prices. The test ZIP must include **all** Python modules, notably new `native_item_sales.py`, `native_endmatch.py`, and your `vpk_pack.py` / `vpk_signatures.py` / `native_offer_numbers.py`.

Preserve your working `.vts_c` / resource-version-2 loader, VPK + signatures mechanism, mixed recipe fix, native trade-ups, terminal certificates and held-skin path. No new item/paint/loot-list definitions are created. Agent shop rows reference an existing official agent list; the backend chooses among the same 63 eligible official agents shown by the UI.

Verified: 15 test suites; real-schema redemption of all 120 catalogue rows, including one agent row and five limited certificates; 40 blue+ weekly finishes; actual native script patch syntax; Windows debug/release cross-builds. New live-client behavior remains unverified. The end-match tab shows actual cached rating/profile level/new unacknowledged drops. It does **not** claim to fix stock XP animation/data-ready flags. It needs a pre-reward inventory baseline and deliberately avoids presenting older unacknowledged items as fresh rewards.

Still open: stock XP animation and stock rank screen data readiness; target-client render/layout and native delete request verification; console echo lines missing from console.log; terminal monetary price cap must not be treated as an offer count. Bot names/chat/personality are outside this update. Existing history below is archival and can contain superseded failures/limits.

---

# Build 05: current status (supersedes historical notes below)

Latest steering: automatic debug launch flags AND exec, disabled for release.
CS2_GC_DEBUG_TOOLS defaultsOFF; test build explicitlyON. Debug-only Windows GUI
launcher prepares nonce/aliases before invoking installed Steam.exe -applaunch730
-insecure -condebug +exec cs2_gc_console. HKCU SteamExe lookup, checks CS2 closed
and installed game folder. No Steam config/autoexec mutations. Helper reuses boot
nonce, retains rotation offset across same-game helper restart. Release proxy does
not poll console controls or launch helper with --debug-console; launcher target
is absent. Keep -insecure for offline operation, omit debug log/exec on release.
Debug launcher and proxy cross-build pass; separate Windows release build with
DEBUG_TOOLS=OFF passes and omits the launcher/control startup. 13 suites pass.
Launcher is not live Windows/Steam tested.

Validation: all13 Linux core/Python suites pass, Windows x64 core/proxy build passes.
1,046 export names match supplied proxy; imports onlyKERNEL32/msvcrt. Generated
25966348 catalogue resolves every item/list; all active goods redeemed over42
rotation cycles in an external offline integration check. Generated full native
xpshop.js passes Node syntax check. No native engine/UI validation claimed.

User requests: every Armory category rotates within its matching native slot,
including current/previous Armory collections, sticker sheets, charms, limited
items; all standard keyed cases and curated popular/team capsules. In-game test
commands for stars/rotation, no purchase/trade-up BAT workflows. Push all changes.

Latest live evidence from build04: profile placement now says one win/nine left;
stars persist. Mixed native picker still segregates after restart. Terminal Buy
still fails. Helper logs: scoreboard/rental `.vjs_c` not found, Store setup
`Corrupt input data`; native recipes prepared then installed. Latest2536 returns
saved offer correctly, but no subsequent native Store checkout is proven. Need
actual `cs2_gc_replay/2501.bin` to debug LZMA, not guessed decompression patches.
End-of-match drops/XP/rank panels remain unimplemented despite inventory rewards.

Build05 changes:
- Loadout state moved from ephemeral LiveInventory slots to saved Inventory slots;
  validate class/slot uniqueness and referenced definition, remove consumed slots,
  save after native equip request. Restored welcome/server item state uses saved
  slots. No reconstruction of selections absent from old saves.
- VPK lookup accepts raw .js/.vjs and compiled .js_c/.vjs_c, normalizes slash/case,
  uses actual installed path and representation. Ambiguity/CRC/layout rejects.
  First04 failures were exact-extension assumptions. Live mount still unproven.
- Native recipes additionally mount Mod alongside Game; this is a test adjustment,
  not evidence that the native craft quality filter now accepts mixtures.
- armory_rotation_catalog.py replaces only campaign11 shop rows, referencing real
  existing definitions/lists. Active schema25966348 gives42cases/34capsules/
  6collections/6stickerpacks/4charmpacks/5limiteditems. Limited four historic
  set_xpshop_wpn_01..04 lists plus single-Howl removed_items. Item/paint/loot-list
  definitions unchanged. AGENTS narrow exception updated for explicit user scope.
- Helper prepares this schema plus recipes and both owned mounts, with backup,
  hashes and manifest. CRC stamp validates original and generated text before
  proxy loads same catalogue. First preparation requires full restart. UI receives
  categories through generated settings, uses actual native shop indexes and
  ActionRedeemOperationGoods. Source patch mounts xpshop via normal UI installer.
- RotationAt and native JS independently sort names within categories and select
  cycle%poolsize, one/category. Every pool advances900s, with timer. Stale native
  inspect returns to main; stale backend buys reject before spending. Generated
  category slots enforce automatically; legacy uncategorised rotation retains
  config fallback. Howl native CRC now lootlist:removed_items, rarity7 preserved.
- ConsoleControls generates session aliases: exec cs2_gc_console, then
  cs2_gc_give_stars (+100), cs2_gc_give_stars_1000, cs2_gc_force_rotation.
  Requires -condebug. Exact freshly appended nonce lines only, cumulative saved
  stars cursor, PID-gated control snapshot, no direct inventory writes by Python.
  Force increments user-info cs2_gc_rotation_offset; native JS reads via existing
  GameInterfaceAPI.GetSettingString, GC polls offset. These aliases require live
  validation. Setup CFG initializes offset, so exec once/launch, not mid-session.
- TestBuild doc rewritten around current behavior/evidence; historical claims
  below must not be read as current proof. Native UI/engine tests remain separate
  from Linux core/Python/Node and Windows cross-compilation.

# Build 04 additions after live build-03 test

Supersedes older pending claims below. User supplied new logs: helper earned1314XP,
completed1match, Premierplacement1/10; proxy saved three match drops and five pass
tracks1315, stars26->41. Profile XP bar visible; EOM drops/XP/skill panels still absent.
Native Terminal2536 request (subjectfield2/counterfield4) was unanswered. User wants
native Buy and trade-ups, no batch workflows; preferences for test console commands
recorded but no console command registration is implemented. ZIP omits those batch
purchase/trade-up launchers. Original helper transports remain diagnostic source.

Native Premier: helper atomically publishes cs2_gc_premier.txt (rating wins placements).
Proxy polls one-second; LocalGameCoordinator replaces captured type11 in9194 and
profilefield20 (welcome and XP updates), preventing old captured zero wins restoring.
Ranktype11 is confirmed in the actual supplied9194 capture. Native scoreboard patch
uses existing RatingEmblem.SetXuid plus FriendsListAPI.GetFriendCompetitiveRank/Wins
(...,'Premier') from the pinned playercard source. Zero rating now renders unranked;
cache key includes wins so placements update even with zero rank. Other humans/modes,
queued matchmaking/demos retain original branch. Bot badges optionally mirror local
badge; not independent earned careers. Native presentation still needs live validation.

native_resources.py reads installed VPK v1/v2 entries with preload/chunk/CRC checks,
reads header12/version4 plaintext script DATA, patches only validated source anchors,
reserializes block offsets preserving other metadata and omitting stale SrMa debugmap.
Format grounded in ValveResourceFormat Resource.cs/Panorama.cs and ValvePak Package.Read.cs;
no guessed engine offsets, no game assets shipped. Unsupported layout logs/skips.
Shared installer uses separate owned folders, gameinfo backups, external-edit protection
and config-driven unmount. Scoreboard and rental-bar overrides require one restart.
Rental patch: skip second Open-to-Keep dialog; hide RentBtn only on local normal path;
X-Ray restrictions and real inventory remain unchanged. Both configurable.

Terminal: 2536 handler replies saved terminal/offer SO updates + notification1012;
checks current counter, no reroll/save/pity mutation. native_store.py copies the local
2501 price sheet, adds missing explicit volatile-container names from real schema,
preserves original protobuf fields/currencies/banner and emits cs2_gc_store_2501.bin.
Proxy reads that generated reply at Store requests with recorded fallback. Original
replay unchanged. Intended to unblock native StoreItemPurchase(def(container)); end-to-end
native Buy remains live test, do not label proven fixed. Actual schema resolves both
crate_community_36 and crate_community_37. Local checkout still free.

Per-level rewards: independent saved level_reward_total cursor (starting level1 excluded),
three items/level by default using same50/50 case/blue+ weapon pool. One pending level/poll;
queued gains survive restart; cursor+items save together. No weekly clock/cooldown, no new
weekly care-package picker. Old saves initialise from current level, no retroactive grants.
Profile cap40 unchanged; match drops stay separate and independent of level switch.

Armory random loot-list pity: map by collection name saved with inventory, soft10/hard100,
top-tier base floor64/10000 without reducing higher existing odds, reset on top-tierhit.
Collections with fifth/sixth tiers get weights13/3 so upper rarities are reachable too.
Lower tiers retain relative weights. Plain/fixed/limited Howl purchases don't advance pity;
failed buys leave all state intact. New options in example cfg. New pity starts at0.

Howl scope clarified: use existing native Limited Edition Item slot alongside usual
limited skins and 15-minute refresh; no separate Howl category. Native rotation/timer/
Howl redeem bridge still pending. Automatic bot difficulty and EOM panel integration
also remain pending. Do not mislabel source generators/backend policies as installed UI.

---

# Current follow-up: build 04, native mixed StatTrak recipes

User explicitly rejected the mixed_tradeup.cmd workaround and wants the native
CS2 screen. native_tradeups.py now parses the supplied full schema with token
spans, broadens exactly six existing normal recipe qualities from
unique,tournament to unique,strange,tournament, and disables the six duplicate
StatTrak recipes. This routes either first-item variant through a shared recipe.
Input counts, rarity, output definitions and all other schema bytes are retained.

The background rewards helper generates game/cs2_gc_native/scripts/items/items_game.txt
from the original beside the DLL, then prepends its owned Game search path in
installed game/csgo/gameinfo.gi. Original schema is untouched; first gameinfo edit
is backed up. Manifest/hash ownership prevents overwriting an unrelated addon or
external edits. Setting mixed_stattrak_tradeups=0 removes only the owned mount.
Both enabling/disabling need one full CS2 restart after helper preparation.
Setup failures log and leave rewards running. Add native_tradeups.py to the ZIP.
AGENTS.md records the user's narrowly scoped exception; no custom cases, paint
kits, item changes or broad schema rewriting are authorised.

Inspected build25966348 schema has normal recipes0..5 and StatTrak10..15;
normal input qualities are unique,tournament (not just unique). crafting.js
uses the native recipe inventory filter and InventoryAPI craft readiness; merely
changing the button would not solve filtering. Source reference is SteamTracking
GameTracking-CS2 commit5ab573fa8afb5b8db98869d79ed79399fca6e747. Recipe patch is
idempotent against the actual supplied schema. Actual pinned gameinfo search-path
mount/unmount is exactly reversible. New tests cover those invariants, backups,
other addons and external edits; endpoint tests cover mixed inputs, both first
selection variants, using normal recipe0 and receiving a valid native response.

Native engine loading/selection is NOT live-confirmed. Test normal-first and
StatTrak-first plus mixed five-Coverts after one restart; inspect both logs.
No Panorama compilation is needed for this recipe-only approach. Refresh the
extracted original schema after game updates to avoid mounting stale item data.

User confirmed stars persist after restart on build03. They are now testing
XP/stars/drops and will send logs after the match. Earnings/drop results remain
pending. Premier is still only the saved local model/manual difficulty cfg;
native Premier panels and automatic bot difficulty have not been implemented.

---

# Current follow-up: build 03, automatic background rewards

User wants to stop manually launching/leaving a rewards window open. Source now
starts gsi_rewards.py from the first normal SteamAPI_RunCallbacks in local,
-insecure mode; never from DllMain and never in capture/normal online mode.
Windows CreateProcessW prefers pyw/pythonw, uses CREATE_NO_WINDOW, quotes every
path/argument, sets the proxy directory and passes the actual game PID/log path.
Game code monitors only the child process handle, never waits for it, and limits
restarts to three per session. rewards_auto_start defaults1; 0 retains manual
start_rewards.cmd diagnostic mode.

New rewards_runtime.py holds an OS file lock per proxy directory before any
state access, then Python binds the loopback port before loading/saving state.
This rejects both duplicate new helpers and a port owned by an older helper
without rewriting reward history. ParentProcess retains a SYNCHRONIZE handle to
the actual launching game on Windows, avoiding PID-reuse races; the HTTP loop
checks it at one-second idle intervals, closes and exits when CS2 closes. No
scheduled tasks, Windows startup entries or services are installed.

Diagnostics: cs2_gc_rewards.log (one rotated previous log) and proxy startup
messages. Token/raw packet data never logged. Dedicated GSI cfg is written only
when missing/changed. First-ever setup during an already-started game may require
one restart to load GSI. Existing config/token/cursors are retained. Close an old
manual helper once when updating so the new game-owned helper can take over.

Tests cover real helper parent exit, single-instance lock/release, duplicate GSI
not paying twice, and port collisions not creating state. Windows argument quoting
and the config switch have core tests. Python 3 is still required on the user's
machine. Automatic startup/shutdown must still be verified in live Windows CS2.

---

# Current follow-up: build 02 (20 October 2026)

This section supersedes the build-01 implementation details below. Source remains on
`codex/bot-progression-terminals-and-test-build`, PR #5 against `schema-loader`.

User priorities: finish current inventory/progression/terminal fixes, then port the
OfflineCS bot/career/achievement features, easier first. Native Store/Armory only;
no legacy Star Shop. Use **Premier-style numeric CS Rating**, not Competitive
Silver-to-Global ranks, hidden until 10 placement wins. See FEATURE-ROADMAP.md.

Implemented this follow-up:

- Mixed StatTrak trade-ups use exact input fraction, including five-Coverts. Gold
  StatTrak rolls use compatible knife pools. Mixed glove-only outcomes stay normal;
  all-StatTrak glove-only contracts refuse atomically. Contract-origin StatTrak is
  explicitly saved so legacy collection repair does not erase intentional outputs.
- Case gold rolls now use validated pools. Saved case pity starts soft on opening
  10, hard on 100; separate per-definition terminal pity advances on reveals only,
  targeting golds where present and highest weapon tier otherwise. Configuration
  and counters persist; failure/stale requests do not consume or reroll.
- Authenticated loopback GSI bridge now publishes a separate completed-match cursor.
  Three independent 50/50 case/blue-through-red skin drops per observed completion;
  LocalGC queues SO creates plus 9137 preview notifications. Inventory completion
  cursor saves with the items; one backlog completion processed per poll.
- Runtime gameplay config is separate from existing proxy/account config:
  examples/cs2_gc_gameplay.cfg. Strict C++ and Python parsing; knobs for XP/stars,
  pass XP/star, drops, mixed contracts, pity, terminals, rotation, Premier and Howl.
  Pass units are stored and rescaled when config changes, then converted to native
  400-unit display; fixed profile levels remain 5000 XP, cap40, pass cap40, max5.
- Optional mixed_tradeup.cmd sends real local Craft messages through a tokenized
  local pending/processing/result transport. terminal_purchase.cmd invokes the
  same displayed-offer acceptance path used by normal Store finalization, without
  requiring the broken native checkout. Neither edits live inventory text.
- Latest user log (build01 session) has terminal offers but zero PurchaseInit
  messages. Native checkout not fixed; helper is a workaround. User save has
  rank1/XP0/reward_total0 and five tracks at1. No gameplay rewards were applied.
  Diagnose start_rewards.cmd/GSI delivery with new received/waiting/earned logs;
  do not claim the zero-star issue is proven fixed just from offline tests.
- Local Premier model in premier_rating.py: competitive-mode final team scores,
  +300/-100, initial1000, cap35000 by default; hidden until10wins. Persisted in
  bridge state alongside completion dedup. start_rewards writes a dedicated
  bot_difficulty cfg (0/1/2/3 at <5k/<10k/<15k/above); manual exec before bots
  spawn. Native profile/rating display, automatic server difficulty and end-match
  XP/rank screens remain pending. CS2 XpUpdate/ServerRankUpdate are server user
  messages, so queueing an arbitrary GC message is not a verified substitute.
- Armory rotation backend: stable name-sorted roster, six-slot windows, UTC900s.
  Enforcement defaults off until UI ready. rotate_armory.py prepares only the
  inspected xpshop.js source override with live countdown/hiding/expiry refresh.
  It has not been compiled/mounted/live-tested. Do not enable enforcement early.
- Howl resolves actual [cu_m4a1_howling]weapon_m4a1 from supplied schema; local
  rotating offer costs40 configurable stars, normal, valid wear, Contraband7.
  Schema and Python skin rarity now preserve explicit Contraband; Howl cannot
  enter Covert trade-ups. Backend timed purchase tested. Native API redemption
  is by schema shop_index, so Howl tile/purchase bridge remains pending. The UI
  generator refuses enabled Howl until that bridge exists, avoiding roster
  mismatch. No invented item IDs, schema edits or added custom finish.

Build02 docs clearly separate offline regression/Windows compile from live-client
validation. Keep uploaded logs/inventory/schema/binaries out of git and packages.
The ZIP contains no user's inventory, tokens or original game DLL. New helpers
and gameplay config must accompany the DLL; restart helper AND CS2 after edits.

---

# Handoff: Codex test 2026-10-20-01

Based on `schema-loader` commit `42150481ac7db513a64f4b6704cd3c0a1b8349c0` (PR #4). User authorized changes and asked that all source changes be pushed so Claude can continue. See [TEST-BUILD.md](TEST-BUILD.md) for installation, exact reward rules, limitations and verification.

## User reports and scope

- Normal ten-item contracts now work in the user's existing build. Keep this as live-confirmed for the predecessor, not a validation of the new binary.
- Five-Covert-to-gold contracts were absent; user explicitly requested native CS2 support.
- Store coupon envelopes require an unwanted extra unlock before the actual capsule/package appears.
- Armory stars reset at every launch; spending must persist.
- Local profile must default to level 1 with 0 XP. Earn XP and pass stars in bot matches.
- Terminals need to work.
- “Open to Keep” extra confirmation should be skipped if possible.
- Buy-screen skins preview correctly, but held weapons revert to default. New user log repeatedly sends `GCServerHello` 4007 without receiving `GCServerWelcome` 4005. This is evidence of a missing listen-server GC path, not proof that the new path fixes every skin issue.
- User requested a Windows test build and a batch of varied test items. The supplied proxy had 1,046 exports; all forwarders were verified to point directly to the original module before generating the replacement .def. Original uploads/logs remain out of git.

## Implementation

- Inventory persistence now owns optional `armory_credits` and a `progression` block: level, in-level XP and cumulative applied reward cursor. Zero is a saved balance. Config seeds only an inventory without a balance. Armory redeem saves balance alongside the item. New profiles patch welcome `game_data2` fields 17/18 to level 1 and native XP base 327680000, confirmed by the existing CS2 log/schema.
- `tools/gsi_rewards.py` is a Python-stdlib loopback GSI receiver. Auth token, local-player identity, live-phase filters and persisted cumulative snapshots prevent paying repeated/old/spectated stats. Proxy polls the cumulative cursor once/second. Profile/pass/star/checkpoint changes save together, and active pass/profile UI messages are queued. Launcher: `tools/start_rewards.cmd`.
- Rank rules: 5 XP/kill, +3/headshot, 25/MVP, 600/match completion; 5000 XP/profile level, level cap 40. Active passes progress in parallel, 400 XP/star, max 40 stars/pass. Plants/defuses are not connected. These are local rules, not a claim of Valve matchmaking XP parity.
- Armory rolls disable StatTrak. Known collection-only skins with impossible hidden StatTrak flags are repaired on startup; known case finishes and unknown definitions are preserved. Counter attributes 80/81 and quality are now visible to the client.
- Gold contracts accept five equal-rarity Covert inputs, preserve StatTrak, select supplied collections proportionally, exclude gloves for StatTrak and preserve special-item quality. Missing pools reject atomically. Catalogue data is versioned under `data/`, generated by `tools/gold_pools.py` from ByMykel's original dataset; every pair is validated against the user's schema. Local uniform outcome selection is not exact Valve phase weighting. Standard case gold drops remain separate work.
- Terminals are schema-classified volatile collection crates. Their expiration, offer count and stored offer persist. Unseal/advance/decline use OpenCrate fields 4/5; notifications use the laptop script's casket_contents 1012. Accept uses Store line supplemental_data 5 and grants the same offer, clearing its storage/price attributes and consuming the terminal. Local offers cost zero. Script/proto names were read at SteamTracking commit `5ab573fa8afb5b8db98869d79ed79399fca6e747`.
- Bot server GC is now a separate endpoint and message queue sharing inventory with the client. Hook actual server Steam pipe, server interface constructor and `SteamGameServer_RunCallbacks`; route callback flag 0x02 separately. ServerHello gets ServerWelcome; equipped CSOEconItems carry field 18 equipped_state and are delivered through CacheSubscribed. Keep testing actual auth/subscribe sequencing: no invented vtable offsets. Proxy generator and CMake require the two new server export interceptions.
- `tools/grant_test_items.py` + `.cmd` add 229 schema-resolved items to the existing inventory. They preserve original text except next_id and inserted items, back up first, and leave rank/balance/pass progress untouched. Real-schema offline integration exercised every generated rarity/StatTrak contract successfully.
- `tools/skip_container_confirm.py` prepares a strict source patch for the inspected `popup_inspect_rental-bar.js`: only local inventory IDs, only Open, retaining rent/real-inventory paths. It is not mounted/compiled in the test DLL, so the confirmation remains until a verified Panorama build/mount path exists.

## Verification

Core/Python regression suites pass, including persisted zero balance, rank defaults/rollover/cap, multiple passes/reward deduplication, bot-server welcome/cache/equipped_state, terminal unseal/decline/accept/no-duplicate finalize, coupons and gold contracts. Windows x64 MinGW core/proxy build succeeds with static runtime; imports are only KERNEL32 and msvcrt. Linux core builds with warnings as errors. Check final PR/test ZIP for current counts and SHA.

Full build-25966348 schema loaded successfully, all supplementary rare pools validated, Fever's pool resolved 52 distinct definition/paint pairs, and all ten generated contract groups succeeded offline. The checked-in original protocol fingerprint is deliberately unchanged; hashes were not relabelled as a new client build.

## Next live checks

1. Test held skins in a bot match: confirm server 4005/24 traffic and server callback registrations, then inspect any following server requests. Do not claim live success based only on a buy-screen preview.
2. Run GSI helper before launching, activate a pass, verify kill/MVP XP, profile UI update, stars and restart persistence. Check real snapshots for missed phase/round transitions.
3. Test each terminal's unseal/offer/decline/accept/reopen. If the native client sends additional messages (including 2536), capture their actual bodies before implementing another codec. Dead Hand special drops and historical-offer/collection-XP reward UI require further work.
4. Test five regular/StatTrak Covert contracts and their model/paint/wear in the client. Exact modern normalized-float formula and gold phase odds need verification; regular wear mapping was preserved.
5. Compile and mount the optional confirmation source override using the user's target Panorama tools. No game-resource rewrite was installed by the ZIP.

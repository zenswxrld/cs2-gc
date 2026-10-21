# Build24: direct custom Armory rewards

Armory::Redeem recognizes the exact Black Market/Gauntlet item names and rolls their resolved crate loot list before any credit mutation. Requires the correct knife/glove type, marks unusual, retains limited owner certificate and normal random wear/seed/knife StatTrak; glove StatTrak stays excluded by RollLootList. Existing OpenCase and rare-case rewards unchanged. UI uses saved reel descriptors for up to64 preview entries (full pool remains backend authority), native faux IDs, random-reward labels and suppresses the key warning even if previews are unavailable. Current build tag24.

Latest user likes Crimson Web Aurora but wants green webs over purple panels. Preserve specialist_webs_red/Aurora legacy palette as a baseline; exact web recolour remains pending actual material-mask attribution. User requires finish-specific design/detail preservation across all gloves; do not claim the saturation heuristic achieves that for every finish.

Validation includes direct rewards, one charge/no case/key, glove StatTrak exclusion, save/reload, insufficient credits, old-case opening and preview routing. All26 suites and Windows builds must pass before packaging. Native appearance/UI need live testing. Care-package claim timeout remains unresolved.

---

# Build23: accent-only glove recolours and neutral-panel variants

User requested gloves first. Existing native_gloves.make_glove_finish called finishes.recolor on ALL eight g_vColorTint vectors; it coloured neutral/structural masks too, matching the flat Magenta screenshot. New recolor_accents classifies actual source palette values: chromatic channels (HSV saturation>=.35 and value>.12) receive theme hue with unchanged value/alpha and capped original saturation. Original variants preserve every other channel, including ambiguous muted colours. White/Black/Inverted Panels operate only on neutral/near-black channels, retaining the same accent colours. This is a conservative palette heuristic, not texture segmentation or a per-finish anatomical mask map. Actual client appearance remains unverified.

Latest user screenshot approves Specialist Gloves Forest DDPAT Toxic as-is. APPROVED_PALETTES explicitly preserves the legacy eight-tint result only for specialist_forest_brown/Toxic original panels; regression compares every serialized vector. Do not apply the blanket accent policy to this approved finish. Its panel variants and other themes still use the new policy. Report lists preserved_legacy_themes per source.

Existing rg_base_theme names/IDs remain. New _panels_white/_panels_black/_panels_inverted variants are in Gauntlet. Config glove_panel_variants=1 defaults on in both parsers;0 stops variant drops but retains known variants in the schema for owned items. Existing shipped unreleased finishes and unsupported newer composite gloves are unchanged. Finish preparation writes cs2_gc_glove_palettes.json (source tint vectors/accent-channel indices, no account data). The current original game VPK is read-only; only the shared owned finish pack is regenerated. Keep the saved finish-ID map.

Tests exercise structural/alpha/value preservation, saturation caps, panel-only changes, neutral-only fail-safe, finite vectors, actual prepare/VPK output, stable IDs/repeated generation and variant-off known-schema retention. These tests use fixtures; no actual glove render is available here. If a finish remains wrong, use the client-generated palette report and exact item screenshot rather than guessing channel numbers.

Care-package user screenshots after build22 show correct selectable tiles and three selected rewards, but claim still times out. Do NOT mark payout fixed. Await latest cs2_gc_log.txt from that attempt; no new protocol changes in build23. Never restore account-zero preview econ objects.

User-confirmed: mission launch, scoreboard names (killfeed BOT prefix remains), direct souvenirs/stickers, key and handwrap sales, Aphrodite125 display. Next queued requests after gloves: rarity-appropriate charm resale (blue charm buy3/sell9 is wrong), wear-adjusted skin resale, all deterministic buy/sell-loop audit, collection/souvenir pity, requested local souvenir trade-ups (currently deliberately blocked), original official LTD prices (re-verify earlier blanket25 fallback). Then mission completion XP/stars, achievements/Career. Keep these separate from the glove change.

---

# Build 22: pending reward tiles, claim compatibility, decorated names, repeat launch and Howl250

User’s build21 screenshots show all faux preview tiles marked claimed and claim timing out. Pinned primary itemtile_store.js SetClaimed sets `item-claimed` for every faux ID. Clear claimed/expired flags immediately after Init only for local pending choices; keep native stock state elsewhere. Native claim field2 is an optional client balance hint, not grant authority: accept zero/default through3, while generation/three unique exact descriptors remain required. Publish new PersonalStore before owned-item creates to ensure inventory callbacks see the acknowledgement. Added non-personal reject diagnostics. No fresh9219 wire capture yet, so the exact original timeout cause remains unconfirmed; request latest GC log if it persists.

Scoreboard API returns decorated HTML. Strip known formatting tags, decode standard/numeric entities and escape once into the existing label. This fixes the literal span markup screenshot while preserving the no-blank fallback.

After first successful mission launch, user saw loading/dedicated-server failure on retry after console disconnect. Recreate solo session, stop stale searches, and wait up to3seconds for actual listen/map/mode/type/flags before native StartMatchmaking. Reject unsupported modes/maps and party launches without breaking an existing party. Needs live retry validation.

Howl default250; both config parsers normalize old values below250, and generated catalogue replaces stale removed_items prices. Existing inventory/stars unaffected.

Confirmed by user: souvenir direct grants/stickers, Aphrodite125 display, first mission bot launch and key selling. Not confirmed: reward claim completion, scoreboard fix and repeated mission launch. Native store Home embeds the care panel independently of the Inventory-only automatic popup.

Next request: actual mission completion XP/star bonuses, then achievements/Career. Not yet implemented; do not promise AWP progress from equipped-weapon GSI snapshots. Need reliable event attribution and current mission-template data. All existing XP/Premier systems remain.

---

# Build 21: remove crashing reward-preview econ objects

Includes build 20. User reports end-of-match crash in build 19. Supplied log ends after first account-zero preview create (def 4186) at ~817106 ms; minidump records access violation reading 0x30 in client.dll +0x83f065. Strong timing evidence, not a symbolized causal stack. Never commit the supplied logs/dump.

Removed all unowned preview creates from match/level notifications and both welcome paths, plus preview destroys on claim. PersonalStore now carries four local choice descriptors (base 3e12, slot in bits32+, paint in bits16-31, definition in low16), not econ item IDs. Popup resolves the display item through native GetFauxItemIDFromDefAndPaintIndex, retains each descriptor as its submission token and enables selection for local catalogue previews. Backend validates current generation, balance3, exactly3 unique descriptors/slots and exact def/paint matches before mapping back to persisted reserved IDs. Only chosen rewards create real owned econ objects. Existing queues are preserved unchanged on disk.

Main-menu popup is Inventory only and requires no loaded map; Home and the match-ending transition cannot open it. XP/Premier end-match patches untouched. Custom Drops tab remains disabled. Metadata cache updates can still occur at match end; no preview items or reward UI are created there.

26 automated suites pass, both Windows cross-builds compile, patched native scripts pass JS syntax checks. Native transport/rendering and crash resolution need live validation. Preserve saved inventory and queues; extract the full ZIP and use the updated launcher before testing.

---

# Build 20: mission launching, direct souvenir purchases, limited prices and scoreboard names

Based on main after PR #11. Build tag `codex-20261021-20`.

- User confirmed hand-wrap sales and souvenir package opening in build 19. Requested direct souvenir weapon grants instead; `RollSouvenir` is shared by Armory and old package opening, preserving tournament attributes/decals and atomic credit deduction. Armory inspect shows weapon contents and filters highlight charms.
- Limited prices: lists 01/02/03 = 25 stars, 04 (Aphrodite) = 125; preparation corrects stale generated catalogue rows. Howl/custom cases retain existing configurable prices.
- Blank scoreboard bot names in build 19 were a UI label regression: stop creating a sibling label. Write escaped names into the existing native name label and restore its formatter if name data is missing or the row becomes human/demo/online. Killfeed untouched; user reports names already work there.
- `native_mission_launch.py` replaces only PlayMission in the inspected mission_tile script. Uses actual GameTypesAPI config to derive type and mapgroup maps, creates `server: listen` practice settings, enables a valid bot difficulty and disables practice assists/infinite warmup. Preserves mission deathmatch/competitive flags. Unsupported data fails locally rather than falling through to official matchmaking. Installed through both prelaunch and rewards-helper preparation; `offline_mission_launch=1` defaults on.
- Evidence: inspected client mission_tile and pinned SteamTracking/GameTracking-CS2 mainmenu_play.js at 5ab573fa8afb5b8db98869d79ed79399fca6e747 (listen-server settings and bot difficulty APIs). No invented engine offsets or console commands.
- Launching does NOT implement mission progress/completion rewards or auto-equip a mission weapon. Those remain pending; ordinary match XP/stars still use the existing bridge.
- Validation: 26 automated suites; JavaScript syntax against inspected sources; all 148 direct souvenir grants/save; Windows cross-builds. Mission UI launch/Armory preview/scoreboard names still need live-client testing.

---

# Current handoff: Codex build 19 (21 October 2026)

Based on `92bc6da` (Claude's custom glove/Gauntlet implementation); changes live on `codex/souvenir-armory-and-glove-quality`. Current installation/checklist: TEST-BUILD.md. User confirmed custom glove colours, realistic bot names and stock XP/Premier end-match screens. User superseded the custom drops tab with native care packages: four offers, choose three after a match/back in menus; one additional package per profile level.

Implemented: reject glove StatTrak in generic loot rolls and repair saved gloves; handwrap selling uses schema IsGlove/hands_paintable (72 default), not the word "glove" in the name; separate official souvenir pool, native quality/event/sticker serialization and keyless opens, trade-up exclusion; top two charms/sticker/agent, bottom souvenir/case/terminal/capsule, excess old-config goods continue rotating. Native scoreboard only: plain bot-name label via verified MockAdapter.GetPlayerName avoids the engine's automatic [BOT] prefix. Hide RUSH, preserve missions.

Care packages: Inventory stores a bounded FIFO of four **unowned** offers with reserved IDs and monotonic generation; each match/level advances its existing reward cursor only when queuing succeeds. Claims require generation, balance=3 and exactly three unique IDs from the front. Ownership + queue advancement save before SO notifications. PersonalStore SO type **4** is verified in the supplied old welcome dump: generation_time(1), balance(2), four repeated ids(3), matching CSOAccountItemPersonalStore in the supplied proto. Claim message **9219** / generation(1),balance(2),items(3) is in the same proto; repeated uint64 accepts packed/unpacked. Front previews are SO econ items with account=0, inventory=0, never in the backend's owned Items vector. Client rendering/ownership filtering needs live validation. Welcome restores the front store/previews, both replay and synthetic paths. Claim destroys previews, publishes exactly three owned items and advances the native store; direct 9137 drop notifications are suppressed in choice mode. Native rankup_redemption_store patch enforces 3 picks and removes weekly language; mainmenu notification also allows Inventory. Working XP/rating baseline capture retained; custom Drops panel disabled by default.

Free keys: no auto-minted keys. free_case_keys=1 accepts native keyless tool=0 or tool=case; popup associated count is zeroed only for local non-volatile containers, in the SAME popup override as knife/glove reels (avoid competing VPKs). Old keys sell for 5 using associated-item schema indices. Rare case channel excludes custom cases from the ordinary pool; default combined 100/10000 of case offers split across enabled Black Market/Gauntlet. Weekly blue+ weapon pool retained. New settings documented in example + TEST-BUILD.

Souvenirs: packages with local loot lists only (148 in supplied schema). Event inherited per attribute (local series must not hide prefab event). Native tournament quality 12; attrs 137/139/140/223 are schema-verified. Decals selected from schema-matched event teams, gold when available, historical foil fallback. Modern named 2021+ packs use map golds; older packs an available team autograph. Locally randomized provenance, **not an actual historical match**, no invented stage. No match-highlight charm integration. Two oldest server-only packages excluded. Do not claim all generations have four stickers.

Still pending: bot-match missions/rewards (native card kept, no unreliable weapon attribution added), native tags outside scoreboard, graffiti, final folder migration + EXE icon, MSVC CI diagnosis. Preserve stable finish IDs. User requested changes pushed and a test ZIP. Automated tests and cross-build evidence are reported in the final build notes; target-client care-package flow remains experimental until tested.

---

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

---

# Claude follow-up on build 17 (user reports, 21 October 2026)
- Armory: removed the second countdown next to the page arrows; the single countdown is now white Stratum2 text
  directly below "Get Armory Passes" (`id-xpshop-more-passes-btn`). Page arrows hide while a tab's inspect grid is
  open (`xpshop-grids-visible`) and return on the tile view.
- Terminal offers: the laptop's "Offer limit" is a price cap; it no longer sets the offer count (terminal.cpp uses
  `terminal_default_offers`). The laptop label is total minus remaining, so the first offer reads 1st.
- `cs2_gc_reset_profile.cmd` / `reset_profile.py`: option 1 resets level/XP/Premier/matches only (inventory progression
  block set to level 1 and `cs2_gc_gsi_state.json` + cursors moved); option 2 also moves the inventory. Files are moved
  to a dated backup folder.
- Still open from the same report: clicking the bottom-right sticker capsule tile opens a random tab. Likely the stock
  scrolling tile (`shuffledArray[iScrollingTile ...]`) routes the click to whichever entry it is showing; not fixed.
- Follow-up (same day): Armory is one stock-style page again: 4 small / 3 large / 4 small, no paging arrows. The
  limited edition item is always one of the 3 large tiles and is moved to the middle (`MoveChildAfter`). The single
  white countdown sits on the right just under the green line (in `cs2gc-category-bar`), below the pass button.
- Reset script bug fixed: in a .cmd file `set MODE=progress` cleared the CHOICE errorlevel, so option 2 always ran as
  option 1 (rank reset, inventory kept). The answer is now read before any SET, and the full reset fails loudly if
  cs2_gc_inventory.txt is still present afterwards.
- Live-confirmed by the user: terminal offers now read 1st, 2nd, ... in order.
- Bottom-right Armory tile opening "a random tab": the stock `InventoryUpdate()` re-activates whichever nav RadioButton
  is `checked`, and our GC pushes inventory updates often. The patched tile click called `_UpdateInspectGrid` directly
  without checking that entry's nav button, so the next update jumped to an older tab. `_LocalOpenEntry()` now checks
  the entry's `<item_name>-nav` button before opening the grid. Needs live confirmation.
- Top row had 3 tiles because the defaults gave it 2 charms + 1 agent; `armory_charm_slots` default is now 3 (C++ and
  Python and the example cfg). Users with their own cfg must set `armory_charm_slots = 3` themselves.
- The countdown's right margin is computed each second from the "Get Another Armory Pass" button
  (`GetPositionWithinWindow` + `actuallayoutwidth`), so it lines up with the button.

### Build 17e (Claude)

- Capsule tile opened Random Agent: on the second open of a crate grid the stock refresh calls
  `elModel.PanZoomEnabled()` on a null `ItemPreviewPanel` and throws before `_UpdateVisibleInspectGrid`, so the
  previously shown grid (Random Agent) stayed visible. `patch_previews` now null-guards both `PanZoomEnabled()`
  calls and the scheduled `TransitionToCamera`, and tiles/tabs open through `_LocalShowGrid`, which catches any
  remaining error (logged as `cs2_gc armory: <item>: <error>` in the console) and still shows the entry's grid.
  Not yet confirmed in the client.
- Countdown right edge now lines up with `id-xpshop-balance` (the pass button is hidden at 5 passes).
- Removed the custom Random Agent grid title styling (it sat over the tab icons) and the explicit `Stratum2` on the
  countdown, so both use the stock CS2 font/styles.

### Build 17f (Claude)

- Armory capsule rows (`local_rotation_slot capsule`) now open on purchase: `Armory::Redeem` rolls one sticker
  from the capsule crate's own loot list (`FindCrate(...)->lootListName`, StatTrak off), falling back to the
  capsule item only if the loot list can't be resolved. Core test added. Requested by the user after seeing the
  capsule itself granted; the client "Received from Armory" popup should show the sticker (not yet verified).

### Build 17g (Claude)

- `free_case_keys = 1` (new, default on): `LiveInventory::EnsureCaseKeys` keeps one matching key for every keyed
  case type owned (at startup and after Armory/Store/match-drop grants, sent as SO creates), and `OpenCase` no
  longer consumes the key while the option is on. No key purchase is needed. `0` restores normal keys.
- `bot_fake_ping = 1`: the scoreboard override (`native_scoreboard.py`, needs `premier_scoreboard`) shows a steady
  per-bot fake ping (15-75 ms, +-3 ms drift) and drops the `bot` row class / BOT ping label. Applied to the user's
  real scoreboard script cleanly; not verified live.
- `bot_random_names = 1`: new `native_bot_names.py` overrides `botprofile.db` in its own `cs2_gc_bots` folder,
  renaming only the profile header names (`Template[+Template] Name`); the launcher reshuffles names on each start
  (seed in `cs2_gc_bot_names_seed.txt`), the helper reuses the seed so it never changes the VPK while CS2 runs.
  An unexpected file layout is refused and logged as "Bot names skipped" without blocking the launch. The CS2
  botprofile.db layout itself has not been inspected; check cs2_gc_prepare.log.
- "Buggy until restart": the user's logs show the launcher prepared everything ("installed", nothing changed by the
  helper) and the GC sessions before/after a restart are identical. Cause still unknown; need concrete symptoms.
  Killfeed/chat "BOT" prefixes are not changed (no script for them inspected).
- 17h: fake bot ping confirmed live but changed too fast; now it moves by at most 2 ms every 3-8 s and stays
  within 5 ms of the bot's base. Random names did NOT apply in the user's test (default names shown) - check the
  "Bot names" line of cs2_gc_prepare.log. The scoreboard shows "[BOT]" before bot names; not changed yet.
- 17h: `skip_key_selection = 1` (new `skip_key_select.py`, folder `cs2_gc_open`) patches the user's
  item_context_entries: Open on a local case (id 1e12..2e12) with exactly one chosen action item goes straight to
  popup_capability_decodable with that key as tool_id (same settings the stock picker passes). Not verified live.
  Bot names list replaced with realistic gamer handles.
- 17i: stock end-of-match panels. New `native_endmatch_stock.py` patches the user's endofmatch-rank and
  endofmatch-skillgroup scripts (folders cs2_gc_eom_xp / cs2_gc_eom_rating): when the engine has no XP / skill
  group data (always offline), they are fed from local values against `EndOfMatch.LocalBaseline` (captured by the
  native_endmatch.py patch at match start, cleared at EOM shutdown): XP from MyPersonaAPI.GetCurrentLevel/
  GetCurrentXp (GetCurrentXp exists in client.dll strings; guarded with typeof), rating/wins from
  FriendsListAPI Premier. The rating panel retries for up to 4 s for the post-match update. Codex's custom panel
  is now drops-only and hides itself when nothing dropped. Not verified live.
  `bot_prefix ""` added to the launcher cfg and premier bots cfg to try to drop "[BOT]" (cvar exists in
  server.dll; whether it is the source of the tag is unverified).

### Knife recolours + Black Market Case (Claude, in progress - not built yet)

User explicitly wants (20 Oct 2026): OfflineCS-style knife recolours (CSOffline `examples/make_recolors.py`,
646 `rk_` kits), existing abstract finishes on knives (Twilight Galaxy = am_aqua_flecks, Gold Brick =
am_gold_brick, Blue Phosphor = am_m4a1s_bluesmoke, ...) plus recolours of those, and one gold-only
"Black Market Case" (CSOffline icon `examples/case_icons/crate_csgogc_black_market.png`) in the Armory limited
slot. This needs an AGENTS.md exception (custom paint kits / one case) - add it when implementing.

Verified on the user's own files (cs2_gc_extracted_3):
- CS2 paint kits in items_game have no colours. A kit either has `composite_material_path` or, for legacy kits,
  uses `weapons/paints/legacy/<name>.vcompmat`. That vcompmat_c (RED2+DATA, KV3 v5 LZ4) only includes
  `_shared_paint_generic.vcompmat` and points `CONTAINER_SOURCE_TYPE_SPECIFIC_MATERIAL` at
  `materials/models/weapons/customization/paints/vmats/<name>.vmat`.
- That vmat_c (RERL, RED2, DATA, INSG) holds `m_vectorParams` g_vColor0..g_vColor3 as 0..1 float4 - the same
  four colours CSOffline changed (0..255 there). Style is `F_PAINT_STYLE` in m_intParams.
- New tools/kv3.py reads KV3 v5 (none/LZ4) and writes it uncompressed, plus resource containers. Round trip
  verified on all six user samples (not committed: proprietary). tests/test_kv3.py is synthetic.
Plan: native_finishes.py at prepare time reads base vcompmat_c/vmat_c from the installed VPK, writes
`rk_<base>_<theme>` copies (vmat: new m_materialName + recoloured g_vColor*, vcompmat: new specific material
path) into a cs2_gc_finishes VPK folder; adds paint_kits (+paint_kits_rarity) entries with
composite_material_path in the native_tradeups items_game override (run before patch_catalogue so the GC, which
loads the mounted native schema, sees them); names via a resource/csgo_english.txt copy with added
`PaintKit_rk_*_Tag` tokens; Black Market crate cloned from an existing case with its own revolving loot list
(unusual tier only) and an Armory limited row. Open questions to test live with a small batch first:
(1) do missing default_generated inventory icons render/fall back, (2) does a VPK resource/csgo_english.txt
override load, (3) the case icon needs a vtex_c (sample: user's default_generated vtex_c, DATA v1 512x384 fmt 28,
image data appended after the resource; VRF Texture.cs has the layout).

User's next list after this: career/achievements + collections tab (not in Armory), souvenir packages, bot
difficulty by rank, bot clan tags/chat/skins, music kit StatTrak/MVP, viewmodel settings + in-game give
command (no default RCON exposure). Still open: random bot names did not apply (need cs2_gc_prepare.log),
"[BOT]" tag (17i tries `bot_prefix ""`), confirm 17i stock XP/rating panels live.

### Build 17k: knife recolours + knife-only Black Market Case (Claude)

- `tools/native_finishes.py` (called by native_tradeups.prepare before the Armory catalogue, so client and GC
  both load the result): reads base vcompmat_c/vmat_c from the installed pak01 (one-time directory index),
  writes `rk_<base>_<theme>` recolours (OfflineCS themes/duo themes, brightness kept, too-dark ones skipped)
  under `weapons/paints/cs2_gc/` + `materials/.../vmats/cs2_gc/` into the `cs2_gc_finishes` VPK folder (Game
  search path), adds paint_kits (ids from 30000, copied base fields + composite_material_path) and
  paint_kits_rarity, names via a copy of the installed `resource/csgo_english.txt` with added tokens, and the
  case icon `panorama/images/econ/weapon_cases/crate_cs2gc_black_market_png.vtex_c` (uncompressed BGRA8888 from
  the OfflineCS PNG, shipped as tools/cs2_gc_black_market_case.png).
- Bases: KNIFE_BASES (official colour knife finishes incl. Gamma Doppler, Freehand, Bright Water) get all 18
  themes on 4 random knives each; extra finishes (Twilight Galaxy am_aqua_flecks, Gold Brick am_gold_brick,
  Blue Phosphor am_m4a1s_bluesmoke + abstract am_/aa_/an_ anodized kits without weapon words) go on every knife
  and get 6 themes on 2 knives each. Official pairs come from data/gold_pools.txt.
- Case: `crate_cs2gc_black_market`, cloned from Operation Bravo (4003: model, key 1203 - free keys apply), new
  def id (first free from 4950), new supply series, loot list with one `_ancient` tier = knives only. GC change:
  a knife rolled from a case loot list is marked unusual (★). Armory: limited row (`black_market_price`,
  default 100) so it rotates through the big tile; xpshop crate preview draws a random 96 of the contents.
- Any failure is reported as "knife finishes: skipped: ..." in the Recipes/catalogue line of
  cs2_gc_prepare.log and never blocks the launch. `knife_finishes = 0` unmounts everything.
- NOT yet verified live: inventory icons for new combos (CS2 ships pre-rendered default_generated icons), the
  csgo_english override, the vtex icon, and the recolours rendering. Check these first.
- 17l: 17k's `resource/csgo_english.txt` override in the cs2_gc_finishes VPK broke ALL game text (raw #tokens
  everywhere). Removed; never override the language file. Finish and case names are now literal text in
  description_string/description_tag/item_name; the old file is deleted on the next prepare (stale cleanup).
- 17q: user's logs: knife finishes built (704 recolours, 4285 case knives). New collections/capsules failed with
  status 5 NotInRotation: the helper never saw console.log (game not started with -condebug), so the GC's
  rotation offset stayed 0 while the page advanced. Armory::Redeem now only checks the rotation when
  armory_rotation_enforce = 1 (default 0, also for the Howl); the page decides what is shown. Bot names were
  skipped because CS2's botprofile.db repeats names; that check is removed.
- 17s: the user's console.log proves CS2 does NOT write `echo` output to console.log (zero "[Console]" lines),
  so stars/rotate never reached the helper. It does log incrementvar results ("<var> 1.000000"). Commands now
  `incrementvar cs2gc_<nonce>_s100|_s1000|_rot 0 1000000 1` (variables setinfo'd per launch by the launcher cfg and
  the helper cfg); console_controls counts each logged line (old echo form still accepted).
- 17t: every theme for Twilight Galaxy / Gold Brick / Blue Phosphor (added after the original set so existing
  ids do not move), extra-finish recolours on 4 knives each. Paint kit ids are now saved in
  game/bin/win64/cs2_gc_finish_ids.json and reused, so owned knives keep their finish when the list changes.
- 17v: the Black Market Case opened with the stock countdown because the client collapses an all-knife loot list
  to one placeholder (GetLootListItemsCount <= 1). New native_knife_reel.py (folder cs2_gc_reel) patches the user's
  popup_capability_decodable: for crate_cs2gc_black_market only, aItemsInLootlist is filled from a 60-knife sample
  (cs2_gc_black_market_reel.json, written by native_finishes) and the stock scroll runs; the stop tile shows the
  granted item as usual.
- 17w: Black Market Case pairs with no shipped `default_generated/<weapon>_<kit>_<light|medium|heavy>_png.vtex_c`
  get the stock `weapon_cases/default_rare_item_png.vtex_c` (user's choice) - added only to the cs2_gc_finishes VPK
  (vpk_pack.pack(extra=...), identical contents stored once), never written loose. Real pictures stay for shipped
  pairs. Base-name fallback for extra finish titles (17v showed "Skeleton Knife | Ember").
- 17z: user wants the Black Market Case to hold ONLY custom finishes (new knife finishes + recolours); all official knife finishes removed from it (they stay in regular cases).
- 18a: 12 four-colour GRADIENT_THEMES (colour i -> hue i) for FADE_BASES (fades, marble fade, doppler/gamma phases, marbleized, tiger tooth); appended after older recolours, ids saved.
- 18b: single-hue themes on FADE_BASES sweep 80 degrees along the finish's colour order (user: fades looked one flat colour).
- 18c: prices: black_market_price 100 (floor sell_knife_glove+1), sell_knife_glove 72, armory_terminal_price 10, new armory_case_price 5. Capsule tiles open as sticker lootlists (the capsule's own stickers) like sticker collections.
- 18d: viewmodel range (OfflineCS viewmodel_range). cs2_gc/proxy/viewmodel_range.cpp: background thread waits for
  client.dll, follows the static CConVarRef objects (client rva 0x25328c0/d0/e0 = viewmodel_offset_x/y/z,
  0x256aad0 = viewmodel_fov, read from the user's client.dll registration code: each call builds a setup with
  SetMin(0x76a610)/SetMax(0x76a600) then RegisterConVar via ICvar vtable +0x130 writing ConVarData* to obj+8),
  checks ConVarData {name, default*, min*, max*} (hl2sdk-cs2 layout) against the exact name and the limits from
  that code (x 1/-2/2.5, y 1/-2/2, z -1/-2/2, fov 60/60/68) and only then widens: offsets x viewmodel_range_percent
  (default 250), fov viewmodel_fov_min..max (40..90). Any mismatch logs "left unchanged". cl_bob was requested but
  no cl_bob convar exists anywhere in this client.dll (removed in CS2), so nothing to restore. Not verified live.
- 18e: gloves + Gauntlet Case (user: "separate glove case like offlinecs", "in the LTD rotation"). Classic glove
  materials (csgo_customglove.vfx) carry eight tints g_vColorTint1..8 (checked on the user's slick_red,
  sporty_purple, specialist_fade, sporty_blue_white_webbing vmats); the Dead Hand (volatile_02) gloves use the
  glove_compositor template plus a preview material and have no tints, so they are not recoloured. New
  tools/native_gloves.py (called from native_finishes.prepare, same VPK folder and items_game override):
  8 shuffled themes per classic glove kit (+12 gradients on specialist_fade / specialist_marble_fade), kept on
  the base kit's own glove type, brightness kept exactly (keep_value). Four shipped finishes with no paint kit
  (gloves/paints/volatile_02/glove_driver_brocade_phoenix_red, _knit_argyle_red, _ostrich_leg_red,
  glove_specialist_dragon_red - red colourways of Dead Hand gloves, NOT in the Dead Hand collection) get kits
  ug_<name> pointing at the game's own vcompmat, titles ours. crate_cs2gc_gauntlet cloned from 4017 (Huntsman,
  key 1307, as OfflineCS), OfflineCS crate_csgogc_gauntlet.png icon, same price as Black Market in the limited
  slot. Reel file is now {case name: pairs}; the reel patch accepts the old list. GC: a glove from a case's own
  loot list is unusual (Schema::IsGlove). glove_finishes = 0 removes it. Official glove finishes are not in it
  (same rule as the knives). Not verified live.
- Note for Codex (21 Oct): every "CS2 port checks" run on this branch (PR #9) fails in the windows-latest Build
  step while ubuntu passes; main last passed at 6b19d25. The job log could not be downloaded from this session
  (log storage host blocked), so the MSVC error is unknown - likely a /W4 /WX warning in cs2_gc_core (src/ only)
  that GCC -Wall -Wextra does not report. Next queued for Claude: souvenir packages.

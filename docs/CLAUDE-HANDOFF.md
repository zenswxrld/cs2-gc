# Build 34 (Claude): mission progress tracking (implemented; live test pending)


User test (build 33): the mission tile and in-match mission panel SHOW ("Get kills with the AWP", DM on Defusal Group
Delta, 0/120, 600 XP) but progress never moves in bot matches. The listen server never sends 9136 MatchEndRunRewardDrops
(quest data) or 1074 IncrementKillCountAttribute, although it does ServerHello (4007) and we already ServerWelcome. So WE
must count. Recorded welcome: SO type 16 = CSOAccountRecurringMission {1 account_id, 2 mission_id, 3 period, 4 progress}
(recorded: 11012 / 1779843600 / 6). Protobufs (GameTracking-CS2 609b2ac, Protobufs/cstrike15_gcmessages.proto):
CMsgRecurringMissionSchema { repeated MissionTemplateList missions = 1 { uint32 period = 1; repeated bytes
mission_templates = 2; } } answer to 9225 (gc_endpoint.cpp maps 9225 -> replayed 9226).
User supplied cs2_gc_replay/9226.bin (NOT committed). tools/decode_mission_schema.py decodes it: weekly periods
(1791939600 = Wed 2026-10-14 01:00 UTC, +7 days...; only Oct 14 (15 templates 11003-11017) and Oct 21 (11016, 11017)
have templates, so after Oct 28 there are NO missions -> must generate a rotating schedule).
Templates (binary KV, key = mission id): name, gamemode, gamemodeflags, mapgroup, map, points "40, 80, 120",
expression, xp_expr "200, 200, 200", xp_round_to, loc_description "#quest_<id>_var_desc:f", string_tokens, gc.random.
Only three expressions: "act_kill_human && !![weapon_a|weapon_b...]" (DM), "act_win_round" (competitive, map given),
"act_win_match" (rush). "![a|b]" / "!![a|b]" = random pick (client rolled AWP + mg_casualdelta for this user).
Client (mission_tile.js / mainmenu_missions.js / hud/hudmissions.js): MissionsAPI.GetRecurringMission() ->
progress_saved, goal_points[], xp_reward[], progress_this_match; HUD uses GameStateAPI.GetActiveQuestID().

Implemented (build 34):
- tools/native_missions.py (prepare step, every launch, UI stage): reads proxy/cs2_gc_replay/9226.bin, keeps the 13
  playable templates (drops lobby_mapveto / rush), one per weekly period from 4 weeks back to 52 ahead, every "![..]"
  list resolved to one option per period (seeded), writes cs2_gc_missions.bin (9226 body) + cs2_gc_missions.json.
  Binary KV kept type-exact (round-trip tested). Map groups from pak01 gamemodes.txt.
- tools/mission_tracker.py, used by gsi_rewards.py (GSI now also requests "player_weapons"): counts kills with the active
  mission weapon, own-team round wins, won matches, only in the mission's mode on its maps; first packet of a match is a
  baseline; tier XP added to the helper total; writes cs2_gc_mission_progress.txt ("mission period progress").
- DLL: PollMissions (proxy) loads cs2_gc_missions.bin once and the progress file each poll; LocalGameCoordinator::
  SetMissions: 9225 answered with the local schema, welcome type 16 replaced by our progress, changes pushed as SO
  Create/Update (CSOAccountRecurringMission). The GSI config change needs ONE CS2 restart after the helper rewrites it.
Other queued user requests: custom-collection trade-ups, multi-sell via popup_select_item_for_capability
(casketstore multi-select, user approved the plan), build-folder cleanup + leftover-file removal tool (last),
detail-preserving palette rotation recolour + texture recolours (Rainbow Spoon / Crimson Foil style).
A star-economy loop audit was started by Claude in this worktree (uncommitted results may be present: check git status).

# Build 33 (Claude) - care packages from level-ups only; claimed package stays on show

User confirmed build 32: the favourite-route claim works and the rewards (cases) open. Extra packages appeared at once
because every match also queued one. New option care_packages_from_matches (default 0): with care packages on, a match
queues nothing and drops nothing; packages come from profile levels (GrantLevelRewards).
User: keep the last claimed rewards on show, labelled claimed, until the next drop. Inventory saves "care_claimed"
(generation + per slot "def paint ownedId", plain numbers, no next_id copies). With an empty queue EncodeCareStore shows
it (balance 0) as the same choice tokens plus CareClaimedFlag (1 << 36) on the taken slots. The page keeps the native
claimed look (ItemTileStore.SetClaimed marks every faux preview claimed) only for flagged tokens; the other one is a
normal tile, disabled because the balance is 0. NotifyCarePackage now compares the encoded store, since a claim keeps the
generation. Next request queued by the user: multi-select selling in the inventory (later).

# Build 32 (Claude) - care-package claim as a tournament favourite

Build 31 log: the page printed the claim line but the DLL never saw it. The rewards helper's own log shows
"console.log does not exist after a minute" every session: CS2 writes csgo/console.log only at exit, so NO console-log
channel (build 31's PollCareClaims, Codex's care bridge, the console star controls) works live.
GameTracking-CS2 (609b2aca32e129e094990e163771d6b86880f65f) has no AsyncWebRequest; mainmenu_watch_eventsched.js calls
TournamentsAPI.SetTournamentFavorite(Number(event_id), bool), and Protobufs/cstrike15_gcmessages.proto defines
CMsgGCCStrike15_v2_SetEventFavorite { uint64 eventid = 1; bool is_favorite = 2; } (9200; 9201/9203 already flow at startup).
The page now calls SetTournamentFavorite(4200000000000000 + generation*16 + mask, true); the GC's new 9200 handler claims
(CompleteCareClaimLocked) only for ids in that range with a matching front generation and exactly three slots.
Live test: GC log must show ">> GAME->GC type=9200" and "care claim received (favorite route)". If the game validates
event ids and sends nothing, the log shows no 9200.

# Build 31 (Claude) - care-package claim from console.log; main merged

Build 30 log: the page called MissionsAPI.ActionRedeemOperationGoods with the marker cost, and the game sent no 9209,
so the game validates that call too. The page's $.Msg lines DO reach csgo/console.log (-condebug). For local packages the
page now prints only "cs2_gc care: claim generation=<g> balance=<b> tokens=<t1>,<t2>,<t3>" and never calls a native claim;
the DLL (steam_api_proxy PollCareClaims, inside PollProgression, 1 s) reads bytes appended since launch, parses them with
ParseCareConsoleClaims and calls LocalGameCoordinator::ClaimCareFromConsole -> CompleteCareClaimLocked (main's shared
claim). The GC validates generation + three distinct tokens; old/duplicate lines grant nothing.
Merged main (PR #28, Codex): kept CompleteCareClaimLocked/ClaimLocalCarePackage and the care_package_bridge/session-code
helper on the GC side; its page call (_SendLocalCareClaim, popup when the session code is missing) and the build-30 Armory
route were removed so there is one page path. Uses data/steam_api64_exports.def for the proxy now.
Preparation cache: LIGHT_HELPERS (UI-only helpers) + DLL/exe changes re-run only the UI patch steps.

# Build 30 (Claude) - care-package claim through the Armory message; build 29 reverted

Build 29 (offers published as type-1 econ items, inventory position 0) made the game show them as NEW owned items
the GC does not own: the user could not open/sell them ("unable to retrieve your item"), and the claim still timed
out. Reverted to the build-28 store (choice tokens, no offer econ items).
StoreRedeemFreeRewards never sends local claims, so the patched page now calls
MissionsAPI.ActionRedeemOperationGoods(GetSeasonalOperationXpShopIndex(), 0, cost) with
cost = 2000000000 + (generation % 1000000) * 16 + slot mask (token slot = (token - 3e12) >> 32). The 9209 handler
treats expectedCost >= CareClaimCost as a care claim (stamp must match the front package, exactly 3 slots) and runs
the shared m_careClaim (same path as 9219). No Armory credits are spent. The Armory message was confirmed to reach the
GC (9209 frames in every log). Live test pending: GC log "care claim received (armory route)".

# (superseded) Build 29 (Claude) - care packages: offers are real econ items

DLL tag claude-20261022-29. User's build-28 console.log: StoreRedeemFreeRewards got three faux ids the client
recognised (IsItemInfoValid/IsValidItemID true) and STILL sent no 9219 (no frame in cs2_gc_log.txt). Valve's recorded
PersonalStore lists real item ids for choosable slots (faux ids only for claimed ones), so the native call evidently
needs ids that are in the store AND are items in the SO cache.
- EncodeCareStore lists CustomItemIdBase+offer.id; EncodeCareOffers publishes the four offers as type-1 econ items of
  the account (NOT account 0, the build-19 crash) with inventory position 0 (CareOfferPosition), in both welcome paths
  and on NotifyCarePackage (old offer objects destroyed first). A claim destroys the four offer objects, then
  NotifyRewardDrops creates the chosen three as owned items (unacknowledged bit). CareChoiceSlot accepts the real ids
  (tokens/faux still accepted).
- JS: _LocalCarePackage accepts the 1e12..2e12 range; tokens are mapped to faux ids only when the store still holds tokens.
- Unverified live: whether position-0 offers appear in the inventory before the claim, and the claim itself.

# Build 28 (Claude) - custom gun collections rebuilt from every gun finish; care-package claim ids

DLL tag claude-20261022-28 (new DLL: care-package claim). Branch claude/collections-rebuild from main.

## Why the old pools were wrong (from the user's cs2_gc_skin_study.zip, study_skins.py)
- 1318 gun finishes inspected. What the game renders = the material's params overridden by the composite's
  loose variables (modern finishes keep g_vColor*, g_tPattern... in "exposed_params"; the vmat is a shared template).
- F_PAINT_STYLE 6 custom paint (373 finishes) has NO colour params; 7 patina, 8 gunsmith and F_CASE_HARDENING take
  colour from textures. Recolouring them = identical copy ("copies with 0 change"). Codex pools had 53 such entries.
- g_bIgnoreWeaponSizeScale=1 / g_bOverrideDefaultMasks=1 (per-gun paint-by-number masks) / styles 6+8 = artwork laid
  out for one gun. Codex pools had 80 entries of that artwork on other guns ("super broken").
- The old detail recolour kept neutral greys, so finishes whose visible parts are grey barely changed.

## New generator: tools/gun_collections.py (wired in native_finishes.prepare after native_skins.custom_cases)
- classify(): recolourable = style 0-5 with four colours and no case hardening; transferable = no gun layout flag,
  no gun in the name. 594 finishes qualify; ~554 used once each across the 36 collections (15 reused once in another
  collection, never an identical look).
- Slots: chase = colour family (6 palette colours) on AK/M4A4/M4A1-S/AWP/Deagle, best anodized finishes first (chases
  are planned before all other slots); 6 chases reuse the knife-finish families (cgf_*: doppler, gamma, marble fade,
  fade, tiger tooth, damascus). Classified: 1 family + 1 fixed recolour; Restricted 3 fixed; Mil-Spec 3 fixed +
  1 original-colour transfer; Industrial 4 fixed + 2 transfers. Transfers only onto guns that pattern never shipped on.
- Recolour (make_recolour) writes the colours where the composite binds them (exposed params, else the material),
  uses native_finishes.recolor (all four colours, greys tinted) and refuses changes below MIN_CHANGE.
- IDENTITIES: one palette per collection spread round the colour wheel (not all red).
- Lineup saved in game/bin/win64/cs2_gc_gun_collections.json (version 1) and reused; "history" keeps every kit it
  ever named defined. Kit names gc3f_/gc3v_/gc3r_/gc3t_, materials gc3m_<donor>_<theme>.
- The older Codex generators (custom_cases chain) still run only so owned skins keep rendering; their pools are
  no longer published. Knives, gloves, Black Market and Gauntlet are untouched (user: "dont touch the knives and gloves").
- Offline dry run on the user's data: 36/36 complete, no duplicate looks, no per-gun art on other guns, no copies.
  NOT verified in game.

## Care package (subagent investigation)
- The user's log has no 9219 at all; after the welcome the client sent nothing to the GC. Original script: OnRedeem
  calls StoreAPI.StoreRedeemFreeRewards(ids) then a 10 s timeout. Our ids were local tokens the client does not
  know, so the native call returns silently.
- Fix: the patch submits the faux ids the tiles render (GetFauxItemIDFromDefAndPaintIndex); the GC maps a faux id
  (0xF000000000000000 | paint<<16 | def, bits 32-59 zero) back to an unused saved offer (CareChoiceSlot), old tokens
  still accepted. Diagnostics: console "cs2_gc care: claim ..." / "claim timed out", GC log "care claim received" /
  "care claim rejected: id N matches no pending offer". paint<<16 layout is unverified for painted offers.
- If still no 9219: next option is real SO econ items for the offers (crash history in build 19) - ask the user first.

## Tools
- study_skins.py/.cmd: read-only dump of every gun finish (used for this work).

---

# Helper27c — collection art pass: accent gradients and inversions

Same DLL tag codex-20261022-27; Python/helper update. Includes27a/27b fixes.
User confirms the27b chase model selection works in the native Armory.

- Rework the12 existing gun collections with a wider, curated set of gun-finish donors; every active entry
  is a colour family, including same-weapon recolours of official finishes. No gun cases added.
- Six selected colour/gradient palettes per collection, plus two inversion candidates. Invalid,
  near-original and duplicate palettes are excluded. No original colourway is an outcome of the NEW families.
- Preserve coloured pattern regions, neutral trim, alpha and tonal contrast. Inversions swap painted neutral
  panels; on all-colour patterns they reverse the existing tonal hierarchy. Not an RGB negative.
- Lower tiers use more subdued saturation. Pattern textures, shader settings, roughness and wear inputs stay intact.
- New cw2* / rwc_* definitions retain the earlier27a/27b definitions for owned skins. Names stay clean:
  variants do not append palette or inversion suffixes to the displayed skin name.
- User's M4A4 Blaze screenshot has no visible flame motif. Exclude aa_flames from new transfers;
  older owned Blaze copies stay supported but their missing motif is NOT claimed fixed.
- Eclipse and Monsoon remain drop-only; the other10 remain in Armory rotation. Standard case pools are unchanged.
- New cs2_gc_weapon_palettes.json records original and generated colour vectors, source materials and exclusions.

Install: close CS2/helper; back up inventory and cs2_gc_finish_ids.json. Extract ALL files (including weapon_palettes.py)
into game/bin/win64; run cs2_gc_debug.exe. Keep the active config, inventory and finish-ID map.

Test:
1. Launch completes preparation with no skipped finish generation; Armory chase previews still match.
2. Inspect all12 collections:16 entries each, no repeated donor within a collection, no new Blaze.
3. Redeem repeated entries: colour and inverted variants roll under one name; original donor colourway absent.
4. Compare accents/neutral panels in preview AND gameplay, including wear. Report dull, overly bright or misplaced
   patterns with the weapon/collection name and cs2_gc_weapon_palettes.json.
5. Existing owned skins still render, selling still works, restart retains inventory/stars/loadouts.

Offline audit using supplied colour vectors and actual schema:192 entries,3–8 variants each,1395 active variants;
154 near-original combinations rejected. This used reconstructed material fixtures, not target-client rendering.
Glitter/pearl/iridescent shader effects remain research work; none were guessed or added here.
Custom collection trade-up membership and the existing care-package claim timeout remain pending.

---

# Helper27b — correct chase tile and distinct patterns per collection

Same DLL tag codex-20261022-27. Includes all27a preparation/crash mitigations.
User screenshots confirm live main-page collection models and full-screen collection inspection render.
They also show an unwanted repeated Ossified pattern in Ashfall and Brimstone/Cascade tiles displaying
lower-tier guns instead of their intended chase.

- Select the tile weapon directly from the generated chase-first manifest, independent of native lootlist ordering.
- Each collection now uses distinct base material patterns; the chase pattern is not reused by a lower-tier gun.
- Retain the previous27a kit/material definitions and colour families so existing owned skins continue rendering.

Extract ALL files with CS2 closed; start cs2_gc_debug.exe. Test: Brimstone tile uses Desert Eagle,
Cascade tile uses AWP; Ashfall has one Ossified pattern, and the lower-tier guns have other patterns.
Redeem several times to confirm colour variations still roll and older owned27a skins still render.
These specific corrections still need in-game verification. Existing custom trade-up/claim limitations remain.

---

# Additional27a fix — bot VPK read error

The screenshot names game/cs2_gc_bots/pak01_000.vpk as unreadable. The rewards helper previously
ran native preparation again inside the running game, including repacking VPKs. It now only handles
rewards/console/profile configuration; all native archive preparation runs before launch in cs2_gc_debug.exe.
This removes a possible archive-replacement race. The exact crash trigger still needs a retest.
Run the updated launcher with CS2 fully closed so it rebuilds any mismatched bot archive.
Do not delete your inventory or finish-ID map. If preparation fails, send cs2_gc_prepare.log instead of starting CS2 directly.

# Helper hotfix27a — preparation failure after build27

Same DLL tag `codex-20261022-27`; Python helper fixes. Extract ALL files over build27, close CS2 and run
cs2_gc_debug.exe. Do not start CS2 directly for this check: preparation must finish successfully first.
Keep your inventory, active config and finish-ID map; no reset is needed.

The supplied preparation log showed KV3-v4 material parsing aborting finish generation while the launcher
still continued. The latest GC session loaded build27 but rejected the colour-family file. The dump records
a null read in client.dll+0x1138394; without game symbols this does not identify the exact crash trigger.
A mismatched generated schema/material/family set is a plausible cause, not yet proven by a successful retest.

- Skip unsupported donor KV3 versions before recolouring; the KV3 writer remains v5-only.
- Use verified gun-pattern donors for recoloured filler slots rather than attempting arbitrary official materials.
- Unexpected finish preparation errors now stop launch instead of silently rebuilding a partial catalogue.

Test: run the helper; cs2_gc_prepare.log must show successful finish generation with no `skipped` KV3 error.
The GC log must accept cs2_gc_skin_families.txt. Then open Armory, inspect custom collections, and restart.
If it crashes again, send the new preparation/GC logs and dump. Native tile rendering remains unverified.

---

# Build27 handoff — collection-only overhaul

DLL tag: `codex-20261022-27`. Target CS2 build25966348.

Close CS2 and the helper. Back up your inventory, active config and **cs2_gc_finish_ids.json**.
Extract ALL files into game/bin/win64 (including collection_icons), preserving your real Steam DLL,
inventory and finish-ID map. Run cs2_gc_debug.exe. Python3 is still required.
Only an example config is shipped; your active config stays yours. The launcher regenerates the owned packs.

Changes:
- Custom Armory collection tiles use one native live 3D chase weapon, keeping the stock click target, title and price.
- Twelve gun collections keep the stock 1 red / 2 pink / 3 purple / 4 blue / 6 industrial layout.
  Chase patterns now include nine gun patterns and three knife-family patterns, across five top weapons.
- Colour families remain one named entry that rolls a colour variant. Pink/purple and two blue slots also get recolours.
- Unchanged official weapon/material pairs and repeated unchanged custom pairs are excluded, including material aliases.
- Ten collections rotate in Armory. Eclipse and Monsoon are drop-only: by default 15% of weapon reward slots,
  respecting match_skin_min_rarity. Existing case/weapon split stays unchanged. Configure custom_collection_drop_percent=0 to disable.
- No new custom gun cases. Previous kit/material definitions remain generated for owned skins.
- Existing Dead Hand recolour removal remains in effect.

Test these:
1. Launch and confirm tag27 and a successful preparation log; open Armory and rotate several times.
2. Custom collection tiles: one visible 3D chase, readable title/price, correct click destination, no gold question mark.
   Check performance and framing on different resolutions; stock tiles should still render normally.
3. Inspect each collection and redeem several times: 16 entries, varied base patterns, colours change within each named family.
   Compare preview with the redeemed item in inventory and in-game. New donor/weapon combinations need visual verification.
4. Eclipse/Monsoon must never appear for purchase. Earn weapon rewards; optionally temporarily use
   match_case_percent=0 and custom_collection_drop_percent=100 to test the two pools quickly. Restore your settings afterward.
   Rewards must respect the configured minimum rarity and have no StatTrak.
5. Check older owned custom skins still render and survive restart. Check normal cases, souvenir purchases and selling.

Still pending: custom collection trade-up membership and the inventory reward-claim timeout are not fixed by this build.
No end-of-match drop popup was added. Automated checks do not prove native rendering or claim delivery.

See CUSTOM-COLLECTIONS.md for the intended chase/availability list. Missing source materials fall back to verified donors;
a collection with too few usable entries is omitted rather than sold incomplete.

---

# Build26q (Claude): stock collection layout + 12 custom gun cases

- User: custom collections/cases must "look like this in the armory ... follow the layout rule for the
  collections" (Overpass 2024 grid). Stock Armory collections are 1 Covert / 2 Classified / 3 Restricted /
  4 Mil-Spec / 6 Industrial (checked set_overpass_2024, set_graphic_design, set_train_2025). FILLER_TIERS now
  follows that; a Classified chase (USP-S, Glock) gets 4 Restricted / 5 Mil-Spec / 6 Industrial instead.
- Custom cases (user's answers: Armory case slot, guns only, no gold, "a few random per case" ranges):
  native_skins.custom_cases(): 12 crates crate_cs2gc_case_<name> ("Ashfall Case" ...) with the user's
  OfflineCS case pictures (tools/case_icons/cs2gc_*.png), base 4003 key, same 16-skin layout. Ranges: the
  Covert chase (cgf_ family on a top gun) plus one Classified and one Restricted classic pattern
  (hydro/spray) family cgc_<pattern>_<tier> whose colours cgr_<pattern>_<theme>_<tier> use NEW recolour
  materials rc_<pattern>_<theme> (native_finishes.make_finish, 8 themes). Sold in the Armory case slot
  (armory_case_price); RollMatchDrops skips crate_cs2gc_case_*; the catalogue no longer sells *_test crates.
  custom_cases = 1 (default). collections() now returns the families dict; family_text() writes the file.
- User wants these trade-up-able later. Note: client item_sets need #CSGO_ tokens (see 26n), so collection
  membership for trade-ups must come from somewhere else (GC-side list) — not done yet.
DLL tag claude-20261021-26q.

# Helper26p (Claude): chase rarity by gun, families = our colours only, one name per family

User clarifications: the chase rarity follows the gun (AK red, USP purple: CHASE_TIERS — USP-S and Glock
Classified, others Covert; fillers only below the chase); a family holds only our colours, not the official
original ("not the normal fade"); every colour is named just like the family ("when you unbox a marble fade,
it's just marble fade, but different colour"). Variant kits cgv_<recolour>_<tier> reuse the rk_ material
(weapons/paints/cs2_gc/<rk>.vcompmat) with the family title and the chase tier; cgf_<family>_<tier> families map
to them. Black Market knives keep their own rk_ names. Room for more colours/skins later.

# Helper26o (Claude): 40 small custom collections with one Covert chase each

User: collections like real ones — "a bunch of other skins, and then one red that's going to be an AK ...
Doppler", unboxing it gives a colour of the family; same for Tiger Tooth, Twilight Galaxy, Case Hardened
(patterns via seed, colourways via rk_ recolours) etc.; "like 40". native_skins.collection_specs(): 40 lists
set_cs2gc_<family>_<gun> ("The AK-47 Doppler Collection"), chase = cgf_<family>_ancient on one of AK-47, M4A4,
M4A1-S, AWP, USP-S, Desert Eagle, Glock-18 (each family on 2-3 guns). Each list: 1 Covert chase, 2 Classified,
3 Restricted, 5 Mil-Spec ordinary skins = official generic patterns (styles 1/2/3/8, no weapon-named kits) on
guns that never had them, via alias kits cga_<kit>_<tier> (official material, our rarity, official title).
Families file unchanged in format (only cgf_*_ancient now). Test cases: crate_cs2gc_collections_test (all 40,
real odds) and crate_cs2gc_chase_test (only the 40 chases, random colours); grant cmds for both.
custom_collections = 1 puts the 40 in the Armory collection rotation (callout from COLLECTIONS). Same DLL 26m.

# Helper26n (Claude): 26m crashed CS2's schema load — no item_sets

User got "Assertion Failed in function CEconItemSystem::ParseItemSchemaFile(): false" with 26m. client.dll
strings include "Item Set %s: item locname tokens must be #CSGO_%s" / "no localized name": the three custom
item_sets used literal names. Removed item_sets; the collections are client_loot_lists only (like charm and
sticker packs), and the Armory rows get their callout from native_skins.COLLECTIONS. Do not add item_sets
without a real #CSGO_ token (the language file cannot be overridden safely). Same DLL 26m.

# Build26m (Claude): custom colour-family collections + test case

User approved colour families ("families sounds great"). native_skins.collections(): family paint kits
cgf_<family>_<rarity> (16 families x 4 tiers) reuse an official finish's composite material for the picture and
title; three item_sets/client_loot_lists — set_cs2gc_doppler (Doppler, Gamma Doppler, Marble Fade),
set_cs2gc_spectrum (Fade, Twilight Galaxy, Gold Brick, Blue Phosphor, Ultraviolet), set_cs2gc_classics (Tiger
Tooth, Slaughter, Crimson Web, Damascus, Case Hardened, Blued Steel, Bright Water, Freehand) — one entry per family
per gun, tier by gun (TIERS: rifles/AWP/Deagle Covert ... shotguns/LMGs/autos Mil-Spec). Families file
cs2_gc_skin_families.txt (family kit -> official variants + rk_ recolours) is loaded by the GC
(Schema::LoadSkinFamilies); RollLootList and the Armory pity top-reward call ApplySkinFamily, granting a random
variant at the tier's rarity. Variants are not item_set members (no trade-ups from them). Grant-only
crate_cs2gc_collections_test (loot = the three collection lists). custom_collections = 1 (default 0) adds the
collections to the Armory rotation as collection rows priced 4 like the others, after the user's test.
patch_items_game gained extra_sections, loot_lists cases and per-kit _rarity. DLL tag claude-20261021-26m.

# Helper26l (Claude): Custom Skins Test Case 2

User: batch 1 "all honestly work. really well". Batch 2: crate_cs2gc_custom_skins2_test (grant
grant_custom_skins_test2_cases.cmd) with the knife finishes on the other 24 guns plus 8 fade/doppler
recolours each, and Twilight Galaxy / Gold Brick / Blue Phosphor (am_aqua_flecks, am_gold_brick,
am_m4a1s_bluesmoke) on all guns where unofficial, plus 4 of their recolours per gun (~760 items). Same DLL 26k.
Next (user approved): colour families (one collection entry per finish family per gun, GC rolls a variant on
grant) and 2-3 custom Armory collections priced like collections.

# Build26k (Claude): Custom Skins Test Case (phase 1 of custom weapon collections)

User: custom skins "same as armory collections, lets make them those instead of cases. but we will need test
cases first". New tools/native_skins.py: grant-only crate_cs2gc_custom_skins_test (base 4003, Black Market
icon) with the official knife-only finishes (Doppler/Gamma phases, marbleized, Marble Fade, Tiger Tooth,
Slaughter, Damascus, Crimson Web, Fade, Case Hardened, Blued, Bright Water, Freehand, Ultraviolet) on AK-47,
M4A4, M4A1-S, AWP, Deagle, USP-S, Glock, FAMAS, Galil, P250 wherever that pair is not official, plus 12
fade/doppler rk_ recolours per gun (existing kits, no new materials). RollMatchDrops now skips every
crate_cs2gc_*_test. grant_custom_skins_test_cases.cmd adds 20. DLL tag claude-20261021-26k. Rendering on guns
unverified (knife-only kits may carry knife-tuned pattern scale/legacy-model flags). Phase 2 after the user's
check: custom item_sets + tiered loot lists as Armory collection rows (catalogue), priced like collections.

# Helper26j (Claude): Dead Hand custom gloves removed

User: "forget the dead hand custom gloves, remove them completely". DEAD_HAND_RECOLOURS = False: no Dead Hand
recolour is in any case, so the Dead Hand Test Case is no longer generated (grant_dead_hand_test_cases.cmd
removed). Already-owned rg_glove_* recolours keep their definitions/materials (known ids) so inventories stay
valid. Classic glove recolours, the four ug_ unreleased finishes and the Gauntlet Case are unchanged. The
Dead Hand rules/tests remain (tests flip the flag on). Next user request: an LTD custom weapon-skin case.

# Helper26i (Claude): Dead Hand curation — only recolours that look proper

User: "keep the ones that work really well, and ones that dont really change or have clashing colors take
out". distinct_themes drops Ash (it only greys the trim of a printed glove) and colours whose hues are all
within 20 degrees of the glove's own accent hue (look like the original), after harmonious_themes.
DEAD_HAND_EXTRA_THEMES now holds the colours the user approved on screen (Cloud Chaser Inferno, Chesterfield
Midnight, Occult Toxic/Magenta, Violet Beadwork Rose/Azure, Ultra Violent Aurora/Cobalt, Plum Quill Sunset,
Red Racer Rose); Brocade Flowers Ember was rejected by the user ("things like this, no"). Red Racer's tan suede
(g_vId4Color, sat .179) is recoloured via DEAD_HAND_EXTRA_ACCENTS with saturation up to .5.

# Helper26h (Claude): Dead Hand recolours only in colours that match the printed parts

User: "just do the ones that work ... use colors that work well with whats already there ... same with all
dead hand gloves" (examples: Lime Polycam Violet, Creme Pinstripe Aurora clash with the printed parts).
Every Dead Hand glove now offers only harmonious_themes(hue): single themes within 60 degrees of the glove's
main hue (plus neutral Ash) and duo themes with both hues within 60. Hue = DEAD_HAND_PRINT_HUES (printed
colour read from screenshots: crane/velvet/pinstripe red, flower/seigaiha teal, Ultra Violent/Plum Quill
purple, Sunburst orange) else the saturation-weighted mean hue of the finish's clear visible accents
(dead_hand_main_hue). DEAD_HAND_SKIP (Big Swell, Blaze) gets no recolours. Owned recolours in colours no
longer offered keep their ids/materials (retained, not in any case). DEAD_HAND_FREE (empty) re-enables all
colours for a finish. Classic gloves unchanged.

# Helper26g (Claude): wear-edge-only Dead Hand accents are not recolours

User: Pillow Punchers Teal (glove_specialist_quilted_white) looks unchanged — its only accents are
DamageBevel/Burnishing tints (worn edges). Report accent_channels now excludes those (WEAR_ONLY), so such
finishes are not offered (owned ids still render). Occult Ash (glove_sport_velvet_red) also looked unchanged:
the red velvet and gold are most likely colour textures; awaiting the user's list of Dead Hand finishes that
barely change before excluding them individually. Chesterfield's gold TORTUE plate/studs, brocade/wave/
Seigaiha prints are texture colour too (user offered texture recolouring as a later option).

# Helper26f (Claude): Dead Hand muted shades, two missed Dead Hand gloves, camo hand-wrap panels

From the user's cs2_gc_glove_palettes.json / cs2_gc_glove_materials.json (26e):
- 20 of 22 Dead Hand finishes were recoloured. glove_driver_dragon_scale_red and
  glove_driver_embroidered_flowers_teal use the same 'paint' + COPY_MATCHING_KEYS layout but were dropped:
  dead_hand_colours required all eight g_vId*Color, and make_glove_finish's fallback then overwrote the
  inspection entry (now merged with setdefault/update). Any recognised colour vector is enough now.
- Plum Quill (glove_driver_ostrich_purple) stayed purple because its ostrich purples are muted (Id3 242/.30,
  Id5 254/.32, Burnishing4 259/.32, bevel 271/.26). dead_hand_accents adds muted shades (sat>=.18, value>.12)
  within 25 degrees of a clear accent hue; creams/tans/greys of other hues stay. Recolour per channel uses the
  same recolor() targets as before, so previously-changed channels get identical values.
- Big Swell's blue leather and the brocade panels are texture colour (white tints): not changeable.
- handwrap_camo_grey: one accent (ch5), camo in seven near-grey green tints; White Panels erased it
  (user: "definitely broken"). NO_PANEL_VARIANTS stops new panel variants for it; owned variant ids still get
  definitions but render with the original-panel colours.
- glove_driver_knit_argyle_green and glove_specialist_graffiti_black have no accents: no recolours (unchanged).
Wear: normal random float/seed per item; bright clean ones are low-float rolls.

# Build26e (Claude): grant-only Dead Hand Test Case; first Dead Hand screenshots

New crate_cs2gc_dead_hand_test ("Dead Hand Test Case", base 4017, Gauntlet icon): exactly the Gauntlet entries
that are Dead Hand recolours (kit names rg_glove_*). Only from grant_dead_hand_test_cases.cmd
(grant_custom_cases.py --dead-hand-test N); not in Armory/Store; RollMatchDrops skips it (core test fails
without the skip). DLL tag claude-20261021-26e (same source as 26 plus that one line).

User screenshots after 26c:
- Driver Gloves | Brocade Crane Glacier: leather changed to blue-violet, tan palm and the red/gold brocade panel
  unchanged (brocade colours are in its surface colour texture, as expected). Plausible, not yet judged by user.
- Driver Gloves | Plum Quill Ash: still purple ostrich + brown, i.e. Ash did nothing visible. The purple is most
  likely the ostrich surface colour texture with a white tint, so g_vId/tint vectors cannot grey it. Need the
  user's cs2_gc_glove_materials.json / cs2_gc_glove_palettes.json for glove_driver_ostrich_purple before
  deciding; do not guess (multiplying a purple texture cannot make grey).
- Hand Wraps | Spruce DDPAT Midnight (classic, handwrap_camo_grey): user says "definitely broken" — wraps almost
  white, camo gone, only the stripe purple. Almost certainly a White Panels variant (clean names hide which):
  the camo is carried by neutral tints and the white panel mapping (.82+.10*sqrt(v)) flattens it. Needs the
  palette report for handwrap_camo_grey; candidate fix is no panel variants for finishes whose pattern lives in
  neutral channels, keeping owned ids. Not changed yet (avoid blanket changes to approved gloves).

# Helper26d (Claude): test grants broke inventories with care packages — fixed

User ran grant_gauntlet_cases.cmd (26c) and the GC started with an empty inventory. Cause: Inventory::FromText
requires every care_packages/<generation> preview block to repeat the profile's next_id exactly; the grant
(grant_test_items.add_items, also Codex's grant_test_items.py) only bumped the top-level next_id, so the whole file
was refused ("invalid, starting empty and not saving over it"). Nothing was overwritten. add_items now updates
every care-package next_id copy too; verified with the real core loader (invalid before, valid after).
repair_inventory.cmd (grant_custom_cases.py --gauntlet 0) re-syncs an already-granted file, keeping the cases.

# Helper26c (Claude): Dead Hand recolours in the Gauntlet Case

User request: Dead Hand gloves recoloured with the same care as the classic gloves; originals stay in the Dead
Hand Terminal, recolours go only to the Gauntlet. Inspected the user's extracted
glove_driver_brocade_phoenix_red.vcompmat_c / .vmat_c (same volatile_02 layout): a LOOSE_VARIABLES container
alias 'paint' holds one LOOSE_VARIABLE_TYPE_RESOURCE_MATERIAL m_strResourceMaterial (the finish's own
items/assets/paintkits/volatile_02/<kit>.vmat, shader csgo_customglove_preview.vfx), and
COMP_MAT_PROPERTY_MUTATOR_COPY_MATCHING_KEYS from 'paint' copies its parameters into the all-white
glove_compositor template. So the white g_vId*Color in the template are defaults; the finish colours are in the
paint material: g_vId1..8Color (tint-ID regions, F_TINT_ID=1, alpha kept) plus g_vSurface/Substrate/Burnishing/
DamageBevelColorTint1..4. native_gloves.make_dead_hand_finish copies both files, changes only those colour
vectors with the same recolor_accents policy (chromatic only, value/alpha kept, saturation capped; greys/whites
untouched) and repoints m_strResourceMaterial/m_materialName. Textures, normals, floats, placement and
non-colour vectors stay identical (test restores and compares). Requires the copy mutator, exactly one paint
resource material, a known shader and all eight g_vId*Color; anything else falls back to the old path/report.
Original panels only: Dead Hand white tints are identity layer multipliers, so panel variants would black out
layers. Pattern colour baked into textures (e.g. brocade colour maps) cannot change; native appearance unverified.
The four ug_ unused finishes are unchanged. New grant_custom_cases.py / grant_gauntlet_cases.cmd add test
cases by generated schema name (test tool, keep out of release packaging).

# Current client report: build26 BOT prefix still present

User screenshot shows literal [BOT] before Ari_, goldnova_, Arlo_ and grayfox_ in the killfeed. Names themselves remain visible. Treat native bot decoration localization override as NOT live-validated/fixed. Investigate whether killfeed uses a separate native bot marker or localization token; do not reintroduce blank names or claim scoreboard-name fix removes killfeed marker. User specifically requested this note for Claude.

# Helper26b: corrected Dead Hand inspection, recolours still blocked

User supplied glove_materials94 entries / glove_palettes72. Exactly22 volatile_02 Dead Hand composites all reference workshop/paintkits/templates/glove_compositor.vmat, shader csgo_customglove.vfx. All22 have IDENTICAL template vectors: g_vId1Color..8Color white, not classic g_vColorTint1..8. Exporter only dumped template, not m_Points overrides; that is insufficient for detailed recolours. Do NOT tint all white template channels or fake material parameter names.

Corrected report_version2 adds typed/ordered composite_document from the actual compiled vcompmat DATA, preserving nested names/values/types (including duplicate names), omitting binary bytes. Next launcher prep regenerates cs2_gc_glove_materials.json. Need user's regenerated report to identify per-finish parameters and implement accent-only edits while preserving normals/roughness/texture masks. No Dead Hand recolours added in26b, originals/terminal pools unchanged. Existing classic-glove recolours unchanged. Same DLL26. Includes26a Store Keys removal.

# Helper update26a: Store Keys tab

User confirms cases removed, rarity resale desired and tested best knife/glove resale below custom-case cost. native_store removes case-associated key names/IDs and every weapon_case_key prefab (including inherited/unlinked keys) from price entries/banner layout. Inspected native StoreItems.MakeStoreItemList classifies key banners; MakeTabsBtnsFromStoreData creates key tab only when category nonempty. No guessed UI IDs or layout rewrite. Existing inventory key selling unchanged. Same DLL26, helper pack26a. Store tests14 pass. Live tab disappearance requires user restart/test.

# Build26: economy safeguards, Store cases, bot labels and material inspection

See TEST-BUILD.md for current behavior and test list; it supersedes older notes below. DLLtag26. Terminal purchases explicitly remain sellable by rarity/wear: do not mark terminal offers noStarSale. Free generic Store grants are marked noStarSale, persisted and inherited by opening/coupon repair/contracts/charm detach/slab seal. Native attribute2 (cannot trade, verified in schema) exposes the restriction to the sale menu. Existing inventory is not retroactively marked. Free terminal purchases are an intentional remaining income route per user instruction, so do not claim an exploit-proof economy.

Store patch removes standard/custom case entries and banner tiles while retaining terminal entries. Proxy canSell rejects direct/coupon case purchases. Default charm blue1/purple3/pink9/red25, blue cap2; weapon/glove wear multipliers125/110/100/80/60. Fixed LTD resale capcost-1; custom gold purchase floor above max wear-adjusted gold resale. XM official price corrected15; Deagle25/M4A1-S25/Aphrodite125; custom Howl250. Collection pity reused for souvenir with independent souvenir:<lootlist> keys; decorate native quality/decals after tier roll, charge only on success.

Bot prefix fix generates COMPLETE installed English localization, replacing exactly two native decoration token values while preserving %s1/%s2. Separate reversible owned pack cs2_gc_bot_labels, bot_hide_tag controls it. No guessed killfeed event/API and no layout patch; native client validation needed. Other game languages not yet covered.

Teal and Hardened knife fixes are on branch after PR17 merged and must be included in follow-up PR. Snow Leopard panel changes preserve dark neutrals<=.25 in this finish only; native appearance unverified. Recent screenshots: Lunar Ash subdued grey/brown consistent; Racing Sunset too subtle; Black Tie Aurora almost unchanged; Emerald Web Aurora/Toxic nearly identical. Record/refine selectively, avoid blanket palette changes.

Dead Hand request: official originals stay in terminal, independent recolours in Gauntlet. Removed blanket skip of composite_material_path: resolve actual schema path and recolour ONLY when existing strict SPECIFIC_MATERIAL + csgo_customglove.vfx + eight g_vColorTint1..8 validation succeeds. Unknown formats remain unchanged; launch writes cs2_gc_glove_materials.json with material shader/vector diagnostics. Need that current report before implementing different shaders/container layouts. No fabricated offsets/parameters or full-coverage claim. Existing Gauntlet pool count2084 is previous coverage, not an updated count after probing.

Claim timeout is still pending. Current log7 was inspected: no9219 frames/claim diagnostics in latest session. StoreAPI may be refusing synthetic descriptor IDs before send (inference). No transport rewrite in26. Never restore unowned preview econ objects that crashed clients. Mission completion XP/stars/Career/release packaging remain pending.

---

# Build25: souvenir-only local contracts and feature notes

Backend TradeUp no longer rejects every souvenir as NotASkin. Config souvenir_tradeups=1 in both parsers. All-souvenir same-rarity ten-input contracts use existing collection weighting/wear mapping and retain Souvenir quality plus one provenance donor selected only from the winning collection. Applied stickers/charms do not transfer, and no new gold decal set is minted. Mixed normal/Souvenir, invalid Souvenir StatTrak and disabled mode refuse atomically; Covert souvenirs never generate souvenir gold items. Unsupported higher-tier outcomes refuse without consuming inputs. Normal/mixed StatTrak behavior retained.

Existing inspected recipe normal input quality already includes tournament (stock unique,tournament; shared unique,strange,tournament), so no new Panorama patch/command path was introduced. Native UI selection/submission still untested. Build tag25, both Windows debug/release cross-builds compile, all26 suites pass. Core tests include native econ quality/event attributes, provenance from weighted winning collection, wear, persistence, disabled/mixed refusal and no-outcome preservation.

FEATURES.md records calculated pools using supplied material coverage: Black Market20 models/1005 finishes/4980 pairs; Gauntlet8 models/2084 finishes/2084 pairs (2080 recolours plus4 shipped unused). No wear/seed/StatTrak multiplication. Pool count reconstructed from current generator, actual runtime can omit unavailable material resources.

User explicitly requested noting Butterfly The Fuschia Is Now Ash nearly-silver contrast issue as a feature task. It is pending, no knife colour algorithm change in25. Earlier Gold Brick green screenshot after24c demonstrates colour change but not all donor texture mapping/sheens validated. Many glove finishes user-approved; avoid blanket resets.

Care-package claim timeout remains unresolved. Latest supplied logs are older, do not guess more transport changes without current cs2_gc_log.txt after a failed claim. No new reward claim code in25. Economy/pity/killfeed/mission rewards/Career and release packaging remain in FEATURES.md.

---

# Additional24c check: Lunar Weave

User Lunar Weave Ash screenshot remains blue/teal. slick_black supplied palette has muted blue/teal channels2/4/5/6 below.35; finish-specific threshold.14 with hue160–250 targets exactly those four, leaving brown/red source colours. Ash caps saturation.10. Textures/wear/roughness unchanged. Fixture and supplied-palette checks pass; native appearance unverified.

# Helper/material update24c: findings from supplied palettes

User supplied knife85/glove72 palette reports. Gold Brick has four related gold source tones; previous rank-based Toxic assigns its neighbouring shades unrelated lime/purple hues. recolor_gold_brick now rotates the related palette to the theme primary hue, preserving circular hue differences/value/alpha and capping saturation. Applied only to am_gold_brick recolours (existing rk identities); official gold base and other knife algorithms unchanged. Supplied Toxic output hues now82–87.8 degrees, values1/1/.937/.733. This fixes the palette relationship, not a verified model UV/material rendering issue. Need live test before claiming appearance fixed.

Bronzed (bloodhound_metallic) has two identical muted bronze vectors (channels1/6) below global saturation.20/.35 boundary; specific threshold.20 recognises only these two, leaving six neutral tints. Supplied palette evaluation confirms changes exactly1/6, with original saturation/value retained. No arbitrary anatomical channel mapping introduced.

Five supplied glove palettes have no detected accents: bloodhound_metallic (now addressed), handwrap_leathery_ducttape, motorcycle_smoke, operation10_snakeskin_black and sporty_jaguar (Nocts). No-accent themes are excluded from Gauntlet instead of advertising colours that do not apply; known saved variants still get definitions/materials under same IDs. Source reports still generated. Do not drop owned definitions or reset IDs. Tests cover retention and exclusion together.

Latest user screenshot: Racing Green Sunset still mostly green. slick_stitched_green_grey actual green/teal channels1/5 are muted (saturation~.298/.224) and skipped by.35, while7/8 are brown and were coloured. Added finish-specific.20 threshold plus hue75–180 degree filter, which supplied-palette evaluation confirms targets exactly1/5. Original-panel brown accents remain, while explicit neutral-panel variants keep their panel behaviour. Display base title Racing replaces Racing Green, yielding Racing Sunset etc. Internal kit names/IDs unchanged. Other glove policies unchanged. User confirms MANY existing recolours look excellent; avoid broad resets.

Includes24b charcoal and clean names for ALL panel variants and24a case presentation/direct grants. All changes are Python/material preparation; same24 DLL. All26 suites and new targeted tests must pass before packaging. Original user reports stay private/uncommitted. Exact24c appearance unverified.

---

# Helper/material update24b: charcoal and clean inverted names

User confirms many Sport glove recolours look excellent; black panels too crushed. Changed black neutral tint transfer from .025+.075*sqrt(v) to .12+.08*sqrt(v); inverted endpoints from .04/.92 to .12/.90. Other panels, accents, approved legacy palettes and all texture/wear/roughness/reflection properties unchanged. Values are material tints, not screen RGB or a validated leather calibration. Target-client comparison pending.

User clarified all variants need clean names. Omit White/Black/Inverted Panels suffixes; all _panels_* internal names/IDs remain distinct and stable. Different panel variants now share the base+theme display name. Regression checks all three styles.

Gold Brick Toxic screenshot is mostly purple rather than gold. Code audit: Toxic replaces original colour channels with lime/purple, assigning brightness-ranked middle channels purple. Cannot infer knife texture/channel coverage from this screenshot. No knife appearance fix claimed or new guessed texture controls. native_finishes.prepare now writes cs2_gc_knife_palettes.json with actual source paths/shader/original+themed vectors. Ask user for it to investigate Gold Brick against actual installed materials. Regression verifies complete material DATA equals the original after undoing only name/colour edits, including texture and roughness fixture fields.

All26 suites pass after changes. Python/material-only update uses existing24 Windows DLL; no new binary rebuild required. Keep inventory/config/finish-ID map. Care-package claim, economics and mission progression remain pending as below.

---

# UI hotfix24a: restore case display, keep direct rewards

User explicitly rejected the finish gallery. Removed custom_rewards preview expansion and random-reward callout changes from rotate_armory.py. Black Market/Gauntlet retain the original crate entry type, single case model, names, native contents and layout. local_direct_case is retained only to hide the irrelevant key warning. Backend direct grants from build24 are unchanged. UI-only patch uses the same build24 DLL; native_resources rebuilds the script override on launcher preparation. Test asserts both custom entries remain cases and their original loot lists/suffixes remain intact. Do not reintroduce the finish gallery.

---

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


## 26r (Claude) - custom gun cases become Armory collections
- The 12 custom cases are now collection tiles (`set_cs2gc_case_<name>` loot lists, rotation type `collection`, count 4)
  like Arabesque: no crate items, no keys. native_skins.custom_cases writes a top list plus the tier lists.
- Emblems: tools/make_collection_icons.py draws CS2-style diamond badges into tools/collection_icons/; native_finishes
  packs them as panorama/images/econ/set_icons/<name>_png / _small_png (template set_arabesque), and the catalogue
  rows set ui_set_image = <name>. The old tools/case_icons pictures are removed.
- The DLL is unchanged from 26q. Crates bought in 26q (crate_cs2gc_case_*) no longer have a definition, so open them first.
- LIVE (user, 21 Oct): the tile and nav emblem render, the callout reads "The Ashfall Collection", and unlocking works
  (e.g. "Desert Eagle | Marble Fade" from The Brimstone Collection, AK-47 Doppler chase from opened cases).
- OPEN BUG, for the next person: the tile has NO gun preview and the collection page is EMPTY.
  Cause (from the user's xpshop.js): _GetLootListForReward('lootlist:set_cs2gc_case_<name>') gets
  InventoryAPI.GetLootListItemsCount(...) == 0, so lootlist = [rewardId], so the single-image path with a non-item id is used
  and PlaceTiles returns early. Stock 'lootlist:set_arabesque' has the same nested structure and works.
  NOT the cause: list order (the stock schema has 562 forward nested refs; 26r now writes the tiers first anyway,
  matching set_arabesque, which is harmless). The same nested lists DO preview inside a crate (collections test case),
  so the items and kits are valid on the client. The difference is probably how the native resolves a "lootlist:" reward
  name (maybe item_sets, which we cannot add: client needs a #CSGO_ localised token, see 26m crash).
  Suggested fix, same approach as 17v native_knife_reel: patch xpshop.js _GetLootListForReward so that when the count is 0
  and the name starts with 'lootlist:set_cs2gc_', it fills itemsList from a generated JSON
  (list name -> [def index + paint kit] -> InventoryAPI.GetFauxItemIDFromDefAndPaintIndex), written by native_finishes
  next to the collection lists. Do not invent APIs; GetFauxItemIDFromDefAndPaintIndex is already used in xpshop.js.
- 26s (Claude): implemented that fix. native_finishes writes cs2_gc_collection_previews.json
  ({collection: [[weapon, kit id]]}, chase first) and rotate_armory passes it in m_localRotation.previews; the patched
  _GetLootListForReward uses it only when the native count is 0. NOT verified live yet; if the tiles stay empty, check
  that cs2_gc_collection_previews.json exists next to the proxy and that the Armory override was regenerated (restart twice).
- 26s LIVE (user): previews WORK. The collection page shows all 16 skins in 3D and the chase is correct.
- NEXT TASK FOR CHATGPT (user's choice): the main Armory tile for a custom collection shows CS2's gold "?" medal.
  Cause: the tile carousel (_MakeShopTile, the `lootlist.length > 1` branch) creates 2D `ItemImage` panels, and new
  weapon+kit pairs have no shipped default_generated icon (same root cause as 17w). The emblem itself is fine (top-left).
  The user wants ONE 3D MODEL on the tile, like the "Received from Armory" screen, not the emblem or a 2D picture.
  Suggested approach, using only calls already in the user's xpshop.js:
  in _MakeShopTile, when ShopEntry.item_name starts with 'lootlist:set_cs2gc_' (or m_localRotation.previews has the name),
  skip the ItemImage carousel and create a model with the existing MakeMapItemPreviewPanel(elTile, camera, 'ui/xpshop_item',
  ShopEntry). Build the camera as in CreateShopTile ('camera_weapon_' + XpShopWeaponCameraSettings entry for the def name),
  then elModel.SetActiveItem(0); elModel.SetItemItemId(ShopEntry.lootlist[0], '') (lootlist[0] is the chase, the previews are
  written chase first), as at xpshop.js ~lines 478-482, and set hittest false so the tile button still opens the page.
  Risks: the tile is smaller than an inspect tile (sizing/CSS class), render cost (use SetRenderInterval like line 482),
  and patch_previews already rewrites nearby code, so assert each replace target count == 1 and test it with node like
  test_custom_collection_previews_fill_an_empty_native_loot_list. Only the custom collections may change; stock tiles stay.
  Do not claim it works until the user sees it in game.
- Still to do: trade-ups for custom skins (GC-side collection membership; client item_sets are not possible),
  effect finishes (glitter/pearl) waiting on the user's extract_finish_materials output, custom_collections (40 chase
  collections) default 0 until the user asks.

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
- Star economy (22 Oct): new `AuditEconomy` (cs2_gc/src/economy_audit.cpp) values every Armory row (incl. case+free key,
  terminal best-of-offers, souvenir, capsule, sticker/charm pack, agent, limited, Black Market) and every trade-up with the
  real odds, long-run pity rate and ItemSaleValue. On the user's schema+config it found loops in all capsules (x10-22),
  sticker packs (x11-13), all cases opened (x3.6-10.7), terminals (x2.3-5), 6/11 collections (x1.9-2.5), 57/148 souvenirs,
  4 charm packs (x1.15) and 12 covert->knife trade-ups (x1.04-1.13). Fix: `BalanceSales` (C++ item_sales.cpp, exact Python
  mirror gameplay_config.balance) lowers configured sale values at load until no route returns more than
  `sell_max_return_percent` (default 90, model at best wear) and trade-ups cannot gain; new sticker sale table
  (`sell_sticker_*`, `sell_sticker_percent` now a cap). All Armory weapon cases cost `armory_case_price` (native Fever
  case was 2); collection/charm/sticker tiles never below 4/3/1. Audit after: no loops; returns ~45-55% cases/terminals,
  35-48% collections, 25-33% souvenirs, ~1-3% capsules, 20-30% sticker packs, 68-85% charms, trade-ups <=80%.
- Build 35 (22 Oct): missions rotate with the Armory (user: "make the missions rotate with the armory"). native_missions
  now writes a pool (cs2_gc_missions.bin: repeated {1 index, 2 template blob}; .json {'variants': [...]}) with every
  combination of each playable recorded template's random lists (49 on the user's 9226.bin), interleaved by template.
  The DLL (LocalGameCoordinator::MissionTick) serves variant (now / armory_rotation_seconds + offset) % pool size as the
  9226 period, pushes the new 9226 when the cycle changes once the game has asked (9225), and the proxy writes
  cs2_gc_mission_current.txt ("variant period") for mission_tracker.py (progress key "period:variant"). REFRESH ARMORY:
  the page sends SetTournamentFavorite(4300000000000000 + offset) on page load and after each Refresh; the 9200 handler
  sets the GC Armory rotation offset and the mission offset from it. Targets stay full; each step reached pays its XP and
  ceil(xp/100) stars (cumulative "stars N" line in cs2_gc_mission_progress.txt -> Inventory::ApplyMissionStars,
  persisted as mission_star_total). Armory passes auto-renew (armory_pass_auto_renew, default 1): a full 40-star track
  restarts and carries over XP. "Add more missions" waits for the user to confirm tracking works live. Not verified live.
- Build 36 (22 Oct): user parked missions ("forget missions for now"); build 35 Refresh did not change the mission
  and SCAR-20 kills did not count while holding a SCAR. Fixes shipped but unverified: MissionTick reports a
  Refresh-made change to the helper (it used to be swallowed), each Refresh gets its own period (window start +
  offset), diagnostics "missions: ..." in cs2_gc_log.txt and "Mission: ..." (why a kill was not counted) in
  cs2_gc_rewards.log. Next time: read both logs before changing anything.
  Custom-collection trade-ups: Schema::TradeUpCollectionsOf/TradeUpCollectionSkins add the set_cs2gc_case_*
  loot-list collections (official item_sets first); a colour variant belongs where its family kit is listed and
  the contract grants a random colour of the outcome family. Client acceptance of these inputs is unverified.
  Multi-sell: inventory context menu "Sell multiple for stars..." opens CS2's own popup_select_item_for_capability
  with capability cs2gc_sell; native_multi_sell.py (override folder cs2_gc_multisell) makes it multi-select like
  casketstore, lists the whole inventory, relabels the confirm button "Sell for N stars" and sells each sellable
  pick via InventoryAPI.DeleteItem after a Yes/No confirmation. Not verified live.
- Build 37 (22 Oct): user confirmed multi-sell works ("flawlessly"); the picker now hides tiles worth 0 stars
  (_LocalSellableOnly re-checks tile itemid attributes every 0.25 s while open). Custom collections did not show in
  the trade-up screen: the client only accepts skins of real item_sets. native_skins.collection_item_sets writes
  item_sets set_cs2gc_case_<icon> named "#CSGO_<key>" / "#CSGO_<key>_desc" (the 26m assertion format) listing the
  owned colours (family variants, never the family kit, each skin in one set); the tokens go to
  cs2_gc_collection_tokens.json and native_bot_names mounts them in its full English override (cs2_gc_bot_labels;
  mounted when bot_hide_tag or tokens; a changed bot-label format no longer drops the tokens). The GC skips
  set_cs2gc_ item_sets (custom path unchanged). custom_collection_tradeups = 0 removes it. If CS2 ever fails its
  schema load after this build, that switch is the first suspect. Gloves: the user's Kimono Magenta showed default
  gloves in a match; it was equipped mid-match and showed after the next map load - no bug found (finish 1437 in
  the log is the official Wave Chaser on another Specialist pair). Not verified live: item sets, language tokens.
- Bot skins (22 Oct, user: "there is a way, give it a go"): CS2's server never asks a GC for bot items (bots have
  no account; the server only sends ServerHello and gets the human's cache), so the GC cannot do it. New optional
  tools/bot_skins.py + bot_skins.cmd install, on the user's PC, Metamod:Source 2.0 (mmsdrop latest), CounterStrikeSharp
  with-runtime (GitHub latest) and ed0ard/CS2-Bot-Randomizer (AGPL-3.0; GiveNamedItem pre-hook + their maintained
  signatures; nothing of ours touches game memory). Mounts Game csgo/addons/metamod via mount_gameinfo (backup
  gameinfo.gi.cs2_gc_bot_skins_backup), sets FollowCS2ServerGuidelines=false, refuses if a foreign Metamod/CSS
  exists, and rewrites the plugin catalogue (original kept as .original) to popular skins per gun / popular sticker
  capsules / popular knife finishes and gloves, resolved by English finish name against the installed schema (all
  35 guns resolved on the user's files). Uninstall removes it. Not verified live; after a CS2 update rerun install.
- Build 39 (22 Oct): user confirmed custom-collection trade-ups work live (P90 Galaxy Reef Grief, Nebula Collection)
  and approved third-party bot plugins. bot_skins.py now installs the CS2-Bot-Improver release (prefers the
  rules_unchanged zip; uses its bundled Metamod/CSS when present, else the official downloads): every addons/ folder
  except plugins/disabled, never its cfg/gamemode_*.cfg, overrides, gameinfo or panel. Its bot config goes to
  cfg/cs2_gc_bot_improver(.cfg|_ffa.cfg) minus binds/difficulty lines, run from gamemode_<mode>_server.cfg files we
  create only when absent (marker line) followed by exec cs2_gc_premier_bots. Skill presets: their botprofile.db per
  tier saved to bin/win64/cs2_gc_bot_presets; native_bot_names.skill_preset picks Low < 10k, Medium < 30k, High 30k+
  from cs2_gc_gsi_state.json and applies our random names on top (PROFILE accepts quoted names; install_override
  takes source=). bot_difficulty: 0 <5k, 1 <10k, 2 <20k, 3 from 20k. Metamod mounted after the write-path
  placeholder (ensure_first_game_path). Refuses to overwrite foreign addons folders. Not verified live.
  Queued next (user): Armory agent tab -> rotating collections of agents grouped by their operation, using the
  operations' own artwork for the tile.
- Build 40 (22 Oct): Armory agent tab = rotating operation agent collections (user; 25 stars, armory_agent_price
  default 25). armory_rotation_catalog.agent_collections groups the official dossier tier lists per operation
  (op09 Shattered Web, op10 Broken Fang, op11 Riptide) into new top lists lootlist_cs2gc_agents_<op> (appended to
  client_loot_lists after the tiers; the only new loot lists in the catalogue), callout #CSGO_set_opN_characters,
  ui_set_image set_opN_characters (the dossier char_pack_* pictures were removed in CS2; the set emblems exist).
  The page shows the operation's own agents. GC: agent rows with a loot list roll 55/28/12/5% by rarity rank (equal
  rarities share), then a uniform agent; LootTiers strips trailing digits from tier suffixes (ancient1/2 were
  rarity 0 = never dropped). The old Random Agent row only ever gave op09 ancient agents. Not verified live.

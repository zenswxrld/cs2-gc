# CS2-GC test build 22 — 21 October 2026

Build tag: `codex-20261021-22`. Includes the build21 crash mitigation and the follow-up fixes below.
This is a test update; the native UI additions below require a run in build 25966348.

## Install

1. Fully close CS2 and its rewards helper. Back up `cs2_gc_inventory.txt`, `cs2_gc_finish_ids.json` and your configs.
2. Extract **all** ZIP contents into `game/bin/win64`. Preserve `steam_api64_real.dll`, schema, replay folder, finish IDs and saved inventory. The ZIP includes an example gameplay config, not an active config that overwrites your choices. New omitted settings use their defaults.
3. Launch the updated `cs2_gc_debug.exe`. It prepares the native resources **before** CS2 starts, avoiding locked VPKs. Python 3 is still required.
4. Check `cs2_gc_prepare.log` for completion and `cs2_gc_log.txt` for the build tag above.

## Implemented

- **Gloves:** every direct glove loot-list roll disables StatTrak. Startup also removes invalid StatTrak flags from owned gloves, preserving IDs, paint, wear, seed, storage and loadout. Mixed-contract weapon StatTrak is retained.
- **Hand-wrap sales:** backend and native menu use the installed `hands_paintable` classification; they no longer require "glove" in the definition's name. Custom hand wraps sell at `sell_knife_glove` (72 by default).
- **Souvenirs:** a separate Armory pool contains the installed packages whose series resolves to local weapon loot (148 in the supplied schema). Armory purchases now grant one weapon directly from that package’s own loot list, with Souvenir quality and event-matched decals; no package is added. The native inspect page shows the weapon pool. Previously owned packages still open without keys. Their weapons have native Souvenir quality (12), persisted event/team metadata, no StatTrak, and event-matched gold decals (foil fallback for older events). Modern named 2021+ packages use map golds; older packages use an available autograph from one of the selected teams. Souvenir weapons are rejected by trade-ups. Wear follows the actual paint-kit range. There is no claim of recreating an actual historical match, MVP or exact Valve souvenir weights; teams are selected locally. Match-highlight charms are not implemented. The two original 2013/Katowice-2014 packages have no local loot lists and are not sold.
- **Armory layout:** top row is two charms, sticker sheet, agent; bottom row is souvenir package, case, terminal, capsule. The two large collection tiles and centered limited offer are retained. Old configs requesting extra offers cannot crowd out souvenirs; excess eligible goods still rotate.
- **Native care packages:** with `care_packages_enabled=1` (default), a completed match and each earned profile level queue four saved offers. The original case/weekly-collection blue+ weapon pool is used. The four choices are lightweight descriptors rendered through native catalogue previews; they are never created as unowned econ items. Only the three claimed rewards enter the econ cache. Exactly three choices can be claimed through the native PersonalStore/StoreRedeemFreeRewards path. Offers are reserved separately from owned items; only the three picks become owned. Duplicate/stale/partial/foreign claims reject. Closing, restarting or earning another package does not reroll existing offers. Queued packages are presented in order; there is no weekly cooldown. The custom end-match Drops tab is suppressed; the working stock XP/Premier screens and their baseline capture remain.
- **Rare custom cases:** within the case half of the reward pool, Black Market/Gauntlet have a combined default 1% chance, split equally when both exist and are enabled. They are excluded from the ordinary case pool. `reward_rare_case_per_10000` controls that combined rate. With the default 50% case/weapon split, it is a combined 0.5% per offered reward. This is independent of case-opening gold pity.
- **No key clutter:** `free_case_keys=1` now opens local cases through the native keyless path, with no generated keys. Existing keys remain usable and sell for 5 stars. `free_case_keys=0` retains normal required/consumed keys. Terminal behaviour is preserved.
- **BOT tag:** the existing native name label now receives the bot name directly, retaining its font and layout. This replaces build 19’s invisible replacement label; an unavailable name restores the stock formatter; human/demo/queued-match names retain stock formatting. Other surfaces such as the victory cards/kill feed remain separate work.
- **Mission launch:** clicking a recurring mission now creates a local listen-server bot match in the mission’s mode and specified map (or a random map from its required group). Deathmatch retains FFA flags; competitive retains its native flags. Unsupported map/mode data shows a message and does not start matchmaking. Practice assists/infinite warmup are disabled. This changes launching only: mission progress, weapon-specific tracking and completion rewards are still pending. Use the required weapon in-game. `offline_mission_launch=0` restores the stock mission button.
- **Limited prices:** Heat Treated, XM1014 Solitude and M4A1-S Solitude are 25 stars each; AK-47 Aphrodite is 125. Previously generated 25-star Aphrodite rows are corrected on preparation. Howl now costs 250 stars by default; existing configs below 250 are raised to 250 and stale generated rows are rebuilt. Higher custom Howl prices and custom-case prices remain configurable.
- **Home promotion:** hides the RUSH promotion and retains the mission card.

## Test checklist

1. Launch once with the updated executable. Confirm preparation completes and skins, loadouts, stars and custom finishes survive restart.
2. Inspect existing StatTrak gloves: the counter/label should be gone, and paint/wear/equipping should be unchanged. Open Gauntlet again to check new gloves are ordinary ★ gloves.
3. Sell custom hand wraps. Verify the confirmation shows your configured glove price, pays once and persists after restart.
4. Check all Armory slots and refresh several times. Buy a souvenir offer: correct collection, Souvenir label, stickers, no key required, and no trade-up eligibility. It should grant the weapon immediately, without a package to open; test more than one tournament/map. Existing packages must still open. Check Aphrodite costs 125 stars and sells for the configured Covert price (50 by default).
5. Finish a bot match, disconnect back to the menu, then open Inventory. No reward popup should open in the end-of-match screen, while the map remains loaded, or on Home. Verify the native care-package popup shows four selectable catalogue previews; no preview should appear as an owned usable/sellable item before claiming. Select two/four: claim must not proceed. Select three: only those three should appear in inventory. Check the fourth is not granted.
6. Close/relaunch before claiming; verify the same four offers remain. Earn a level as well as finishing a match and verify both packages can be claimed in order without a weekly lock. Verify the working stock XP/Premier screens remain and the old custom Drops tab is absent.
7. Open a standard case with no matching key owned, then sell an old key for 5 stars. Also check a terminal still uses its normal offers flow.
8. Check scoreboard bot names lose `[BOT]` and humans retain their names. Click the mission card: verify the correct local map/mode with bots, without the insecure official-matchmaking warning. Mission completion rewards are not implemented. Check the RUSH promotion remains hidden.
9. Rare custom cases are probabilistic. For testing only, `reward_rare_case_per_10000=10000` makes case offers use the custom-case pool; restore 100 afterwards.

## Settings

New launch setting: `offline_mission_launch=1`. Existing defaults: `care_packages_enabled=1`, `armory_souvenir_slots=1`, `armory_souvenir_price=5`, `reward_rare_case_per_10000=100`, `bot_hide_tag=1`, `hide_mainmenu_promo=1`. Charm slots now default to 2. The fixed 4/3/4 layout can show one souvenir, case, terminal and capsule at a time, regardless of larger existing pool counts.

`care_packages_enabled=0` is the legacy immediate-grant mode and custom end-match Drops tab; pending choices are retained for re-enabling. `bot_hide_tag=0` restores stock scoreboard name formatting. `hide_mainmenu_promo=0` restores the promotion.

## Still pending

Bot-match mission launching is implemented; saved mission progress and mission-completion stars/XP are **not implemented**. The native mission card consumes a mission schedule and recurring-mission progress, and weapon-specific missions need reliable kill/event attribution; the existing GSI snapshots alone are insufficient to claim that support. Stock end-match item drops are superseded by the requested care-package flow. Graffiti, exact souvenir match provenance/highlight charms, BOT tags outside the scoreboard, release folder migration and executable icon remain future work.

## Reset

Use `cs2_gc_reset_profile.cmd` with CS2/helper closed: option 1 resets progression/cursors and queued care packages while retaining owned items/stars; option 2 backs up and removes the inventory too. Files are moved to a dated backup folder. A fresh profile starts at level 1 / 0 XP / unranked; `armory_credits` and `premier_bonus_wins` can seed test bonuses. Keep `cs2_gc_finish_ids.json` to preserve the identity of custom finishes in any restored inventory.

## Validation

All 26 automated suites pass. Mission, scoreboard and Armory script patches apply to the inspected client sources and pass JavaScript syntax checks. All 148 supported souvenir offers directly grant and save a souvenir against the supplied schema. Windows debug and release cross-builds are checked separately from live-client testing. Hand-wrap selling and package opening were confirmed by the user on build 19; this update’s UI changes require live testing.

## Build 21 crash fix

The supplied build 19 log ends immediately after creating the first account-zero reward-preview econ item at match end. The supplied minidump shows an access violation reading address 0x30 inside client.dll (+0x83f065); without symbols this does not establish the exact engine function. The rewards helper connection-reset messages follow the client exit.

This build removes all four preview econ objects from live notifications AND reconnect/welcome messages, and removes their destroy notifications on claim. Saved offers are encoded as local selection descriptors; the popup resolves def/paint via the actual InventoryAPI.GetFauxItemIDFromDefAndPaintIndex API. Duplicate rewards retain distinct selectable slots. The backend validates descriptors against the saved generation and exact offers before granting exactly three once. Existing saved queues are converted on publication without changing offers or inventory IDs.

Inventory-only gating additionally checks that GetMapBSPName is empty; stock XP/Premier end-match integration is unchanged. The custom Drops tab remains suppressed. Main-menu and popup native patches pass syntax checks; regression tests cover no preview econ creates at match end/reconnect, selection and inventory/map gating. The native selection transport and crash resolution still require in-game testing.

## Build 22 follow-up

- Pending local catalogue previews explicitly clear ItemTileStore’s automatic faux-item `item-claimed`/expired flags after native tile initialization. Native selection remains exactly three.
- Claim balance is treated as an optional client hint (including zero/default), with the saved generation and exactly three distinct matching offers remaining authoritative. Store metadata is updated before owned-item creates so inventory callbacks see the completed claim. Rejection reasons are logged without personal identifiers. The original timeout’s exact wire data is not yet available: this is a compatibility/acknowledgement fix requiring a live retest, not a confirmed diagnosis.
- Bot names strip native decorated span/font markup, decode entities, then escape text once. Human/demo/online fallback is retained.
- Repeat mission launches stop the previous search, recreate the solo session and wait for verified listen-server settings before starting. Settings that do not settle within three seconds fail locally. Parties are asked to leave before starting a solo bot mission. Mission completion/progress bonuses are still pending.
- User confirmed direct souvenir grants/stickers, Aphrodite’s125-star display, initial mission launch and5-star key sales. Reward selection and repeat mission launch remain unconfirmed. The store also embeds its stock care-package panel; the added automatic popup remains Inventory-only after map unload.

Retest: select exactly three offers (none initially marked claimed), claim and check three owned items/no timeout; restart and check no regrant. Confirm scoreboard names show names without markup. Launch a mission twice, disconnecting between launches. Check Howl250 in the native page. Preserve saved inventory and pending queues.

Mission XP/star completion rewards, achievements and Career are requested next; they are not included in this build. Reliable weapon-specific event attribution and current mission-template data are needed before counting those objectives. Existing match XP/stars are unchanged.

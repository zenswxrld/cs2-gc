# CS2-GC test build 19 — 21 October 2026

Build tag: `codex-20261021-19`. Based on Claude's Gauntlet build/handoff at `92bc6da`.
This is a test update; the native UI additions below require a run in build 25966348.

## Install

1. Fully close CS2 and its rewards helper. Back up `cs2_gc_inventory.txt`, `cs2_gc_finish_ids.json` and your configs.
2. Extract **all** ZIP contents into `game/bin/win64`. Preserve `steam_api64_real.dll`, schema, replay folder, finish IDs and saved inventory. The ZIP includes an example gameplay config, not an active config that overwrites your choices. New omitted settings use their defaults.
3. Launch the updated `cs2_gc_debug.exe`. It prepares the native resources **before** CS2 starts, avoiding locked VPKs. Python 3 is still required.
4. Check `cs2_gc_prepare.log` for completion and `cs2_gc_log.txt` for the build tag above.

## Implemented

- **Gloves:** every direct glove loot-list roll disables StatTrak. Startup also removes invalid StatTrak flags from owned gloves, preserving IDs, paint, wear, seed, storage and loadout. Mixed-contract weapon StatTrak is retained.
- **Hand-wrap sales:** backend and native menu use the installed `hands_paintable` classification; they no longer require "glove" in the definition's name. Custom hand wraps sell at `sell_knife_glove` (72 by default).
- **Souvenirs:** a separate Armory pool contains the installed packages whose series resolves to local weapon loot (148 in the supplied schema). Packages are granted closed and open without keys. Their weapons have native Souvenir quality (12), persisted event/team metadata, no StatTrak, and event-matched gold decals (foil fallback for older events). Modern named 2021+ packages use map golds; older packages use an available autograph from one of the selected teams. Souvenir weapons are rejected by trade-ups. Wear follows the actual paint-kit range. There is no claim of recreating an actual historical match, MVP or exact Valve souvenir weights; teams are selected locally. Match-highlight charms are not implemented. The two original 2013/Katowice-2014 packages have no local loot lists and are not sold.
- **Armory layout:** top row is two charms, sticker sheet, agent; bottom row is souvenir package, case, terminal, capsule. The two large collection tiles and centered limited offer are retained. Old configs requesting extra offers cannot crowd out souvenirs; excess eligible goods still rotate.
- **Native care packages:** with `care_packages_enabled=1` (default), a completed match and each earned profile level queue four saved offers. The original case/weekly-collection blue+ weapon pool is used. Exactly three choices can be claimed through the native PersonalStore/StoreRedeemFreeRewards path. Offers are reserved separately from owned items; only the three picks become owned. Duplicate/stale/partial/foreign claims reject. Closing, restarting or earning another package does not reroll existing offers. Queued packages are presented in order; there is no weekly cooldown. The custom end-match Drops tab is suppressed; the working stock XP/Premier screens and their baseline capture remain.
- **Rare custom cases:** within the case half of the reward pool, Black Market/Gauntlet have a combined default 1% chance, split equally when both exist and are enabled. They are excluded from the ordinary case pool. `reward_rare_case_per_10000` controls that combined rate. With the default 50% case/weapon split, it is a combined 0.5% per offered reward. This is independent of case-opening gold pity.
- **No key clutter:** `free_case_keys=1` now opens local cases through the native keyless path, with no generated keys. Existing keys remain usable and sell for 5 stars. `free_case_keys=0` retains normal required/consumed keys. Terminal behaviour is preserved.
- **BOT tag:** a separate plain-text scoreboard name label bypasses CS2's automatic `[BOT]` formatter for local bots; human/demo/queued-match names retain stock formatting. Other surfaces such as the victory cards/kill feed remain separate work.
- **Home promotion:** hides the RUSH promotion; the mission card is retained for future bot mission integration.

## Test checklist

1. Launch once with the updated executable. Confirm preparation completes and skins, loadouts, stars and custom finishes survive restart.
2. Inspect existing StatTrak gloves: the counter/label should be gone, and paint/wear/equipping should be unchanged. Open Gauntlet again to check new gloves are ordinary ★ gloves.
3. Sell custom hand wraps. Verify the confirmation shows your configured glove price, pays once and persists after restart.
4. Check all Armory slots and refresh several times. Buy/open a souvenir package: correct collection, Souvenir label, stickers, no key required, and no trade-up eligibility. Test more than one tournament/map.
5. Finish a bot match and return to Home or Inventory. Verify the native care-package popup shows four selectable previews; no preview should appear as an owned usable/sellable item before claiming. Select two/four: claim must not proceed. Select three: only those three should appear in inventory. Check the fourth is not granted.
6. Close/relaunch before claiming; verify the same four offers remain. Earn a level as well as finishing a match and verify both packages can be claimed in order without a weekly lock. Verify the working stock XP/Premier screens remain and the old custom Drops tab is absent.
7. Open a standard case with no matching key owned, then sell an old key for 5 stars. Also check a terminal still uses its normal offers flow.
8. Check scoreboard bot names lose `[BOT]` and humans retain their names. Check the RUSH promotion is hidden and the mission card remains.
9. Rare custom cases are probabilistic. For testing only, `reward_rare_case_per_10000=10000` makes case offers use the custom-case pool; restore 100 afterwards.

## Settings

New defaults: `care_packages_enabled=1`, `armory_souvenir_slots=1`, `armory_souvenir_price=5`, `reward_rare_case_per_10000=100`, `bot_hide_tag=1`, `hide_mainmenu_promo=1`. Charm slots now default to 2. The fixed 4/3/4 layout can show one souvenir, case, terminal and capsule at a time, regardless of larger existing pool counts.

`care_packages_enabled=0` is the legacy immediate-grant mode and custom end-match Drops tab; pending choices are retained for re-enabling. `bot_hide_tag=0` restores stock scoreboard name formatting. `hide_mainmenu_promo=0` restores the promotion.

## Still pending

Bot-match missions with saved progress/stars/XP are **not implemented**. The native mission card consumes a mission schedule and recurring-mission progress, and weapon-specific missions need reliable kill/event attribution; the existing GSI snapshots alone are insufficient to claim that support. Stock end-match item drops are superseded by the requested care-package flow. Graffiti, exact souvenir match provenance/highlight charms, BOT tags outside the scoreboard, release folder migration and executable icon remain future work.

## Reset

Use `cs2_gc_reset_profile.cmd` with CS2/helper closed: option 1 resets progression/cursors and queued care packages while retaining owned items/stars; option 2 backs up and removes the inventory too. Files are moved to a dated backup folder. A fresh profile starts at level 1 / 0 XP / unranked; `armory_credits` and `premier_bonus_wins` can seed test bonuses. Keep `cs2_gc_finish_ids.json` to preserve the identity of custom finishes in any restored inventory.

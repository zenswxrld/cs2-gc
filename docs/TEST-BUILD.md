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

# Test build27 — custom collection previews and variety

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

# Build26e (Claude) — Dead Hand Test Case

New steam_api64.dll / cs2_gc_debug.exe (log line "test build: claude-20261021-26e"). Extract everything into
game/bin/win64, start CS2 once, close it, then run grant_dead_hand_test_cases.cmd: 20 "Dead Hand Test Case"s that
contain ONLY the new Dead Hand glove recolours. The test case is never sold or dropped. Send
cs2_gc_glove_materials.json and cs2_gc_glove_palettes.json with any screenshots of wrong gloves.

# Helper update26c (Claude) — Dead Hand recolours

Same DLLtag26. Extract all files into game/bin/win64 and launch twice. The Gauntlet Case now also has recolours of
all 22 Dead Hand gloves (8 colours each, same accent-only style as the other gloves); the original Dead Hand gloves
stay in the Dead Hand Terminal only. To test, close CS2 and run grant_gauntlet_cases.cmd (adds 20 Gauntlet Cases;
start CS2 once first so the case exists). Check: Dead Hand recolours render with patterns intact, whites/greys
unchanged, names like "Wave Chaser Cobalt". Send cs2_gc_glove_materials.json if any look wrong.

# Helper update26b — corrected Dead Hand report

Includes26a Keys-tab removal; same DLLtag26. Extract all files and launch once. Send the regenerated **cs2_gc_glove_materials.json**: version2 now includes each Dead Hand composite's own parameter overrides, not just its shared all-white template. Dead Hand recolours are still pending this inspection; none are falsely added from template colours. Originals stay in the terminal.

User confirms rarity resale, below-case gold resale and case Store removal. User reports BOT prefix remains in killfeed; recorded for Claude, not considered fixed.

# Helper update26a — hide Store keys

Removes key price entries and banner tiles, including inherited key prefabs. The native Store creates the Keys tab only when key banner entries exist, so it should disappear after restarting with this update. Existing inventory keys remain sellable. Same DLLtag26; extract all files and launch again to regenerate the Store sheet. Target-client tab check pending.

User confirmed build26 removes Store cases, higher rarities sell for more, and tested best knife/glove resale is one star below the custom-case price. Those pricing rules are unchanged.

# CS2-GC test build26 — pricing, native bot labels and material checks

DLL tag: `codex-20261021-26`. Target client build25966348.

## Install

Close CS2 and the helper. Back up your inventory, config and **cs2_gc_finish_ids.json**. Extract ALL ZIP files into game/bin/win64 and run the updated cs2_gc_debug.exe. Keep your real Steam DLL, schema/replays, existing inventory and finish-ID map. Only an example config is included; your active config is not replaced. Python3 remains required. The launcher rebuilds the owned native packs before starting CS2.

## Changes

- Charm resale uses separate rarity prices: blue1, purple3, pink9, red25 stars by default. Blue is capped below its three-star purchase cost.
- Painted weapons/gloves use wear multipliers: FN125%, MW110%, FT100%, WW80%, BS60%, rounded down with minimum1 for positive prices. Terminal purchases stay sellable and use the same rarity/wear rules, explicitly requested by the user.
- Guaranteed fixed limited skins resell below their purchase cost. Custom gold cases cost more than the maximum configured knife/glove resale across all wear tiers. Random rare rewards can still be worth more than a roll costs.
- Official LTD prices: Heat Treated Deagle25, XM1014 Solitude15, M4A1-S Solitude25, Aphrodite125. Custom Howl250.
- Standard/custom case Store entries and banner tiles removed; cases remain in Armory rotation. Backend rejects direct/coupon case Store purchases too. Existing cases still open.
- New free generic Store grants cannot be sold for stars, including their opened contents, contract outputs and attached/detached charms/slabs. This is saved and exposed with the installed schema's native cannot-trade attribute so the Sell for Stars button stays hidden. Existing items are not retroactively reclassified. **Terminal offers are exempt**, including items accepted through native Store purchase flow. Debug/test grants and earned drops remain unchanged. This deliberately leaves the user-requested free terminal-to-sale route available; it is not a claim of a closed, exploit-proof economy.
- Native English bot decoration changes from BOT %s1 to %s1, retaining controlled-bot/player placeholders. Generated from the complete installed localization file, not a partial replacement. Config bot_hide_tag=0 unmounts the label override on next preparation/restart. Other languages still need matching localization support.
- Souvenir Armory purchases now use the collection soft/hard pity settings with separate saved counters per souvenir loot pool. Default soft10/hard100. No case/collection counter is consumed by a souvenir roll.
- Includes souvenir-only contracts from build25. Ten same-rarity Souvenirs use collection weighting/wear mapping; output retains Souvenir quality and selected collection provenance. Applied stickers/charms do not transfer. Unsupported mixes/outcomes refuse without consumption.
- Knife Teal no longer sweeps into green; Hardened retains its light/dark metal channels with two accent tones. Snow Leopard panel variants retain dark neutral contrast. Official finishes and saved custom IDs stay intact.
- Newer glove schema composite paths are now inspected. Only materials matching the verified eight-tint glove format are recoloured into separate Gauntlet entries. Unknown formats are skipped and listed in **cs2_gc_glove_materials.json**; originals/terminal loot lists stay unchanged. Full Dead Hand recolour coverage is **not yet verified or complete**.

## Test checklist

1. Confirm tag26 and successful cs2_gc_prepare.log. Check normal menus/localization and custom names still display correctly.
2. Play a bot match: names present, BOT prefix absent in killfeed, controlled-bot names retained; scoreboard names unaffected.
3. Store: no weapon/custom case purchase tiles; Armory case rotation still works. Open an existing case. Terminal reveal/buy still works.
4. Sell the same rarity in FN and BS: FN must pay more. Sell terminal skins at different rarities/wears. Verify popup value equals credited stars and survives restart.
5. Blue charm: buy3/sell1. Higher-rarity charm prices increase. Check LTD buy/sell and custom gold grants do not give guaranteed star profit.
6. Free generic Store items must have no Sell for Stars action. Their capsule contents/contract outputs must not become sellable after restart. Earned/star-bought items and terminal purchases must remain sellable.
7. Native souvenir trade-up: ten consumed, one Souvenir output; normal/mixed StatTrak contracts still work. Unsupported mixes/outcomes must preserve inputs.
8. Collection and souvenir pity: counters persist independently and the 100th miss-free top roll guarantees the highest available tier. Optional debug config can shorten thresholds for testing.
9. Inspect Teal/Hardened knives and Snow Leopard original/white/black/inverted variants. Compare patterns, wear and lighting in preview and in game. Lunar Weave Ash should be muted grey; Racing Sunset still needs a current-build comparison.
10. Send cs2_gc_glove_materials.json after launch so unsupported Dead Hand material layouts can be handled without guessing.

## Still pending

Inventory care-package claim timeout is NOT fixed here. Latest supplied log7 contains no9219 claim reaching the local GC. No new claim transport, unowned preview econ objects or end-match reward popup added. Send the log after testing claims separately.

Black Tie Aurora and near-identical Emerald Web Aurora/Toxic, Racing Sunset, Ash knife contrast and full Dead Hand coverage remain material follow-ups. Mission completion rewards, Career/achievements and release-folder cleanup remain later work.

Automated checks verify offline behavior; target-client UI and material appearance need the tests above.

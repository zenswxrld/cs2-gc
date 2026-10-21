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

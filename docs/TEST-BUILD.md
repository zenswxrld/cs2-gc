# CS2-GC test build24c — related knife tones and glove pool corrections

Helper/material update24c; DLL tag remains `codex-20261021-24`. Client build25966348.

## Install

Close CS2 and its helper. Back up your inventory, active config and **cs2_gc_finish_ids.json**, keeping them in place. Extract **all** ZIP files into `game/bin/win64` and run the updated **cs2_gc_debug.exe**. Python3 remains required. Launcher preparation regenerates the owned finish VPK; do not replace packs while the game is running. Only an example config is shipped.

## Changes

- Gold Brick recolours now keep the donor's related metallic palette together. Toxic uses related lime/olive tones rather than splitting neighbouring gold shades into purple and green. Source relative hue offsets, maximum RGB values and alpha stay intact; original textures, roughness, reflection and wear properties are untouched. This changes the existing recolour material under its same saved paint-kit ID. Native appearance still needs testing; the report alone does not prove texture mapping on a knife.
- Bronzed gloves recognise their two muted bronze tint channels (1 and6) as accents. Other six neutral channels remain structural. Lime should now affect the bronze regions rather than leaving them unchanged. Saturation is capped at the original to preserve the muted metal look.
- Racing variants now target the muted green/teal source colours and preserve brown accents on original-panel versions. Names use “Racing Sunset”, “Racing Cobalt”, etc., dropping the misleading original “Green”. Supplied palette check changes channels1/5 rather than the previous7/8. Other panel styles retain their explicit neutral-panel material changes.
- Neutral-only recolours (including the supplied Nocts palette) stop entering Gauntlet drops. They previously advertised different colours while looking unchanged. All known saved definitions/materials are retained so owned items continue to render; no inventory reset.
- Includes24b: softer charcoal Black Panels, raised darkest inverted tones, and clean base+theme display names for all variants. Internal names/IDs remain separate; different colour variants can share a display name.
- Includes24a: original case display/layout for Gauntlet and Black Market Armory pages, but purchases grant a finished glove/knife directly with one charge and no case/key. Existing inventory cases still open normally.
- Existing Forest DDPAT Toxic and Crimson Web Aurora approved legacy palettes remain. Individual finishes still require refinement; no claim every glove/knife is correct.

## Test

1. Reinspect Gold Brick Toxic after preparation, including in a bot match: related lime/olive tones should replace the previously mostly-purple result. Compare wear, seed and material sheen.
2. Inspect Racing Sunset/Cobalt: green/teal areas should change while brown details stay on original-panel versions. Compare Bronzed Lime and charcoal panel variants in inspect and in-game. Check texture/stitching detail remains visible.
3. Confirm old Nocts variants still render but do not appear in new Gauntlet rolls. Restart and verify saved items/loadout.
4. Confirm all panel suffixes are gone, with inventory IDs/wear/seed intact.
5. Buy Gauntlet/Black Market from Armory: original case page, one finished reward, one star deduction, no new case/key. Old inventory cases should still open.
6. For a remaining issue, send exact finish name, screenshot and the updated **cs2_gc_knife_palettes.json** or **cs2_gc_glove_palettes.json**. Keep inventory and finish-ID map.

## Validation and remaining work

All26 automated suites pass. Fixture tests verify related knife tones, material DATA preservation apart from name/colour edits, muted accents, no-op drop exclusion with saved definition retention, repeat preparation and stable IDs. Changes are Python/material-only; Windows binaries are the previously compiled build24 debug binaries. Actual24c rendering needs user testing.

Care-package claiming still times out in the latest user test; latest failed-claim cs2_gc_log.txt is needed. Do not restore unowned econ preview objects implicated in the earlier crash. Stock XP/Premier end-match screens stay; custom Drops tab stays disabled.

Queued: charm rarity/wear resale and full price-loop/LTD audit; collection/souvenir pity; local souvenir trade-ups; killfeed BOT prefix; mission completion XP/stars, achievements and Career. These are not implemented by24c.

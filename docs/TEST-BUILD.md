# CS2-GC test build 24b — charcoal panels and cleaner names

Material/helper update24b; DLL build tag: `codex-20261021-24`. Includes build22 fixes. Client build25966348.

## Install

1. Fully close CS2 and its helper. Back up your inventory, config and **cs2_gc_finish_ids.json**; keep the finish-ID file in place.
2. Extract **all** ZIP contents into `game/bin/win64`, preserving steam_api64_real.dll, schema/replays, inventory and finish IDs. Only an example config is included; your active config is not replaced.
3. Run the updated **cs2_gc_debug.exe**. Python3 remains required. The launcher rebuilds the finish VPK before the game starts; existing custom gloves keep their paint-kit IDs and receive the revised materials.
4. Confirm preparation completes in cs2_gc_prepare.log and the proxy logs the build tag above. Do not replace native packs while CS2 is running.

## Changed in this build

- Black Panels now use a lighter charcoal tint range (.12–.20 rather than .025–.10), retaining source tonal ordering. The dark end of Inverted Panels is raised to.12. Textures, masks, wear, roughness and reflections are unchanged. Exact perceived darkness needs in-game checking.
- All panel variants use clean base+theme display names: White/Black/Inverted Panels suffixes are removed. Internal variant names and saved IDs remain distinct and unchanged. Different colour variants may share a displayed name.
- Preparation writes **cs2_gc_knife_palettes.json** with actual source material paths, shaders, original colours and themed colours. Gold Brick Toxic has NOT been declared fixed: the Toxic recolour replaces gold with purple/green and may distribute them poorly over a particular knife. Send this report for the next finish-specific check. No knife colour algorithm change in24b.

- Armory Black Market and Gauntlet purchases immediately roll one knife or glove from the full corresponding custom pool, charge the displayed price once, and grant the finished item with its owner certificate. No case or key is minted. Existing inventory cases and rare case drops still open normally.
- Their native Armory pages retain the previous case model/layout and case names. Buying still grants the finished glove/knife immediately; the key warning stays hidden. The oversized finish gallery from build24 is removed. Native page rendering still needs testing.

- Ordinary glove recolours now target chromatic accent tints instead of tinting every channel. Near-black, grey, white and ambiguous muted channels keep their original colours. Accent brightness/alpha are preserved and saturation is never increased beyond the original.
- Separate **White Panels**, **Black Panels** and **Inverted Panels** variants recolour the structural neutral tints while keeping the same coloured accents. Small tonal differences are retained. These are named variants in the Gauntlet pool, not a skin-editing menu.
- **Forest DDPAT Toxic** keeps its exact previous two-tone palette, as approved in your screenshot. Crimson Web Aurora also keeps its current baseline while its requested green web awaits verified material-mask mapping. Existing names/IDs stay unchanged; panel variants use the new accent policy. Other finishes still need individual live checks.
- Existing `rg_` recolour names and saved paint-kit IDs are retained. Wear, seed and inventory ownership are not changed. The four shipped unreleased glove finishes are unchanged.
- `glove_panel_variants=1` defaults on. Set0 to stop those variants dropping; previously generated known variants remain in the schema so owned items can still render. `glove_finishes=0` retains the existing full glove-feature disable; knife_finishes must remain enabled for the shared generated finish pack.
- Preparation writes **cs2_gc_glove_palettes.json** containing original tint vectors and detected accent channels for diagnosis. A neutral-only palette keeps its original hue rather than guessing a tint channel and painting the whole glove.

This is material-palette classification, not texture segmentation. It preserves shipped textures, masks, stitching, material properties and wear definitions, but an individual tint mask can cover more than one visible region. Newer composite-material gloves remain outside the recolour generator. Exact in-game results are not yet verified.

## Test first

1. Compare the same Black Panels gloves after launcher preparation: look for clearer seams and surface detail in inspect and a bot match. Check unchanged wear/seed. Confirm all panel variants have cleaner display names.
2. Buy Black Market and Gauntlet from the Armory: exactly one knife/glove, one star deduction, no case/key. Inspect/equip/restart. Confirm old cases still open.
3. Confirm Forest DDPAT Toxic still looks the same. Inspect your existing Superconductor Magenta: dark/neutral sections should remain structural, with the coloured accents changed. Equip it in a bot match and check both palms and backs at your existing wear.
4. Open Gauntlet cases and inspect White/Black/Inverted Panels variants. Compare the same accent theme across panel variants. Test hand wraps, driver, specialist and other glove types too.
5. Restart and confirm IDs, finishes, wear, seeds and loadout persist. Keep cs2_gc_finish_ids.json.
6. If a glove still looks flat, unchanged or changes the wrong region, send its exact name, screenshot and cs2_gc_glove_palettes.json. Do not reset the inventory or finish IDs.

## Current status

User-confirmed: hand-wrap/key selling, direct souvenir grants/stickers, Aphrodite125 display, mission launch and scoreboard names. Howl costs250 from build22, including normalization of older lower config values.

**Care-package claiming still times out in the latest user test.** The claimed-banner/selection visuals are repaired, but payout is not confirmed. Existing pending offers remain saved. Keep native catalogue previews; do not restore unowned econ previews, which were implicated in the build19 crash. The current cs2_gc_log.txt from a failed claim is required to trace transport/rejection. Stock XP/Premier end-match screens remain in place; the custom Drops tab stays disabled.

## Next work requested

After glove validation: kill-feed BOT prefix; charm resale by rarity (blue charms must not guarantee profit); weapon resale by wear; audit every fixed buy/sell loop and official LTD prices against original values; check existing collection pity and add souvenir pity; review requested local souvenir trade-ups (currently deliberately excluded). Mission completion XP/stars, achievements and Career remain pending. No claim that these are implemented in build23.

## Validation

All26 automated suites pass, and Windows debug/release cross-builds compile. Glove tests cover accent/neutral preservation, panel variants, original alpha/value, stable IDs, variant-off rendering retention, repeat preparation and VPK generation. Live appearance still needs your test.

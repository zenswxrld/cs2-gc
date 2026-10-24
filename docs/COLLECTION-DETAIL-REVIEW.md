# Custom collection detail review

Scope: all **36 collections / 576 visible slots**, checked against the fresh supported-build output on 24 October 2026. This is a source/lineup review, not a claim that every skin has been visually approved in CS2.

The active generator's legacy policy deliberately moves neutral colours as well as accent colours. There are **462** visible fixed/family slots using that policy. This can colour ink, pale trim or hardware and flatten the donor's contrast. Six collections also use an existing knife-family chase; those successful definitions are retained.

## First rebuild batch

- Forged: AK-47 | Gold Brick fixed red chase, combining the real Gold Brick gold palette/material with the real Doppler smoke pattern. Both pink slots are colour families, keeping two family slots in total; forged/steel/metal pattern preferences and restrained contrasting accents.
- Phantom Blade: M4A1-S chase; spectral/glass/shard motifs, with working native effect donors preferred in premium slots.
- Harbor: AWP chase; nautical/patina motifs. Add a classified M4A1-S Berries and Cherries-derived colour family using the M4A1-S's own Fade material/masks.
- Mosaic: Desert Eagle chase; tile/prism/geometric preferences. Add a classified AWP Berries and Cherries-derived colour family using the AWP's own Fade material/masks.

The shared Berries palette is read from actual aa_fade_red_blue colour parameters. It does not transplant the Five-SeveN composite/UV layout onto another weapon. Rolled variants have distinct palette checks and colour-prefixed names.

New revisions use separate gc4 kit/material names. Old gc3 definitions and stable IDs remain available for owned items, and their actual materials receive the detail-preserving repair too. Historical colour variants are never removed. If an old variant cannot support a visible selective recolour, retain its original rendering and list it in existing_material_fallbacks for a deliberate redesign. Preserve existing alpha channels. The DEV finish-ID map and lineup history supplied by the user are the authoritative migration files; never substitute a fresh install's ID map. Promote a revised collection only when all 16 slots can be generated; otherwise retain its complete prior pool and report the missing rebuild. Preserve 1 red / 2 pink / 3 purple / 4 blue / 6 industrial and two family slots. Do not create a partial sellable collection.

## Detail and effect checks

- Recolour painted accents while preserving neutral channels, their values/alpha and source hue relationships. A neutral finish receives at most one accent rather than a full wash.
- Keep the actual target material's textures, masks, roughness, metalness, wear, overlay, glitter and pearlescent/iridescent parameters. No guessed shader controls.
- Detect active effect intensity/strength parameters, not the generic glitter-normal binding that exists even on ordinary finishes.
- Respect per-gun layouts. Shader parameter preservation alone does not prove a new colourway looks good in game.
- Review every collection at generation time for legacy whole-palette recolours, missing donors, original-weapon transfer copies, reused donors and simple premium finishes. Reusing a donor is a review flag, not automatically a duplicate: different weapons/colourways can be intentional.

The audit is written under gun_collections.audit in the local cs2_gc_weapon_palettes.json. Remaining collections are included in that audit and still require individual visual approval/rebuild decisions; this first batch does not mark all 36 complete.

## Baseline inventory of collections

| Collection | Visible slots | Families | Legacy whole-palette slots | Chase donor/family |
| --- | ---: | ---: | ---: | --- |
| ashfall | 16 | 2 | 13 | am_fuschia |
| aurora | 16 | 2 | 12 | gamma |
| brimstone | 16 | 2 | 13 | aa_fade_m4a1s |
| cascade | 16 | 2 | 13 | aa_awp_fade |
| cinder | 16 | 2 | 13 | am_tigers_blue |
| cipher | 16 | 2 | 13 | aa_vertigogeo_neon |
| driftwood | 16 | 2 | 12 | damascus |
| eclipse | 16 | 2 | 13 | am_intelligence_magenta |
| fathom | 16 | 2 | 13 | am_jorm_green |
| forged | 16 | 2 | 13 | am_lizard_red |
| halcyon | 16 | 2 | 13 | aa_spacerace_orange |
| harbor | 16 | 2 | 13 | aa_vertigo |
| insignia | 16 | 2 | 13 | am_royal |
| ironclad | 16 | 2 | 13 | am_jorm_orange |
| juggernaut | 16 | 2 | 13 | am_copper_flecks |
| kaleido | 16 | 2 | 12 | marble_fade |
| kestrel | 16 | 2 | 13 | am_bloom_blue |
| lodestar | 16 | 2 | 13 | am_ossify_red |
| marauder | 16 | 2 | 13 | am_numbers_magenta |
| monsoon | 16 | 2 | 13 | am_lightning_awp |
| mosaic | 16 | 2 | 13 | am_diamond_plate |
| nebula | 16 | 2 | 12 | doppler |
| nightwatch | 16 | 2 | 13 | am_electric_red |
| obelisk | 16 | 2 | 13 | am_awp_glory |
| outrider | 16 | 2 | 12 | tiger_tooth |
| phantom blade | 16 | 2 | 13 | am_bamboo_jungle |
| quarry | 16 | 2 | 13 | am_crystallized |
| rampart | 16 | 2 | 13 | am_aqua_flecks |
| redoubt | 16 | 2 | 13 | am_ddpatdense_peacock |
| solstice | 16 | 2 | 12 | fade |
| talisman | 16 | 2 | 13 | am_crystallized_blue |
| tidewater | 16 | 2 | 13 | am_m4a1s_bluesmoke |
| undertow | 16 | 2 | 13 | am_awp_pawpaw |
| warden | 16 | 2 | 13 | am_jorm_blue |
| zenith | 16 | 2 | 13 | am_gold_brick |
| zephyr | 16 | 2 | 13 | am_ancient_warm |

## Validation still required

Automated tests check the colour-channel/mask/effect contract, target-gun Berries palette adaptation, naming, family distinctness, slot counts and history. Actual game assets remain on the player's machine. The first regenerated report and native inspections must confirm donor availability, the intended appearance, icons and rolled outcomes before this batch is labelled visually working. Do not overwrite the separate known-good knife/glove systems.

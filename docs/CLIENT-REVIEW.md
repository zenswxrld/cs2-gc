# Client review: collection finishes

The 25 October client review repairs 13 reported skins. It preserves every other visible lineup slot, historical paint-kit IDs, knives, gloves and Gold Brick.

## Repairs

- Heat (MAC-10/MAG-7), Golden Coil, Howl and Phantom Disruptor: recolour RGB on material-mask islands without changing alpha.
- Ghost Protocol: recolour the separate overlay as well as base artwork.
- Midnight Laminate: cobalt rather than the source purple.
- Vogue, Neon Rider and Atheris: coordinated full artwork rather than isolated accent changes.
- AWP Printstream: invert neutral artwork including zero-alpha material islands.
- Sovereign: coordinated enamel while retaining natural portrait/gold tones.
- AXIA: Crimson, Emerald and Violet on pull, excluding default blue. The existing two Undertow families remain, making three in this explicitly requested pool. Historical blue items stay defined.

Native preflight covered all 23 affected outcomes, exact alpha preservation and unchanged shader/normal/roughness/wear bindings. The complete matrix contains 576 slots and 727 outcomes. Final appearance still needs target-client review.

## Audit of all collections

The audit decoded 416 texture-authored sources across all 36 collections; 160 channel-palette finishes were covered by the complete matrix/material audit. No source texture was missing or undecodable.

63 additional sources have at least 10,000 zero-alpha chromatic pixels and at least 10% of their chromatic texture area in that mask (or neutral area for inversion). These are review candidates, not 63 confirmed visual defects: unused atlas regions can also carry RGB. Eleven candidates exceed 95%. No automatic palette changes were made to these unreported skins.

| Collection | Skin | Coloured area skipped by old alpha gate |
|---|---|---|
| ashfall | Basalt Powercore | 14.4% |
| ashfall | Basalt Steel Sentinel | 99.9% |
| brimstone | Sulfur Corp Defense | 99.1% |
| brimstone | Sulfur Kill Confirmed | 46.7% |
| brimstone | Sulfur Traitor | 99.9% |
| cascade | Whitewater Ocean Drive | 12.4% |
| cinder | Kiln Half Sleeve | 100.0% |
| cinder | Kiln System Lock | 32.1% |
| cipher | Cipher Echoing Sands | 31.8% |
| cipher | Cipher Fuel Injector | 84.5% |
| cipher | Cipher Phobos | 20.6% |
| driftwood | Mangrove Allure | 13.9% |
| driftwood | Mangrove Guerrilla | 10.3% |
| driftwood | Mangrove Wildfire | 11.4% |
| eclipse | Umbra Neon Ply | 12.1% |
| forged | Foundry Triqua | 19.9% |
| halcyon | Stillwater Fire Elemental | 61.8% |
| halcyon | Stillwater Panthera onca | 14.1% |
| harbor | Dockside Nexus | 18.2% |
| insignia | Regalia Spirit Board | 62.6% |
| ironclad | Dreadnought | 11.9% |
| juggernaut | Siege Fuel Rod | 54.0% |
| juggernaut | Siege Memorial | 100.0% |
| kaleido | Prismatic Classic Crate | 20.3% |
| kaleido | Prismatic Fever Dream | 61.6% |
| kestrel | Raptor Food Chain | 27.5% |
| kestrel | Raptor Necro Jr. | 76.8% |
| kestrel | Raptor Run and Hide | 62.5% |
| lodestar | Starchart Fever Dream | 18.6% |
| lodestar | Starchart Fubar | 53.3% |
| lodestar | Starchart Parallax | 64.3% |
| lodestar | Starchart Vendetta | 18.2% |
| marauder | Reaver Eye of Horus | 17.3% |
| marauder | Reaver PC-GRN | 10.4% |
| marauder | Reaver Wasteland Princess | 63.3% |
| monsoon | Rainline Epicenter | 99.9% |
| monsoon | Rainline O.S.I.P.R. | 33.7% |
| monsoon | Rainline Yorkshire | 99.5% |
| mosaic | Tessera Decommissioned | 64.5% |
| mosaic | Tessera Necropos | 45.7% |
| nebula | Astral Dark Sigil | 83.7% |
| nebula | Astral Inlay | 36.0% |
| nebula | Astral Lil' Pig | 100.0% |
| outrider | Frontier Black Lotus | 72.4% |
| outrider | Frontier Dezastre | 100.0% |
| outrider | Frontier Monarch | 22.0% |
| outrider | Frontier The Outsiders | 42.7% |
| phantom_blade | Spectral Ghost Crusader | 29.3% |
| quarry | Malachite Button Masher | 67.0% |
| rampart | Bastion Big Iron | 34.3% |
| rampart | Bastion RMX | 100.0% |
| redoubt | Citadel Stone Cold | 22.2% |
| redoubt | Citadel Wood Fired | 68.3% |
| redoubt | Citadel Yorick | 31.4% |
| solstice | Suncrest Embargo | 41.9% |
| solstice | Suncrest Sure Grip | 100.0% |
| talisman | Relic Rapid Transit | 32.0% |
| talisman | Relic Violent Daimyo | 30.0% |
| tidewater | Tidal Black Limba | 93.0% |
| tidewater | Tidal Capillary | 10.9% |
| zenith | Skyline Hunter | 87.2% |
| zenith | Skyline Plastique | 22.3% |
| zephyr | Jade Jaguar | 28.6% |

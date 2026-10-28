# Remaining collection rebuild and similarity review

The remaining 28 pools use 16 visible gun skins each, in the 1 red / 2 pink / 3 purple / 4 blue / 6 industrial split. Red and one pink are colour families. Lower tiers use fixed authored colourways. Source weapon UV constraints, neutral trim, masks, wear and effect settings remain intact. Gloves and knives are outside this change.

The eight reviewed pools (Forged, Phantom Blade, Harbor, Mosaic, Kestrel, Juggernaut, Lodestar and Fathom) retain their saved definitions and lineups. Gold Brick is retained. Historical definitions and finish IDs are preserved for owned items.

| Theme | Collections |
| --- | --- |
| Heat, embers and industrial metal | Ashfall, Brimstone, Cinder |
| Polar mineral and ice patterns | Aurora |
| Currents, storm, reef and depth | Cascade, Halcyon, Monsoon, Tidewater, Undertow |
| Celestial charts and star metal | Eclipse, Nebula |
| Faceted glass and geometry | Kaleido |
| Stone, crystal and carved minerals | Obelisk, Quarry |
| Armour, fortification and metalwork | Rampart, Ironclad, Redoubt, Warden |
| Predatory markings and field equipment | Marauder, Outrider |
| Aviation and wind geometry | Zephyr, Zenith |
| Runes, heraldry and ornamental carving | Talisman |
| Circuits, codes and surveillance markings | Nightwatch, Cipher |
| Wood grain, carved timber and weathering | Driftwood |
| Ceremonial metal and heraldry | Solstice, Insignia |

## Similarity checks across all 36

Comparisons use the actual rendered material parameters: pattern resource or known geometry family, source weapon constraints, paint style, palette channels and authored brightness multiplier. They do not use display-name or numeric-ID equality as a duplicate test.

- Compare same-weapon candidates against the official source palette and other visible custom outcomes.
- Group related source variants (for example Jörmungandr, quartz and DDPAT) even when their resource names differ.
- Reject weak trim-only shifts and colours that become indistinguishable after brightness clipping.
- Check each colour-family outcome separately. Keep at least three visibly distinct accepted outcomes.
- Preserve good transfers/colourways on different guns, as requested.
- Keep the prior complete collection if there are too few compatible, sufficiently distinct choices. Record the shortage rather than publishing a collection with holes.
- Report similarity findings and coverage for every visible pool in the gun collection preparation report, including the eight reviewed pools.
- Keep owned historical definitions even if they are retired from visible loot pools.

This is a conservative material-level preflight, not a rendering engine. Different unrelated textures, UV placement, lighting and small masked areas can still yield similar-looking guns. Texture-authored Printstream and Waters of Nephthys have separate selective decoder checks; they are labelled for visual review rather than assigned fictitious four-colour descriptors. Target-client visual review is required before considering all 576 slots approved.

Builds and checks run in GitHub Actions. No installed game files or user inventory/map files are committed or modified during development.

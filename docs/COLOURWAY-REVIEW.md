# Colourway review

This update preserves the approved artwork, weapon layouts, rarity tiers,
normal maps, wear, material masks and special effects. It changes colours only.

101 slots in twelve collections receive palette refinements: Aurora, Cascade,
Driftwood, Halcyon, Insignia, Juggernaut, Kestrel, Obelisk, Outrider, Tidewater,
Zenith and Lodestar. The other 24 pools were included in the complete material
and similarity audit. Gold Brick with black-grain wood, approved chase additions,
Rainbow Spoon, Foil, Berry families and Composite Armour are retained.

The revised pool accents include ember/violet, rose/amber, crimson/gunmetal,
navy/amber, sandstone/violet and rose/navy. Entries too close to an official
colourway keep a distinct validated alternative rather than forcing the palette.
Named premium families retain their approved range unless explicitly reviewed.

Neon Rider now rolls Ember, Violet and Crimson. Its dominant artwork and accent
inks are mapped separately, keeping internal tonal detail instead of squeezing
all hues into green. Each outcome has a deliberate secondary colour.

Tropical Breeze now has a rose floral overlay, warm shell/gold highlights and
dark navy/plum body channels. The floral artwork is a separate native overlay;
changing body colour constants alone left its original green visible. Recolour
the overlay itself without altering its alpha/material masks or detail.

Validation against installed game resources is read-only. Both reported textures
retain their 2048 x 2048 resolution and exact alpha bytes; maximum RGB values
are preserved within one byte of rounding. Neutral texture trim remains intact.
Native material parameters outside the intended colour inputs remain identical.
All 36 pools, 576 slots and 727 colour outcomes pass material/family preflight,
with no near matches or unrated outcomes, all special-material coverage retained,
and identical artwork sources and rarity assignments. This is material and
texture validation; final lighting and appearance need review in the client.

Trade-up definitions include every custom collection and concrete rolled family
colour. The live prepared schema was inspected read-only: all 36 custom item sets
are present. New checks expand the complete authored matrix into item sets and
verify membership, unique ownership and localized collection labels. Missing or
empty generated collection lists now fail preparation instead of silently hiding
a collection from trade-ups. Native trade-up UI behavior still needs client review.

No game textures, generated caches or player inventory are included in this file
or the portable package. Knives and gloves are unchanged.

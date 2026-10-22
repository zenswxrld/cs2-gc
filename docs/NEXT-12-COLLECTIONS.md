# Collection donor, detail and naming revision

The Build 31 Crimson Foil and Rainbow Spoon labels were incorrect. They were
attached to substitute donors including Serum and Marble Fade. The revised
lineups bind those families to gsch_sport_ump45 (UMP-45) and
aq_titanium_rainbow_galilar (Galil AR), verified against tracked schema revision
6ac247908a83c309b37314fd097c47dc78103746. No alternative donor can inherit those names.
These weapon-specific finishes stay on their source weapons to preserve artwork.

The next 12 are considered first. Fixed recolours use donors from the installed
Weekly and Armory item sets that were not used in the older active collection
pools. Within each collection a material cannot repeat; normal donor reuse is
capped at two across the new 12. The six explicitly requested family placements
are exceptions to prior-use/reuse limits, never to the correct-donor rule.
The older 24 then use the same donor/detail pipeline with a reuse cap of four
across successful upgrades. Original source weapon restrictions apply to custom,
gunsmith and anodized multicolour artwork. Generic cross-weapon transfers require
an eligible style and a generic donor name.

The detail palette rotates existing painted accents together. It retains relative
hue spacing, exact value/alpha, muted saturation, dark ink and neutral silver or
white details. An entirely neutral donor gets at most one accent. Shader, foil/iridescence settings, roughness, wear and masks are retained.
Four-colour finishes edit their actual colour controls. The two named texture
families use the selective lacquer/ramp treatment described below. Unsupported layouts are
reported; a different donor is never substituted for a named required family.
This is structural preservation, not a claim of rendered visual approval.

Each complete pool has 16 skins (1/2/3/4/6), fourteen fixed unique names and two
colour families. Family variant names use their actual palette; e.g. Teal Foil
rather than Teal Crimson Foil. Older fixed/rolled names are upgraded without
changing kit names or their persistent IDs. Previous Build 30 and nc31 material
definitions remain generated for owned items; misleading owned nc31 aliases get
names describing their actual source.

All 36 custom collections are assessed. Complete upgrades replace active lists
atomically; unavailable older upgrades retain their former complete pools.
The new 12 publish only complete safe lineups. Inspect collection_upgrade and
next_12 in cs2_gc_weapon_palettes.json for actual selected donors, source sets,
weapons, colours and reasons for unavailable pools. No partial pool is sold.

The Armory UI takes custom names from the authored collection map and clears
stale suffixes, including Phantom Blade's underscore. This branch also contains
the cache/Armory fixes from PR #26, so its helper artifact includes them.

## Validation limits

GitHub Actions runs Windows core build and CTest, then packages changed helper
sources only. It separately audits publicly tracked schema metadata. No builds or generated material packs are made on the user's PC during
development. Installed donor metadata was read without writing to the game.
No proprietary game binaries, installed assets, inventory or config are committed.

CI material fixtures establish property preservation and source-selection rules,
not that every installed donor is supported, that every pool publishes on the
user's game build, or that an in-game finish looks good. Those require a generated
palette audit and client review. The downloadable artifact is a helper test
update, not a new DLL release.

After delivering the collection test update, investigate the separately reported
care-package claim timeout. The screenshots alone do not establish its cause.


## Composite/material correction

Read-only inspection of the installed material metadata confirmed that both
requested finishes use KV3 v4 composite documents with exposed parameters that
override the template VMAT. The previous generator only edited the VMAT and
skipped v4. New collection materials read v4/v5 and edit exposed colour variables
where present; the compatibility generator keeps its original v5-only behavior.

Crimson Foil recolours only chromatic red lacquer pixels in its original albedo.
Neutral silver, dark ink, alpha, roughness, metalness, normal and wear maps stay
unchanged. Rainbow Spoon recolours its actual case-hardening ramp into the
family's related hue range, retaining tonal variation and its source pattern.
The generated report records sampled colours from changed pixels and the count
changed; no fake donor palette is used to identify a texture recolour.

The BC7 decoder is built in Actions from the unmodified MIT-licensed bcdec
header plus our small colour-selection utility. It is included with the helper
update and requires no local compilation. Generated textures have their own
paths; original files remain referenced for all untouched detail maps.

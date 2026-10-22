# Authored next 12 collections

The Build 30 draft used the generic filler shuffle for the third batch. These
collections now have authored skin names, chase selections, donor preferences
and palette ranges in `tools/next_collection_lineups.py`. They run through the
existing `native_finishes.make_finish` material generator.

Forged, Phantom Blade, Harbor, Mosaic, Kestrel, Juggernaut, Lodestar, Fathom,
Cipher, Driftwood, Insignia and Warden each have 16 visible entries: one red,
two pink, three purple, four blue and six industrial. Each has 14 fixed finishes
and two variable families. Phantom Blade and Lodestar use a red family; the
other collections keep the chase fixed. Family outcomes include the selected
palette in their displayed name; fixed skins have unique authored names.

The chase uses the first compatible preferred donor, then a documented fallback.
It is an authored premium choice; appearance still needs in-game review. The
lineup report records actual selected donors and accepted colours, including
fallbacks. Rainbow Spoon and Crimson Foil are custom family names over supported
donors; this does not introduce new shader effects.

The generator rejects missing/unsupported materials, near-original palettes and
duplicate accepted palettes. It requires at least two distinct accepted colours
for a family. An incomplete collection publishes no new definitions, material
files, loot lists or family mappings. No case items are added. Identical
donor/weapon/tier/palette rolls are excluded across these new collections.

## Recovery from the supplied build

GitHub main at `59f351c` has the 12-collection helper27c source and a Build 28
checksum note, but not the later helper sources. This change recovers the
collection-specific Build 30 sources, the previous detailed artwork and the
four original pattern masks from `cs2-gc-build30-next12-repacked.zip` in the
user's Downloads. It does not import the ZIP's EXE/DLL, active configuration,
inventory, ID map or recorded game data. `builds/BUILD30-SOURCE-RECOVERY.json`
records checksums for the recovered source inputs.

Build 30's older 24 pools retain their active entries. Its draft third-batch kit
definitions, materials and family mappings remain generated for owned inventory;
only their active loot lists are replaced. New `nc31_` kit identities use the
existing persistent finish-ID allocator. The 12 new icons use the original
detailed emblem artwork as image-generation references. The first 24 detailed
icons are recovered artwork rather than regenerated replacements.

## Verification

- MSVC x64 Release core build succeeds. Existing Windows compiler blockers were
  limited to a signed optional comparison and shadowed variables; type/name
  corrections keep their behavior unchanged.
- All 28 CTest suites pass, including the six new lineup tests; all 166 Python
  tests pass. CTest enables Python UTF-8 for the existing Unicode fixtures.
- Read-only generation using the installed CS2 pak01 produces 36 collections
  and 576 entries overall, including all 192 new entries and 24 new families.
- Comparison with the supplied Build 30 source preserves 3,473 kit definitions,
  3,806 generated material files, 429 family mappings and all 384 older active
  entries. This compares regenerated outputs without modifying the installation.
- The new PNG icons have transparency and were reviewed at 32px and 64px.
- Rendering, wear appearance, Armory purchases and roll results require client
  testing. Existing reward-claim/trade-up issues are outside this change.

Run the read-only audit with reports outside the installation:

```powershell
python -X utf8 tools/audit_next_collections.py --game '<CS2 installation>/game' --output audit --full
```

This creates `collections-audit.json` and `collection-lineups.md`. It never mounts
or installs generated assets. `docs/NEXT-12-LINEUPS.md` contains the selected
lineups from the current validation run.

## Using the helpers

With the game and helper closed, use the matching Build 30 helper set and replace
`native_skins.py`, `native_finishes.py`, `weapon_palettes.py`, `native_patterns.py`
and `next_collection_lineups.py` from `tools`, together with `collection_icons`
and `weapon_patterns`, beside the launcher. Do not remove the inventory, active
configuration or finish-ID map. Run the existing debug launcher so preparation
rebuilds the owned override before CS2 starts. No live installation was performed
while developing this branch.

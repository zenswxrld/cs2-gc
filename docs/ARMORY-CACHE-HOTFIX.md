# Armory presentation and preparation cache

The installed Build 31 logs show dozens of manual refreshes. All 12 new pools,
their 16-item preview manifests and their Armory catalogue rows were present in
the generated schema and packed UI settings. That rules out failed generation,
but does not prove that the tiles displayed correctly in the running client.
The same log shows requests for missing custom `.vsvg_c` set icons, while the
emblems are packaged as `_png.vtex_c` textures.

## Armory changes

- Resolve custom collection titles, weapon lists, row and emblem names from the
  generated catalogue/preview settings, replacing stale native donor metadata.
- Use generated previews even when the engine reports a nonempty native list.
- Use PNG image paths for custom emblems in tiles, navigation and purchase bars;
  official collections keep their normal SVG/fallback behavior.
- Log received custom catalogue coverage and the visible collection names on
  each rotation. Existing rotation pools, timing and purchase IDs stay intact.

This needs a client retest. In the current console log, look for
`cs2_gc armory catalogue: custom=32/32 missing=[]` and
`cs2_gc armory visible collections:`. The 32 excludes the four drop-only pools.
Those lines distinguish a native row-loading problem from a visible title/image
problem if the new collections still appear absent.

## Launch cache

Previously every launch regenerated all collection/knife/glove materials before
checking whether packed outputs changed. `prepare_native.py` now caches only a
successfully completed preparation. On a hit it reuses the owned packs and schema,
while preserving per-launch bot-name reshuffling and VPK-signature maintenance.

Inputs include the loaded configuration, helper sources, source schema, donor
VPK index/content-file metadata, Steam version file, source Store replay, artwork
and launcher/proxy binary identity. Outputs include owned pack identities,
mounts, schema/stamp, finish-ID map, families, previews, reel, palette report,
Store sheet and signature file. Changed/missing inputs or outputs trigger a
rebuild. Failed preparation never marks a new cache complete.

The first launch after installing this hotfix rebuilds. The next unchanged launch
should log `Preparation cache: hit`. A full rebuild remains available with:

```
python prepare_native.py --proxy-dir . --rebuild
```

Logs now include per-stage cold-build timings and total preparation time. A
read-only validation against the user's real installed input/output fingerprints
took approximately 0.23 seconds; this measures cache validation, not total game
startup or the separate bot-name refresh.

## Validation and installation

All 30 CTest suites pass. New fixtures cover cache reuse/invalidation, failed
builds, retained bot reshuffling, authoritative custom tile metadata, PNG icons,
and manifest previews when the native list is nonempty. The patched installed
xpshop script passes Node syntax validation. No installed files were modified
during development.

Close CS2/helper, then extract the hotfix's `prepare_native.py`,
`preparation_cache.py` and `rotate_armory.py` beside the existing Build 31
launcher. Keep inventory, active configuration and finish IDs. Run the existing
debug launcher; let the first rebuild finish. Check a second launch for a cache
hit, then inspect and refresh Armory. This is a helper-only update.

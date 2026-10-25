# Native preparation performance

The launcher keeps its complete-preparation cache. A changed helper or collection
no longer has to regenerate every unchanged artwork texture inside that rebuild.

## What changes

- Large LZ4 blocks use a bounded native decoder. Small blocks and older helper
  executables retain the Python fallback. The native compressor verifies its
  lossless result before returning it.
- Each source texture is decompressed once per render, rather than repeatedly
  decoding it while inspecting and rebuilding its resource header.
- A local, content-addressed artwork cache stores full-resolution texture files
  on disk. Keys include the original source bytes, colour recipe, material policy,
  Python transform code and native pipeline fingerprint. Lineup text or another
  skin changing does not invalidate an unchanged colour recipe.
- Required artwork is prepared on at most four native workers, with fewer on
  smaller CPUs. This bounds simultaneous texture memory while using spare cores.
- Materials refer to cached texture files rather than retaining every large
  pixel payload in Python dictionaries. Publication uses atomic hard links where
  supported and a streaming-copy fallback elsewhere.
- Only resources referenced by current or historical paint kits enter the VPK.
  Clean installs can validate the authored matrix directly. Existing inventories
  and finish-ID files retain their legacy planning and history path.
- Unchanged archive inputs and intact archive stamps skip repacking. Changed
  archives are staged on the same filesystem and renamed into place, avoiding
  another full copy of every numbered archive part.

## Local measurements

These measurements read the supported game's native assets without modifying the
installed game. They are preparation-stage benchmarks, not total launch times.

| Test | Previous implementation | New implementation |
| --- | ---: | ---: |
| 23 reviewed skin outcomes, uncached | 83.84 s | 30.44 s |
| Same 23 outcomes, populated artwork cache | regenerated | 0.72 s |
| Texture bytes retained by that 23-outcome result | 235,885,392 | 0 (file-backed) |

The full saved catalogue, including historical inventory definitions, produced
36 complete collections, 576 visible entries, 2,540 paint-kit definitions and
4,456 resources. Sequential cache initialization took 746.54 seconds; the
subsequent collection rebuild took 29.67 seconds with no artwork regenerated.
Every resource hash and colour-family mapping matched between those runs.
The bounded four-worker cold path completed the same catalogue in 244.89 seconds
(about 4 minutes 5 seconds), with all 4,456 resource hashes and colour families
matching the sequential and cached runs. This excludes archive publication,
Steam/profile initialization and the other preparation helpers.

Normal launches with a valid complete-preparation cache still bypass the heavy
collection stage entirely. The first launch after this update initializes the
new artwork cache; it will take longer than a cached launch.

## Cache integrity and upgrades

The cache is generated locally in `game/cs2_gc_artwork_cache`. It contains no
downloaded assets and is excluded from the release ZIP. It is separate from
inventory, settings and finish IDs. Missing, damaged or incompatible cache entries
are regenerated; complete pool validation and source effects remain in place.
New native binaries use a source fingerprint rather than a build timestamp, so
rebuilding identical code does not invalidate every texture. CMake also tracks
decoder/header edits when doing incremental developer builds.

Upgrade through the usual portable ZIP while CS2 is closed. Cache setup and reuse
are automatic; no additional commands or manual extraction steps are needed.

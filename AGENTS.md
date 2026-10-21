# CS2 port

Develop this repository from `main`. The original CS:GO repository is a separate
project; do not push changes to `zenswxrld/Test` when working here.

The root CMake project builds the new 64-bit CS2 core. `legacy/` is a preserved
snapshot of the CS:GO source for porting, not CS2-compatible runtime code.
Instructions in `legacy/AGENTS.md` apply only to that reference subtree.

Keep custom cases, custom paint kits and schema rewriting out of the active CS2
port for now. Exception authorised by the user on 20 October 2026: native mixed
StatTrak trade-ups may use a dedicated, reversible recipe-only override generated
from the user's current schema. Broaden only the existing normal recipe input
qualities and disable their duplicate StatTrak recipes; do not edit original item,
paint-kit, collection or case definitions. Additional user-authorised exception:
generate native Armory catalogue rows referencing existing official items and
loot lists, for per-category rotation of Armory collections, charms, stickers,
limited items, cases, souvenir packages, terminals, curated capsules and official tradable agents. Do not create
or alter item/loot-list definitions. Load the same generated catalogue in the client and local GC.
Additional user-authorised exception (21 October 2026): knife-only custom finishes and one custom case, as
in OfflineCS. Generate recoloured copies of existing finish materials (new g_vColor values only) and new
paint_kits entries pointing at them, plus one knife-only "Black Market Case" (cloned from an existing case,
own loot list and icon) in the generated override and the cs2_gc_finishes VPK. Never edit the game's own
files or existing definitions; knife_finishes = 0 removes everything. Extended by the user the same day to
gloves: recoloured copies of classic glove materials (new g_vColorTint values only), paint_kits for the four
shipped glove finishes no paint kit uses, and one glove-only "Gauntlet Case" in the Armory limited rotation;
glove_finishes = 0 removes the gloves and their case. Further user authorisation (21 October 2026): custom
weapon skins (official knife finishes and existing rk_ recolour kits on guns that never had them), first in a
grant-only test case, then as custom Armory collections priced like the other collections; custom_skins_test = 0
removes the test case. Back up gameinfo.gi before adding the
owned native search path and preserve other addons. The store must live in CS2's native Armory page with the user's stock 4/3/4 catalogue layout. The user requested removing the text category tabs on 20 October 2026. Do not bring back the legacy Riptide store.
Do not claim the Armory UI works until mounted and verified in the target client.

Build and test with:

```
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON
cmake --build build --config Release
ctest --test-dir build -C Release --output-on-failure
```

Use an x64 Visual Studio developer environment on Windows (`-A x64` if needed).
The active core has no third-party dependencies. Python 3.9+ is needed for the
read-only client inspector and its tests.

Runtime integration needs an identified CS2 build, its actual Steam/GC interfaces,
protobuf schema and Panorama scripts. Do not invent offsets, vtables, message
IDs, item IDs or UI APIs. Store client fingerprints and protocol fixtures only
when provided; do not commit proprietary game binaries, account data or logs.

Core tests prove offline behavior only. Report live-client validation separately.
Do not publish a copied legacy DLL as a CS2 release, expose RCON by default, or
touch the user's existing game files while doing build inspection.

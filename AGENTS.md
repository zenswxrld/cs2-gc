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
paint-kit, collection or case definitions. Back up gameinfo.gi before adding the
owned native search path and preserve other addons. The store must live in CS2's native Armory page, with category tabs
and pagination for the catalogue. Do not bring back the legacy Riptide store.
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

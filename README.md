# cs2-gc

A separate CS2 port of [zenswxrld/CSOffline](https://github.com/zenswxrld/CSOffline), intended
to bring its local inventory, standard case opening, progression, rewards,
career tracking and bot features to CS2.

**Development foundation only. There is no working CS2 launcher, game DLL,
inventory connection or Armory UI integration yet. Do not install the legacy
CS:GO binaries into CS2.**

## Implemented so far

- A 64-bit C++20 build independent of the legacy launcher and game hooks.
- Bounded protobuf envelope reading/writing. Header and body bytes are preserved;
  message schemas and IDs still need validation against the target client.
- A synchronized, bounded message queue with Steam-style size-query and
  buffer-too-small behavior. This is not yet attached to Steam's interface.
- Local XP and star reward rules adapted from the CS:GO fork, including headshot
  bonuses, level rollover and the level-40 cap. Events are not yet connected to CS2.
- An Armory catalogue model with categories, ASCII-insensitive search and paging.
  It accepts schema-derived goods; it does not include an invented item list or
  execute purchases. Full localization-aware search remains future work.
- A KeyValues parser and `items_game.txt` schema loader: standard cases, their keys and
  loot tiers, resolved from the real schema (tested offline against a synthetic fixture).
- An in-memory inventory with strict, atomic file persistence, and offline case opening that
  consumes the case and key and grants an item as one step. The special (knife/glove) tier
  is not resolved yet.
- GC message IDs derived from the protobuf descriptors embedded in the target `client.dll`
  (`tools/extract_gc_protocol.py` generates `gc_msg_ids.h`), plus a record of the target
  build's file hashes. In this build cases open through `k_EMsgGCOpenCrate`
  (`CMsgOpenCrate`), not the deprecated `UnlockCrate`; which field is the key and which the
  case is inferred from the field names and is unverified.
- A bounded protobuf reader/writer, codecs for the Hello/Welcome/SOCacheSubscribed handshake
  messages, and `LocalGameCoordinator`: an in-process stand-in with the same three calls as
  `ISteamGameCoordinator` that answers a client Hello with a Welcome. The encoders were
  cross-checked with Google's protobuf library against the target client's own descriptors.
  It is not attached to Steam's interface, and the welcome version, owner ID and cache
  contents are caller-supplied because they cannot be derived offline.
- A diagnostic `steam_api64.dll` stand-in that gives the game the local GC and logs what it
  sends, active only with `-insecure`. It cross-compiles but has **never been run**; see
  [docs/PROXY.md](docs/PROXY.md) for the risks before using it.
- A read-only Windows CS2 build inspector and automated core checks.

## Store direction

Use **CS2's native Armory page** as the store. Add category tabs and previous/next
pages so the full catalogue fits without cramming everything into one screen.

Initial categories: Cases, Capsules, Souvenir Packages, Agents and Music Kits.
All pages use one local star balance and inventory. Cases should include their
correct key where required, resolved from the target CS2 schema. Preserve the
native cards, item previews and redemption presentation where the client allows.
This is the integration plan; only the catalogue/paging model exists today.

Custom cases and custom finishes are **out of scope for now**. Standard game
containers remain in scope. Nothing in this project creates real Steam items,
changes a real Steam wallet or redeems official Armory purchases.

## Build the current core

Requirements: CMake 3.20+, a 64-bit C++20 compiler, and Python 3.9+ for inspection
tests. No Steam client or third-party libraries are required for the core tests.

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON
cmake --build build --config Release
ctest --test-dir build -C Release --output-on-failure
```

On Visual Studio use `-A x64` if the default generator selects another platform.
The output is a static core library and test executable, not an installable mod.

## Identify the target CS2 build

Run from this checkout, with the path of your Steam CS2 installation (the directory
containing `game`). Keep the output report outside that installation:

```powershell
py -3 tools/inspect_cs2.py "D:\SteamLibrary\steamapps\common\Counter-Strike Global Offensive" --out cs2-build.json
```

The inspector only reads game files. It records module SHA-256 fingerprints,
PE architecture, build metadata and missing files. It never loads code from game
DLLs, installs hooks, downloads files or uploads the report. Existing output
reports are not overwritten. A complete x64 file layout does **not** mean the mod
is compatible. Exit codes: `0` complete layout, `2` missing/invalid modules, `1`
inspection/output error.

The exact build and relevant client assets are still needed to implement and
verify the Steam/GC bridge and mount the shop controls on the native Armory page.

## Port milestones

| Area | Current state / acceptance check |
| --- | --- |
| Core envelope and queue | Offline tests; no live message exchange yet |
| Client adapter | Message IDs, codecs and an offline Hello/Welcome endpoint done; Steam interface hook and live Hello/Welcome/SOCache exchange pending in the identified CS2 client |
| Inventory and loadouts | Offline model and persistence tested; show, equip and reload in CS2 pending |
| Standard case opening | Offline logic tested against the real schema; client message handling, previews and the knife/glove tier pending |
| Armory shop | Catalogue paging tested; native UI and redemption bridge pending |
| XP/stars | Pure reward rules tested; match-event bridge and persistence pending |
| Ranks, drops, achievements and career | Reference logic preserved; CS2 integration pending |
| Bot names, skins, chat and difficulty | Reference logic preserved; Source 2 interfaces pending |
| Trade-ups, tools, stickers, storage and StatTrak | Reference logic preserved; current protocol mapping pending |
| Lobbies / private server inventory sync | Reference logic preserved; CS2 integration pending |
| Custom cases / finishes | Deferred |

## Source layout and attribution

- `cs2_gc/`: active CS2 core.
- `tests/`: offline tests; synthetic fixtures are not real game data.
- `tools/inspect_cs2.py`: read-only build fingerprinting.
- `legacy/`: pinned reference submodule containing the CS:GO source from commit
  `5d31c61786ac9b2b78299b9f28e3fd9bed3b006d` of `zenswxrld/Test`.

The original BSD license, source credits and third-party notices are retained.
The upstream history remains in the original repository and the downloadable
source bundle. To download the optional reference, run `git submodule update
--init legacy` after cloning. The reference includes features and dependencies not yet ported;
its custom cases are not loaded or built by the active project. See
[legacy/README.md](legacy/README.md) for original authors and dependency licenses.

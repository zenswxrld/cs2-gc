# Diagnostic proxy (`steam_api64.dll` stand-in)

**Status: built and cross-compiled, never run.** It has not been tested on Windows or against
a real CS2 client. Treat the first run as an experiment.

## What it is

The proxy is a `steam_api64.dll` that forwards every export to the original (renamed
`steam_api64_real.dll`) except two. For the name `SteamGameCoordinator001` it returns a local,
in-process GC instead of Steam's, so the game's GC traffic stays on your machine. It answers
the client Hello with a Welcome and writes every message the game sends to `cs2_gc_log.txt`.

The game can ask for that interface two ways, so both are covered:

- `SteamInternal_FindOrCreateUserInterface(user, "SteamGameCoordinator001")`, directly.
- Through the `ISteamClient` object (`SteamInternal_CreateInterface("SteamClient023")`, then
  its `GetISteamGenericInterface`). The proxy redirects that one vtable entry on the real
  object. The entry's offset is decoded at runtime from the real library's own flat-API
  wrapper, and if it cannot be decoded the hook is simply not installed.

The game only picks GC replies up after Steam's `GCMessageAvailable_t` callback, so the proxy also
takes over registration of the two GC callbacks (ids 1701 and 1702) and fires them itself from
`SteamAPI_RunCallbacks`. The callback objects are called through explicit vtable slots because
the game's MSVC layout of overloaded virtuals differs from the one this file is compiled with;
the callback's size is checked first and delivery is skipped if it looks wrong. The cache owner
is read from the local Steam session (`steam_id` in the config overrides it); the value is never
logged.

The first test run showed the game never used the first route, which is why the second exists.
Every distinct interface name the game requests is logged ("interface requested via ..."), so
the log shows how the game really gets its interfaces even if the GC hook does not take.

Its purpose is to find out **what CS2 sends and expects**. It is not a working inventory yet:
the Welcome carries no items, and the Welcome version and owner values are unverified guesses.

## Risks, read first

- **VAC.** This replaces a game file. Do not run it on a VAC-secured server, in matchmaking
  or Premier, and prefer an account you can afford to lose. The proxy does nothing unless the
  game was started with `-insecure`, but while it is installed the file on disk is modified.
  **Uninstall it before you play online.**
- It touches only `steam_api64.dll` in the game's `bin\win64` folder. Steam's "Verify
  integrity of game files" restores the original.
- Logs redact values shaped like a SteamID64, but read `cs2_gc_log.txt` before sharing it.
- Nothing is sent to Valve by this component and no real Steam items are created.

## Install

In `...\Counter-Strike Global Offensive\game\bin\win64`:

1. Rename `steam_api64.dll` to `steam_api64_real.dll`.
2. Copy the proxy's `steam_api64.dll` into the same folder.
3. Optional: create `cs2_gc.cfg` next to it (see below).
4. Launch CS2 with the launch option `-insecure`.
5. Each run appends to `cs2_gc_log.txt` and marks the start with `---- new session ----`. Delete
   the file before a run if you want a clean one.

Without `-insecure` the proxy forwards everything to the real library and writes nothing.
The log appears next to the DLL as `cs2_gc_log.txt` (capped at 8 MB).

## Uninstall

Delete the proxy `steam_api64.dll`, rename `steam_api64_real.dll` back to `steam_api64.dll`
(or verify game files in Steam). Delete `cs2_gc.cfg` and `cs2_gc_log.txt` if you like.

## Capture mode: record what the real GC sends

Add the launch option `-cs2gc_capture` next to `-insecure`, or set `mode = capture` in
`cs2_gc.cfg` (the launch option wins). It still requires `-insecure`. The log's first lines say
which mode is running, for example `mode=capture`; if it says `mode=local`, capture is not on. The game then talks to
Valve's real GC exactly as it normally would, and the proxy only records the traffic in both
directions in `cs2_gc_log.txt`. This is how we learn what a real Welcome contains and what
object type IDs the game uses, instead of guessing them.

- **Everything you do is real.** Your actual inventory loads. Do not open cases, buy anything,
  trade, delete, or use tools while capturing; just open the inventory, loadout, store and
  armory pages and look around. Equipping a skin and joining a practice match are fine.
- The log contains descriptions of your own inventory. It is summarised (object type IDs, counts,
  and one sample object per type, not every item). Your SteamID64 and 32-bit account ID are
  read from the local Steam session and redacted wherever they appear, but read the log
  before sharing it.
- Nothing is changed in what the game sends or receives.
- The first reply of each message type is also saved, as raw bytes, in a `cs2_gc_replay` folder
  next to the DLL (one `<id>.bin` per message, at most 64, 1 MB each). These files hold your
  account data. They are for local mode below and must not be shared, uploaded or committed.
  Delete the folder to forget them.

### Replay in local mode

When `cs2_gc_replay` exists, local mode (no `-cs2gc_capture`) answers the game with the recorded
Welcome and the other messages the real GC sent unprompted after it, and answers the requests the
capture showed being answered (recurring missions, store data, event favorites, rank update) with
their recorded replies. Message types with no recording behave as before. It reproduces the account
the recordings came from; it is a way to test whether a faithful Welcome is enough, not the final
inventory.

### Custom items in local mode

If `cs2_gc_inventory.txt` sits next to the DLL (and `cs2_gc_replay` has a recorded Welcome), its items
are added to your recorded inventory when the Welcome is sent. Delete the file to turn this off.
The file is the same text format the core saves inventories in, so it is easy to edit:

```
"inventory" { "next_id" "3" "items" {
  "1" { "def_index" "7" "paint_kit" "282" "wear" "0.15" "seed" "661" "stattrak" "0" "rarity" "0" }
} }
```

`def_index` and `paint_kit` come from the game's `items_game.txt` (7 is the AK-47, 282 is the
Redline finish, 801 is Asiimov). `next_id` must be greater than every item id. Seeds are 1 to 1000,
wear 0 to 1. Items are added with ids from 1000000000001 up, so they cannot clash with your own.
StatTrak is not encoded yet, and `rarity` is optional (0 leaves it to the game; if the game shows
the wrong rarity, set the schema's rarity value there). Added items exist only in this session's
view of the inventory: nothing is stored on Valve's side, and they vanish when you remove the file.

## Config (`cs2_gc.cfg`, optional)

The file lives next to `steam_api64.dll`. Windows hides known file extensions, so make sure it is
really named `cs2_gc.cfg` and not `cs2_gc.cfg.txt` (the proxy also accepts the `.txt` name).
The log says whether the file was found.

```
# mode = local (default) or capture
# SteamID64 used as the cache owner. Leave out to read it from the local Steam session.
steam_id = 7656119XXXXXXXXXX
welcome_version = 0
owner_type = 1
cache_version = 1
```

An unknown key or malformed value makes the file invalid; the log says so and defaults are
used. These defaults mirror the CS:GO fork and are unverified for CS2.

## Build it yourself

The proxy forwards by export name, so it must be built from **your** `steam_api64.dll`:

```
py -3 tools/make_proxy_def.py "<game>\game\bin\win64\steam_api64.dll" --out steam_api64.def
cmake -S . -B build-proxy -A x64 -DCS2_GC_BUILD_PROXY=ON -DCS2_GC_PROXY_DEF=%CD%\steam_api64.def
cmake --build build-proxy --config Release --target cs2_gc_proxy
```

Cross-compiling works too (for example `zig c++ -target x86_64-windows-gnu`). The output is
`steam_api64.dll`.

## What to send back after a run

The whole log. The `interface requested via ...` lines matter most if there are no `>> GAME->GC` lines. Otherwise the Hello (`>> GAME->GC type=4006`) and whatever the game sends next, plus anything the
log reports as rejected. If the game sits waiting, or crashes, send the last lines of the log
and when it happened.

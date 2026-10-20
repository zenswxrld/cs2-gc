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

### A fresh inventory with your own items (local mode)

Local mode starts you with an **empty inventory**: the items in your recording are removed from the
replayed Welcome, and only the items in `cs2_gc_inventory.txt` (next to the DLL) appear. Everything
else in the recording (rank, level, mission data and so on) is kept as recorded. To keep your real
items as well, set `real_items = keep` in `cs2_gc.cfg`.

The inventory file is the same text format the core saves inventories in:

```
"inventory" { "next_id" "3" "items" {
  "1" { "def_index" "7" "paint_kit" "282" "wear" "0.15" "seed" "661" "stattrak" "0" "rarity" "5" }
} }
```

To avoid looking numbers up by hand, point the helper at the `items_game.txt` you extracted:

```
py -3 tools/inventory_item.py items_game.txt weapon_ak47 cu_ak47_asiimov --id 2 --wear 0.25 --seed 12
```

It prints a ready-to-paste entry with the right indices and the rarity the game shows (finish rarity +
the weapon's base rarity - 1, capped at Covert). `next_id` must be greater than every item id. Seeds
are 1 to 1000. Items get ids from 1000000000001 up. StatTrak is not encoded yet. Added items exist only
in this session's view of the inventory: nothing is stored on Valve's side.

### Loadout, Armory and Store: what is known and what works

- **Equipping works through the local GC.** When you equip an item in the Loadout the game sends
  `AdjustEquipSlotsManual` (2531: class, slot, item id). The proxy updates its own slot table and
  tells the game with a shared-object update (the loadout slots are SO type 3, shaped like
  `CSOEconEquipSlot`). Only your own items and the built-in defaults can be equipped; anything else is
  ignored. The slots live in memory for the session and are not saved yet.
- **Purchases are refused cleanly.** Buying on the Store page sends `StorePurchaseInit` (2510); in a test
  it was for the Armory Pass (item 1354, 2275 in currency 21). The proxy now answers with a failure and
  echoes the request's job id, so the game shows a normal purchase failure instead of timing out into the
  generic Steam error and reconnecting. Nothing is charged: no request ever reaches Valve.
- **Armory purchases are emulated** (needs `items_game.txt` next to the DLL; see below). The Armory's tiles
  are in `items_game.txt`: the `seasonaloperations` entry that has `redeemable_goods = xpshop` (11 in the
  current build) lists each tile with its `points` cost and `item_name`. The game's `redeem_id` is the
  CRC32 of that name; this matched all four requests captured so far. A valid purchase (known tile, the
  schema's cost, enough credits) creates the item, lowers the balance and tells the game, which should
  show "You received from Armory". A `lootlist:` tile rolls a random item from that loot list (skins,
  stickers or charms), a plain item name (a case) grants that item. Granted items are saved to
  `cs2_gc_inventory.txt`. Not confirmed in the game yet: the popup (it relies on pickup type 23,
  `xpshopredeem`, derived from the order of the client's pickup names), and the layout of sticker and
  charm items.
- **Applying stickers works through the local GC** (offline test only until confirmed in the game). The apply
  screen's Confirm Position sends `ApplySticker` (1086: sticker item, weapon item, slot, rotation, offsets). The
  proxy checks both items are its own and the slot is free, writes the sticker onto the weapon (attributes
  113 + 4 * slot for id, wear, scale and rotation; 278 + 2 * slot for the offsets, per `items_game.txt`), answers
  with an SO update of the weapon and an SO destroy of the sticker item, and saves `cs2_gc_inventory.txt`
  (`sticker_<slot>` lines on the weapon). Scraping and removing stickers are not handled.
- **Armory credits.** The Credits Balance and the two Armory Pass tracks live in one recorded object
  (type 6, shaped like `CSOAccountXpShop`). `armory_credits = N` in `cs2_gc.cfg` sets the balance in the
  Welcome, which tests whether that guess is right: the Armory page should then show N credits.
- **Armory purchases.** Buying a tile sends `ClientRedeemMissionReward` (9209: campaign id, redeem id,
  expected cost, your balance). Nothing answers it yet. The log records the request, which tells us
  each tile's redeem id and cost.
- The Armory's tile catalogue is not in `items_game.txt`, and the Store page's catalogue is a compressed
  price sheet inside message 2501. Decoding those is the next step.

### The Store's catalogue (message 2501)

The Store page is built from a price sheet inside message 2501: Valve binary KeyValues, compressed in an
"LZMA" container, in field 8 of `CMsgStoreGetUserDataResponse`. It has `store/entries` (one per item sold:
`item_link` is the item's schema name, plus `category_tags` and a price per currency in minor units, AUD
being currency 21), `store/store_banner_layout` (the Home page tiles) and `store/currencies`. It lists keys
for most cases but no cases.

`tools/price_sheet.py` reads and edits it. It refuses to touch a sheet it cannot reproduce byte for byte.

```
py -3 tools/price_sheet.py dump cs2_gc_replay/2501.bin
py -3 tools/price_sheet.py add-cases cs2_gc_replay/2501.bin items_game.txt --out new_2501.bin
```

`add-cases` adds an entry for every standard case (and any key that has none), copying the prices of an
existing entry (`--price-from`, default "Weapon Case Key"). Back up your recorded `2501.bin`, then put
`new_2501.bin` in `cs2_gc_replay` under the name `2501.bin`; local mode replays it.

The Store builds its tabs from the sheet's `store_banner_layout` (keyed by item index), not from `entries`.
In Valve's sheet 21 cases are banner entries with `market_link`, which the Market tab shows as "View On
Market" and never sells. `add-cases` removes that flag, adds a tile for every other case and key, and adds the
priced `entries` rows they need.

Purchases (needs `items_game.txt` next to the DLL): `StorePurchaseInit` (2510) for items the schema defines is
answered with a transaction id, the proxy then fires `MicroTxnAuthorizationResponse_t` (callback 152, 150 ms
later, as the CS:GO fork does), the game sends `StorePurchaseFinalize` (2504) and the proxy creates the items
as unacknowledged purchases, answers with their ids and saves the inventory. It is free and never reaches
Valve. This flow is copied from CS:GO and not yet confirmed in the CS2 client.

### Armory setup

Copy the `items_game.txt` you extracted from the game (it is in `game\csgo`) next to `steam_api64.dll`.
With it present, the log says `armory: 11 goods loaded from items_game.txt (campaign 11)`. Set the starting
credits with `armory_credits = N` in `cs2_gc.cfg` (default 0); each launch starts from that number.

## Config (`cs2_gc.cfg`, optional)

The file lives next to `steam_api64.dll`. Windows hides known file extensions, so make sure it is
really named `cs2_gc.cfg` and not `cs2_gc.cfg.txt` (the proxy also accepts the `.txt` name).
The log says whether the file was found.

```
# mode = local (default) or capture
# real_items = hide (default, a fresh inventory) or keep (your recorded items stay)
# armory_credits = 25   (the Armory Credits Balance to show; leave out to keep the recording)
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

# Build 06 (Claude) — what changed, what to check, what comes next

Everything here is verified **offline only** (13 Linux test suites, Windows cross-build). Nothing below has been
run in the live client yet; the checklist is how we find out.

## What this build changes

- **Armory / scoreboard / rental-bar patches can now be found.** The installed game stores these Panorama scripts as
  `.vts_c`, with resource header version 2 (blocks `RED2`, plaintext `DATA`, `STAT`). The helper only looked for
  `.js`, `.vjs`, `.js_c`, `.vjs_c` and only accepted version 4, so every patch logged "Installed VPK asset not found"
  and never mounted. Fixed in `tools/native_resources.py` (looks for `.vts_c`, accepts version 2 or 4, keeps the
  file's own version when rewriting). Checked against the real `xpshop`, `store_items` and `mainmenu_store_fullscreen`
  resources: they parse, an identity rewrite keeps `RED2`/`STAT` and `DATA`, and the Armory patch anchors match the real
  `xpshop` source. **Whether the engine loads the patched files is exactly what the checklist tests.**
- **`premier_bonus_wins`** (new, `cs2_gc_gameplay.cfg`): a running total of extra placement wins. Raising it grants
  only the difference, once, and remembers it; lowering it removes nothing. Shipped set to 8.
- **Console commands** (`tools/console_controls.py`): fixed the match for the game's `[Console] ` tag (see C), and the helper
  now logs which `console.log` it watches and warns if that file never appears or a line carries a different launch code.
- **Terminal Store sheet decode** (`tools/price_sheet.py`): see F.
- Regenerated the proxy export list from your original `steam_api64.dll` (1,046 exports, with the two bot-server
  exports intercepted). **The DLL and the helper files must be updated together**: the proxy rejects a gameplay config
  containing a key it does not know.

## Checklist for this build

Install: close CS2; copy everything in the ZIP into `game/bin/win64` (keep `steam_api64_real.dll`, `items_game.txt`,
`cs2_gc_replay`, `cs2_gc.cfg`, `cs2_gc_inventory.txt`); start with `cs2_gc_debug.exe`; wait for the preparation lines;
**fully close CS2 and start it again once** (native files load on the second start).

### A. Logs (open these first)
1. `cs2_gc_log.txt` says `gameplay: cs2_gc_gameplay.cfg loaded` and **not** `ERROR: cs2_gc_gameplay.cfg invalid`.
2. `cs2_gc_rewards.log` says `Granted 8 bonus Premier wins` on the first launch only, never again on later launches.
3. `cs2_gc_rewards.log` no longer says `Installed VPK asset not found` for `xpshop`, `scoreboard` or `popup_inspect_rental-bar`.
   You should see `prepared from panorama/scripts/…vts_c; RESTART CS2 ONCE`, then `installed: …` after the restart.
   If one still says not found or `Unsupported Panorama script resource`, copy that line to us.
4. `cs2_gc_rewards.log` has `Console controls watching …console.log (exists=True…)`.

### B. Premier placement (the 8 wins)
1. Profile / Play menu: placement shows **9 of 10 wins**, rating hidden.
2. Play one competitive bot match to completion and **win** it (the bridge needs valid final T/CT scores).
   Expect 10 wins and a visible CS Rating (the local model is +300 per win from the start rating, hidden until 10 wins).
   A loss leaves you at 9 wins and lowers the hidden rating by 100: just play again.
3. Check the rating on the profile card and on the scoreboard (the scoreboard needs the patch from A3 to have mounted).
4. Note if the match-end screens (XP bar, rank change) appear. They are **not implemented**; that is expected.

### C. Console commands (give stars, force rotation)
Cause found from a console screenshot: the commands worked in the game (`cs2_gc_give_stars` printed
`[Console] CS2GC_<code> stars 100`) but the helper never matched the line, because the game tags echo output with
`[Console] ` and the helper only accepted a line starting with the code. Fixed: the tag is accepted; alias-definition
echoes, trailing text, glued text and other launches' codes are still rejected (tested).
1. Start through `cs2_gc_debug.exe`. In the console, `cs2_gc_give_stars`: the `[Console] CS2GC_… stars 100` line prints
   and within a couple of seconds the rewards log shows `Console controls: test stars total=…`; the Armory balance rises
   (re-open the Armory tab to refresh it).
2. `cs2_gc_give_stars_1000` likewise.
3. `cs2_gc_force_rotation`, wait two seconds, open the Armory: the six pools should have advanced. Also look in the console
   for `Unknown command` lines mentioning `incrementvar` or `setinfo`: the Armory screen reads the rotation counter from a
   user-info variable that the setup file creates with `setinfo`; if that command is unknown in CS2, the backend rotation
   still advances but the on-screen tiles may not, and we need to know.
4. Send the last 40 lines of `game/csgo/console.log` and `cs2_gc_rewards.log` either way.

### D. Armory
Timer visible; six category tiles; buy one; stars drop; inventory gains the item; restart: stars and loadout persist.

### E. Held skins in bot matches (still failing)
The server did receive your five equipped items (including the Desert Eagle) 2 ms after its hello, yet the weapon in hand
is the plain default. To see what the server actually holds:
1. Equip the skins, start a bot match, buy the weapon.
2. In the console run **`sv_cs_dump_econ_item_stringtable`** (a command in the game's server library that prints the econ
   items the server has published for its players: index, id, name, attributes) and send the full output.
3. Also tell us whether the skin shows on the **starting pistol** or only on bought weapons, and on your knife.
This one output decides what we fix next.

### F. Terminal Buy
The cause of `Native terminal Store setup skipped: Corrupt input data` is fixed (the real `2501.bin` was received and
decodes; the stream states its size **and** ends with an end-of-data marker, which older liblzma builds, such as some
bundled with Windows Python, reject; the decoder now tries the other header forms and a raw decode).
1. `cs2_gc_rewards.log` should now say `Native terminal Store: ready: 2 missing terminal Store definitions added`.
2. Open a terminal's offer on the native laptop and press Buy. Send `cs2_gc_log.txt`: a `StorePurchaseInit` (2510) with
   `supplemental_data` means the Store accepted the request; if there is no 2510 at all the Store sheet is still not being
   used (tell us what the Store page showed).

### G. Quick regression (from build 20)
Ten-skin trade-up; five-Covert gold contract; sticker and charm on the C4; sticker scrape/removal; Sticker Slab; storage
unit add/extract; Armory pass activation (max 5, saved); coupon → capsule → open.

### H. Send back
`cs2_gc_log.txt`, `cs2_gc_rewards.log`, the console output from C and E, `console.log` tail, `2501.bin`.

### If a UI patch breaks the menu
Set `armory_rotation_enabled = 0`, `premier_scoreboard = 0`, `skip_container_confirmation = 0`, `hide_rent_button = 0`,
`mixed_stattrak_tradeups = 0` in `cs2_gc_gameplay.cfg`, launch once (the helper removes only its own `gameinfo.gi` lines),
then restart. Original game files are never modified.

## What we do next, once this is confirmed

1. **Held skins on the server.** Use the dump from E to see whether the server ingests our cache at all, then fix delivery
   (for example, when and how the per-player cache is pushed) instead of guessing.
2. **Terminal Buy** through the native Store, from the real `2501.bin`.
3. **End-of-match screens**: XP bar, drops, rank change (the GC/GSI side already earns the rewards).
4. **Remaining containers**: music kits and boxes (the Store sells them), patch packs, the X-Ray package, graffiti boxes.
5. **Bot features** from `FEATURE-ROADMAP.md`: names and identity, chat, career page, achievements, nemesis.
6. **Release hygiene**: debug tools off by default, release docs, `AGENTS.md` scope update, a clean tagged build, and a
   tidy-up of the test-only helpers.

Wherever this document says "verified", it means offline tests only.

## Build 07 findings (from the 20 Oct test logs)
- Console commands: `console.log` is written (launch flags and `+exec cs2_gc_console` are confirmed), but text printed by
  `echo` and by typed commands does **not** appear in it, so the helper cannot see `cs2_gc_give_stars`. Stars/rotation
  through the log transport are unconfirmed. Rotation itself is read by the Armory script from the
  `cs2_gc_rotation_offset` convar; whether `setinfo` creates that convar in this build is unverified.
- Native UI mounts (`cs2_gc_native/armory/scoreboard/confirm` appear in the filesystem list). Build 07 adds `$.Msg`
  lines so console.log shows whether the patched scoreboard / Armory scripts actually run.
- Server cache now includes equip-slot objects (type 3). The server library registers `CSOEconEquipSlot`.
- The scoreboard in the test was `Competitive | Vertigo`; the rank badge hook only reached a "0" cell there. Premier
  mode scoreboard behaviour is unverified.

## Confirmed live (build 07)
- Held skins in a bot match: the equipped StatTrak USP-S | Caiman is held (weapon HUD shows it). Cause: the server cache
  needed the equip-slot objects (type 3) as well as items. Knife, gloves and bought weapons still to be checked.

## Build 09: why no native UI/schema override has ever loaded
The console.log search-path list shows `csgo\pak01.vpk` and `core\pak01.vpk` (GAME) **before** our `cs2_gc_*` folders, so
the installed originals always win over loose override files. Build 09 also writes a `pak01_dir.vpk` inside each
`cs2_gc_*` folder (tools/vpk_pack.py); VPKs are listed in gameinfo order and ours come before `csgo`. Unverified in the
client. To revert: delete `pak01_dir.vpk` from the `game\cs2_gc_*` folders (the loose files stay).
Also in build 09: terminal offers are labelled limit minus remaining (the stock label is the remaining counter, so it
counted down); offer numbers use a new `cs2_gc_offers` override.
What to look for after the second launch: the console.log top list should show `cs2_gc_*\pak01.vpk (vpk)` lines before
`csgo\pak01.vpk`, plus the `cs2_gc scoreboard hook reached` and `cs2_gc armory rotation hook` lines.

# Codex test build 2026-10-20-17

## Install

1. Fully close CS2. Back up the proxy DLL, `cs2_gc_inventory.txt` and gameplay config.
2. Extract **all** ZIP contents into `game/bin/win64`. Preserve your original `steam_api64_real.dll`, schema, replay folder, proxy config and saved inventory. The ZIP supplies `cs2_gc_gameplay.example.cfg`; it does not overwrite your live gameplay config. New settings use their defaults when omitted.
3. Start the **updated `cs2_gc_debug.exe`**. It prepares the native files while CS2 is closed, then starts Steam/CS2 with the debugging flags. No second launch is needed for files prepared this way.
4. If preparation fails, read `cs2_gc_prepare.log` beside the launcher. The launcher leaves CS2 closed so its VPKs remain unlocked. Python 3 is required, as before.

Do not use the old launcher or start through Steam first when installing this update: Windows locks already-mounted VPKs. Build 15's logs show exactly this failure, leaving old Armory/scoreboard resources mounted against the new coordinator catalogue. The background helper remains for rewards; it should find the prebuilt native packs unchanged.

## User-confirmed working before this update

Selling pays stars; newer weekly-collection weapon drops arrive; hiding Open to Rent and skipping the opening confirmation work. The rewards/rating tab appears and shows rating changes. Existing mixed trade-ups, held skins, certificates and rotation were also reported working earlier. These paths are retained. The missing end-match cards and poor layout are separate from the successful inventory rewards.

## Build 17 changes

- Removes the worded category tabs. Larger 56×48 paging arrows, a larger page number and a 23px countdown sit together in a centered header.
- Balances the currently rotating goods across pages so shorter rows do not repeat unchanged. The featured limited item is pinned on the first page and stays visible while paging. Types are interleaved so container offers do not crowd stickers off the first page.
- Agent tile portraits move to the right of the title/cost. Agent inspection uses up to eight named cards per page, a smaller heading and its own pager; a lower-height viewport uses fewer rows. Space is reserved for the native purchase/confirmation bar. Browsing previews does not choose the random purchase outcome.
- Adds a dedicated rotating terminal offer, 2 stars by default, using installed volatile-container definitions. The inspected schema contains Genesis and Dead Hand. It grants a closed terminal through the existing native purchase/open path; it does not roll its offers at redemption. Settings: `armory_terminal_slots=1`, `armory_terminal_price=2`. Setting `terminals_enabled=0` also removes it from rotation. The catalogue now contains 122 real goods.
- User confirmed the native bottom Sell for Stars placement. Graffiti is reported broken and intentionally deferred at the user's request.

Use the updated launcher after fully closing CS2, as above. New UI placement and terminal redemption need live testing. Paging/agent bounds and terminal rotation, star spending and unsealing have automated checks; the stock XP animation remains unresolved.

## Earlier build 16 changes retained

- **Pre-launch preparation:** fixes the logged Windows `Access is denied` errors when replacing `pak01_000.vpk`. Updates the client catalogue, Armory, scoreboard and results before those files can be mounted. This also addresses stale tiles attempting purchases that the newer coordinator correctly rejected.
- **Sales menu:** removes Community Market sell/listing actions for local inventory items, and puts Sell for Stars at the bottom with a separator. The working native sale request and confirmation are retained.
- **Armory:** retains the native tile/inspect style, adds visible category filters, a main-page countdown and paging. Native rows hold at most 4 / 3 / 4 offers, closer to the user's reference; a longer row gets another page. Rotation still controls eligible goods and purchases.
- **Correct artwork/routing:** limited tiles explicitly hide the old hardcoded artwork and display the actual offer. Tile/nav callbacks rebind to their own current entry. Optional preview variations no longer disable the entire rotation patch. Failed coordinator redeems now log the reason code, cost and balance.
- **Bot ratings:** removes the unverified player-name API call. Each bot gets its own cached rating within the configured spread, keyed by its actual scoreboard slot and identity. The value stays fixed rather than following each later player-rating change. A fresh UI session randomizes the set.
- **Results layout:** fixes the native `id-eom-layout` 300-pixel height limit that clipped profile level and drop cards. The tab gets full height, a centered results card, smaller headings and opaque background; other tabs retain their stock height.
- **Drop presentation:** captures new unacknowledged rewards on inventory updates and retains their IDs after acknowledgement, so an inventory popup cannot erase the results tab's detected cards. It never grants or acknowledges items itself.
- **More time:** results tab displays for 20 seconds; local match restart delay is set to 45 seconds. Both settings are configurable. This needs confirmation in the target server/client.
- **Music:** parses installed `music_definitions`, writes and saves music-id attribute 166, opens flat keyless music capsule lists, and respects their guaranteed StatTrak metadata. Music StatTrak uses the MVP counter type. Fixed music item definitions with a schema music ID also resolve correctly.
- **Existing envelopes:** converts owned single-item guaranteed Store offers to their actual sticker/container/music item at startup, preserving item IDs and storage membership. Repeated launches do not add duplicates. New purchases resolve guaranteed contents directly. Ambiguous bundles remain unchanged; missing historical music IDs cannot be reconstructed from an empty generic item.

## Useful settings

`end_match_duration=20`, `match_end_delay=45`, `premier_bot_spread=1200`.
Armory group counts and OfflineCS sale values remain in the gameplay config. Prices default to 1/2/5/10/25/50 by rarity, 150 for knives/gloves, 50% rarity value for stickers/charms, 10 for music, 30% container value and 50% agent price. StatTrak adds no sale premium. Cases/capsules use their CS2 local Armory costs.

## Test checklist

1. Confirm `cs2_gc_prepare.log` ends with preparation complete and `cs2_gc_log.txt` identifies build `codex-20261020-17`.
2. Check both Armory arrows change the rows, the limited offer appears on page one, the centered countdown, and the paged agent preview. Buy a case, sticker, charm, capsule, terminal and agent; confirm each action matches its tile and spends the displayed stars.
3. Right-click a spare item: Sell for Stars should be last, Community Market sell absent. Cancel once, then sell and confirm the saved balance.
4. Check bots have varied ratings; win/loss changes your rating without moving their already-assigned values.
5. Finish a local competitive match. Check the centered results card, profile level, drop images/names, and time to read them. The stock XP animation remains unresolved; this is the local results tab.
6. Open a normal and StatTrak music capsule, equip each kit and check playback. Look for old guaranteed offer envelopes converting to their proper contents.

## Validation boundary

15 automated suites pass, including cached bot ratings, category paging/countdown, sale confirmation, acknowledged drop-card retention, music IDs/StatTrak, old-offer migration and save/reload. The preparation pipeline was exercised twice against inspected native scripts packed as version-2 resources: all updated overrides were built before launch, read back from their VPKs, syntax-checked, and remained byte-identical on the second pass. Windows x64 debug and release cross-builds pass. New target-client behavior still requires the checklist above.

Console echo-to-log transport for the testing commands remains unresolved in the last live logs. No change here claims to fix it. Terminal monetary-cap semantics and stock XP animation are also outside this update.

## Reset local inventory and progression

Fully close CS2 and the rewards helper. Move these files from `game/bin/win64` into a backup folder: `cs2_gc_inventory.txt`, `cs2_gc_gsi_state.json`, `cs2_gc_rewards.txt`, `cs2_gc_matches.txt`, `cs2_gc_premier.txt`, `cs2_gc_console.txt` and `cs2_gc_console_boot.txt`. Missing files are fine. Restart using the launcher; local saves are recreated as the helper starts and the inventory saves. Resetting only the inventory can reapply old cumulative rewards.

Keep your configs, schema and replay folder. A fresh inventory uses the starting `armory_credits` from `cs2_gc.cfg`; set it to 0 if you want zero starting stars. Set `premier_bonus_wins=0` in `cs2_gc_gameplay.cfg` to avoid granting test placement wins again. Default profile progression starts at level 1, 0 XP.

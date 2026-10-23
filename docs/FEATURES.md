# Features and known issues

Status reflects the repository and user test reports through **24 October 2026**. Automated checks prove offline rules and packaging contracts; they do not prove every native UI path or finish looks correct.

## Working baseline

| Feature | Evidence and limits |
| --- | --- |
| Local inventory and loadouts | User-tested; saved items/profile reappeared after restoring the user's own replay folder in the separate game copy. |
| Standard cases, capsules and souvenir handling | User-tested opening baseline. Souvenir direct grants preserve tournament attributes/stickers. Music/graffiti and less common container paths still need review. |
| Native Armory | User-tested category rotation, purchases, collection inspection and custom knife/glove cases. Uses the native page, not the legacy CS:GO Star Shop. |
| Local stars and selling | User-tested persistence and selling. Rarity/wear and purchase-origin safeguards exist; the full economy still needs a loop audit. |
| Profile XP and local rating | Bot-match XP/stars, native results and local Premier-style placement/rating baseline exist. Not official competitive matchmaking ranks. |
| Care packages | User confirmed claims and opening awarded cases after the tournament-favourite message fix. Three of four rewards; level-up packages by default; optional match packages are configurable. |
| Bot identity | Realistic names and scoreboard decoration work; BOT labels/killfeed/language coverage vary. |
| Mission launch | Native mission cards can launch the relevant bot modes/maps. This is separate from progress tracking. |
| Preparation cache | User confirmed substantially faster repeat launch. Mounted VPKs are prepared before CS2 starts. |
| Classic custom knives and gloves | Many finishes user-tested. Material support and calculated outcome counts depend on the installed game; counts are not promises of unique visual quality. |

## Implemented, still being tested or repaired

| Area | Remaining work |
| --- | --- |
| Complete ZIP / launcher | Direct launch of the separate copy was manually confirmed. The new automated DLL/schema/runtime/profile bootstrap and complete upgrade ZIP need target-client testing. |
| Gun collections | New generator classifies real finish parameters, separates transferable patterns from per-gun artwork, retains history/IDs and distributes colour families. Reported unchanged official copies, duplicate looks, bad masks/overlays and palette quality require a collection-wide review. |
| Family colour rolls | Backend selects and saves a colour variant with its matching displayed name. Confirm every advertised family uses a visibly distinct actual material/texture variant. |
| Missions | Progress tracking, rotated mission templates and tier XP exist. Weapon/mode/map attribution and full native completion require live validation. |
| Trade-ups | Standard/mixed StatTrak baseline exists. Native Souvenir selection, custom collection membership, wear/weighting and edge cases need more live coverage. No claim that every custom pool can trade up. |
| Multi-select selling | Native multi-select path is under validation. Preserve the working single-item sale path. |
| Economy | Review deterministic purchase/sale loops, rarity-specific charm resale, wear-based skin values, fixed offers, gold costs and limits. Implemented safeguards are not a completed audit. |
| Finish quality | Individual knife/glove palettes and Dead Hand glove coverage remain under review. Preserve the successful classic finishes rather than applying a blanket recolour. |
| Helper startup | The ZIP uses a bundled runtime; GSI first setup can still need one restart. Rewards/progression must not double-count after a move or helper restart. |
| Terminal / rare tool paths | Existing native/helper paths are retained; broaden repeat-launch and client coverage. |

## Future features

- Career/statistics page with accurate local match, collection, opening, spending and selling history.
- Achievements and unique collectible rewards, only where supported by the actual CS2 schema/UI.
- More complete mission completion presentation and rewards.
- Difficulty-aware bot progression, richer bot identity and optional bot chat/personality systems.
- Wider language coverage, clearer error reporting, launcher polish and complete owned-file cleanup.
- Compatibility with newer CS2 builds after explicit testing.

These are plans, not included functionality. The CS:GO reference's career/bot/achievement systems are not automatically CS2 integrations.

## Data and compatibility

- Local mod data never creates real Steam items or charges a Steam wallet.
- The ZIP ships no user's inventory, config, replay recordings or Valve game files.
- Existing IDs, collection history and inventory must survive upgrades.
- Supported version and downgrade instructions are in [DOWNGRADE.md](DOWNGRADE.md); installation and logs are in [INSTALL.md](INSTALL.md).

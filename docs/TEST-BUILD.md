# CS2-GC test build25 — local souvenir contracts and feature notes

DLL tag:`codex-20261021-25`. Client build25966348. Includes24c material changes.

## Install

Close CS2/helper, back up inventory/config/**cs2_gc_finish_ids.json**, extract ALL files into game/bin/win64 and run the updated cs2_gc_debug.exe. Keep inventory/config/finish-ID map and the real Steam DLL. Only an example config is shipped. Launcher preparation rebuilds the owned native packs.

## Souvenir contracts

- `souvenir_tradeups=1` defaults on in both config parsers. Set0 to disable local souvenir contracts.
- Ten Souvenir weapons of the same rarity can produce one next-rarity Souvenir weapon using normal collection weighting and wear mapping. Mixed Souvenir/normal or Souvenir/StatTrak inputs are rejected atomically.
- Output stays native Souvenir quality, never StatTrak. Tournament event/team/player provenance comes from a contributing Souvenir in the selected collection. Applied stickers/charms do not transfer; this custom contract does not generate replacement decals.
- No new outcomes are invented: a collection without a higher-tier skin is rejected without consuming inputs. Souvenir knives/gloves are not created. These are local custom rules, not a change to official matchmaking.
- Existing inspected native recipes already accept tournament quality, so this fixes the backend rejection without a new command, bat file or custom trade-up screen. Actual native UI selection/submission still needs user validation.

## Test

1. In the native trade-up UI, select ten same-rarity Souvenir weapons from a collection with an available next tier. Confirm successful consumption of exactly ten items, one Souvenir output, expected wear and persistence after restart.
2. Check mixing with normal/StatTrak items refuses without loss; collections with no higher-tier outcome must also preserve inputs.
3. Test normal and mixed StatTrak contracts still work. Existing material/loadout tests from24c still apply.
4. Store care-package claims remain unresolved: capture the current cs2_gc_log.txt immediately after a failed claim and send it. No new claim protocol changes in25.

All26 automated suites pass; Windows debug/release cross-builds compile. Tests cover Souvenir quality, provenance/collection selection, wear, persistence, disabled mode, mixed-quality atomic refusal and unsupported collection safety. Native trade-up UX and new glove/knife renders remain separately unverified.

See FEATURES.md for current custom-case counts and pending work. Ash knife contrast is recorded as pending, not changed in25. Prior24c fixes target Gold Brick tone relationships and Bronzed/Racing/Lunar Weave accents; no broad recolour reset.

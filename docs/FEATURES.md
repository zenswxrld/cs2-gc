# Features and remaining work

## Custom cases

Current generator, reconstructed using the supplied build25966348 palette reports:

| Case | Models | Distinct finishes | Model/finish outcomes |
|---|---:|---:|---:|
| Black Market |20|1,005|4,980|
| Gauntlet |8|2,084|2,084|

Total:7,064 model/finish outcomes, before wear, seeds and StatTrak variations. Includes2080 glove recolours/panel variants and four shipped unused glove finishes. Some panel variants share clean display names. Runtime omits materials unavailable in the installed game; these are calculated pool counts, not owned inventory counts.

Armory purchases display the case and directly grant a knife/glove; existing inventory cases still open normally. Original owner certificates, persistent IDs and per-item wear/seeds are retained.

## Current priorities

- Souvenir-only trade-up contracts in the native UI: retain Souvenir quality, collection weighting and wear mapping; input applied stickers/charms do not transfer. Backend implemented in build25, with native UI/client testing pending. Config: souvenir_tradeups=1 (default). Mixed Souvenir/non-Souvenir or Souvenir/StatTrak inputs are rejected. Collections without a next-rarity outcome remain unsupported; no souvenir knives/gloves.
- Store/care-package reward claim: four offers, choose three in Inventory. Selection works but claims timed out: the build-27 log of a failed claim has no 9219 (and no other GAME->GC frame) after the welcome, so StoreAPI.StoreRedeemFreeRewards sent nothing for the synthetic choice tokens. The popup now submits the client-resolved faux ids of the displayed tiles; the GC maps them (or tokens) back to the saved offers and logs "care claim received/rejected". Needs the new DLL + helper and live testing; if no 9219 appears again, send console.log (-condebug, "cs2_gc care:" lines) with cs2_gc_log.txt. No reward UI at match end and no unowned preview econ objects.
- Knife finish review: user reports Butterfly The Fuschia Is Now Ash looks like nearly bare silver. Retain donor tonal/pattern contrast when desaturating. Pending investigation; do not mark fixed. Gold Brick Toxic now uses related lime/olive tones and has a live screenshot; exact donor mapping/sheens still need review.

## Remaining gameplay/economy

- Build26 implements rarity-specific charm resale, wear-based skin resale, fixed-offer/gold-cost safeguards and official LTD price correction. New free generic Store grants/derivatives cannot sell; terminal purchases explicitly remain sellable by rarity/wear. Existing inventory origins are not retroactively inferred. Native tests pending.
- Build26 adds independent souvenir Armory pity using collection settings; core guarantee/disabled-mode checks pass, native testing pending.
- Build26 changes complete installed English native bot decoration tokens, preserving names/placeholders. Killfeed and other languages require client validation.
- Mission completion tracking with real weapon/event attribution and XP/star bonuses; mission clicks already launch bot matches.
- Career/statistics page and achievements/rewards, following OfflineCS where supported.
- Dead Hand independent Gauntlet recolours: schema paths now inspected, supported eight-tint materials only; full coverage pending cs2_gc_glove_materials.json from target client.
- Deferred graffiti/music-kit/envelope issues; refine Racing Sunset, Black Tie Aurora, Emerald Web Aurora/Toxic similarity and other individually reported finishes while retaining successful palettes. Snow Leopard panel contrast candidate fix in26.
- Later release packaging: tidy game-folder files into owned folders, launcher icon and final install/build cleanup.

Core automated verification and native client testing are separate. Confirm individual fixes in game before calling them complete.

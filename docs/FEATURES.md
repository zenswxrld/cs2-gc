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
- Store/care-package reward claim: four offers, choose three in Inventory. Selection works but latest claim times out; current failed-claim cs2_gc_log.txt required before further transport changes. No reward UI at match end and no unowned preview econ objects.
- Knife finish review: user reports Butterfly The Fuschia Is Now Ash looks like nearly bare silver. Retain donor tonal/pattern contrast when desaturating. Pending investigation; do not mark fixed. Gold Brick Toxic now uses related lime/olive tones and has a live screenshot; exact donor mapping/sheens still need review.

## Remaining gameplay/economy

- Charm resale by rarity; weapon resale by wear; audit all deterministic buy/sell loops and historical official LTD prices. Howl250 and Aphrodite125 already applied.
- Verify collection pity and add souvenir pity.
- Remove BOT prefix in killfeed (scoreboard names work).
- Mission completion tracking with real weapon/event attribution and XP/star bonuses; mission clicks already launch bot matches.
- Career/statistics page and achievements/rewards, following OfflineCS where supported.
- Deferred graffiti/music-kit/envelope issues; refine individually reported glove/knife finishes while retaining successful palettes.
- Later release packaging: tidy game-folder files into owned folders, launcher icon and final install/build cleanup.

Core automated verification and native client testing are separate. Confirm individual fixes in game before calling them complete.

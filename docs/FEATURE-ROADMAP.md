# CS2 OfflineCS feature roadmap

User-approved scope, 20 October 2026. The supplied “confirmed” labels refer to the
OfflineCS reference implementation; they are **not CS2 validation claims**.
Port within verified CS2 interfaces and client resources. Leave the hardest work
until the core progression/inventory flow is stable. Keep the native Store and
Armory; **do not port the legacy Star Shop**. Custom cases and paint/schema rewriting
remain outside this port's scope.

## Delivery order

1. Stabilise current CS2 inventory/loadout, collection trade-ups and five-Covert
   contracts, terminal offer acceptance, saved profile/pass/stars, match rewards,
   configuration, and Armory rotation integration.
2. Basic bot identity: generated gamer/pro-style names plus optional `bot_names.txt`,
   hidden BOT label, team agent pictures on scoreboard, then round report/freeze
   panel. Fake ping and clan tags require actual scoreboard/server support;
   never spoof real Steam profiles or copy old engine signatures.
3. Career and skill progression: match counters, wins/losses and difficulty-aware
   rewards; native end-of-match XP bar, skill-group screen and rank-change banner;
   profile card rank. **Use local Premier-style numeric CS Rating, hidden until 10 placement wins.**
   Do not port the Silver-to-Global Competitive ladder.
   Profile XP rank remains a separate level 1–40 system starting at level 1/0 XP.
   Bot skill should follow the local Premier rating in the Play menu, with a manual
   config override. Verify the available CS2 bot-skill controls before wiring them.
4. Basic bot chat: greetings, kill reactions, bomb/round comments and final gg.
   Use real CS2 events/chat delivery, delay/rate-limit speech, avoid noisy polling.
5. Career page, collections and achievements: schema-derived real case names,
   one block per category, no duplicates. Track cases, rarity pulls, golds,
   knives/gloves, ownership/collecting, trade-ups, matches and earned/spent stars.
   Track Store/Armory purchases and sales only once a real local sale path exists.
   Remove/exclude all Danger Zone counters and achievements.
6. Advanced bots: chatty/quiet/rusher/camper/friendly personalities, identity hints,
   distinct chat styles/frequency. Only write Aggression if the target bot profile
   already supports that field. Nemesis after the same bot kills the local player
   three times, nemesis achievements and gloating; next-round revenge, headshot
   remarks, teasing and bot-to-bot banter. Persist/clear memory deliberately across
   rounds/matches, rather than assuming bot entity indexes remain stable.
7. Hardest career/UI work: approximately 400 meaningful achievements with rewards
   scaled by difficulty, and unique collectible rewards for the hardest ones.
   Each eligible achievement awards its own schema-valid pin/coin/trophy exactly
   once, never a service medal or a repeat of another achievement's collectible.
   Show that specific collectible next to the star reward. Validate that the real
   schema has enough suitable distinct collectible items before promising the
   final catalogue. Gauntlet/Black Market openings do not count toward knife/glove
   achievements if those case types are ever added; do not invent them in CS2 now.

## Limited-time Howl offer

Use the existing native **Limited Edition Item** slot, rotating Howl alongside
usual limited skins. Keep the requested 15-minute timer. No separate Howl store
or category. The user supplied a screenshot of the existing limited pistol tile.

Add the schema's existing M4A4 Howl as an optional timed offer, default 40 stars,
normal/non-StatTrak with valid schema wear. It participates in the 15-minute
rotation and must be rejected outside its active window. Preserve Contraband
rarity so it cannot enter Covert trade-ups. Backend availability/purchase rules
are tested independently; native `MissionsAPI.ActionRedeemOperationGoods` uses
schema shop indexes, so **a new Howl tile cannot be purchased just by inventing
an index**. Native display plus a verified local redeem bridge remain required.
Do not describe this as already visible or buyable on the current client page.

## Current test-build boundary

Build 04 prepares a narrowly scoped native mixed-StatTrak recipe override from
existing schema data and mounts a dedicated search path, with backup and clean
removal. It needs one restart and live selection/crafting verification. Build 03
starts/stops rewards automatically with CS2. Star persistence is user-confirmed;
build-03 XP/star earning and three match drops are confirmed by latest logs. Build04 also connects native Premier cache/badges, prepares container UI overrides, repairs terminal reload/Store data, and adds per-level drops plus Armory pity; new UI paths require live testing.

Build 02 adds configurable mixed StatTrak contracts, saved case/terminal pity,
three guaranteed local match drops (independent 50% case / 50% blue+ skin by
 default), progression diagnostics and a terminal-purchase helper fallback.
The native rotation/countdown and confirmation override are source generators;
they still need target-client compilation/mounting. Native bot-match XP/skill
screens, bot identity/chat, career UI and achievement catalogue remain future
work. Do not describe the CS:GO implementations as functioning CS2 integrations.

Difficulty scaling, wins/skill progression and achievements require reliable
match result/difficulty data first. GSI currently supplies XP/completion facts,
only provisional local win/loss classification from valid competitive-mode final scores,
not a trusted server difficulty event stream; avoid retroactively
inventing wins or reward history from an inventory snapshot.

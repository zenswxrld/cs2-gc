# Pity, missions and stats update

## Pity

The default soft-pity start is now pull 70 instead of 10, with a quadratic
ramp and the same guaranteed top reward on pull 100. Counters are preserved.
Case gold pity remains separate from Armory collection pity; collection
counters remain independent. A pink does not reset the red counter.

Five-tier collections use weights 6400/2500/750/300/50 from lowest to highest.
Six-tier collections use 4500/3000/1400/750/300/50. Smaller pools retain their
existing base weights. Ordinary case base rarity weights are unchanged.
The Armory top-tier minimum defaults to 50 per 10000 (0.5%). With defaults,
the five-tier custom collections average about 2.97% pinks and 1.49% reds
including pity. These are long-run expectations, not guarantees within a
short batch. Existing explicit settings still take precedence.

The sale-value calculator and economy audit use the same weights and curve
as purchases. Automatic sale-value caps are recalculated accordingly.

## Missions

Refreshing no longer generates a future mission start period. Valid local
mission data is shown independently of online GC/Prime flags; both native
mission queries are tried, and a 15-second cache bridges schema refresh gaps.
One scheduled retry per panel restores the card when fresh data arrives.
An unavailable schema is not replaced with invented progress or objectives.
Existing mission pinning and reward deduplication remain in place.

## Stats and achievements

The News tab becomes Stats. Rank, Premier wins, current level and XP use the
native client APIs. The page also displays saved match, combat, mission and
bonus-star totals. Those saved totals refresh when the game launches; they
are explicitly labelled in the page. Combat and mission-completion counters
start with this update because older saves do not contain those totals.

Only authenticated local live-match deltas count. Repeated GSI packets,
old scoreboard totals on reconnect and spectated bots do not add combat
stats. Stats and unlocked local milestones persist in the existing GSI save
and are included in progress backups. Unlocked milestones stay unlocked
when the rating falls. They do not grant Steam achievements or extra rewards.

The native script contracts and JavaScript syntax are checked against build
25966348. Client layout, mission visibility after returning from matches and
the new page still require in-game review.

Close CS2 and its helper, extract into the portable game root, replace the
included files and launch normally. No player saves or Valve assets ship.

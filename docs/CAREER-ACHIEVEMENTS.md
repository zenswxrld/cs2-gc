# Career achievements

82 finite achievements now award 2,925 stars in total across all tiers. Most
first milestones award 5–15 stars; difficult long-term milestones award up to
150. These are small, one-time bonuses alongside normal gameplay rewards.
Achievement payouts do not advance earned-star milestones, preventing reward
loops. Existing unlocked achievements get their first payment once. Payment
history lives in the normal progress save and its backups. Disabling stars
also disables these rewards; unlocking while disabled does not defer payment.

## Conditions and tracking

The native Stats tab has Overview and Achievements views, category filters,
progress bars, native weapon/utility icons and hover explanations. Hover a
card, title, reward or icon for its target and exact conditions. Completed
cards distinguish paid rewards from a pending payment.

The achievement browser now groups the 82 existing milestones into 27
achievement groups. Select a group on the left to see its objective, larger
icon, progress, reward and full tier ladder on the right. Selecting a tier
shows that tier's conditions. The next unfinished tier is selected by default.
This changes presentation only: all existing IDs, targets and payout amounts
remain the same.

A recent-unlocks strip records new unlocks in saved order, including the
stars actually paid. Older saves without that history show an explicitly
labelled "Unlocked achievements" selection instead of invented chronology.
The strip and saved totals refresh on launch. Clicking a recent unlock opens
its category, group and exact tier.

New counters include enemies flashed for at least one second, flash assists,
through-smoke kills, kills while YOU are flashed, no-scopes, wallbangs, HE and
fire kills, knife/Zeus kills and kills by weapon class. Teammates, self-flashes,
warmup and spectated bots' actions are excluded by the event bridge. A flash
hitting three enemies can add three successful enemy flashes.

Basic combat totals continue to use authenticated local game-state deltas.
Advanced events come from the owned CS2GCCareerBridge server plugin, built
against the installed CounterStrikeSharp API. It installs at launch into its
own plugin directory, verifying its payload and API hashes first. Disabled
server plugins leave advanced event tracking unavailable; unsupported events
are never inferred from scoreboard changes. Only local bot-server events can
be tracked; this is not a tracker for other servers.

Saved career totals refresh on the Stats page when the game launches. Current
level, XP, Premier rating and wins use native APIs. The reward helper saves
new progress during play and publishes stars through the existing reward
channel. Advanced counters start with this update; old matches cannot supply
missing flash/smoke information. Restart to see newly saved career totals.

## Install and verification

Close CS2 and its helper. Extract the entire update into the portable game
root containing Launch CS2 GC.exe, replace the included files and launch
normally. No player saves, settings or original game assets are included.
CS2 GC Saves backs up the achievement payment history with other progress.

Checks cover payout/restart/deduplication, event replay and regression,
installer ownership/hash verification, UI hover/filter behaviour, actual
build-25966348 script anchors and JavaScript syntax. The plugin compiles
against the installed API. Actual in-game event delivery and visual layout
still need client verification; compilation and mock UI tests do not prove
those. Launch preparation reports whether the event plugin was installed.

Reward tiers were informed by Offline CS's career structure:
https://github.com/zenswxrld/CSOffline/blob/main/csgo_gc/career.cpp
Our reward amounts and implementation are authored for this project's economy.

The source archive includes the C# plugin. Build it against the target
CounterStrikeSharp API and matching .NET runtime references; write its DLL
and SHA-256/API hash bundle metadata to build/career. package_release.py
includes that owned payload when available. No Valve assets or framework
reference assemblies belong in the plugin payload.

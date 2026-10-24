# Roadmap

The current implementation and validation status live in [FEATURES.md](FEATURES.md). Historical build notes remain in TEST-BUILD.md and CLAUDE-HANDOFF.md; old instructions there are not fresh-install instructions.

## Current priorities

1. Complete drag-and-drop ZIP: direct adjacent-game launch, private runtime, original-DLL preservation, automatic schema extraction, own-account bootstrap, clear failure messages and upgrade preservation.
2. Verify fresh setup and existing-profile upgrades on supported Steam build 25966348. Publish a full ZIP only after its checks; distinguish automated checks from user-client confirmation.
3. Review custom gun collections for actual recolours, compatible transfers, duplicate looks and balanced finish/colour distribution. Keep successful knife/glove finishes and all owned IDs/history.
4. Validate mission progress/completion and XP, native Souvenir/custom trade-ups, multi-select selling and the economy safeguards.

## Next

- Career and statistics: track only observed events; never infer past rewards/wins from an inventory snapshot.
- Mission completion presentation and reliable mode/map/weapon attribution.
- Refine the existing BotRandomizer loadouts, Bot Improver and rating-based skill presets; optional event-driven chat/personalities come later.
- Fix remaining graffiti/music/tool flows and individual material issues.
- Better localization, launcher visuals and owned-file removal.

## Longer term

- A substantial achievement catalogue with schema-valid unique collectible rewards.
- Nemesis/revenge and richer optional bot behaviour.
- Additional supported CS2 versions, tested and versioned explicitly.

Keep the native Store and Armory. The legacy CS:GO Star Shop is not the target UI. No feature should be labelled working solely because a CS:GO reference implementation exists or a synthetic test passes.

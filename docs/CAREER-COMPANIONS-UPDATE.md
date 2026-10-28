# Career, local Premier and companions

Close CS2 and the reward helper. Back up progress with **CS2 GC Saves**. Extract
this overlay into the folder containing **Launch CS2 GC.exe**, replacing its
included files, then use that launcher. The first launch rebuilds the changed
glove materials. No player save, personal configuration or Valve asset is shipped.

- Career page uses more width, leaves space around scrollbars and adds recorded
  unboxing totals, rarity distribution, recent results, top three pulls and closest
  achievement goals. New opening history starts with this update; old inventory
  contents are not reconstructed as past openings. Best pulls rank by rarity,
  StatTrak, float and recency, rather than market price. Saved views refresh on launch.
- The native local profile carousel includes owned collectible pins/medals. Its
  tooltip marks the featured/equipped item. Other players' profiles are unchanged.
- Competitive includes installed night variants with native map-group definitions.
  Local Premier offers a simulated opposing captain, six BO1 bans and starting-side
  selection. This uses local bot matchmaking, rating and rewards.
- Bots can follow human objectives and automatically follow teammates again.
  Existing difficulty and `bot_nades less` settings remain available.
- Profile XP defaults to **125%**, configurable as `profile_xp_percent` in the
  reward settings. The underlying Armory pass XP and all star rates are unchanged.

## Chickens

The next eligible **level-up reward** grants one guaranteed test egg, in addition
to the normal reward. A consumed flag lives in the inventory save: restarting or
installing this update again does not repeat that guaranteed grant. It is not a
permanent 100% drop chance. Normal completed matches have a 10% egg chance.

Each egg is a separate native chicken item, with a saved appearance seed and
Catalana, Silkie or Polish breed. It hatches after one or two completed matches,
then grows through chick, pullet and adult stages. Multiple pets stay owned;
only one follower is active. **Stats > Companions** selects the pet and accessory.
Eggs remain inventory items until hatched; they do not walk around the map.

The **Chicken Cosmetics** Armory collection offers ten permanent accessory items
for three stars per roll, using installed helmet, glasses and hat models. It
participates in collection rotation. Equip owned accessories from Companions.
The console alternative is `css_chicken <owned-pet-item-id> <accessory-definition>`;
`css_chicken off` unequips the follower. Selecting an unowned item is rejected.

Pet ownership, growth, appearance, active selection and the one-time test grant
are saved together with inventory. There is no hunger expiry or pet destruction.
The local server follower has damage disabled and is recreated after death/map
changes when the player is alive. This does not implement Valve's full HatchBook
or feeding backend. Server plugins must be enabled for the follower to spawn.

## Glove repair and validation

Mostly neutral classic glove palettes now colour their light leather panels as
well as their accents. This includes Black Tie, Snow Leopard and the other neutral
palettes found in the audit. Dark markings and the source value hierarchy remain;
Midnight also darkens the pale panels. Existing paint-kit IDs are preserved.
Previously approved non-neutral palettes and disabled Dead Hand recolours remain.

Automated checks cover native builds, save/load, the one-time egg flag, pet growth,
XP/star separation, both veto captain orders, accessory schema extension, profile
pin filtering, glove contrast and native script/resource contracts. The plugin
compiles against this installation's CounterStrikeSharp API. These checks do not
prove the client visuals: follower movement, seed appearance, hat placement,
native accessory preview, night-map launch and glove appearance need in-game
verification after installation.

Career views refresh on launch. Kills and headshots have since been confirmed tracking in the client.

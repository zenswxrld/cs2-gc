# Follow-up to the Career / Companions build

Close CS2 and its reward helper. Back up with **CS2 GC Saves**, extract this
cumulative overlay beside **Launch CS2 GC.exe**, replace the included files,
and use the launcher. No player saves or Valve assets are included.

## Existing egg repair

The prior build successfully granted the test egg, but used definition 4948
(`chicken_egg`, a consumable) rather than 4681 (`pet`, the actual companion).
The saved owned item is migrated in place: its inventory ID, seed, breed,
growth, accessory and one-time grant flag remain unchanged. Ordinary consumable
eggs without our saved companion fields are not converted. No duplicate egg is
granted. Pet growth remains based on completed matches.

The selected companion is equipped through the client's native loadout API.
**Stats > Companions** can also select or unequip it. Accessory requests now use
the same immediate local GC transport already used for care-package choices;
they no longer depend on console logs flushing. Ownership is checked before
equipping. Hunger/upgrade timers are kept in the future; the local match counter
controls stage changes. Verify the repaired egg in Companions and on the main
menu after restarting, then complete its remaining one or two matches to hatch.

## Premier and previews

The local veto is explicitly positioned outside the native parent's layout
flow. GO and veto failures now write `[CS2GC Premier]` diagnostics and errors
produce a popup instead of silently returning. Both captain orders still leave
one map after six bans, followed by side selection. The installed Active Duty
list can be read from either an array or object map configuration.

Large Armory collection previews are attached to the tile rather than the
image's layout container. Custom care-package weapons use native 3D previews
instead of the missing generated static thumbnail. These are runtime UI changes,
not newly rendered inventory thumbnails. The client may still show the Rare
Special Item question mark in other surfaces without a native 3D preview.

## Colourways and collectibles

- Midnight leather uses navy/midnight blue, with no pink dominant colour.
- Sunset uses muted copper/orange with a restrained rose accent. Rose/Magenta
  leather is pastel rather than fluorescent.
- Snow Leopard adds **Coloured Dark Panels**, keeping the light printed leather,
  and an explicitly named **Inverted Panels** pair. These affect available
  material masks, not separately painted spots inside the printed texture.
- Amphibious and Spruce DDPAT no longer receive the broad neutral-panel rewrite,
  preserving their pattern contrast. Existing paint-kit IDs remain intact.
- At 10 completed local matches, earn a pin; at 50, a coin; at 100, a trophy.
  They are saved one-time grants, separate from stars and care-package choices.
  The GC uses collectibles present in the installed schema, skips already-owned
  definitions, and excludes service medals/licenses. These are local milestones,
  not official tournament results. A season badge is not yet awarded merely by
  displaying the Premier season-progress screen.

The glove-only preparation step reuses weapon materials. A workspace test against
copies of this installation took about 48 seconds, followed by a cache hit; the
previous release's heavy-cache migration was verified. Changed game assets,
configuration, damaged output or other material generators can still require a
full rebuild.

## Validation boundaries

Native core, save migration, one-time collectible payouts, pet ownership and UI
equipment transport are tested. Both veto captain orders and the glove palette
rules are tested. The server plugin compiles against the installed API. All five
modified native script contracts and their JavaScript syntax were checked against
build 25966348. No installed game files were changed during development.

Menu pet appearance, preview rendering, the visible veto and actual map launch
still require in-game testing after installation. The user has now confirmed
kills/headshots are tracking, so that tracking path was preserved.

## Permanent companion food hint

The native main-menu chick is now confirmed visible in the client. The stock
client still displayed a low-food hint despite the future food timestamp.
For saved, owned local companions only, the vanity hint clears its food-warning
classes. Other items keep the stock behavior. This UI adjustment does not add
a feeding requirement or change permanent ownership or match-driven growth.
Five menu tests passed, including stale-warning removal and preservation of
stock checks for an unknown pet; the exact installed resource patch also passed.
The disappearance of the warning still requires a live restart check.

## Native Premier interface

The previous local draft and match launch are now confirmed working in the
client. This update replaces the bespoke veto panel with the installed
`popup_premier_pick_ban` layout and styles: native map cards/screenshots,
phase bars, reflection panels, ban state and CT/T selection controls.
The local controller still performs the six bans and starts the remaining map
through the already confirmed listen-server path. It does not overwrite
MatchDraftAPI or require an online reservation. Unknown layout contracts
produce an error popup. No Valve layouts, styles, images or scripts ship
in the ZIP; the launcher reads the installed resources locally.

The official match-history spider graph and party chat are hidden because
there is no online draft reservation or history behind this local match.
The native layout still needs visual confirmation in the client.
Both captain-order tests now exercise actual native button bindings, six bans,
late-click rejection, side selection and the selected-map launch. The installed
layout bindings and patched mainmenu script syntax were also checked.

## Music, chat, viewmodel and shade update

- Store: all 102 installed music definitions are directly selectable, with
  96 schema-supported StatTrak versions (198 choices total). Existing coupons
  and prices stay intact; missing direct selections use our stable local
  coupon definitions. Capsule bundles remain available. Missing prices copy
  native regular/StatTrak music templates, not arbitrary real-money pricing.
- Stats > Settings: native client viewmodel FOV and X/Y/Z inputs, with numeric
  range validation. Apply before returning to the match. These are ordinary
  archived client settings; no animation or player-camera FOV changes. The
  installed client log already confirms the range hook: offsets at 250%, FOV
  40–90. Console commands remain usable.
- Bot chat: delayed authored reactions to kills, headshots, bomb events, rounds
  and match completion. Actual bot display names, only to the one local human;
  global and per-bot cooldowns and cancellation across map/round transitions.
  `css_bot_chat off|less|normal|more` saves the frequency. The Settings buttons
  send the same command while you are in a local bot match. No fake rankings,
  hidden-enemy callouts or online draft communication are synthesized.
- Skin shades: Light, Muted, Deep and Vivid choices extend colour families
  across classic gloves, knives, active fixed and family weapon recolours.
  Existing base kit names and IDs remain intact; new choices append IDs.
  Already-disabled Dead Hand recolours and unchanged official transfer skins
  stay outside the new offerings. Shade transforms retain native artwork,
  alpha, neutral trim, dark ink and relative tonal differences. Muted/light
  pinks coexist with stronger versions instead of forcing all pinks pastel.
- The declared pattern palette IDs preserve Amphibious outline ink. Only
  Snow Leopard (`slick_jaguar_white`) and Queen Jaguar (`slick_jaguar_yellow`)
  receive opposite spot ink: pale on a dark base, dark on a light base.

All 52 regression groups passed across the full run and affected-group reruns.
New tests cover catalogue completeness/idempotence, supported StatTrak prices,
shade/texture mask preservation, the two-glove spot scope and safe native
viewmodel inputs. The plugin compiled against the exact installed server API.
The actual native Store sheet and career resource were patched and validated
from read-only installed files. Native knife/glove generation was checked
against the installed schema; projected IDs remain within the native limit.
Live appearance, chatter and settings behavior still require client testing.

Install as usual with CS2 and helper closed. This cumulative ZIP also contains
the updated owned texture decoder and native Premier UI. First launch performs
a full skin-resource rebuild for the new shades; later launches reuse the cache.
No player saves or original Valve assets are included.

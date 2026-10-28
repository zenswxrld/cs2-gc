"""Prepare native resources while CS2 is closed, before Windows locks the VPKs."""
import argparse
import contextlib
from pathlib import Path
import traceback
import time
from gameplay_config import load
from native_tradeups import prepare as recipes
from rotate_armory import prepare as armory
from native_scoreboard import prepare as scoreboard
from native_store import prepare as store
from skip_container_confirm import prepare as confirmation
from native_item_sales import prepare as sales
from native_multi_sell import prepare as multi_sell
from native_endmatch import prepare as results
from native_offer_numbers import prepare as offers
from native_bot_names import prepare as bot_names
from skip_key_select import prepare as key_select
from native_endmatch_stock import prepare as stock_results
from native_care_packages import prepare as care_packages
from native_mainmenu import prepare as mainmenu
from music_store import prepare as music_store
from native_mission_launch import prepare as missions
from native_knife_reel import prepare as knife_reel
from native_missions import prepare as missions_schedule
from native_stats import prepare as stats_page
from combat_events import prepare as combat_tracking
from native_local_play import prepare as local_play
from chicken_cosmetics import prepare as chicken_cosmetics
from native_profile_pins import prepare as profile_pins
from glove_refresh import prepare as glove_palettes
from native_resources import ensure_first_game_path
from vpk_signatures import update as signatures
from preparation_cache import PreparationCache



def mount_finish_resources(directory, config):
    """Restore the owned material mount after schema writers, also on warm starts.

    First-run recipe preparation can rewrite gameinfo from a snapshot taken
    before finish generation mounted its pack. Keep this inexpensive final
    check outside the material/cache rebuild so an existing pack can be repaired.
    """
    import json
    import native_finishes
    from native_tradeups import read_text, atomic_write, mount_gameinfo
    directory = Path(directory).resolve()
    if not config.get('knife_finishes', 1):
        return 'disabled'
    game = directory.parent.parent
    folder = game / native_finishes.FOLDER
    manifest = folder / 'cs2_gc_finishes_manifest.json'
    if not manifest.is_file():
        raise ValueError('Generated finish manifest is missing; preparation is incomplete.')
    if json.loads(read_text(manifest)).get('owner') != native_finishes.OWNER:
        raise ValueError('Finish folder is not owned by CS2 GC; refusing to mount it.')
    if not (folder / 'pak01_dir.vpk').is_file():
        raise ValueError('Generated finish VPK is missing; preparation is incomplete.')
    info = game / 'csgo/gameinfo.gi'
    current = read_text(info)
    mounted = mount_gameinfo(current, True, native_finishes.FOLDER, native_finishes.COMMENT)
    if mounted == current:
        return 'installed: owned finish materials and collection icons'
    backup = info.with_name(info.name+'.'+native_finishes.FOLDER+'_backup')
    if not backup.exists():
        with backup.open('x',encoding='utf-8',newline='') as output:
            output.write(current)
    atomic_write(info,mounted)
    return 'restored: owned finish materials and collection icons'


def prepare(directory, force_rebuild=False):
    started = time.perf_counter()
    try:
        from settings_editor import create_settings
        create_settings(directory)  # all commented out: the parsed settings, and so the cache, are unchanged
    except OSError as error:
        print('Settings file not created: ' + str(error), flush=True)
    config = load(directory)
    cache = PreparationCache(directory, config)
    cached = not force_rebuild and cache.hit()
    if cached:
        print('Preparation cache: hit; reusing validated native packs, schema and collection materials.', flush=True)
    elif not force_rebuild and cache.heavy_hit():
        print('Preparation cache: schema and collection materials unchanged; re-running the UI patch steps only.', flush=True)
    else:
        print('Preparation cache: rebuild requested' if force_rebuild else 'Preparation cache: miss; ' + cache.reason, flush=True)
        step = time.perf_counter()
        print('Recipes/catalogue: ' + recipes(directory, bool(config['mixed_stattrak_tradeups']), config) +
              ' [%.2fs]' % (time.perf_counter() - step), flush=True)
    print('Finish resources: ' + mount_finish_resources(directory, config), flush=True)
    print('Chicken Cosmetics: ' + chicken_cosmetics(directory,config),flush=True)
    print('Music-kit Store: ' + music_store(directory,config),flush=True)
    print('Glove palettes: ' + glove_palettes(directory,config),flush=True)
    actions = [('Armory', armory), ('Scoreboard', scoreboard), ('Store', store),
                         ('Opening confirmation', confirmation), ('Item sales', sales), ('Multi-sell', multi_sell),
                         ('Match results', results), ('Terminal offers', offers), ('Key picker', key_select),
                         ('Stock XP/rating panels', stock_results), ('Main-menu promotion', mainmenu), ('Care packages', care_packages), ('Bot mission launch', missions), ('Black Market reel', knife_reel)]
    if not cached:
        for name, action in actions:
            step = time.perf_counter()
            print(name + ': ' + action(directory, config) + ' [%.2fs]' % (time.perf_counter()-step), flush=True)
    try: print('Missions: ' + missions_schedule(directory, config), flush=True)  # cheap; follows the calendar
    except (OSError, ValueError, KeyError) as error: print('Missions skipped (recorded missions stay): ' + str(error), flush=True)
    print('Combat event tracking: ' + combat_tracking(directory,config),flush=True)
    print('Local Premier and night maps: ' + local_play(directory,config),flush=True)
    print('Stats & achievements: ' + stats_page(directory, config),flush=True)
    print('Profile pins: ' + profile_pins(directory,config),flush=True)
    try: print('Bot names: ' + bot_names(directory, config, reshuffle=True), flush=True)
    except (OSError, ValueError, KeyError) as error: print('Bot names skipped (bots keep their normal names): ' + str(error), flush=True)
    print(ensure_first_game_path(directory), flush=True)
    print(signatures(directory), flush=True)
    try:
        from finish_storage import compact
        print('Finish storage: ' + compact(directory), flush=True)  # one copy on disk: the pack CS2 reads
    except (OSError, ValueError) as error:
        print('Finish storage: left unchanged (' + str(error) + ')', flush=True)
    cache.save()
    print('Preparation time: %.2fs (%s).' % (time.perf_counter()-started, 'cache hit' if cached else 'rebuilt'), flush=True)
    print('Native preparation complete; safe to start CS2.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proxy-dir', type=Path, required=True)
    parser.add_argument('--rebuild', action='store_true', help='Ignore the preparation cache and regenerate all owned packs')
    args = parser.parse_args()
    with (args.proxy_dir / 'cs2_gc_prepare.log').open('w', encoding='utf-8', buffering=1) as output:
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            try: prepare(args.proxy_dir, force_rebuild=args.rebuild)
            except Exception:
                traceback.print_exc()
                return 1
    return 0

if __name__ == '__main__': raise SystemExit(main())

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
from native_mission_launch import prepare as missions
from native_knife_reel import prepare as knife_reel
from native_missions import prepare as missions_schedule
from native_resources import ensure_first_game_path
from vpk_signatures import update as signatures
from preparation_cache import PreparationCache


def prepare(directory, force_rebuild=False):
    started = time.perf_counter()
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
    try: print('Bot names: ' + bot_names(directory, config, reshuffle=True), flush=True)
    except (OSError, ValueError, KeyError) as error: print('Bot names skipped (bots keep their normal names): ' + str(error), flush=True)
    print(ensure_first_game_path(directory), flush=True)
    print(signatures(directory), flush=True)
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

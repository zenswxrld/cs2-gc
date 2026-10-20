"""Prepare native resources while CS2 is closed, before Windows locks the VPKs."""
import argparse
import contextlib
from pathlib import Path
import traceback
from gameplay_config import load
from native_tradeups import prepare as recipes
from rotate_armory import prepare as armory
from native_scoreboard import prepare as scoreboard
from native_store import prepare as store
from skip_container_confirm import prepare as confirmation
from native_item_sales import prepare as sales
from native_endmatch import prepare as results
from native_offer_numbers import prepare as offers
from native_bot_names import prepare as bot_names
from native_resources import ensure_first_game_path
from vpk_signatures import update as signatures


def prepare(directory):
    config = load(directory)
    print('Recipes/catalogue: ' + recipes(directory, bool(config['mixed_stattrak_tradeups']), config), flush=True)
    for name, action in [('Armory', armory), ('Scoreboard', scoreboard), ('Store', store),
                         ('Opening confirmation', confirmation), ('Item sales', sales),
                         ('Match results', results), ('Terminal offers', offers)]:
        print(name + ': ' + action(directory, config), flush=True)
    try: print('Bot names: ' + bot_names(directory, config, reshuffle=True), flush=True)
    except (OSError, ValueError, KeyError) as error: print('Bot names skipped (bots keep their normal names): ' + str(error), flush=True)
    print(ensure_first_game_path(directory), flush=True)
    print(signatures(directory), flush=True)
    print('Native preparation complete; safe to start CS2.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proxy-dir', type=Path, required=True)
    args = parser.parse_args()
    with (args.proxy_dir / 'cs2_gc_prepare.log').open('w', encoding='utf-8', buffering=1) as output:
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            try: prepare(args.proxy_dir)
            except Exception:
                traceback.print_exc()
                return 1
    return 0

if __name__ == '__main__': raise SystemExit(main())

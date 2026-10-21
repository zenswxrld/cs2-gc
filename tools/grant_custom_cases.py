"""Add Gauntlet (and optionally Black Market / Dead Hand Test) Cases to the local inventory for testing, while CS2 is closed.

Reads the case definitions from the generated native items_game override (game/cs2_gc_native), so it only works
after CS2 has been prepared once with glove_finishes / knife_finishes on. Preserves stars, passes, profile and
existing items, and backs up the inventory first.
"""
import argparse
from pathlib import Path

from grant_test_items import add_items
from inventory_item import as_dict, collect, parse

CASES = {'gauntlet': 'crate_cs2gc_gauntlet', 'black_market': 'crate_cs2gc_black_market',
         'dead_hand_test': 'crate_cs2gc_dead_hand_test', 'custom_skins_test': 'crate_cs2gc_custom_skins_test'}


def case_items(schema_text, counts):
    items = collect(parse(schema_text)).get('items', {})
    by_name = {as_dict(node).get('name'): key for key, node in items.items() if isinstance(node, list)}
    result = []
    for name, count in counts.items():
        if count and name not in by_name:
            raise ValueError(name + ' is not in the generated schema; start CS2 once with it enabled')
        result += [[('def_index', by_name[name]), ('paint_kit', '0'), ('wear', '0'), ('seed', '0'),
                    ('stattrak', '0'), ('rarity', '0')] for _ in range(count)]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schema', type=Path, default=Path('../../cs2_gc_native/scripts/items/items_game.txt'))
    parser.add_argument('--inventory', type=Path, default=Path('cs2_gc_inventory.txt'))
    parser.add_argument('--gauntlet', type=int, default=20)
    parser.add_argument('--black-market', type=int, default=0)
    parser.add_argument('--dead-hand-test', type=int, default=0)
    parser.add_argument('--custom-skins-test', type=int, default=0)
    args = parser.parse_args()
    if not all(0 <= n <= 500 for n in (args.gauntlet, args.black_market, args.dead_hand_test, args.custom_skins_test)):
        parser.exit(1, 'Counts must be between 0 and 500\n')
    try:
        additions = case_items(args.schema.read_text(encoding='utf-8-sig'),
                               {CASES['gauntlet']: args.gauntlet, CASES['black_market']: args.black_market,
                                CASES['dead_hand_test']: args.dead_hand_test,
                                CASES['custom_skins_test']: args.custom_skins_test})
        count, backup = add_items(args.inventory, additions)
        print(f'Added {count} cases ({args.gauntlet} Gauntlet, {args.black_market} Black Market, '
              f'{args.dead_hand_test} Dead Hand Test, {args.custom_skins_test} Custom Skins Test). '
              'Stars, passes and rank preserved.' if count else
              'Inventory checked: care-package copies of next_id now match (repairs a 26c grant).')
        if backup: print(f'Backup: {backup.name}')
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f'Could not add cases: {error}\n')


if __name__ == '__main__':
    main()

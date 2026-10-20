"""Submit a local trade-up even when CS2's native recipe menu filters mixed StatTrak variants."""
import argparse
from pathlib import Path
import time
import uuid
from inventory_item import parse, as_dict, collect
from gsi_rewards import atomic_text

BASE = 1000000000000


def submit(directory, ids, token=None):
    if len(ids) not in (5, 10) or len(set(ids)) != len(ids) or any(type(i) is not int or not 0 < i < BASE for i in ids):
        raise ValueError('Use five or ten distinct inventory IDs from the list')
    pending = directory / 'cs2_gc_tradeup_request.txt'
    if pending.exists() or (directory / 'cs2_gc_tradeup_processing.txt').exists():
        raise ValueError('A contract is already pending. Check its result before submitting another.')
    token = token or uuid.uuid4().hex
    if len(token) != 32 or any(c not in '0123456789abcdef' for c in token):
        raise ValueError('Invalid request token')
    result = directory / 'cs2_gc_tradeup_result.txt'
    result.unlink(missing_ok=True)
    atomic_text(pending, token + ' ' + ' '.join(str(BASE + i) for i in ids) + '\n')
    return token


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proxy-dir', type=Path, default=Path.cwd())
    args = parser.parse_args()
    directory = args.proxy_dir
    inventory = as_dict(as_dict(parse((directory / 'cs2_gc_inventory.txt').read_text(encoding='utf-8-sig')))['inventory'])
    schema = collect(parse((directory / 'items_game.txt').read_text(encoding='utf-8-sig')))
    rarity = int(input('Input rarity (1 Consumer, 2 Industrial, 3 Mil-Spec, 4 Restricted, 5 Classified, 6 Covert): '))
    if not 1 <= rarity <= 6:
        raise ValueError('Choose rarity 1 through 6')
    candidates = {}
    for item_id, data in inventory['items']:
        item = as_dict(data)
        if int(item.get('rarity', 0)) != rarity or int(item.get('paint_kit', 0)) == 0 or item.get('stored_in'):
            continue
        candidates[int(item_id)] = item
        weapon = as_dict(schema['items'].get(item['def_index'], [])).get('name', item['def_index'])
        finish = as_dict(schema['paint_kits'].get(item['paint_kit'], [])).get('name', item['paint_kit'])
        print(f"ID {item_id:>5} | {'StatTrak' if item['stattrak'] == '1' else 'Normal':8} | {weapon} / {finish} | wear {item['wear']}")
    required = 5 if rarity == 6 else 10
    ids = [int(v) for v in input(f'Enter {required} IDs separated by spaces (or close to cancel): ').replace(',', ' ').split()]
    if len(ids) != required or any(i not in candidates for i in ids) or len(set(ids)) != required:
        raise ValueError('Select the required number of distinct IDs from this list')
    count = sum(candidates[i]['stattrak'] == '1' for i in ids)
    print(f'StatTrak chance: {100 * count / required:g}%. Selected inputs will be consumed. Gloves cannot be StatTrak.')
    if input('Submit this contract to the running local game? [y/N] ').strip().lower() != 'y':
        return
    token = submit(directory, ids)
    print('Submitted. Keep CS2 running in local -insecure mode; no reward helper is needed for this contract.')
    for _ in range(90):
        result = directory / 'cs2_gc_tradeup_result.txt'
        if result.exists():
            lines = result.read_text().splitlines()
            if lines and lines[0] == token and len(lines) > 1:
                print('Contract ' + lines[1] + '. Check the game inventory and log for the result.')
                return
        time.sleep(.5)
    print('Still pending. Do not submit another contract; return to the running game and check the result/log.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError) as error:
        print(f'Could not submit contract: {error}')
        raise SystemExit(1)

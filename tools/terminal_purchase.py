"""Accept an already revealed local terminal offer if native checkout does not submit it."""
import argparse
from pathlib import Path
import time
import uuid
from inventory_item import parse, as_dict
from gsi_rewards import atomic_text

BASE = 1000000000000


def submit(directory, terminal_id, token=None):
    if type(terminal_id) is not int or not 0 < terminal_id < BASE:
        raise ValueError('Invalid local terminal ID')
    pending = directory / 'cs2_gc_terminal_request.txt'
    if pending.exists() or (directory / 'cs2_gc_terminal_processing.txt').exists():
        raise ValueError('A terminal purchase is already pending; check its result first')
    token = token or uuid.uuid4().hex
    if len(token) != 32 or any(c not in '0123456789abcdef' for c in token):
        raise ValueError('Invalid request token')
    (directory / 'cs2_gc_terminal_result.txt').unlink(missing_ok=True)
    # Same strict token/ID-list envelope as the trade-up transport, with one repeated terminal ID.
    atomic_text(pending, token + ' ' + ' '.join([str(BASE + terminal_id)] * 5) + '\n')
    return token


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proxy-dir', type=Path, default=Path.cwd())
    args = parser.parse_args()
    inventory = as_dict(as_dict(parse((args.proxy_dir / 'cs2_gc_inventory.txt').read_text(encoding='utf-8-sig')))['inventory'])
    items = {int(key): as_dict(value) for key, value in inventory['items']}
    candidates = {}
    for item_id, item in items.items():
        parent = int(item.get('stored_in', 0))
        terminal = items.get(parent, {})
        if 'purchase_price' in item and int(terminal.get('expiration', 0)) > time.time():
            candidates[parent] = item
            print(f"Terminal ID {parent}: displayed offer definition {item['def_index']}, finish {item['paint_kit']}, rarity {item['rarity']}")
    if not candidates:
        print('No active offer found. Reveal an offer inside a terminal first.'); return
    chosen = int(input('Enter the terminal ID whose displayed offer you want to keep: '))
    if chosen not in candidates: raise ValueError('Choose a listed terminal ID')
    if input('Keep that offer and consume this terminal? Free/local only. [y/N] ').strip().lower() != 'y': return
    token = submit(args.proxy_dir, chosen)
    for _ in range(90):
        result = args.proxy_dir / 'cs2_gc_terminal_result.txt'
        if result.exists():
            lines = result.read_text().splitlines()
            if len(lines) > 1 and lines[0] == token:
                print('Purchase ' + lines[1] + '. Close the terminal screen and check your inventory.'); return
        time.sleep(.5)
    print('Still pending. Keep the local game running; do not resubmit. Check the result and log.')


if __name__ == '__main__':
    try: main()
    except (OSError, ValueError, KeyError) as error:
        print(f'Could not accept offer: {error}')
        raise SystemExit(1)

"""Add varied trade-up test items to a local inventory while CS2 is closed.

Preserves stars, passes, profile and existing items. Backs up before atomic replacement.
Only definitions/finishes found in the supplied items_game.txt are granted.
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import random
import re
import shutil
from inventory_item import parse, collect, as_dict, find_entry, TOKEN
from gsi_rewards import atomic_text


def encode(nodes, depth=0):
    lines = []
    indent = '\t' * depth
    def quote(value):
        return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'
    for key, value in nodes:
        if isinstance(value, list):
            lines += [indent + quote(key), indent + '{', encode(value, depth + 1), indent + '}']
        else:
            lines.append(indent + quote(key) + '\t' + quote(value))
    return '\n'.join(lines)


def test_items(sections, gold_text):
    gold_cases = {key for key, _ in as_dict(parse(gold_text)).get('gold_pools', [])}
    case_sets = set()
    for key, node in sections['items'].items():
        values = as_dict(node)
        if key in gold_cases and 'volatile' not in values.get('prefab', ''):
            tags = as_dict(values.get('tags', []))
            item_set = as_dict(tags.get('ItemSet', []))
            if item_set.get('tag_value'):
                case_sets.add(item_set['tag_value'])
    collections = []
    for name, node in sections.get('item_sets', {}).items():
        entries = as_dict(node).get('items', [])
        tiers = {}
        for loot, _ in entries:
            match = re.fullmatch(r'\[([^]]+)\](.+)', loot)
            if not match:
                continue
            try:
                entry = find_entry(sections, match[2], match[1])
            except ValueError:
                continue
            tiers.setdefault(entry['rarity'], []).append(entry)
        collections.append((name, tiers))
    result = []
    random_source = random.Random(25966348)
    for tracked in (False, True):
        for rarity in range(3 if tracked else 1, 7):
            candidates = [(name, tiers) for name, tiers in collections if rarity in tiers
                          and ((rarity < 6 and rarity + 1 in tiers) or (rarity == 6 and name in case_sets))
                          and (not tracked or name in case_sets)]
            if not candidates:
                raise ValueError(f'No valid trade-up test collection for rarity {rarity}, StatTrak={tracked}')
            # One collection per rarity/variant keeps each group a valid contract while varying finishes.
            name, tiers = candidates[0]
            count = 10 if rarity == 6 else 20
            for i in range(count):
                entry = tiers[rarity][i % len(tiers[rarity])]
                wear = entry['wear_min'] + (entry['wear_max'] - entry['wear_min']) * random_source.random()
                result.append([('def_index', str(entry['def_index'])), ('paint_kit', str(entry['paint_kit'])),
                               ('wear', f'{wear:.8f}'), ('seed', str(random_source.randint(1, 1000))),
                               ('stattrak', str(int(tracked))), ('rarity', str(rarity))])
    # Real current-build item names: missing entries are skipped for older schemas.
    extras = {'crate_community_35': 8, 'crate_sticker_pack_csgo10_capsule': 8,
              'crate_sticker_pack_katowice2019_legends': 4, 'crate_patch_pack01': 4,
              'crate_xray_p250': 4, 'XpShopTicket1': 5, 'crate_community_36': 4, 'crate_community_37': 4}
    for definition, node in sections['items'].items():
        count = extras.get(as_dict(node).get('name'), 0)
        for _ in range(count):
            result.append([('def_index', definition), ('paint_kit', '0'), ('wear', '0'), ('seed', '0'),
                           ('stattrak', '0'), ('rarity', '0')])
        if count and as_dict(node).get('name') == 'crate_community_35':
            for key, _ in as_dict(node).get('associated_items', []):
                if key in sections['items']:
                    for _ in range(count):
                        result.append([('def_index', key), ('paint_kit', '0'), ('wear', '0'), ('seed', '0'),
                                       ('stattrak', '0'), ('rarity', '0')])
    return result


def grant(schema_path, inventory_path, gold_path):
    sections = collect(parse(schema_path.read_text(encoding='utf-8-sig')))
    return add_items(inventory_path, test_items(sections, gold_path.read_text(encoding='utf-8')))


def add_items(inventory_path, additions):
    """Append item field lists to the inventory; returns (count, backup path or None)."""
    existing = inventory_path.read_text(encoding='utf-8-sig') if inventory_path.exists() else '"inventory" { "next_id" "1" "items" { } }'
    nodes = parse(existing)
    root = as_dict(nodes).get('inventory')
    if not isinstance(root, list):
        raise ValueError('Invalid inventory root; nothing changed')
    values = as_dict(root)
    items = values.get('items')
    if not isinstance(items, list) or len(values) != len(root):
        raise ValueError('Invalid or duplicate inventory fields; nothing changed')
    ids = [int(key) for key, _ in items]
    if len(set(ids)) != len(ids) or any(i <= 0 for i in ids):
        raise ValueError('Invalid existing inventory IDs; nothing changed')
    next_id = int(values['next_id'])
    if next_id <= max(ids, default=0):
        raise ValueError('Invalid next_id; nothing changed')
    for item in additions:
        items.append((str(next_id), item))
        next_id += 1
    root[:] = [(key, str(next_id) if key == 'next_id' else value) for key, value in root]
    # Make a new, never-overwritten backup. Do not reset progression, passes or currency.
    backup = None
    if inventory_path.exists():
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
        backup = inventory_path.with_name(inventory_path.name + '.pre-test-items-' + stamp + '.bak')
        shutil.copy2(inventory_path, backup)
    # Patch only next_id and insert at the items block's closing brace. Existing text stays byte-for-byte.
    # Care-package previews are saved as small inventories that must repeat the profile's next_id exactly
    # (the GC refuses the whole file otherwise), so every copy is updated together.
    stack, pending, close, next_spans = [], None, None, []
    for match in TOKEN.finditer(existing):
        string, brace = match.group(1), match.group(2)
        if string is None and not brace:
            continue
        if brace == '{':
            stack.append(pending)
            pending = None
        elif brace == '}':
            if stack == ['inventory', 'items']:
                close = match.start()
            stack.pop()
        elif pending is None:
            pending = string
        else:
            if pending == 'next_id' and (stack == ['inventory'] or
                                         (len(stack) == 3 and stack[:2] == ['inventory', 'care_packages'])):
                next_spans.append(match.span())
            pending = None
    if close is None or not next_spans or stack != []:
        raise ValueError('Could not locate inventory fields; nothing changed')
    first_id = next_id - len(additions)
    inserted = '\n' + encode([(str(first_id + i), item) for i, item in enumerate(additions)], 2) + '\n\t'
    edits = [(close, close, inserted)] + [(start, end, '"' + str(next_id) + '"') for start, end in next_spans]
    updated = existing
    for start, end, text in sorted(edits, reverse=True):
        updated = updated[:start] + text + updated[end:]
    atomic_text(inventory_path, updated)
    return len(additions), backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schema', type=Path, default=Path('items_game.txt'))
    parser.add_argument('--inventory', type=Path, default=Path('cs2_gc_inventory.txt'))
    parser.add_argument('--gold-pools', type=Path, default=Path('gold_pools.txt'))
    args = parser.parse_args()
    try:
        count, backup = grant(args.schema, args.inventory, args.gold_pools)
        print(f'Added {count} local test items. Existing stars, passes and rank preserved.')
        if backup:
            print(f'Backup: {backup.name}')
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f'Could not grant test items: {error}\n')


if __name__ == '__main__':
    main()

"""Read installed CS2 assets and audit generated collections without installing them."""
import argparse
import json
from pathlib import Path

import native_finishes as finishes
import native_patterns
import native_skins
import next_collection_lineups
from inventory_item import collect, parse


def audit(game, output, full=False):
    source = finishes.Source(vpk=Path(game) / 'csgo/pak01_dir.vpk')
    schema = source.read('scripts/items/items_game.txt').decode('utf-8-sig')
    _, _, kits, _ = finishes.schema_info(schema, '')
    titles = finishes.titles_from(source.read('resource/csgo_english.txt').decode('utf-8-sig'), kits)
    report, families = {}, {}
    if full:
        result = native_skins.custom_cases(schema, kits, titles, finishes.kit_path,
                                          source, families, set(), report)
    else:
        added, pattern_titles, pattern_files, _ = native_patterns.plan(source, kits, titles)
        result = next_collection_lineups.build(schema, dict(kits, **added), dict(titles, **pattern_titles),
            finishes.kit_path, native_patterns.GeneratedSource(source, pattern_files), families, set(), report)
    definitions, files, lists, names, items, icons = result
    lookup = {n: (title, values) for n, title, values in definitions}
    if len(lookup) != len(definitions):
        raise ValueError('Duplicate paint kit definitions')
    rows = report.get('next_12', {})
    if len(rows) != 12 or any(r['status'] != 'ready' for r in rows.values()):
        raise ValueError('Incomplete new collections: ' + json.dumps(rows))
    parsed = collect(parse('"items_game" { "client_loot_lists" { ' + lists + ' } }'))['client_loot_lists']
    for icon, row in rows.items():
        name = 'set_cs2gc_case_' + icon
        counts = [len(parsed[name + '_' + tier]) for tier in next_collection_lineups.RARITIES]
        if counts != [1, 2, 3, 4, 6]:
            raise ValueError('Incorrect rarity layout in ' + name)
        if len(row['skins']) != 16 or sum(s['family'] for s in row['skins']) != 2:
            raise ValueError('Incorrect visible/family skin count in ' + name)
        for skin in row['skins']:
            if lookup[skin['kit']][0] != skin['title']:
                raise ValueError('Authored finish title was overwritten: ' + skin['kit'])
            for kit in [skin['kit']] + skin['variants']:
                path = lookup[kit][1]['composite_material_path']
                if path + '_c' not in files:
                    raise ValueError('Missing generated material: ' + path)
    report['verification'] = dict(new_collections=12, visible_new_skins=192, fixed_new_skins=168,
        family_new_skins=24, published_collections=len(names), published_entries=len(items),
        paint_kit_definitions=len(definitions), material_files=len(files),
        game_files_modified=False, live_rendering='not tested')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'collections-audit.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    lines = ['# New 12 collection lineups', '',
        'Validated against installed material data; appearance still needs in-game review.', '']
    for icon, row in rows.items():
        lines += ['## ' + icon.replace('_', ' ').title(), '',
            '| Rarity | Weapon | Finish | Mode | Selected donor | Colours |', '|---|---|---|---|---|---|']
        for s in row['skins']:
            lines.append('| %s | %s | %s | %s | %s | %s |' % (s['rarity'], s['weapon'].removeprefix('weapon_'),
                s['title'], 'family' if s['family'] else 'fixed', s['donor'], ', '.join(s['themes'])))
        lines.append('')
    (output / 'collection-lineups.md').write_text('\n'.join(lines), encoding='utf-8')
    return report['verification']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', required=True, type=Path, help='CS2 game folder containing csgo/pak01_dir.vpk')
    parser.add_argument('--output', required=True, type=Path, help='Audit report directory outside the game installation')
    parser.add_argument('--full', action='store_true', help='Audit the combined recovered and new collection generator')
    args = parser.parse_args()
    game, output = args.game.resolve(), args.output.resolve()
    if output == game or game in output.parents:
        parser.error('--output must be outside the game installation')
    print(json.dumps(audit(game, output, args.full), indent=2))


if __name__ == '__main__':
    main()

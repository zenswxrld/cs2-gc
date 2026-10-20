"""Build supplementary rare pools from ByMykel/CSGO-API's published crates and skins datasets.

Input JSON stays outside the repository. The DLL validates every output pair against the user's schema.
"""
import argparse
import json
from pathlib import Path


def render(crates, skins):
    by_id = {skin['id']: skin for skin in skins}
    lines = ['// Rare pool membership: ByMykel/CSGO-API, commit 70dcba880a09901c3cf17249756370deb276038a',
             '// https://github.com/ByMykel/CSGO-API (MIT). Definitions and finishes validated at load.',
             '"gold_pools"', '{']
    for crate in crates:
        pairs = set()
        for rare in crate.get('contains_rare', []):
            skin = by_id[rare['id']]
            weapon = int(skin['weapon']['weapon_id'])
            paint = int(skin['paint_index'] or 0)
            pairs.add((weapon, paint))
        if pairs:
            lines += [f'    "{int(crate["def_index"])}"', '    {']
            lines += [f'        "{weapon}:{paint}" "1"' for weapon, paint in sorted(pairs)]
            lines += ['    }']
    return '\n'.join(lines + ['}', ''])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--crates', type=Path, required=True)
    parser.add_argument('--skins', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.write_text(render(json.loads(args.crates.read_text(encoding='utf-8')),
                               json.loads(args.skins.read_text(encoding='utf-8'))), encoding='utf-8')

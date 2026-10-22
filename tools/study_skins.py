"""Read-only study of every gun finish, for remaking the custom collections.

Usage (from game\\bin\\win64, CS2 closed or open):  python study_skins.py
Writes cs2_gc_skin_study.zip next to this script. Nothing in the game is modified.

The zip holds, as text only (no textures, no game binaries):
- official_finishes.json: every paint kit used on a gun in the installed schema: its schema values, the weapons
  it ships on, and the parameters (shader, colours, floats, texture slot names) of its composite material and
  every material that composite names.
- custom_finishes.json: the same for the generated custom kits currently in the cs2_gc override, read from the
  generated cs2_gc_finishes VPK, so finishes that change nothing compared with their donor can be found.
- custom_lists.txt: the generated custom paint kits and loot lists (only the cs2gc parts of the override).
- the helper's own logs/reports and the care-package script, for the claim problem.
"""
from pathlib import Path
import json
import re
import sys
import zipfile

import kv3
from native_finishes import Source, kit_path

REPORTS = ('cs2_gc_log.txt', 'cs2_gc_prepare.log', 'cs2_gc_weapon_palettes.json', 'cs2_gc_finish_ids.json',
           'cs2_gc_skin_families.txt', 'cs2_gc_collection_previews.json', 'cs2_gc_inventory.txt',
           'cs2_gc_gameplay.cfg')
CUSTOM_PREFIXES = ('rk_', 'cg', 'cw', 'rc_', 'rwc_', 'nc3', 'ccf_', 'ccv_', 'cwf_')
SCRIPTS = ('panorama/scripts/rankup_redemption_store.vts_c', 'panorama/scripts/rankup_redemption_store.vjs_c')
MAX_STRING = 300


def plain(node):
    """KV3 node -> JSON-able value. Binary blobs become their length."""
    value = node.value
    if isinstance(value, list):
        if value and all(isinstance(item, tuple) for item in value):
            result = {}
            for key, child in value:
                key = key if key not in result else '%s#%d' % (key, len(result))
                result[key] = plain(child)
            return result
        return [plain(child) for child in value]
    if isinstance(value, (bytes, bytearray)): return {'bytes': len(value)}
    if isinstance(value, str) and len(value) > MAX_STRING: return value[:MAX_STRING] + '...'
    return value


def document(source, path):
    data = source.read(path + '_c')
    if data is None: return None
    try:
        _, blocks = kv3.read_resource(data)
        _, root = kv3.read_kv3(dict(blocks)['DATA'])
    except (ValueError, KeyError, IndexError) as error:
        return {'error': str(error)}
    return root


def material_names(node, found):
    if isinstance(node.value, list):
        for child in node.value:
            material_names(child[1] if isinstance(child, tuple) else child, found)
    elif isinstance(node.value, str) and node.value.lower().endswith('.vmat'):
        found.add(node.value)
    return found


def study(source, kits, weapons):
    result = {}
    for name, (kit_id, values) in sorted(kits.items()):
        path = kit_path(name, values)
        row = {'id': kit_id, 'values': values, 'weapons': sorted(weapons.get(name, ())), 'composite': path}
        root = document(source, path)
        if root is None: row['missing'] = True
        elif isinstance(root, dict): row.update(root)
        else:
            row['compmat'] = plain(root)
            row['materials'] = {}
            for material in sorted(material_names(root, set())):
                found = document(source, material)
                row['materials'][material] = None if found is None else found if isinstance(found, dict) else plain(found)
        result[name] = row
    return result


def paint_kits(text):
    from inventory_item import as_dict, collect, parse
    sections = collect(parse(text))
    kits = {}
    for key, value in sections.get('paint_kits', {}).items():
        if isinstance(value, list):
            values = {k: v for k, v in as_dict(value).items() if isinstance(v, str)}
            if 'name' in values: kits[values['name']] = (key, values)
    return kits


def main():
    here = Path(__file__).resolve().parent
    game = here.parent.parent
    pak = game / 'csgo' / 'pak01_dir.vpk'
    if not pak.is_file():
        print('Run this from game\\bin\\win64 (csgo/pak01_dir.vpk not found at %s)' % pak); return 1
    official = Source(vpk=pak)
    schema = official.read('scripts/items/items_game.txt')
    text = schema.decode('utf-8-sig') if schema else (here / 'items_game.txt').read_text(encoding='utf-8-sig')
    weapons = {}
    for kit, weapon in re.findall(r'"\[([^\]]+)\](weapon_[a-z0-9_]+)"', text):
        if 'knife' not in weapon and weapon != 'weapon_bayonet': weapons.setdefault(kit, set()).add(weapon)
    kits = {name: row for name, row in paint_kits(text).items() if name in weapons}
    print('Studying %d gun finishes...' % len(kits), flush=True)
    out = {'official_finishes.json': json.dumps(study(official, kits, weapons), indent=0, sort_keys=True)}

    override = game / 'cs2_gc_native' / 'pak01_dir.vpk'
    finishes = game / 'cs2_gc_finishes' / 'pak01_dir.vpk'
    if override.is_file() and finishes.is_file():
        generated = Source(vpk=override).read('scripts/items/items_game.txt')
        if generated:
            generated = generated.decode('utf-8-sig')
            custom = {n: r for n, r in paint_kits(generated).items() if n.startswith(CUSTOM_PREFIXES) and n not in kits}
            print('Studying %d generated custom finishes...' % len(custom), flush=True)
            class Both:  # generated materials first, official templates/textures as fallback
                def read(self, path, a=Source(vpk=finishes)):
                    found = a.read(path)
                    return found if found is not None else official.read(path)
            out['custom_finishes.json'] = json.dumps(study(Both(), custom, {}), indent=0, sort_keys=True)
            out['custom_lists.txt'] = '\n'.join(re.findall(
                r'\n\t\t"(?:set_cs2gc|crate_cs2gc)[^"]*"\n\t\t\{[^{}]*\}', generated))
    else:
        print('No generated cs2_gc override found (custom finishes skipped).')
    for name in REPORTS:
        path = here / name
        if path.is_file(): out['reports/' + name] = path.read_bytes()
    from native_resources import script_blocks
    for path in SCRIPTS:
        data = official.read(path)
        if data:
            try:
                js = next(d for k, d in script_blocks(data) if k == b'DATA').rstrip(b'\0')
                out['scripts/' + Path(path).stem + '.js'] = js
            except ValueError as error:
                print(path, error)
    target = here / 'cs2_gc_skin_study.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, content in out.items():
            archive.writestr(name, content)
    print('Wrote', target, '- send this file.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

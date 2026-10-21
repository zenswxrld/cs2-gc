"""Knife recolours and the knife-only Black Market Case (OfflineCS style), built from the user's own CS2 files.

A CS2 finish is a paint_kits entry whose composite material (weapons/paints/.../<kit>.vcompmat) points at one
material (materials/.../vmats/<kit>.vmat) holding the pattern's four colours g_vColor0..g_vColor3. A recolour is a
copy of that pair with new colours under a new name, plus a paint_kits entry naming the copy. Nothing in the
game's own files changes: the copies, the case icon and the added finish names live in the cs2_gc_finishes VPK,
and the paint kits / case go into the generated native items_game override (cs2_gc_native) that the client and
the local GC both load. Turn it off with knife_finishes = 0.
"""
import colorsys
import hashlib
import json
from pathlib import Path
import random
import re
import struct
import zlib

import kv3
from inventory_item import as_dict, collect, parse

FOLDER = 'cs2_gc_finishes'
COMMENT = 'cs2_gc knife finishes'
OWNER = 'cs2-gc-knife-finishes-v1'
CASE_NAME = 'crate_cs2gc_black_market'
CASE_TITLE = 'Black Market Case'
CASE_DESCRIPTION = 'Knives only. Every knife in every finish, plus finishes and colours no knife ever shipped with.'
CASE_IMAGE = 'econ/weapon_cases/' + CASE_NAME
CASE_BASE = '4003'  # Operation Bravo Case: its model and key
FIRST_KIT_ID = 30000
FIRST_CASE_ID = 4950
VMAT_DIR = 'materials/models/weapons/customization/paints/vmats/cs2_gc/'
COMPMAT_DIR = 'weapons/paints/cs2_gc/'
ICON = Path(__file__).resolve().parent / 'cs2_gc_black_market_case.png'

# OfflineCS make_recolors.py themes: (hue, saturation, spread) keep each colour's brightness.
THEMES = {
    'Crimson': (355, 0.78, 14), 'Ember': (18, 0.82, 14), 'Amber': (40, 0.80, 12), 'Lime': (82, 0.70, 18),
    'Emerald': (148, 0.68, 16), 'Teal': (178, 0.70, 14), 'Azure': (208, 0.74, 16), 'Cobalt': (226, 0.78, 12),
    'Violet': (272, 0.62, 18), 'Magenta': (316, 0.66, 16), 'Rose': (338, 0.60, 12), 'Ash': (210, 0.10, 0),
}
DUO_THEMES = {
    'Aurora': (148, 272, 0.70), 'Sunset': (18, 316, 0.78), 'Glacier': (190, 214, 0.55),
    'Toxic': (82, 272, 0.72), 'Inferno': (355, 40, 0.80), 'Midnight': (226, 316, 0.74),
}
# Official knife finishes made of colours, named so the recolours of different phases stay distinct.
KNIFE_BASES = {
    'am_blackpearl_marbleized': 'Pearl Marble', 'am_doppler_phase1': 'Doppler', 'am_doppler_phase2': 'Doppler Swirl',
    'am_doppler_phase3': 'Doppler Flow', 'am_doppler_phase4': 'Doppler Drift', 'am_marble_fade': 'Marble Fade',
    'am_ruby_marbleized': 'Marbleized', 'am_sapphire_marbleized': 'Marbled Glass', 'am_emerald_marbleized': 'Gamma Marble',
    'am_gamma_doppler_phase1': 'Gamma Doppler', 'am_gamma_doppler_phase2': 'Gamma Swirl',
    'am_gamma_doppler_phase3': 'Gamma Flow', 'am_gamma_doppler_phase4': 'Gamma Drift', 'am_zebra': 'Slaughter',
    'an_tiger_orange': 'Tiger Tooth', 'aa_fade': 'Fade', 'aq_blued': 'Blued Steel', 'aq_damascus': 'Damascus',
    'aq_forced': 'Stained', 'aq_oiled': 'Hardened', 'aq_steel_knife': 'Steel', 'hy_webs': 'Web',
    'am_marked_up': 'Freehand', 'hy_ocean_knife': 'Bright Water', 'so_purple': 'Ultraviolet',
}
# Finishes never sold on knives that the user asked for by name; the abstract anodized ones are added below.
EXTRA_FINISHES = ('am_aqua_flecks', 'am_gold_brick', 'am_m4a1s_bluesmoke')
EXTRA_THEMES = 6  # recolours per extra finish (knife bases get every theme)
RECOLOUR_KNIVES = 4  # knives each knife-base recolour appears on in the case
EXTRA_RECOLOUR_KNIVES = 4
WEAPON_WORDS = ('ak47', 'ak_', 'awp', 'm4a1', 'm4a4', 'deagle', 'scar20', 'g3sg1', 'p250', 'p90', 'mp9', 'mp7', 'mac10',
                'ump', 'famas', 'galil', 'aug_', 'sg553', 'sg556', 'ssg08', 'nova', 'xm1014', 'mag7', 'sawedoff', 'negev',
                'm249', 'glock', 'usp', 'p2000', 'fiveseven', 'tec9', 'cz75', 'elite', 'bizon', 'revolver', 'knife', 'glove',
                'bayonet', 'karam', 'butterfly', 'falchion', 'bowie', 'huntsman', 'flip', 'gut', 'm9', 'push', 'widow',
                'ursus', 'stiletto', 'navaja', 'talon', 'kukri', 'cord', 'canis', 'outdoor', 'skeleton', 'css')
KNIFE_VARIANT = re.compile(r'_(widow|b|90|fine|prisma)$')


def brightness(rgb):
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


def recolor(colors, theme):
    """colors: four [r, g, b, a] in 0..1. Returns four new colours with the theme's hue, brightness kept."""
    order = sorted(range(4), key=lambda i: brightness(colors[i]))
    out = [None] * 4
    for rank, index in enumerate(order):
        r, g, b, a = colors[index]
        value = max(r, g, b)
        if theme in DUO_THEMES:
            hue_a, hue_b, saturation = DUO_THEMES[theme]
            hue = hue_a if rank in (0, 3) else hue_b
        else:
            base, saturation, spread = THEMES[theme]
            hue = (base + spread * (rank / 3.0 - 0.5)) % 360
        saturation *= 0.6 if value > 0.85 else 0.85 if value < 0.2 else 1.0
        value = min(0.97, 0.12 + 0.88 * value ** 0.85)
        rr, gg, bb = colorsys.hsv_to_rgb(hue / 360.0, saturation, value)
        out[index] = [rr, gg, bb, a]
    return out


def kit_title(base, theme, titles):
    return KNIFE_BASES.get(base) or titles.get(base) or base


def _vector_params(root):
    params = root.get('m_vectorParams')
    if params is None or not isinstance(params.value, list): return None
    found = {}
    for entry in params.value:
        if entry.type != kv3.OBJECT: continue
        name, value = entry.get('m_name'), entry.get('m_value')
        if name and value and name.value in ('g_vColor0', 'g_vColor1', 'g_vColor2', 'g_vColor3'):
            found[name.value] = value
    return found if len(found) == 4 else None


def _specific_material(root):
    """The one SPECIFIC_MATERIAL container of a composite material, or None."""
    found = []

    def walk(node):
        if node.type == kv3.OBJECT:
            kind = node.get('m_nCompositeMaterialInputContainerSourceType')
            if kind and kind.value == 'CONTAINER_SOURCE_TYPE_SPECIFIC_MATERIAL':
                found.append(node.get('m_strSpecificContainerMaterial'))
            for _, child in node.value: walk(child)
        elif isinstance(node.value, list):
            for child in node.value: walk(child)
    walk(root)
    return found[0] if len(found) == 1 and found[0] is not None and found[0].type == kv3.STRING else None


class Source:
    """Reads compiled files from the installed pak01 (indexed once) or a folder of extracted files (tests)."""
    def __init__(self, vpk=None, folder=None):
        self.vpk, self.folder, self.index = vpk and Path(vpk), folder, None

    def _load_index(self):
        data = self.vpk.read_bytes()
        magic, version, tree_size = struct.unpack_from('<III', data, 0)
        if magic != 0x55aa1234 or version not in (1, 2): raise ValueError('Unsupported VPK header')
        header = 12 if version == 1 else 28
        tree, position, self.index = data[header:header + tree_size], 0, {}
        self.data_start = header + tree_size
        self.directory = data

        def string():
            nonlocal position
            end = tree.index(b'\0', position)
            value = tree[position:end].decode('utf-8', 'replace'); position = end + 1
            return value
        while True:
            extension = string()
            if not extension: break
            while True:
                folder = string()
                if not folder: break
                while True:
                    name = string()
                    if not name: break
                    crc, preload, archive, offset, length, end = struct.unpack_from('<IHHIIH', tree, position)
                    position += 18
                    small = tree[position:position + preload]; position += preload
                    path = ('' if folder == ' ' else folder + '/') + name + ('' if extension == ' ' else '.' + extension)
                    self.index[path.lower()] = (small, archive, offset, length)

    def read(self, path):
        if self.folder is not None:
            file = Path(self.folder) / path
            return file.read_bytes() if file.is_file() else None
        if self.index is None: self._load_index()
        entry = self.index.get(path.lower())
        if entry is None: return None
        small, archive, offset, length = entry
        if not length: return bytes(small)
        if archive == 0x7fff:
            start = self.data_start + offset
            return bytes(small) + self.directory[start:start + length]
        with (self.vpk.parent / self.vpk.name.replace('_dir.vpk', '_%03d.vpk' % archive)).open('rb') as handle:
            handle.seek(offset)
            return bytes(small) + handle.read(length)


def _with_block(data, name, content):
    version, blocks = kv3.read_resource(data)
    for block in blocks:
        if block[0] == name: block[1] = content
    return kv3.write_resource(version, blocks)


def make_finish(source, kit, kit_path, new_name, theme):
    """(vcompmat bytes, vmat bytes) for a recolour of `kit`, or None when it is not a four-colour finish."""
    compmat = source.read(kit_path + '_c')
    if compmat is None: return None
    version, blocks = kv3.read_resource(compmat)
    data = dict(blocks).get('DATA')
    if data is None: return None
    guid, root = kv3.read_kv3(data)
    specific = _specific_material(root)
    if specific is None: return None
    material = source.read(specific.value + '_c')
    if material is None: return None
    m_version, m_blocks = kv3.read_resource(material)
    m_data = dict(m_blocks).get('DATA')
    if m_data is None: return None
    m_guid, m_root = kv3.read_kv3(m_data)
    colors = _vector_params(m_root)
    if colors is None: return None
    current = [[item.value for item in colors['g_vColor%d' % i].value] for i in range(4)]
    if any(len(color) != 4 for color in current): return None
    new_colors = recolor(current, theme)
    if max(brightness(c) for c in new_colors) < 110 / 255: return None  # dark patterns need a bright colour to show
    for i in range(4):
        for item, value in zip(colors['g_vColor%d' % i].value, new_colors[i]): item.value = value
    vmat_path = VMAT_DIR + new_name + '.vmat'
    name = m_root.get('m_materialName')
    if name is not None: name.value = vmat_path
    specific.value = vmat_path
    vmat = _with_block(material, 'DATA', kv3.write_kv3(m_guid, m_root))
    vcompmat = _with_block(compmat, 'DATA', kv3.write_kv3(guid, root))
    return vcompmat, vmat


def schema_info(source_text, gold_pools_text):
    sections = collect(parse(source_text))
    items = {key: as_dict(value) for key, value in sections.get('items', {}).items() if isinstance(value, list)}
    knives = {key: value['name'] for key, value in items.items()
              if value.get('prefab', '').startswith('melee_unusual') and value.get('name')}
    kits = {}
    for key, value in sections.get('paint_kits', {}).items():
        if isinstance(value, list) and 'name' in as_dict(value): kits[as_dict(value)['name']] = (key, as_dict(value))
    by_id = {key: name for name, (key, _) in kits.items()}
    official = set()
    for knife, kit in re.findall(r'"(\d+):(\d+)"', gold_pools_text):
        if knife in knives:
            official.add((knives[knife], by_id.get(kit, '') if kit != '0' else ''))
    return sections, knives, kits, official


def kit_path(name, values):
    return values.get('composite_material_path') or 'weapons/paints/legacy/' + name + '.vcompmat'


def plan(source_text, gold_pools_text, titles, finish_source, known_ids=None):
    """Everything to generate, deterministic for the same game files.

    Returns (files {path: bytes}, kit entries [(name, base, title, values)], case entries ["[kit]weapon"], tokens)."""
    sections, knives, kits, official = schema_info(source_text, gold_pools_text)
    knife_names = sorted(set(knives.values()))
    official = {pair for pair in official if pair[1] == '' or pair[1] in kits}
    knife_kits = sorted({kit for _, kit in official if kit})
    extras = [name for name in EXTRA_FINISHES if name in kits]
    for name, (_, values) in sorted(kits.items()):
        if (values.get('style') in ('4', '5', '6') and re.match(r'(am|aa|an)_', name) and name not in knife_kits
                and not any(word in name for word in WEAPON_WORDS) and name not in extras and titles.get(name)):
            extras.append(name)
    files, entries, case, tokens = {}, [], [], {}
    # Official finishes on the knives they shipped with, and the colour finishes on every knife.
    case += sorted(('[%s]%s' % (kit, knife)) if kit else knife for knife, kit in official)
    colour_kits = [kit for kit in knife_kits if kits[kit][1].get('style') in ('1', '2', '3', '5', '6', '8')
                   and not KNIFE_VARIANT.search(kit)]
    for kit in colour_kits + extras:
        case += ['[%s]%s' % (kit, knife) for knife in knife_names]
    # Paint kit ids are stored on owned knives, so an existing recolour keeps its id: known ids come first, and new
    # recolours take the next free number after them.
    known_ids = dict(known_ids or {})
    next_id = max([FIRST_KIT_ID - 1] + [int(v) for v in known_ids.values()]) + 1
    rng = random.Random(20261021)

    def add(base, theme, knives_for):
        nonlocal next_id
        name = 'rk_%s_%s' % (base, theme.lower())
        made = make_finish(finish_source, base, kit_path(base, kits[base][1]), name, theme)
        if not made: return
        vcompmat, vmat = made
        files[COMPMAT_DIR + name + '.vcompmat_c'] = vcompmat
        files[VMAT_DIR + name + '.vmat_c'] = vmat
        title = '%s %s' % (KNIFE_BASES.get(base) or titles.get(base, base), theme)
        values = {k: v for k, v in kits[base][1].items() if k not in ('name', 'description_string', 'description_tag',
                                                                       'composite_material_path') and isinstance(v, str)}
        if name in known_ids:
            kit_id = str(known_ids[name])
        else:
            kit_id = str(next_id); next_id += 1
        entries.append((kit_id, name, title, values))
        tokens['PaintKit_' + name] = title
        tokens['PaintKit_' + name + '_Tag'] = title
        picks = knife_names[:]
        rng.shuffle(picks)
        case.extend('[%s]%s' % (name, knife) for knife in sorted(picks[:knives_for]))

    themes = list(THEMES) + list(DUO_THEMES)
    for base in sorted(name for name in KNIFE_BASES if name in kits):
        for theme in themes: add(base, theme, RECOLOUR_KNIVES)
    for base in extras:
        picks = themes[:]
        random.Random(base).shuffle(picks)
        for theme in picks[:EXTRA_THEMES]: add(base, theme, EXTRA_RECOLOUR_KNIVES)
    # Added in 17t after the first set (so earlier ids never move): every colour for the finishes asked for by name.
    for base in [name for name in EXTRA_FINISHES if name in extras]:
        picks = themes[:]
        random.Random(base).shuffle(picks)
        for theme in picks[EXTRA_THEMES:]: add(base, theme, EXTRA_RECOLOUR_KNIVES)
    return files, entries, sorted(set(case)), tokens


def _quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'


def _block(key, values, indent):
    pad = '\t' * indent
    lines = [pad + _quote(key), pad + '{']
    for k, v in values:
        if isinstance(v, list): lines.append(_block(k, v, indent + 1))
        else: lines.append(pad + '\t' + _quote(k) + '\t\t' + _quote(v))
    lines.append(pad + '}')
    return '\n'.join(lines)


def patch_items_game(source_text, entries, case, case_price=None):
    """Add the recolour paint kits and the knife-only Black Market Case to an items_game override."""
    from native_tradeups import parse as parse_spans
    if CASE_NAME in source_text: raise ValueError('items_game already has the Black Market Case')
    sections = collect(parse(source_text))
    used_ids = set(sections.get('items', {}))
    case_id = next(str(i) for i in range(FIRST_CASE_ID, FIRST_CASE_ID + 1000) if str(i) not in used_ids)
    base = sections.get('items', {}).get(CASE_BASE)
    if not isinstance(base, list): raise ValueError('Base case %s missing' % CASE_BASE)
    base = as_dict(base)
    series = max([int(k) for k in sections.get('revolving_loot_lists', {}) if k.isdigit()] + [0]) + 1
    for kit_id, _, _, _ in entries:
        if kit_id in sections.get('paint_kits', {}): raise ValueError('Paint kit id %s is taken' % kit_id)
    # Names are written as plain text: overriding the game's language file broke every other string (17k).
    kit_text = '\n'.join(_block(kit_id, [('name', name), ('description_string', title),
                                         ('description_tag', title)] + sorted(values.items()) +
                                [('composite_material_path', COMPMAT_DIR + name + '.vcompmat')], 2)
                         for kit_id, name, title, values in entries)
    rarity_text = '\n'.join('\t\t' + _quote(name) + '\t\t"ancient"' for _, name, _, _ in entries)
    case_def = [('item_name', CASE_TITLE), ('item_description', CASE_DESCRIPTION),
                ('name', CASE_NAME), ('image_inventory', CASE_IMAGE)]
    case_def += [(k, base[k]) for k in ('model_player', 'prefab') if k in base]
    for key in ('associated_items', 'tool'):
        if isinstance(base.get(key), list): case_def.append((key, base[key]))
    case_def.append(('attributes', [('set supply crate series', [('attribute_class', 'supply_crate_series'),
                                                                 ('value', str(series))])]))
    item_text = _block(case_id, case_def, 2)
    tier = CASE_NAME + '_ancient'
    lists_text = _block(CASE_NAME, [(tier, '1')], 2) + '\n' + _block(tier, [(entry, '1') for entry in case], 2)
    revolving_text = '\t\t' + _quote(str(series)) + '\t\t' + _quote(CASE_NAME)
    top = parse_spans(source_text).one('items_game')
    inserts = {}
    for key, text in (('paint_kits', kit_text), ('paint_kits_rarity', rarity_text), ('items', item_text),
                      ('client_loot_lists', lists_text), ('revolving_loot_lists', revolving_text)):
        nodes = [node for node in top.children if node.key == key and node.children is not None]
        if not nodes: raise ValueError('items_game has no %s section' % key)
        inserts[nodes[-1].end - 1] = inserts.get(nodes[-1].end - 1, '') + '\n' + text + '\n\t'
    for position in sorted(inserts, reverse=True):
        source_text = source_text[:position] + inserts[position] + source_text[position:]
    return source_text, {'case': CASE_NAME, 'case_id': case_id, 'series': series, 'kits': len(entries),
                         'case_items': len(case)}


def localization(english_text, tokens):
    """The installed csgo_english.txt with our names added inside its Tokens block."""
    match = re.search(r'"Tokens"\s*\{', english_text, re.I)
    if not match: raise ValueError('csgo_english.txt has no Tokens block')
    added = ''.join('\t\t' + _quote(k) + '\t' + _quote(v) + '\n' for k, v in sorted(tokens.items()))
    return english_text[:match.end()] + '\n' + added + english_text[match.end():]


def titles_from(english_text, kits):
    tokens = {k.lower(): v for k, v in re.findall(r'"([^"\n]+)"\s+"([^"\n]*)"', english_text)}
    return {name: tokens.get(values.get('description_tag', '').lstrip('#').lower(), '')
            for name, (_, values) in kits.items()}


def read_png(data):
    """8-bit RGB/RGBA, non-interlaced PNG -> (width, height, rows of RGBA bytes). Standard library only."""
    if data[:8] != b'\x89PNG\r\n\x1a\n': raise ValueError('Not a PNG')
    position, chunks, header = 8, [], None
    while position < len(data):
        length, kind = struct.unpack_from('>I4s', data, position)
        body = data[position + 8:position + 8 + length]
        position += 12 + length
        if kind == b'IHDR': header = struct.unpack('>IIBBBBB', body)
        elif kind == b'IDAT': chunks.append(body)
        elif kind == b'IEND': break
    width, height, depth, color, _, _, interlace = header
    if depth != 8 or color not in (2, 6) or interlace: raise ValueError('Unsupported PNG layout')
    channels = 4 if color == 6 else 3
    raw = zlib.decompress(b''.join(chunks))
    stride = width * channels
    rows, previous, position = [], bytearray(stride), 0
    for _ in range(height):
        kind = raw[position]; line = bytearray(raw[position + 1:position + 1 + stride]); position += 1 + stride
        for i in range(stride):
            left = line[i - channels] if i >= channels else 0
            up = previous[i]
            corner = previous[i - channels] if i >= channels else 0
            if kind == 1: line[i] = (line[i] + left) & 255
            elif kind == 2: line[i] = (line[i] + up) & 255
            elif kind == 3: line[i] = (line[i] + (left + up) // 2) & 255
            elif kind == 4:
                p = left + up - corner
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - corner)
                line[i] = (line[i] + (left if pa <= pb and pa <= pc else up if pb <= pc else corner)) & 255
        previous = line
        if channels == 3:
            line = bytearray(b''.join(bytes(line[i:i + 3]) + b'\xff' for i in range(0, stride, 3)))
        rows.append(bytes(line))
    return width, height, rows


def make_vtex(template, png):
    """An uncompressed BGRA8888 vtex_c (one mip) for `png`, keeping the template icon's resource layout."""
    width, height, rows = read_png(png)
    pixels = bytearray()
    for row in rows:
        for i in range(0, len(row), 4):
            r, g, b, a = row[i:i + 4]
            pixels += bytes((b, g, r, a))
    count = width * height
    reflect = [sum(pixels[i + k] for i in range(0, len(pixels), 4)) / count / 255 for k in (2, 1, 0, 3)]
    version, blocks = kv3.read_resource(template[:struct.unpack_from('<I', template, 0)[0]])
    names = [name for name, _ in blocks]
    if 'DATA' not in names: raise ValueError('Template texture has no DATA block')
    flags = struct.unpack_from('<H', dict(blocks)['DATA'], 2)[0]
    data = struct.pack('<HH4fHHHBBIII', 1, flags, *reflect, width, height, 1, 28, 1, 0, 8, 0)
    blocks = [[name, data if name == 'DATA' else content] for name, content in blocks]
    return kv3.write_resource(version, blocks) + bytes(pixels)


def prepare(proxy_directory, config, items_game_text):
    """Write the finish VPK folder and return items_game_text with the paint kits and case added.

    Called by native_tradeups while it builds the native items_game override."""
    from native_tradeups import atomic_write, mount_gameinfo, read_text
    proxy = Path(proxy_directory).resolve()
    game = proxy.parent.parent
    mod = game / FOLDER
    info = game / 'csgo/gameinfo.gi'
    manifest_path = mod / 'cs2_gc_finishes_manifest.json'
    current = read_text(info)
    enabled = bool(config.get('knife_finishes', 1))
    if manifest_path.exists():
        if json.loads(read_text(manifest_path)).get('owner') != OWNER: raise ValueError('Finish folder is not owned by this feature')
    elif mod.exists() and any(mod.iterdir()): raise ValueError('Finish folder contains unowned files')
    mounted = mount_gameinfo(current, enabled, FOLDER, COMMENT)
    if not enabled:
        if mounted != current: atomic_write(info, mounted)
        return items_game_text, 'disabled'
    source = Source(vpk=game / 'csgo/pak01_dir.vpk')
    english = source.read('resource/csgo_english.txt')
    if english is None: raise ValueError('resource/csgo_english.txt not found in the installed VPK')
    english = english.decode('utf-8-sig')
    gold = (proxy / 'gold_pools.txt').read_text(encoding='utf-8')
    _, _, kits, _ = schema_info(items_game_text, gold)
    ids_path = proxy / 'cs2_gc_finish_ids.json'
    try:
        known = json.loads(ids_path.read_text(encoding='utf-8')) if ids_path.is_file() else {}
    except ValueError:
        known = {}
    files, entries, case, tokens = plan(items_game_text, gold, titles_from(english, kits), source, known)
    known.update({name: int(kit_id) for kit_id, name, _, _ in entries})
    atomic_write(ids_path, json.dumps(known, indent=1, sort_keys=True) + '\n')
    template = source.read('panorama/images/econ/weapon_cases/crate_operation_ii_png.vtex_c')
    if template is not None and ICON.is_file():
        files['panorama/images/' + CASE_IMAGE + '_png.vtex_c'] = make_vtex(template, ICON.read_bytes())
    patched, details = patch_items_game(items_game_text, entries, case)
    atomic_write(manifest_path, json.dumps(dict(owner=OWNER, files=len(files), **details), indent=2) + '\n')
    wanted = {mod / path for path in files}
    for path, content in files.items():
        target = mod / path
        if not target.exists() or target.read_bytes() != content:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + '.tmp')
            temporary.write_bytes(content); temporary.replace(target)
    for stale in [p for p in mod.rglob('*') if p.is_file() and p.suffix not in ('.vpk', '.json') and p not in wanted]:
        stale.unlink()
    from vpk_pack import pack
    changed = pack(mod)
    if mounted != current:
        backup = info.with_name(info.name + '.' + FOLDER + '_backup')
        if not backup.exists():
            with backup.open('x', encoding='utf-8', newline='') as output: output.write(current)
        atomic_write(info, mounted); changed = True
    return patched, ('%d recolours, %d knives in the %s%s' % (len(entries), len(case), CASE_TITLE,
                     '; RESTART CS2 ONCE' if changed else ''))

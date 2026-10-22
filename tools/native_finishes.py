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
# Four-colour gradients for fades and marbles: colour i of the finish takes hue i, so the fade keeps its sweep.
GRADIENT_THEMES = {
    'Ocean': ((190, 205, 175, 225), 0.75), 'Lava': ((0, 18, 35, 350), 0.85), 'Candy': ((330, 300, 190, 350), 0.65),
    'Galaxy': ((270, 230, 300, 200), 0.75), 'Forest': ((95, 130, 60, 150), 0.65), 'Sunrise': ((45, 20, 340, 280), 0.75),
    'Vapor': ((300, 190, 330, 170), 0.60), 'Frost': ((200, 190, 220, 180), 0.35), 'Royal': ((280, 45, 260, 50), 0.70),
    'Toxin': ((100, 70, 280, 130), 0.80), 'Coral': ((10, 340, 190, 20), 0.70), 'Rainbow': ((0, 60, 180, 280), 0.80),
}
FADE_BASES = ('aa_fade', 'aa_fade_grassland', 'aa_fade_metallic', 'am_marble_fade', 'am_doppler_phase1', 'am_doppler_phase2',
              'am_doppler_phase3', 'am_doppler_phase4', 'am_gamma_doppler_phase1', 'am_gamma_doppler_phase2',
              'am_gamma_doppler_phase3', 'am_gamma_doppler_phase4', 'am_ruby_marbleized', 'am_sapphire_marbleized',
              'am_emerald_marbleized', 'am_blackpearl_marbleized', 'an_tiger_orange')
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
EXTRA_TITLES = {'am_aqua_flecks': 'Twilight Galaxy', 'am_gold_brick': 'Gold Brick', 'am_m4a1s_bluesmoke': 'Blue Phosphor'}
ICON_DIR = 'panorama/images/econ/default_generated/'
FALLBACK_ICON = 'panorama/images/econ/weapon_cases/default_rare_item_png.vtex_c'
WEARS = ('light', 'medium', 'heavy')
EXTRA_THEMES = 6  # recolours per extra finish (knife bases get every theme)
RECOLOUR_KNIVES = 4  # knives each knife-base recolour appears on in the case
EXTRA_RECOLOUR_KNIVES = 4
PALETTE_REPORT = 'cs2_gc_knife_palettes.json'
WEAPON_WORDS = ('ak47', 'ak_', 'awp', 'm4a1', 'm4a4', 'deagle', 'scar20', 'g3sg1', 'p250', 'p90', 'mp9', 'mp7', 'mac10',
                'ump', 'famas', 'galil', 'aug_', 'sg553', 'sg556', 'ssg08', 'nova', 'xm1014', 'mag7', 'sawedoff', 'negev',
                'm249', 'glock', 'usp', 'p2000', 'fiveseven', 'tec9', 'cz75', 'elite', 'bizon', 'revolver', 'knife', 'glove',
                'bayonet', 'karam', 'butterfly', 'falchion', 'bowie', 'huntsman', 'flip', 'gut', 'm9', 'push', 'widow',
                'ursus', 'stiletto', 'navaja', 'talon', 'kukri', 'cord', 'canis', 'outdoor', 'skeleton', 'css')
KNIFE_VARIANT = re.compile(r'_(widow|b|90|fine|prisma)$')


def brightness(rgb):
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


def recolor(colors, theme, fade=False, keep_value=False):
    """colors: [r, g, b, a] in 0..1 (four for a weapon finish, eight glove tints). Returns new colours with the
    theme's hue; brightness is kept (keep_value: exactly, for glove tints that multiply a texture)."""
    count = len(colors)
    last = max(1, count - 1)
    order = sorted(range(count), key=lambda i: brightness(colors[i]))
    out = [None] * count
    for rank, index in enumerate(order):
        r, g, b, a = colors[index]
        value = max(r, g, b)
        if theme in GRADIENT_THEMES:
            hues, saturation = GRADIENT_THEMES[theme]
            hue = hues[index * 4 // count]
        elif theme in DUO_THEMES:
            hue_a, hue_b, saturation = DUO_THEMES[theme]
            hue = hue_a if rank in (0, count - 1) else hue_b
        else:
            base, saturation, spread = THEMES[theme]
            if fade and spread:
                # A fade needs visible movement: sweep 80 degrees along the finish's own colour order.
                hue = (base + 80 * (index / last - 0.5)) % 360
            else:
                hue = (base + spread * (rank / last - 0.5)) % 360
        saturation *= 0.6 if value > 0.85 else 0.85 if value < 0.2 else 1.0
        if not keep_value: value = min(0.97, 0.12 + 0.88 * value ** 0.85)
        rr, gg, bb = colorsys.hsv_to_rgb(hue / 360.0, saturation, value)
        out[index] = [rr, gg, bb, a]
    return out


CLEAN_COLLECTION_TITLES = {
    'am_m4a1s_bluesmoke': 'Blue Phosphor',
    'am_aqua_flecks': 'Twilight Galaxy',
    'am_gold_brick': 'Gold Brick',
    'am_jorm_orange': 'Jörmungandr',
    'am_jorm_blue': 'Jörmungandr',
    'am_moro_textile_bright': 'Bright Textile',
    'am_zebra_dark': 'Zebra',
    'am_knots_brown': 'Knotted',
    'soe_teal_glitter': 'Glitter',
    'soe_pink_pearl': 'Pink Pearl',
    'soe_iridescent_purple': 'Iridescence',
    'soe_metallic_green_2': 'Metallic',
    'cg_pattern_tidal_contour': 'Tidal Contour',
    'cg_pattern_obsidian_fault': 'Obsidian Fault',
    'cg_pattern_prismatic_facets': 'Prismatic Facets',
    'cg_pattern_vector_lattice': 'Vector Lattice',
}


def source_title(base, titles):
    if base in CLEAN_COLLECTION_TITLES:
        return CLEAN_COLLECTION_TITLES[base]
    localized=(titles.get(base) or '').strip()
    if localized: return localized
    named={'am_carbon_fiber':'Carbon Weave','aa_wiring':'Circuitwork',
           'aa_vertigogeo_neon':'Prism Grid','am_metal_inlay':'Metal Inlay'}
    if base in named:return named[base]
    return re.sub(r'^(?:am|aa|aq|hy|so|cu|sp|an)_','',base).replace('_',' ').strip().title() or 'Custom Finish'


def variant_title(base, theme, inverse, titles):
    """Use actual rolled colour in item title, but not in the collection preview."""
    root = source_title(base, titles)
    # Canonical colour names only when a palette actually matches.
    colour = {'Royal':'Purple','Galaxy':'Violet','Ocean':'Blue','Forest':'Green',
              'Frost':'Frost','Glacier':'Glacier','Coral':'Coral','Vapor':'Vapor',
              'Sunrise':'Sunset','Lava':'Crimson','Toxin':'Toxic'}.get(theme,theme)
    if root == 'Blue Phosphor': root='Phosphor'
    if root == 'Gold Brick': root='Brick'
    return f'{colour} {root}' + (' Inverted' if inverse else '')

def kit_title(base, theme, titles):
    return KNIFE_BASES.get(base) or titles.get(base) or base


def recolor_gold_brick(colors, theme):
    """Keep the donor's related metallic tones together rather than splitting them by brightness rank.

    Gold Brick's supplied palette is four shades of gold, not four separate accent colours.
    The theme's primary hue replaces gold, retaining relative hue offsets, value and alpha.
    """
    hsv = [colorsys.rgb_to_hsv(*color[:3]) for color in colors]
    anchor = max(range(len(colors)), key=lambda i: (hsv[i][2], hsv[i][1]))
    hue, saturation = ((DUO_THEMES[theme][0],DUO_THEMES[theme][2]) if theme in DUO_THEMES else THEMES[theme][:2])
    output = []
    for color, (h,s,v) in zip(colors,hsv):
        offset = (h-hsv[anchor][0]+.5)%1-.5
        rgb = colorsys.hsv_to_rgb((hue/360+offset)%1,min(s,saturation),v)
        output.append([*rgb,color[3]])
    return output


def recolor_hardened(colors, theme):
    """Retain aq_oiled's light/dark metal channels and vary its two midtone accents."""
    output = [list(color) for color in colors]
    accents = recolor(colors, theme, keep_value=True)
    for index in (1, 2):
        h, s, _ = colorsys.rgb_to_hsv(*accents[index][:3])
        if theme in THEMES:
            base, _, spread = THEMES[theme]
            # Related heat-treated tones, rather than four nearly identical tints.
            separation = 0 if not spread else 20 if theme == 'Teal' else 55
            h = (base - (separation if index == 2 else 0)) % 360 / 360
        value = max(colors[index][:3])
        output[index] = [*colorsys.hsv_to_rgb(h, min(s, .65), value), colors[index][3]]
    return output


def _vector_params(root, allow_partial=False):
    params = root.get('m_vectorParams')
    if params is None or not isinstance(params.value, list): return None
    found = {}
    for entry in params.value:
        if entry.type != kv3.OBJECT: continue
        name, value = entry.get('m_name'), entry.get('m_value')
        if name and value and name.value in ('g_vColor0', 'g_vColor1', 'g_vColor2', 'g_vColor3'):
            found[name.value] = value
    return found if len(found) == 4 or (allow_partial and found) else None


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

    def exists(self, path):
        if self.folder is not None: return (Path(self.folder) / path).is_file()
        if self.index is None: self._load_index()
        return path.lower() in self.index

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


def make_finish(source, kit, kit_path, new_name, theme, report=None, weapon_palette=None, weapon_inverse=False, weapon_tone=2):
    """(vcompmat bytes, vmat bytes) for a recolour of `kit`, or None when it is not a four-colour finish."""
    compmat = source.read(kit_path + '_c')
    if compmat is None: return None
    version, blocks = kv3.read_resource(compmat)
    data = dict(blocks).get('DATA')
    if data is None: return None
    # Older official donors can use KV3 v4. They cannot be recoloured by this
    # writer; skip the donor rather than aborting the entire schema generation.
    if len(data) < 4 or struct.unpack_from('<I', data)[0] != kv3.MAGIC5: return None
    guid, root = kv3.read_kv3(data)
    specific = _specific_material(root)
    if specific is None: return None
    material = source.read(specific.value + '_c')
    if material is None: return None
    m_version, m_blocks = kv3.read_resource(material)
    m_data = dict(m_blocks).get('DATA')
    if m_data is None: return None
    if len(m_data) < 4 or struct.unpack_from('<I', m_data)[0] != kv3.MAGIC5: return None
    m_guid, m_root = kv3.read_kv3(m_data)
    partial=weapon_palette and kit.startswith('soe_')
    colors = _vector_params(m_root,allow_partial=partial)
    if colors is None: return None
    channels=sorted(colors)
    current = [[item.value for item in colors[name].value] for name in channels]
    if partial and len(current)<4:current += [list(current[-1]) for _ in range(4-len(current))]
    if any(len(color) != 4 for color in current): return None
    if not weapon_palette:
        new_colors = (recolor_hardened(current, theme) if kit == 'aq_oiled' else
                      recolor_gold_brick(current, theme) if kit == 'am_gold_brick' else
                      # Teal needs related blue-green tones: the wide fade sweep reaches
                      # green at one end. Keep this knife-only exception out of glove tinting.
                      recolor(current, theme, fade=kit in FADE_BASES and theme != 'Teal'))
    if weapon_palette:
        from weapon_palettes import recolour, is_new_colourway, invert_panels
        new_colors = recolour(current, theme, weapon_palette, THEMES, DUO_THEMES, GRADIENT_THEMES,tone=weapon_tone)
        if weapon_inverse: new_colors = invert_panels(current,new_colors,tone=weapon_tone)
        if not is_new_colourway(current,new_colors):
            if report is not None:
                report.setdefault('excluded',[]).append({'donor':kit,'theme':theme,'tier':weapon_palette,'reason':'near-original colourway'})
            return None
    if report is not None:
        report_key = kit + ':' + weapon_palette if weapon_palette else kit
        entry = report.setdefault(report_key, {'source_compmat': kit_path, 'source_material': specific.value,
            'shader': m_root.get('m_shaderName').value if m_root.get('m_shaderName') else '',
            'original_colors': current, 'policy': ('weapon-accent-gradient-v%d'%weapon_tone if weapon_palette else
                'hardened-metal-accents-v1' if kit == 'aq_oiled' else
                'related-metal-tones-v1' if kit == 'am_gold_brick' else 'ranked-theme-v1'),
            'themes': {}})
        entry['themes'][theme + (' / inverted' if weapon_inverse else '')] = new_colors
    if max(brightness(c) for c in new_colors[:len(channels)]) < 110 / 255: return None  # dark patterns need a bright colour to show
    for i,name in enumerate(channels):
        for item, value in zip(colors[name].value, new_colors[i]): item.value = value
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


REEL_FILE = 'cs2_gc_black_market_reel.json'
# Armory previews for the custom collections: CS2 reports 0 items for their lootlist rewards (26r), so the
# patched xpshop.js (rotate_armory.py) builds the tiles from this list of [weapon, paint kit id].
PREVIEW_FILE = 'cs2_gc_collection_previews.json'


def collection_previews(lists_text, names, kit_ids):
    """{collection: [[weapon, kit id], ...]} best tier first, from the generated tier lists."""
    order = ('ancient', 'legendary', 'mythical', 'rare', 'uncommon')
    previews = {}
    for name in names:
        for tier in order:
            block = re.search(r'"%s_%s"\s*\{([^}]*)\}' % (re.escape(name), tier), lists_text)
            for kit, weapon in re.findall(r'"\[([^\]]+)\]([^"]+)"', block.group(1) if block else ''):
                if kit in kit_ids: previews.setdefault(name, []).append([weapon, int(kit_ids[kit])])
    return previews


def reel_sample(source_text, gold_pools_text, entries, case, size=60, defs=None):
    """[[knife def index, paint kit id], ...] for the opening reel: the client collapses an all-knife loot list to
    one placeholder, so native_knife_reel.py fills the reel from this list instead. defs: {item name: def index}
    for other gold items (gloves); knives by default."""
    _, knives, kits, _ = schema_info(source_text, gold_pools_text)
    if defs is None: defs = {name: int(key) for key, name in knives.items()}
    ids = {name: int(key) for name, (key, _) in kits.items()}
    ids.update({name: int(kit_id) for kit_id, name, _, _ in entries})
    pairs = []
    for entry in case:
        match = re.fullmatch(r'\[([^\]]+)\](\w+)', entry)
        if match and match.group(2) in defs and match.group(1) in ids:
            pairs.append([defs[match.group(2)], ids[match.group(1)]])
    rng = random.Random(len(pairs))
    rng.shuffle(pairs)
    return sorted(pairs[:size])


def kit_path(name, values):
    return values.get('composite_material_path') or 'weapons/paints/legacy/' + name + '.vcompmat'


def plan(source_text, gold_pools_text, titles, finish_source, known_ids=None, report=None):
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
    # Only finishes no regular case has: the new knife finishes and the recolours below (user's choice, 21 Oct).
    # Official knife finishes stay in the regular cases.
    for kit in extras:
        case += ['[%s]%s' % (kit, knife) for knife in knife_names]
    # Paint kit ids are stored on owned knives, so an existing recolour keeps its id: known ids come first, and new
    # recolours take the next free number after them.
    known_ids = dict(known_ids or {})
    next_id = max([FIRST_KIT_ID - 1] + [int(v) for v in known_ids.values()]) + 1
    rng = random.Random(20261021)

    def add(base, theme, knives_for):
        nonlocal next_id
        name = 'rk_%s_%s' % (base, theme.lower())
        made = make_finish(finish_source, base, kit_path(base, kits[base][1]), name, theme, report=report)
        if not made: return
        vcompmat, vmat = made
        files[COMPMAT_DIR + name + '.vcompmat_c'] = vcompmat
        files[VMAT_DIR + name + '.vmat_c'] = vmat
        base_title = KNIFE_BASES.get(base) or titles.get(base) or EXTRA_TITLES.get(base) or base.split('_', 1)[-1].replace('_', ' ').title()
        title = '%s %s' % (base_title, theme)
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
    # Added in 18a: gradient colours for the fades and marbles (ids are saved, so order no longer moves old ones).
    for base in FADE_BASES:
        if base in kits:
            for theme in GRADIENT_THEMES: add(base, theme, RECOLOUR_KNIVES)
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


def patch_items_game(source_text, entries, case, case_price=None, extra_cases=(), extra_sections=None):
    """Add the recolour paint kits and the knife-only Black Market Case to an items_game override.

    extra_cases: more gold-only cases as dicts (name, title, description, base, items), e.g. the Gauntlet Case."""
    from native_tradeups import parse as parse_spans
    cases = [dict(name=CASE_NAME, title=CASE_TITLE, description=CASE_DESCRIPTION, base=CASE_BASE, items=case)]
    cases += list(extra_cases)
    for spec in cases:
        if spec['name'] in source_text: raise ValueError('items_game already has the %s' % spec['title'])
    sections = collect(parse(source_text))
    used_ids = set(sections.get('items', {}))
    series = max([int(k) for k in sections.get('revolving_loot_lists', {}) if k.isdigit()] + [0])
    for kit_id, _, _, _ in entries:
        if kit_id in sections.get('paint_kits', {}): raise ValueError('Paint kit id %s is taken' % kit_id)
    # Names are written as plain text: overriding the game's language file broke every other string (17k).
    kit_text = '\n'.join(_block(kit_id, [('name', name), ('description_string', title), ('description_tag', title)] +
                                sorted((k, v) for k, v in values.items()
                                       if k != 'composite_material_path' and not k.startswith('_')) +
                                [('composite_material_path',
                                  values.get('composite_material_path') or COMPMAT_DIR + name + '.vcompmat')], 2)
                         for kit_id, name, title, values in entries)
    rarity_text = '\n'.join('\t\t' + _quote(name) + '\t\t' + _quote(values.get('_rarity', 'ancient'))
                            for _, name, _, values in entries)
    item_texts, list_texts, revolving_texts, details = [], [], [], {'kits': len(entries)}
    for spec in cases:
        base = sections.get('items', {}).get(spec['base'])
        if not isinstance(base, list): raise ValueError('Base case %s missing' % spec['base'])
        base = as_dict(base)
        case_id = next(str(i) for i in range(FIRST_CASE_ID, FIRST_CASE_ID + 1000) if str(i) not in used_ids)
        used_ids.add(case_id)
        series += 1
        case_def = [('item_name', spec['title']), ('item_description', spec['description']),
                    ('name', spec['name']), ('image_inventory', 'econ/weapon_cases/' + spec['name'])]
        case_def += [(k, base[k]) for k in ('model_player', 'prefab') if k in base]
        for key in ('associated_items', 'tool'):
            if isinstance(base.get(key), list): case_def.append((key, base[key]))
        case_def.append(('attributes', [('set supply crate series', [('attribute_class', 'supply_crate_series'),
                                                                     ('value', str(series))])]))
        item_texts.append(_block(case_id, case_def, 2))
        if spec.get('loot_lists'):  # a case made of existing (tiered) loot lists, e.g. custom collections
            list_texts.append(_block(spec['name'], [(name, '1') for name in spec['loot_lists']], 2))
        else:
            tier = spec['name'] + '_ancient'
            list_texts.append(_block(spec['name'], [(tier, '1')], 2) + '\n' +
                              _block(tier, [(entry, '1') for entry in spec['items']], 2))
        revolving_texts.append('\t\t' + _quote(str(series)) + '\t\t' + _quote(spec['name']))
        if spec['name'] == CASE_NAME:
            details.update(case=CASE_NAME, case_id=case_id, series=series, case_items=len(spec['items']))
        else:
            details[spec['name']] = dict(case_id=case_id, series=series, case_items=len(spec['items']))
    top = parse_spans(source_text).one('items_game')
    inserts = {}
    sections_text = [('paint_kits', kit_text), ('paint_kits_rarity', rarity_text), ('items', '\n'.join(item_texts)),
                     ('client_loot_lists', '\n'.join(list_texts)), ('revolving_loot_lists', '\n'.join(revolving_texts))]
    sections_text += [(key, text) for key, text in (extra_sections or {}).items() if text]
    for key, text in sections_text:
        nodes = [node for node in top.children if node.key == key and node.children is not None]
        if not nodes: raise ValueError('items_game has no %s section' % key)
        inserts[nodes[-1].end - 1] = inserts.get(nodes[-1].end - 1, '') + '\n' + text + '\n\t'
    for position in sorted(inserts, reverse=True):
        source_text = source_text[:position] + inserts[position] + source_text[position:]
    return source_text, details


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


def make_vtex(template, png, max_size=None):
    """An uncompressed BGRA8888 vtex_c (one mip) for `png`, keeping the template icon's resource layout."""
    width, height, rows = read_png(png)
    if max_size and max(width,height)>max_size:
        # Render high-resolution source art at a bounded UI size. Keep source PNGs
        # untouched; premultiplied bilinear sampling avoids dark transparent edges.
        out_w=max(1,round(width*max_size/max(width,height)))
        out_h=max(1,round(height*max_size/max(width,height)))
        output=[]
        for y in range(out_h):
            yy=max(0,min(height-1,(y+.5)*height/out_h-.5));y0=int(yy);fy=yy-y0
            row=bytearray()
            for x in range(out_w):
                xx=max(0,min(width-1,(x+.5)*width/out_w-.5));x0=int(xx);fx=xx-x0
                samples=[(rows[sy][sx*4:sx*4+4],weight) for sy,sx,weight in (
                    (y0,x0,(1-fy)*(1-fx)),(y0,min(width-1,x0+1),(1-fy)*fx),
                    (min(height-1,y0+1),x0,fy*(1-fx)),(min(height-1,y0+1),min(width-1,x0+1),fy*fx))]
                alpha=sum(pixel[3]*weight for pixel,weight in samples)
                rgb=[round(sum(pixel[c]*pixel[3]*weight for pixel,weight in samples)/alpha) if alpha else 0 for c in range(3)]
                row.extend((*rgb,round(alpha)))
            output.append(bytes(row))
        width,height,rows=out_w,out_h,output
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
    template = source.read('panorama/images/econ/weapon_cases/crate_operation_ii_png.vtex_c')
    gold = (proxy / 'gold_pools.txt').read_text(encoding='utf-8')
    _, _, kits, _ = schema_info(items_game_text, gold)
    ids_path = proxy / 'cs2_gc_finish_ids.json'
    try:
        known = json.loads(ids_path.read_text(encoding='utf-8')) if ids_path.is_file() else {}
    except ValueError:
        known = {}
    titles = titles_from(english, kits)
    knife_palettes = {}
    files, entries, case, tokens = plan(items_game_text, gold, titles, source, known, report=knife_palettes)
    atomic_write(proxy / PALETTE_REPORT, json.dumps(knife_palettes, sort_keys=True, indent=1) + '\n')
    glove_entries, glove_case, glove_defs = [], [], {}
    if config.get('glove_finishes', 1):
        import native_gloves
        glove_palettes = {}
        glove_inspection = {}
        glove_files, glove_entries, glove_case, glove_defs = native_gloves.plan(
            items_game_text, gold, titles, source, known, [kit_id for kit_id, _, _, _ in entries],
            panel_variants=bool(config.get('glove_panel_variants', 1)), report=glove_palettes, inspection=glove_inspection)
        atomic_write(proxy / native_gloves.PALETTE_REPORT, json.dumps(glove_palettes, sort_keys=True, indent=1) + '\n')
        atomic_write(proxy / 'cs2_gc_glove_materials.json', json.dumps(glove_inspection, sort_keys=True, indent=1) + '\n')
        files.update(glove_files)
        if glove_case and template is not None and native_gloves.ICON.is_file():
            for name in (native_gloves.CASE_NAME, native_gloves.TEST_CASE_NAME):
                files['panorama/images/econ/weapon_cases/' + name + '_png.vtex_c'] = \
                    make_vtex(template, native_gloves.ICON.read_bytes(),max_size=512)
    entries += glove_entries
    known.update({name: int(kit_id) for kit_id, name, _, _ in entries})
    atomic_write(ids_path, json.dumps(known, indent=1, sort_keys=True) + '\n')
    if template is not None and ICON.is_file():
        files['panorama/images/' + CASE_IMAGE + '_png.vtex_c'] = make_vtex(template, ICON.read_bytes(),max_size=512)
    extra = []
    reels = {CASE_NAME: reel_sample(items_game_text, gold, entries, case)}
    if glove_case:
        import native_gloves
        extra.append(native_gloves.case_spec(glove_case))
        reels[native_gloves.CASE_NAME] = reel_sample(items_game_text, gold, entries, glove_case, defs=glove_defs)
        test_items = native_gloves.dead_hand_test_items(glove_case)
        if test_items:
            extra.append(native_gloves.test_case_spec(test_items))
            reels[native_gloves.TEST_CASE_NAME] = reel_sample(items_game_text, gold, entries, test_items, defs=glove_defs)
    skins = []
    if config.get('custom_skins_test', 1):
        import native_skins
        skins = native_skins.test_items(items_game_text, set(kits),
                                        [name for _, name, _, _ in entries if name.startswith('rk_')])
        if skins:
            extra.append(native_skins.test_case_spec(skins))
            if template is not None and ICON.is_file():
                files['panorama/images/econ/weapon_cases/' + native_skins.TEST_CASE_NAME + '_png.vtex_c'] = \
                    make_vtex(template, ICON.read_bytes(),max_size=512)
        skins2 = native_skins.test2_items(items_game_text, set(kits),
                                          [name for _, name, _, _ in entries if name.startswith('rk_')])
        if skins2:
            extra.append(native_skins.test2_case_spec(skins2))
            if template is not None and ICON.is_file():
                files['panorama/images/econ/weapon_cases/' + native_skins.TEST2_CASE_NAME + '_png.vtex_c'] = \
                    make_vtex(template, ICON.read_bytes(),max_size=512)
            skins += skins2
    sections_extra, previews = {}, {}
    if config.get('custom_skins_test', 1) or config.get('custom_collections', 0) or config.get('custom_cases', 1):
        import native_skins
        family_kits, sets_text, lists_text, families, set_names, collection_items, chases = native_skins.collections(
            items_game_text, kits, [name for _, name, _, _ in entries if name.startswith('rk_')], kit_path, titles)
        case_lists, icons = '', {}
        weapon_palettes = {}
        if config.get('custom_cases', 1):
            case_kits, case_files, case_lists, case_specs, case_items, icons = native_skins.custom_cases(
                items_game_text, kits, titles, kit_path, source, families, {n for n, _, _ in family_kits}, report=weapon_palettes)
            atomic_write(proxy / 'cs2_gc_weapon_palettes.json', json.dumps(weapon_palettes,sort_keys=True,indent=1)+'\n')
            family_kits += case_kits
            files.update(case_files)
            skins += case_items
            emblem_template = source.read('panorama/images/econ/set_icons/set_arabesque_png.vtex_c') or template
            for name in icons:
                emblem = Path(__file__).resolve().parent / 'collection_icons' / (name + '.png')
                if emblem_template is not None and emblem.is_file():
                    for suffix in ('_png.vtex_c', '_small_png.vtex_c'):
                        files['panorama/images/econ/set_icons/' + name + suffix] = make_vtex(emblem_template, emblem.read_bytes(),max_size=256)
        if family_kits:
            next_id = max([FIRST_KIT_ID - 1] + [int(v) for v in known.values()] + [int(k) for k, _, _, _ in entries]) + 1
            for name, title, values in family_kits:
                if name in known: kit_id = str(known[name])
                else: kit_id = str(next_id); next_id += 1
                entries.append((kit_id, name, title, values))
            known.update({name: int(kit_id) for kit_id, name, _, _ in entries})
            atomic_write(ids_path, json.dumps(known, indent=1, sort_keys=True) + '\n')
            drop_collections = native_skins.DROP_ONLY_COLLECTIONS.intersection(icons)
            atomic_write(proxy / native_skins.FAMILIES_FILE, native_skins.family_text(families, drop_collections))
            previews = collection_previews(case_lists, icons, known)
            # Loot lists only: CS2 refuses the whole schema for an item_set whose name is not a #CSGO_ token
            # (26m: CEconItemSystem::ParseItemSchemaFile assertion), and overriding the language file breaks text.
            sections_extra = {'client_loot_lists': '\n'.join(t for t in (lists_text, case_lists) if t)}
        if set_names:
            skins += collection_items
            if config.get('custom_skins_test', 1):
                extra.append(native_skins.collections_test_spec(set_names))
                extra.append(native_skins.chase_test_spec(chases))
                if template is not None and ICON.is_file():
                    for name in (native_skins.COLLECTIONS_TEST_NAME, native_skins.CHASE_TEST_NAME):
                        files['panorama/images/econ/weapon_cases/' + name + '_png.vtex_c'] = \
                            make_vtex(template, ICON.read_bytes(),max_size=512)
    patched, details = patch_items_game(items_game_text, entries, case, extra_cases=extra, extra_sections=sections_extra)
    atomic_write(proxy / REEL_FILE, json.dumps(reels, sort_keys=True) + '\n')
    atomic_write(proxy / PREVIEW_FILE, json.dumps(previews, sort_keys=True) + '\n')
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
    # Knife+finish pairs the game never shipped have no pre-rendered inventory picture; give them the stock
    # "Rare Special Item" icon (one shared copy inside the VPK) instead of a blank tile.
    fallback = source.read(FALLBACK_ICON)
    icons = []
    if fallback is not None:
        for entry in case + glove_case + skins:
            match = re.fullmatch(r'\[([^\]]+)\](\w+)', entry)
            if not match: continue
            for wear in WEARS:
                path = '%s%s_%s_%s_png.vtex_c' % (ICON_DIR, match.group(2), match.group(1), wear)
                if not source.exists(path): icons.append((path, fallback))
    from vpk_pack import pack
    changed = pack(mod, icons)
    if mounted != current:
        backup = info.with_name(info.name + '.' + FOLDER + '_backup')
        if not backup.exists():
            with backup.open('x', encoding='utf-8', newline='') as output: output.write(current)
        atomic_write(info, mounted); changed = True
    gloves = ', %d gloves in the Gauntlet Case' % len(glove_case) if glove_case else ''
    return patched, ('%d recolours, %d knives in the %s%s%s' % (len(entries), len(case), CASE_TITLE, gloves,
                     '; RESTART CS2 ONCE' if changed else ''))


def read_vtex(data):
    """BGRA8888 vtex_c -> (width, height, mip 0 BGRA bytes). Mips are stored smallest first, each optionally LZ4."""
    resource_size = struct.unpack_from('<I', data, 0)[0]
    _, blocks = kv3.read_resource(data[:resource_size])
    header = dict(blocks)['DATA']
    (version, flags, _, _, _, _, width, height, depth, fmt, mips, _, extra_offset, extra_count) = \
        struct.unpack_from('<HH4fHHHBBIII', header, 0)
    if version != 1 or fmt != 28 or depth != 1: raise ValueError('Unsupported icon texture format %d' % fmt)
    compressed = None
    position = 32 + extra_offset  # extra_offset counts from its own field (offset 32)
    for index in range(extra_count):
        kind, offset, size = struct.unpack_from('<III', header, position + index * 12)
        if kind == 4:  # COMPRESSED_MIP_SIZE
            start = position + index * 12 + 4 + offset
            method, mips_offset, count = struct.unpack_from('<III', header, start)
            sizes_at = start + 4 + mips_offset
            compressed = (method, list(struct.unpack_from('<%di' % count, header, sizes_at)))
    def size_of(level): return max(1, width >> level) * max(1, height >> level) * 4
    position = resource_size
    for level in range(mips - 1, -1, -1):
        raw = size_of(level)
        stored = raw if compressed is None else min(raw, compressed[1][level])
        if level == 0:
            chunk = data[position:position + stored]
            if stored < raw:
                if compressed[0] != 1: raise ValueError('Unsupported icon mip compression')
                chunk = kv3.lz4_block_decompress(chunk, raw)
            return width, height, chunk
        position += stored
    raise ValueError('Icon texture has no mips')

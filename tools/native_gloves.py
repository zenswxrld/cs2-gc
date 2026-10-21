"""Glove recolours and the glove-only Gauntlet Case (OfflineCS style), built from the user's own CS2 files.

A classic CS2 glove finish (gloves/paints/<kit>.vcompmat) names one csgo_customglove material whose eight tints
g_vColorTint1..8 colour the glove's masks. A recolour copies that pair with new tints under a new name, on the same
glove type only (glove patterns are drawn for one model). The four Dead Hand-era glove finishes CS2 ships with no
paint kit (red colourways of released gloves) get paint kits that point at the game's own files. Everything is
added next to the knife finishes (native_finishes.py): same VPK folder, same items_game override, nothing in the
game's own files changes. glove_finishes = 0 removes the Gauntlet Case; knife_finishes = 0 removes both cases.
"""
import random
import colorsys
import math
import re

import kv3
from inventory_item import as_dict, collect, parse
import native_finishes as finishes

CASE_NAME = 'crate_cs2gc_gauntlet'
CASE_TITLE = 'Gauntlet Case'
CASE_DESCRIPTION = ('Gloves only. Every glove type in colours no glove ever shipped with, plus four glove finishes '
                    'CS2 has in its files but never released.')
CASE_BASE = '4017'  # Huntsman Weapon Case: its model and key, like OfflineCS's Gauntlet Case
VMAT_DIR = 'materials/models/weapons/customization/paints_gloves/cs2_gc/'
COMPMAT_DIR = 'gloves/paints/cs2_gc/'
ICON = finishes.Path(__file__).resolve().parent / 'cs2_gc_gauntlet_case.png'
REEL_KEY = CASE_NAME
TINTS = ['g_vColorTint%d' % i for i in range(1, 9)]
# Shipped finishes no paint kit uses; each is a red colourway of a Dead Hand glove. Names are ours.
UNUSED = {
    'glove_driver_brocade_phoenix_red': ('slick_gloves', 'Brocade Phoenix'),
    'glove_driver_knit_argyle_red': ('slick_gloves', 'Crimson Sweaters'),
    'glove_driver_ostrich_leg_red': ('slick_gloves', 'Scarlet Quill'),
    'glove_specialist_dragon_red': ('specialist_gloves', 'Fire Chaser'),
}
UNUSED_DIR = 'gloves/paints/volatile_02/'
GLOVE_FADES = ('specialist_fade', 'specialist_marble_fade')
THEMES_PER_GLOVE = 8
PANEL_STYLES = {'original': '', 'white': 'White Panels', 'black': 'Black Panels', 'inverted': 'Inverted Panels'}
PALETTE_REPORT = 'cs2_gc_glove_palettes.json'
# User-approved existing finish: keep its exact legacy two-tone palette and saved identity.
# Panel variants still use accent-only recolouring; approval does not extend to other themes.
APPROVED_PALETTES = {('gloves/paints/specialist_forest_brown.vcompmat', 'Toxic'),
                     ('gloves/paints/specialist_webs_red.vcompmat', 'Aurora')}


def recolor_accents(colors, theme, fade=False, panels='original'):
    """Recolour chromatic accents; preserve structural tones and alpha unless a panel variant is requested.

    Read the actual material palette. No channel number is assumed to mean a palm, seam or panel.
    Ambiguous/muted colours are retained; a neutral-only palette is never turned into an all-over tint.
    """
    if panels not in PANEL_STYLES: raise ValueError('Unknown glove panel style: ' + panels)
    if any(len(c) != 4 or any(not math.isfinite(v) or v < 0 or v > 1 for v in c) for c in colors):
        raise ValueError('Expected finite normalized glove tint vectors')
    themed = finishes.recolor(colors, theme, fade=fade, keep_value=True)
    result = []
    for original, target in zip(colors, themed):
        _, saturation, value = colorsys.rgb_to_hsv(*original[:3])
        color = list(original)
        if value > .12 and saturation >= .35:
            hue, target_saturation, _ = colorsys.rgb_to_hsv(*target[:3])
            color[:3] = colorsys.hsv_to_rgb(hue, min(saturation, target_saturation), value)
        elif panels != 'original' and (saturation <= .2 or value <= .12):
            if panels == 'white': tone = .82 + .10 * math.sqrt(value)
            elif panels == 'black': tone = .025 + .075 * math.sqrt(value)
            else: tone = .04 + .88 * (1 - value)
            color[:3] = [tone] * 3
        result.append(color)
    return result



def glove_info(source_text, gold_pools_text):
    """({glove item name: def index}, {glove name: sorted official kit names}, {kit name: (id, values)})."""
    sections = collect(parse(source_text))
    items = {key: as_dict(value) for key, value in sections.get('items', {}).items() if isinstance(value, list)}
    gloves = {value['name']: key for key, value in items.items()
              if 'hands_paintable' in value.get('prefab', '').split() and value.get('name')}
    by_def = {key: name for name, key in gloves.items()}
    kits = {}
    for key, value in sections.get('paint_kits', {}).items():
        if isinstance(value, list) and 'name' in as_dict(value): kits[as_dict(value)['name']] = (key, as_dict(value))
    by_id = {key: name for name, (key, _) in kits.items()}
    official = {}
    for glove, kit in re.findall(r'"(\d+):(\d+)"', gold_pools_text):
        if glove in by_def and by_id.get(kit): official.setdefault(by_def[glove], set()).add(by_id[kit])
    return gloves, {name: sorted(values) for name, values in official.items()}, kits


def _tints(root):
    params = root.get('m_vectorParams')
    if params is None or not isinstance(params.value, list): return None
    found = {}
    for entry in params.value:
        if entry.type != kv3.OBJECT: continue
        name, value = entry.get('m_name'), entry.get('m_value')
        if name and value and name.value in TINTS: found[name.value] = value
    return found if len(found) == len(TINTS) else None


def make_glove_finish(source, compmat_path, new_name, theme, fade=False, panels='original', report=None):
    """(vcompmat bytes, vmat bytes) for a recolour, or None when the finish is not an eight-tint glove material."""
    compmat = source.read(compmat_path + '_c')
    if compmat is None: return None
    _, blocks = kv3.read_resource(compmat)
    data = dict(blocks).get('DATA')
    if data is None: return None
    guid, root = kv3.read_kv3(data)
    specific = finishes._specific_material(root)
    if specific is None: return None
    material = source.read(specific.value + '_c')
    if material is None: return None
    _, m_blocks = kv3.read_resource(material)
    m_data = dict(m_blocks).get('DATA')
    if m_data is None: return None
    m_guid, m_root = kv3.read_kv3(m_data)
    shader = m_root.get('m_shaderName')
    if shader is None or shader.value != 'csgo_customglove.vfx': return None
    tints = _tints(m_root)
    if tints is None: return None
    current = [[item.value for item in tints[name].value] for name in TINTS]
    if any(len(color) != 4 for color in current): return None
    approved = panels == 'original' and (compmat_path, theme) in APPROVED_PALETTES
    try:
        new = (finishes.recolor(current, theme, fade=fade, keep_value=True) if approved else
               recolor_accents(current, theme, fade=fade, panels=panels))
    except ValueError: return None
    if report is not None:
        report[compmat_path] = {
            'original_tints': current,
            'accent_channels': [i+1 for i,c in enumerate(current)
                if max(c[:3]) > .12 and colorsys.rgb_to_hsv(*c[:3])[1] >= .35],
            'policy': 'accent-only-v1',
            'preserved_legacy_themes': sorted(t for path,t in APPROVED_PALETTES if path == compmat_path),
        }
    if panels != 'original' and new == recolor_accents(current, theme, fade=fade): return None
    for name, color in zip(TINTS, new):
        for item, value in zip(tints[name].value, color): item.value = value
    vmat_path = VMAT_DIR + new_name + '.vmat'
    name = m_root.get('m_materialName')
    if name is not None: name.value = vmat_path
    specific.value = vmat_path
    return (finishes._with_block(compmat, 'DATA', kv3.write_kv3(guid, root)),
            finishes._with_block(material, 'DATA', kv3.write_kv3(m_guid, m_root)))


def plan(source_text, gold_pools_text, titles, source, known_ids, used_ids, panel_variants=True, report=None):
    """(files, kit entries, case items, {glove name: def index}); deterministic for the same game files.

    known_ids: saved {kit name: id}; used_ids: ids already given out this run (knife recolours)."""
    gloves, official, kits = glove_info(source_text, gold_pools_text)
    files, entries, case = {}, [], []
    next_id = max([finishes.FIRST_KIT_ID - 1] + [int(v) for v in known_ids.values()] + [int(v) for v in used_ids]) + 1

    def kit_id(name):
        nonlocal next_id
        if name in known_ids: return str(known_ids[name])
        value = next_id; next_id += 1
        return str(value)

    for original, (glove, title) in sorted(UNUSED.items()):
        path = UNUSED_DIR + original + '.vcompmat'
        name = 'ug_' + original
        if glove not in gloves or original in kits or name in kits or not source.exists(path + '_c'): continue
        entries.append((kit_id(name), name, title, {'composite_material_path': path}))
        case.append('[%s]%s' % (name, glove))
    themes = list(finishes.THEMES) + list(finishes.DUO_THEMES)
    for glove in sorted(official):
        for base in official[glove]:
            values = kits[base][1]
            if values.get('composite_material_path'): continue  # newer composited gloves have no tints to change
            compmat = 'gloves/paints/%s.vcompmat' % base
            picks = themes[:]
            random.Random(base).shuffle(picks)
            picks = picks[:THEMES_PER_GLOVE] + (list(finishes.GRADIENT_THEMES) if base in GLOVE_FADES else [])
            base_title = titles.get(base) or base.split('_', 1)[-1].replace('_', ' ').title()
            for theme in picks:
                for panels, panel_title in PANEL_STYLES.items():
                    suffix = '' if panels == 'original' else '_panels_' + panels
                    name = 'rg_%s_%s%s' % (base, theme.lower(), suffix)
                    # Retain known variants in the schema if disabled later, but stop offering them as drops.
                    if panels != 'original' and not panel_variants and name not in known_ids: continue
                    made = make_glove_finish(source, compmat, name, theme, fade=base in GLOVE_FADES,
                                             panels=panels, report=report)
                    if not made: continue
                    files[COMPMAT_DIR + name + '.vcompmat_c'], files[VMAT_DIR + name + '.vmat_c'] = made
                    title = '%s %s%s' % (base_title, theme, ' — ' + panel_title if panel_title else '')
                    entries.append((kit_id(name), name, title,
                                    {'composite_material_path': COMPMAT_DIR + name + '.vcompmat'}))
                    if panel_variants or panels == 'original': case.append('[%s]%s' % (name, glove))
    return files, entries, sorted(set(case)), {name: int(key) for name, key in gloves.items()}


def case_spec(items):
    return dict(name=CASE_NAME, title=CASE_TITLE, description=CASE_DESCRIPTION, base=CASE_BASE, items=items)

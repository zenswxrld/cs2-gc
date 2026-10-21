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
# The supplied Bronzed palette has two identical muted bronze tints; its other six tints are neutral.
ACCENT_THRESHOLDS = {'gloves/paints/bloodhound_metallic.vcompmat': .20,
                     'gloves/paints/slick_stitched_green_grey.vcompmat': .20,
                     'gloves/paints/slick_black.vcompmat': .14}
ACCENT_HUE_RANGES = {'gloves/paints/slick_stitched_green_grey.vcompmat': (75,180),
                    'gloves/paints/slick_black.vcompmat': (160,250)}
GLOVE_TITLES = {'slick_stitched_green_grey': 'Racing'}
# Finishes whose pattern lives in their neutral tints: the panel variants flatten those tints and erase the
# pattern (user report: Hand Wraps | Spruce DDPAT Midnight came out plain white; handwrap_camo_grey's camo is
# seven near-grey green tints, one accent). No new panel variants; owned ones render as the original panels.
NO_PANEL_VARIANTS = {'gloves/paints/handwrap_camo_grey.vcompmat'}
# Dead Hand gloves whose main colour is printed into a texture (only trim and cuffs can change), from the
# user's screenshots: offer only colours that sit within 60 degrees of that printed colour, so the result reads
# as one design (other Dead Hand gloves use their own main accent hue, see dead_hand_main_hue). Beadwork:
# blue-violet beads, so blues are offered too (user liked Violet Beadwork Azure). Hues: crane brocade red, flower brocade teal, seigaiha teal, Ultra Violent purple, Occult red
# velvet, Plum Quill purple, Sunburst orange.
DEAD_HAND_PRINT_HUES = {'glove_sport_beadwork_diamonds_purple': 265, 'glove_sport_pinstripe_black': 0, 'glove_driver_brocade_crane_red': 355, 'glove_driver_brocade_flower_red': 190,
                        'glove_driver_scallop_metallic_blue': 195, 'glove_sport_tech_gradient_bright': 285,
                        'glove_sport_velvet_red': 350, 'glove_driver_ostrich_purple': 275,
                        'glove_specialist_sunburst_red': 30}
# No recolours (user's call): the main printed panel cannot change, so every colour looks wrong or the same —
# Big Swell (wave, blue leather), Blaze (flames), Brocade Crane and Brocade Flowers (brocade panel),
# Seigaiha (wave panel), Wave Chaser (white silk with blue print), Chocolate Chesterfield (user: doesn't work).
DEAD_HAND_SKIP = {'glove_specialist_quilted_black', 'glove_specialist_wave_blue', 'glove_sport_flames_orange', 'glove_driver_brocade_crane_red',
                  'glove_driver_brocade_flower_red', 'glove_driver_scallop_metallic_blue',
                  'glove_driver_silk_dragon_white'}
HARMONY_DEGREES = 60
# Pale tint-ID regions (saturation .14-.18, so below the muted-shade threshold) that are whole panels, not
# printed: Red Racer's tan suede (Id4, confirmed in game), Ultra Violent's pale violet base (Id2, Id3) and
# Frosty's pale blue panel (Id7). Brocade Flowers' cream (Id4) stays cream on purpose.
DEAD_HAND_EXTRA_ACCENTS = {'glove_sport_racer_red': ('g_vId4Color',),
                           'glove_sport_tech_gradient_bright': ('g_vId2Color', 'g_vId3Color'),
                           'glove_sport_camo_winter': ('g_vId7Color',)}
# Colours the user approved on screen; always offered, even outside the glove's range.
DEAD_HAND_EXTRA_THEMES = {'glove_driver_ostrich_purple': ['Sunset'], 'glove_specialist_dragon_blue': ['Inferno'],
                          'glove_specialist_quilted_black': ['Midnight'],
                          'glove_sport_velvet_red': ['Toxic', 'Magenta'],
                          'glove_sport_beadwork_diamonds_purple': ['Rose', 'Azure'],
                          'glove_sport_tech_gradient_bright': ['Aurora', 'Cobalt'], 'glove_sport_racer_red': ['Rose']}
# User: keep only recolours that look proper; drop ones that barely change. Ash only greys the trim of a printed
# glove, and a colour within SAME_DEGREES of the glove's own accent colour looks like the original.
SAME_DEGREES = 20


def distinct_themes(picks, own_hue):
    """Drop Ash and colours that would look like the original (all of a theme's hues near `own_hue`)."""
    def near(h): return min(abs(h - own_hue) % 360, 360 - abs(h - own_hue) % 360) <= SAME_DEGREES
    kept = []
    for name in picks:
        if name in finishes.THEMES:
            base, saturation, spread = finishes.THEMES[name]
            if spread == 0 or near(base): continue
        elif name in finishes.DUO_THEMES:
            a, b, saturation = finishes.DUO_THEMES[name]
            if near(a) and near(b): continue
        kept.append(name)
    return kept
# Every Dead Hand glove gets colours that match its own (user: "use colors that work well with whats already
# there ... same with all dead hand gloves"). Add a finish here to offer every colour on it again.
DEAD_HAND_FREE = set()


def dead_hand_main_hue(source, compmat):
    """Saturation-weighted mean hue (degrees) of the finish's clear, visible accents, or None."""
    report = {}
    try:
        make_dead_hand_finish(source, compmat, 'probe', 'Ash', report=report)
    except (ValueError, NotImplementedError):
        return None
    info = report.get(compmat)
    if not info: return None
    x = y = 0.0
    for name in info['accent_channels']:
        h, saturation, value = colorsys.rgb_to_hsv(*info['original_colours'][name][:3])
        if saturation < .35: continue
        x += saturation * math.cos(h * 2 * math.pi); y += saturation * math.sin(h * 2 * math.pi)
    return None if not x and not y else math.degrees(math.atan2(y, x)) % 360


def harmonious_themes(hue):
    """Themes whose every hue is within HARMONY_DEGREES of `hue`, plus neutral Ash; in theme order."""
    def close(h): return min(abs(h - hue) % 360, 360 - abs(h - hue) % 360) <= HARMONY_DEGREES
    picks = [name for name, (base, saturation, spread) in finishes.THEMES.items() if spread == 0 or close(base)]
    picks += [name for name, (a, b, saturation) in finishes.DUO_THEMES.items() if close(a) and close(b)]
    return picks
# Dead Hand (volatile_02) composites: a LOOSE_VARIABLES container 'paint' names the finish's own material
# (csgo_customglove_preview.vfx) and COPY_MATCHING_KEYS copies its parameters into the shared, all-white
# glove_compositor template. That finish material holds the colours: eight tint-ID region colours plus
# per-layer surface/substrate/burnishing/damage-bevel tints (inspected on the user's
# glove_driver_brocade_phoenix_red files). A recolour edits only those colour vectors in a copy.
DEAD_HAND_SHADERS = ('csgo_customglove_preview.vfx', 'csgo_customglove.vfx')
DEAD_HAND_COLOURS = re.compile(r'^g_v(?:Id[1-8]Color|(?:Surface|Substrate|Burnishing|DamageBevel)ColorTint[1-4])$')
DEAD_HAND_IDS = ['g_vId%dColor' % i for i in range(1, 9)]
DEAD_HAND_FAMILY_DEGREES = 25
# Burnishing and damage-bevel tints only colour worn edges. A finish whose only accents are those (Pillow
# Punchers: an all-white glove with orange scuffs) would look unchanged, so it is not offered as a recolour.
WEAR_ONLY = re.compile(r'^g_v(?:Burnishing|DamageBevel)ColorTint')
DEAD_HAND_FAMILY_SATURATION = .18


def _is_accent(color, threshold=.35, hue_range=None):
    hue,saturation,value = colorsys.rgb_to_hsv(*color[:3])
    return value > .12 and saturation >= threshold and (hue_range is None or hue_range[0] <= hue*360 <= hue_range[1])


def recolor_accents(colors, theme, fade=False, panels='original', accent_saturation=.35, accent_hue_range=None,
                    protect_dark_neutrals=False):
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
        if _is_accent(original,accent_saturation,accent_hue_range):
            hue, target_saturation, _ = colorsys.rgb_to_hsv(*target[:3])
            color[:3] = colorsys.hsv_to_rgb(hue, min(saturation, target_saturation), value)
        elif panels != 'original' and (saturation <= .2 or value <= .12):
            if protect_dark_neutrals and value <= .25:
                result.append(color)
                continue
            if panels == 'white': tone = .82 + .10 * math.sqrt(value)
            elif panels == 'black': tone = .12 + .08 * math.sqrt(value)
            else: tone = .12 + .78 * (1 - value)
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


def diagnostic_node(node):
    """Lossless structural inspection of a local composite, including typed override values.

    Keep object fields as ordered pairs so repeated parameter names are not lost.
    Do not export embedded binary/texture bytes.
    """
    if node.type == kv3.OBJECT:
        value = [[key, diagnostic_node(child)] for key, child in node.value]
    elif isinstance(node.value, list):
        value = [diagnostic_node(child) for child in node.value]
    elif isinstance(node.value, bytes):
        value = {'binary_length':len(node.value)}
    else:
        value = node.value
    return dict(type=node.type, flag=node.flag, subtype=node.subtype, value=value)


def _dead_hand_paint(root):
    """The 'paint' resource-material variable of a Dead Hand composite, when its parameters are copied into
    the compositor; otherwise None."""
    found, copies = [], []

    def walk(node):
        if node.type == kv3.OBJECT:
            kind, alias = node.get('m_nCompositeMaterialInputContainerSourceType'), node.get('m_strAlias')
            if (kind and kind.value == 'CONTAINER_SOURCE_TYPE_LOOSE_VARIABLES' and alias and alias.value == 'paint'):
                variables = node.get('m_vecLooseVariables')
                for variable in (variables.value if variables and isinstance(variables.value, list) else []):
                    vtype = variable.get('m_nVariableType') if variable.type == kv3.OBJECT else None
                    material = variable.get('m_strResourceMaterial') if variable.type == kv3.OBJECT else None
                    if (vtype and vtype.value == 'LOOSE_VARIABLE_TYPE_RESOURCE_MATERIAL' and material is not None
                            and material.type == kv3.STRING):
                        found.append(material)
            command, src = node.get('m_nMutatorCommandType'), node.get('m_strCopyMatchingKeys_InputContainerSrc')
            if command and command.value == 'COMP_MAT_PROPERTY_MUTATOR_COPY_MATCHING_KEYS' and src and src.value == 'paint':
                copies.append(node)
            for _, child in node.value: walk(child)
        elif isinstance(node.value, list):
            for child in node.value: walk(child)
    walk(root)
    return found[0] if len(found) == 1 and copies else None


def dead_hand_colours(m_root):
    """{name: vector node} for the finish material's colour vectors, or None without all eight tint-ID colours."""
    params = m_root.get('m_vectorParams')
    if params is None or not isinstance(params.value, list): return None
    found = {}
    for entry in params.value:
        if entry.type != kv3.OBJECT: continue
        name, value = entry.get('m_name'), entry.get('m_value')
        if name and value and DEAD_HAND_COLOURS.match(name.value) and isinstance(value.value, list) and len(value.value) == 4:
            found[name.value] = value
    return found or None


def dead_hand_accents(colours):
    """Indices to recolour: the clear accents (as for classic gloves) plus muted shades of the same colours.

    Dead Hand finishes spread one colour over several tint-ID regions and wear layers, many of them muted
    (Plum Quill's purple ostrich sits at saturation ~.3, so recolouring only the strong purples left it purple).
    A muted colour joins only when it is close in hue to a clear accent; greys, whites and unrelated muted
    colours (cream, tan) are kept."""
    hsv = [colorsys.rgb_to_hsv(*c[:3]) for c in colours]
    strong = {i for i, c in enumerate(colours) if _is_accent(c)}
    hues = [hsv[i][0] * 360 for i in strong]
    near = lambda h: any(min(abs(h - x) % 360, 360 - abs(h - x) % 360) <= DEAD_HAND_FAMILY_DEGREES for x in hues)
    family = {i for i, (h, s, v) in enumerate(hsv)
              if i not in strong and v > .12 and s >= DEAD_HAND_FAMILY_SATURATION and near(h * 360)}
    return strong | family


def make_dead_hand_finish(source, compmat_path, new_name, theme, report=None, inspection=None):
    """(vcompmat bytes, vmat bytes) for a Dead Hand recolour, or None when the composite is not that layout.

    Only colour vectors change: textures, normals, roughness, wear, placement and every other parameter stay
    byte-for-byte as shipped. The same accent-only policy as the classic gloves: chromatic colours take the
    theme hue with their brightness, alpha and (capped) saturation; greys, whites and blacks are untouched."""
    compmat = source.read(compmat_path + '_c')
    if compmat is None: return None
    _, blocks = kv3.read_resource(compmat)
    data = dict(blocks).get('DATA')
    if data is None: return None
    guid, root = kv3.read_kv3(data)
    paint = _dead_hand_paint(root)
    if paint is None: return None
    material = source.read(paint.value + '_c')
    if material is None: return None
    _, m_blocks = kv3.read_resource(material)
    m_data = dict(m_blocks).get('DATA')
    if m_data is None: return None
    m_guid, m_root = kv3.read_kv3(m_data)
    shader = m_root.get('m_shaderName')
    colours = dead_hand_colours(m_root)
    if inspection is not None:
        inspection.setdefault(compmat_path, {}).update(
            dead_hand_material=paint.value, dead_hand_shader=shader.value if shader else '',
            dead_hand_colours={name: [v.value for v in node.value] for name, node in sorted((colours or {}).items())})
    if shader is None or shader.value not in DEAD_HAND_SHADERS or colours is None: return None
    names = [n for n in DEAD_HAND_IDS if n in colours] + sorted(n for n in colours if n not in DEAD_HAND_IDS)
    current = [[item.value for item in colours[name].value] for name in names]
    if any(len(c) != 4 or any(not math.isfinite(v) or v < 0 or v > 1 for v in c) for c in current): return None
    accents = dead_hand_accents(current)
    base = compmat_path.rsplit('/', 1)[-1].replace('.vcompmat', '')
    extra = {i for i, n in enumerate(names) if n in DEAD_HAND_EXTRA_ACCENTS.get(base, ())}
    accents |= extra
    themed = finishes.recolor(current, theme, keep_value=True)
    new = []
    for index, (original, target) in enumerate(zip(current, themed)):
        color = list(original)
        if index in accents:
            _, saturation, value = colorsys.rgb_to_hsv(*original[:3])
            hue, target_saturation, _ = colorsys.rgb_to_hsv(*target[:3])
            # Hand-picked pale regions take a visible share of the theme colour instead of their own near-grey.
            cap = .5 if index in extra else saturation
            color[:3] = colorsys.hsv_to_rgb(hue, min(cap, target_saturation), value)
        new.append(color)
    accents = [names[i] for i in sorted(accents)]
    if report is not None:
        report[compmat_path] = {'original_colours': dict(zip(names, current)), 'accent_vectors': accents,
                                'accent_channels': [n for n in accents if not WEAR_ONLY.match(n)], 'policy': 'dead-hand-accent-only-v1',
                                'family_rule': [DEAD_HAND_FAMILY_DEGREES, DEAD_HAND_FAMILY_SATURATION],
                                'material': paint.value}
    if inspection is not None:
        inspection[compmat_path]['status'] = 'supported Dead Hand finish material'
    if not accents: return None
    for name, color in zip(names, new):
        for item, value in zip(colours[name].value, color): item.value = value
    vmat_path = VMAT_DIR + new_name + '.vmat'
    material_name = m_root.get('m_materialName')
    if material_name is not None: material_name.value = vmat_path
    paint.value = vmat_path
    return (finishes._with_block(compmat, 'DATA', kv3.write_kv3(guid, root)),
            finishes._with_block(material, 'DATA', kv3.write_kv3(m_guid, m_root)))


def make_glove_finish(source, compmat_path, new_name, theme, fade=False, panels='original', report=None, inspection=None):
    """(vcompmat bytes, vmat bytes) for a recolour, or None when the finish is not an eight-tint glove material."""
    compmat = source.read(compmat_path + '_c')
    if compmat is None: return None
    _, blocks = kv3.read_resource(compmat)
    data = dict(blocks).get('DATA')
    if data is None: return None
    guid, root = kv3.read_kv3(data)
    specific = finishes._specific_material(root)
    if inspection is not None:
        inspection.setdefault(compmat_path, {}).update({'status':'unsupported composite layout',
            'root_fields':[key for key,_ in root.value] if root.type == kv3.OBJECT else []})
        if '/volatile_02/' in compmat_path:
            inspection[compmat_path]['composite_document'] = diagnostic_node(root)
            inspection[compmat_path]['report_version'] = 2
    if specific is None: return None
    material = source.read(specific.value + '_c')
    if material is None: return None
    _, m_blocks = kv3.read_resource(material)
    m_data = dict(m_blocks).get('DATA')
    if m_data is None: return None
    m_guid, m_root = kv3.read_kv3(m_data)
    shader = m_root.get('m_shaderName')
    if inspection is not None:
        vectors = m_root.get('m_vectorParams')
        inspection[compmat_path].update(material=specific.value, shader=shader.value if shader else '',
            vectors={entry.get('m_name').value:[v.value for v in entry.get('m_value').value]
                for entry in vectors.value if entry.type == kv3.OBJECT and entry.get('m_name') and entry.get('m_value')
                    and isinstance(entry.get('m_value').value,list)}
                if vectors and isinstance(vectors.value,list) else {})
    if shader is None or shader.value != 'csgo_customglove.vfx': return None
    tints = _tints(m_root)
    if tints is None:
        if inspection is not None:
            inspection[compmat_path]['status']='composite overrides require inspection; template has no classic tints'
        return None
    if inspection is not None: inspection[compmat_path]['status']='supported eight-tint material'
    current = [[item.value for item in tints[name].value] for name in TINTS]
    if any(len(color) != 4 for color in current): return None
    approved = panels == 'original' and (compmat_path, theme) in APPROVED_PALETTES
    threshold = ACCENT_THRESHOLDS.get(compmat_path,.35)
    hue_range = ACCENT_HUE_RANGES.get(compmat_path)
    protect_dark = compmat_path == 'gloves/paints/slick_jaguar_white.vcompmat'
    try:
        new = (finishes.recolor(current, theme, fade=fade, keep_value=True) if approved else
               recolor_accents(current, theme, fade=fade, panels=panels,accent_saturation=threshold,accent_hue_range=hue_range,
                               protect_dark_neutrals=protect_dark))
    except ValueError: return None
    if report is not None:
        report[compmat_path] = {
            'original_tints': current,
            'accent_channels': [i+1 for i,c in enumerate(current)
                if _is_accent(c,threshold,hue_range)],
            'accent_saturation_threshold': threshold,
            'accent_hue_range_degrees': hue_range,
            'protect_dark_neutrals': protect_dark,
            'policy': 'accent-only-v1',
            'preserved_legacy_themes': sorted(t for path,t in APPROVED_PALETTES if path == compmat_path),
        }
    if panels != 'original' and new == recolor_accents(current, theme, fade=fade,accent_saturation=threshold,accent_hue_range=hue_range,
                                                     protect_dark_neutrals=protect_dark): return None
    for name, color in zip(TINTS, new):
        for item, value in zip(tints[name].value, color): item.value = value
    vmat_path = VMAT_DIR + new_name + '.vmat'
    name = m_root.get('m_materialName')
    if name is not None: name.value = vmat_path
    specific.value = vmat_path
    return (finishes._with_block(compmat, 'DATA', kv3.write_kv3(guid, root)),
            finishes._with_block(material, 'DATA', kv3.write_kv3(m_guid, m_root)))


def plan(source_text, gold_pools_text, titles, source, known_ids, used_ids, panel_variants=True, report=None, inspection=None):
    """(files, kit entries, case items, {glove name: def index}); deterministic for the same game files.

    known_ids: saved {kit name: id}; used_ids: ids already given out this run (knife recolours)."""
    gloves, official, kits = glove_info(source_text, gold_pools_text)
    files, entries, case = {}, [], []
    palette_report = report if report is not None else {}
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
            # Use the schema's actual path for newer gloves. Only the verified
            # eight-tint shader is recoloured; other formats are reported for inspection.
            compmat = values.get('composite_material_path') or 'gloves/paints/%s.vcompmat' % base
            picks = themes[:]
            random.Random(base).shuffle(picks)
            picks = picks[:THEMES_PER_GLOVE] + (list(finishes.GRADIENT_THEMES) if base in GLOVE_FADES else [])
            if base in DEAD_HAND_SKIP: picks = []
            elif base in DEAD_HAND_PRINT_HUES: picks = harmonious_themes(DEAD_HAND_PRINT_HUES[base])
            elif '/volatile_02/' in compmat and base not in DEAD_HAND_FREE:
                hue = dead_hand_main_hue(source, compmat)
                if hue is not None: picks = harmonious_themes(hue)
            if '/volatile_02/' in compmat and base not in DEAD_HAND_FREE and picks:
                own = dead_hand_main_hue(source, compmat)
                if own is not None: picks = distinct_themes(picks, own)
            if base in DEAD_HAND_EXTRA_THEMES and base not in DEAD_HAND_SKIP:
                picks += [t for t in DEAD_HAND_EXTRA_THEMES[base] if t not in picks]
            # Owned recolours keep rendering even when their colour is no longer offered.
            retained = [t for t in themes if t not in picks and 'rg_%s_%s' % (base, t.lower()) in known_ids]
            offered = set(picks)
            picks = picks + retained
            base_title = GLOVE_TITLES.get(base) or titles.get(base) or base.split('_', 1)[-1].replace('_', ' ').title()
            for theme in picks:
                for panels, panel_title in PANEL_STYLES.items():
                    suffix = '' if panels == 'original' else '_panels_' + panels
                    name = 'rg_%s_%s%s' % (base, theme.lower(), suffix)
                    # Retain known variants in the schema if disabled later, but stop offering them as drops.
                    if panels != 'original' and not panel_variants and name not in known_ids: continue
                    no_panels = panels != 'original' and compmat in NO_PANEL_VARIANTS
                    if no_panels and name not in known_ids: continue
                    try:
                        made = None
                        if '/volatile_02/' in compmat:
                            # Dead Hand: original panels only. Its white tints are identity multipliers of
                            # whole material layers, so the panel variants' neutral rewrite would black them out.
                            if panels != 'original': continue
                            made = make_dead_hand_finish(source, compmat, name, theme, report=palette_report,
                                                         inspection=inspection)
                        dead_hand = palette_report.get(compmat, {}).get('policy') == 'dead-hand-accent-only-v1'
                        if made is None and not dead_hand:
                            made = make_glove_finish(source, compmat, name, theme, fade=base in GLOVE_FADES,
                                                     panels='original' if no_panels else panels,
                                                     report=palette_report, inspection=inspection)
                    except (ValueError, NotImplementedError) as error:
                        if not values.get('composite_material_path'): raise
                        if inspection is not None:
                            inspection[compmat] = {'status':'unsupported resource format', 'reason':str(error)}
                        continue
                    if not made: continue
                    has_accents = bool(palette_report[compmat]['accent_channels'])
                    # Do not sell differently named themes that cannot colour this source palette.
                    # Keep every known definition/material so already-owned items still render.
                    if not has_accents and name not in known_ids: continue
                    files[COMPMAT_DIR + name + '.vcompmat_c'], files[VMAT_DIR + name + '.vmat_c'] = made
                    # Panel style remains in the stable kit identity, not the player-facing name.
                    title = '%s %s' % (base_title, theme)
                    entries.append((kit_id(name), name, title,
                                    {'composite_material_path': COMPMAT_DIR + name + '.vcompmat'}))
                    if (has_accents and not no_panels and theme in offered and
                            (panel_variants or panels == 'original')): case.append('[%s]%s' % (name, glove))
    return files, entries, sorted(set(case)), {name: int(key) for name, key in gloves.items()}


TEST_CASE_NAME = 'crate_cs2gc_dead_hand_test'
TEST_CASE_TITLE = 'Dead Hand Test Case'


def dead_hand_test_items(case):
    """Gauntlet entries that are Dead Hand recolours: every Dead Hand paint kit name starts with glove_, no
    classic one does. For the grant-only test case (never in the Armory or Store)."""
    return [item for item in case if item.startswith('[rg_glove_')]


def test_case_spec(items):
    return dict(name=TEST_CASE_NAME, title=TEST_CASE_TITLE, base=CASE_BASE, items=items,
                description='Test case: only the Dead Hand glove recolours from the Gauntlet Case. '
                            'Only given by grant_dead_hand_test_cases.cmd.')


def case_spec(items):
    return dict(name=CASE_NAME, title=CASE_TITLE, description=CASE_DESCRIPTION, base=CASE_BASE, items=items)

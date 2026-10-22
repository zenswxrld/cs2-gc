"""The 36 custom gun collections, rebuilt from every gun finish in the installed game (user, 22 Oct 2026:
"remake the custom collections using every skin in the game (guns only)").

Each official gun finish is read from the game and sorted by what its shader can actually do:

- recolourable: the finish's look comes from its four g_vColor colours (solid, hydrographic, spray paint,
  anodized, anodized multicolour/airbrushed), wherever the composite actually binds them (its exposed
  parameters or its material). Custom paint, patina, gunsmith and case-hardened finishes take their colours
  from textures, so new colour values change nothing on them (the "copies with 0 change").
- transferable: a tiling pattern that fits any gun. Finishes painted for one gun's UV layout (the shader's
  g_bIgnoreWeaponSizeScale, per-gun paint-by-number masks, custom paint, gunsmith, or a gun in the name)
  only stay on the gun they were made for.

A finish that is neither can not become a new skin, so it is not used. Every other finish is used at most
once across all 36 collections, and nothing in a collection looks like an official skin: a recolour changes
every colour (greys included), and an original colourway only appears on a gun that pattern never shipped on.

Layout per collection (like the stock ones): 1 Covert chase, 2 Classified, 3 Restricted, 4 Mil-Spec,
6 Industrial. The chase and one Classified are colour families (one name, a random colour of the
collection's palette when unboxed); a few chases reuse the knife-finish families (Doppler, Gamma Doppler...).

The lineup is saved in cs2_gc_gun_collections.json so a later game update can not reshuffle owned skins;
every kit it ever named keeps its definition.
"""
import colorsys
import json
import random
import re

import kv3

VERSION = 1
LINEUP_FILE = 'cs2_gc_gun_collections.json'
TIER_COUNTS = (('ancient', 1), ('legendary', 2), ('mythical', 3), ('rare', 4), ('uncommon', 6))
RANK = {name: i for i, name in enumerate(('common', 'uncommon', 'rare', 'mythical', 'legendary', 'ancient'))}
# What each slot of a collection is, highest tier first (16 slots).
SLOT_MODES = {'ancient': ('family',), 'legendary': ('family', 'fixed'), 'mythical': ('fixed', 'fixed', 'fixed'),
              'rare': ('fixed', 'fixed', 'fixed', 'transfer'),
              'uncommon': ('fixed', 'fixed', 'fixed', 'fixed', 'transfer', 'transfer')}
CHASE_GUNS = ('weapon_ak47', 'weapon_m4a1', 'weapon_m4a1_silencer', 'weapon_awp', 'weapon_deagle')
FEATURED_GUNS = {
    'legendary': ('weapon_usp_silencer', 'weapon_glock', 'weapon_ak47', 'weapon_m4a1', 'weapon_m4a1_silencer',
                  'weapon_awp', 'weapon_deagle', 'weapon_aug', 'weapon_sg556', 'weapon_famas', 'weapon_galilar'),
    'mythical': ('weapon_usp_silencer', 'weapon_glock', 'weapon_p250', 'weapon_fiveseven', 'weapon_tec9',
                 'weapon_cz75a', 'weapon_mp9', 'weapon_mac10', 'weapon_mp7', 'weapon_ump45', 'weapon_ssg08',
                 'weapon_p90', 'weapon_aug', 'weapon_sg556', 'weapon_famas', 'weapon_galilar')}
# Knife-finish colour families (native_skins.FAMILIES, built by native_skins.collections) as a few chases:
# "dont make the chase all dopplers and other knife finishes a few is okay".
KNIFE_CHASES = {'nebula': 'doppler', 'aurora': 'gamma', 'kaleido': 'marble_fade', 'solstice': 'fade',
                'outrider': 'tiger_tooth', 'driftwood': 'damascus'}
# Each collection's palette, spread round the colour wheel so chases are not all red. The first four colour
# the fixed skins; all six make the chase family, the first four the Classified family.
IDENTITIES = {
    'ashfall': ('Ember', 'Amber', 'Crimson', 'Inferno', 'Lava', 'Sunset'),
    'aurora': ('Emerald', 'Teal', 'Violet', 'Aurora', 'Toxin', 'Galaxy'),
    'brimstone': ('Inferno', 'Crimson', 'Amber', 'Lava', 'Ember', 'Coral'),
    'cascade': ('Azure', 'Teal', 'Ocean', 'Glacier', 'Cobalt', 'Frost'),
    'cinder': ('Ember', 'Amber', 'Lava', 'Sunset', 'Crimson', 'Sunrise'),
    'eclipse': ('Violet', 'Midnight', 'Cobalt', 'Galaxy', 'Magenta', 'Royal'),
    'halcyon': ('Azure', 'Rose', 'Glacier', 'Frost', 'Teal', 'Coral'),
    'kaleido': ('Candy', 'Vapor', 'Magenta', 'Lime', 'Rainbow', 'Toxin'),
    'monsoon': ('Cobalt', 'Teal', 'Ocean', 'Forest', 'Azure', 'Glacier'),
    'nebula': ('Galaxy', 'Violet', 'Magenta', 'Midnight', 'Royal', 'Vapor'),
    'solstice': ('Amber', 'Sunrise', 'Rose', 'Sunset', 'Ember', 'Coral'),
    'zephyr': ('Lime', 'Teal', 'Emerald', 'Forest', 'Glacier', 'Toxin'),
    'tidewater': ('Ocean', 'Teal', 'Azure', 'Glacier', 'Cobalt', 'Emerald'),
    'obelisk': ('Cobalt', 'Midnight', 'Royal', 'Violet', 'Galaxy', 'Frost'),
    'zenith': ('Azure', 'Amber', 'Royal', 'Frost', 'Sunrise', 'Teal'),
    'rampart': ('Emerald', 'Amber', 'Forest', 'Lime', 'Teal', 'Ember'),
    'ironclad': ('Cobalt', 'Frost', 'Glacier', 'Azure', 'Teal', 'Midnight'),
    'marauder': ('Crimson', 'Ember', 'Lava', 'Inferno', 'Rose', 'Amber'),
    'nightwatch': ('Midnight', 'Violet', 'Cobalt', 'Galaxy', 'Royal', 'Azure'),
    'outrider': ('Amber', 'Ember', 'Forest', 'Sunset', 'Lime', 'Coral'),
    'quarry': ('Amber', 'Lime', 'Forest', 'Emerald', 'Sunrise', 'Teal'),
    'redoubt': ('Crimson', 'Cobalt', 'Royal', 'Inferno', 'Azure', 'Violet'),
    'talisman': ('Magenta', 'Emerald', 'Amber', 'Royal', 'Teal', 'Toxin'),
    'undertow': ('Teal', 'Cobalt', 'Ocean', 'Midnight', 'Emerald', 'Glacier'),
    'forged': ('Ember', 'Amber', 'Lava', 'Inferno', 'Crimson', 'Sunrise'),
    'phantom_blade': ('Violet', 'Midnight', 'Galaxy', 'Magenta', 'Cobalt', 'Royal'),
    'harbor': ('Azure', 'Teal', 'Rose', 'Ocean', 'Coral', 'Glacier'),
    'mosaic': ('Candy', 'Vapor', 'Sunrise', 'Lime', 'Rainbow', 'Coral'),
    'kestrel': ('Amber', 'Azure', 'Rose', 'Sunrise', 'Teal', 'Coral'),
    'juggernaut': ('Crimson', 'Cobalt', 'Inferno', 'Lava', 'Royal', 'Midnight'),
    'lodestar': ('Cobalt', 'Amber', 'Galaxy', 'Royal', 'Azure', 'Violet'),
    'fathom': ('Teal', 'Cobalt', 'Midnight', 'Ocean', 'Glacier', 'Emerald'),
    'cipher': ('Lime', 'Emerald', 'Toxic', 'Teal', 'Toxin', 'Aurora'),
    'driftwood': ('Amber', 'Teal', 'Forest', 'Rose', 'Coral', 'Sunset'),
    'insignia': ('Amber', 'Cobalt', 'Royal', 'Crimson', 'Azure', 'Rose'),
    'warden': ('Emerald', 'Cobalt', 'Frost', 'Forest', 'Glacier', 'Teal'),
}
# Recolourable styles (F_PAINT_STYLE): 0 solid, 1 hydrographic, 2 spray paint, 3 anodized,
# 4 anodized multicolour, 5 anodized airbrushed. 6 custom paint, 7 patina and 8 gunsmith use texture colours.
COLOUR_STYLES = (0, 1, 2, 3, 4, 5)
STYLE_SCORE = {4: 3, 5: 3, 1: 2, 2: 2, 0: 1, 3: 1, 7: 1}
COLOUR_WORDS = {'red', 'blue', 'green', 'orange', 'yellow', 'purple', 'pink', 'black', 'white', 'grey', 'gray',
                'gold', 'golden', 'silver', 'teal', 'cyan', 'crimson', 'navy', 'violet', 'brown', 'tan', 'olive',
                'azure', 'cobalt', 'emerald', 'amber', 'magenta', 'rose', 'lime', 'jade', 'scarlet', 'indigo'}
MIN_CHANGE = .14  # mean RGB distance a recolour must move its colours by


def plain(node):
    value = node.value
    if isinstance(value, list):
        if value and all(isinstance(item, tuple) for item in value):
            return {key: plain(child) for key, child in value}
        return [plain(child) for child in value]
    if isinstance(value, (bytes, bytearray)): return None
    return value


def _loose(variable):
    kind = variable.get('m_nVariableType', '')
    if kind.endswith('COLOR4'): return [c / 255 for c in variable['m_cValueColor4'][:3]]
    if kind.endswith('RESOURCE_TEXTURE'):
        return variable.get('m_strTextureRuntimeResourcePath') or variable.get('m_strTextureContentAssetPath')
    if kind.endswith('BOOLEAN'): return int(bool(variable.get('m_bValueBoolean')))
    if kind.endswith('INTEGER1'): return variable.get('m_nValueIntX', 0)
    values = [variable.get('m_flValueFloat' + axis, 0.0) for axis in 'XYZW']
    return values[0] if kind.endswith('FLOAT1') else values


def effective_params(compmat, material):
    """The parameters the game renders with: the material's, overridden by the composite's loose variables.
    compmat/material: plain() dicts."""
    params = {}
    for entry in (material or {}).get('m_intParams') or []: params[entry['m_name']] = entry['m_nValue']
    for entry in (material or {}).get('m_floatParams') or []: params[entry['m_name']] = entry['m_flValue']
    for entry in (material or {}).get('m_vectorParams') or []: params[entry['m_name']] = list(entry['m_value'])[:3]
    for entry in (material or {}).get('m_textureParams') or []: params[entry['m_name']] = entry['m_pValue']

    def walk(node):
        if isinstance(node, dict):
            for variable in node.get('m_vecLooseVariables') or []:
                name = variable.get('m_strName', '')
                if name.startswith(('g_', 'F_')):
                    try: params[name] = _loose(variable)
                    except (KeyError, TypeError): pass
            for child in node.values(): walk(child)
        elif isinstance(node, list):
            for child in node: walk(child)
    walk(compmat or {})
    return params


def classify(name, params):
    """(recolourable, transferable) from the rendered parameters."""
    from native_finishes import WEAPON_WORDS
    style = params.get('F_PAINT_STYLE', 0)
    colours = all('g_vColor%d' % i in params for i in range(4))
    recolourable = style in COLOUR_STYLES and colours and params.get('F_CASE_HARDENING') != 1
    gun_layout = (params.get('g_bIgnoreWeaponSizeScale') == 1 or params.get('g_bOverrideDefaultMasks') == 1
                  or style in (6, 8))
    transferable = not gun_layout and not any(word in name for word in WEAPON_WORDS)
    return recolourable, transferable


def _read(source, path):
    data = source.read(path + '_c')
    if data is None: return None
    try:
        _, blocks = kv3.read_resource(data)
        guid, root = kv3.read_kv3(dict(blocks)['DATA'])
    except (ValueError, KeyError, IndexError, UnicodeDecodeError):
        return None
    return data, guid, root


def inspect(source, kit_path):
    """{'params', 'compmat', 'material'} for one finish, or None when it can not be read."""
    import native_finishes as finishes
    comp = _read(source, kit_path)
    if comp is None: return None
    specific = finishes._specific_material(comp[2])
    if specific is None: return None
    mat = _read(source, specific.value)
    if mat is None: return None
    return {'params': effective_params(plain(comp[2]), plain(mat[2])), 'compmat': comp, 'material': mat,
            'specific': specific.value}


def distance(first, second):
    return sum(sum((a - b) ** 2 for a, b in zip(x[:3], y[:3])) ** .5 for x, y in zip(first, second)) / len(first)


def visible_change(original, changed):
    """Every colour moves (greys too), so whichever channels a pattern uses look different."""
    moved = [sum((a - b) ** 2 for a, b in zip(x[:3], y[:3])) ** .5 for x, y in zip(original, changed)]
    return sum(m >= .08 for m in moved) >= len(moved) - 1 and sum(moved) / len(moved) >= MIN_CHANGE


def _colour_bindings(root):
    """{g_vColorN: [loose variable nodes]} from the composite's exposed parameters."""
    found = {}

    def visit(node):
        if node.type == kv3.OBJECT:
            variables = node.get('m_vecLooseVariables')
            if variables is not None and isinstance(variables.value, list):
                for item in variables.value:
                    if item.type != kv3.OBJECT: continue
                    name, colour = item.get('m_strName'), item.get('m_cValueColor4')
                    if name is not None and colour is not None and re.fullmatch(r'g_vColor[0-3]', str(name.value)):
                        found.setdefault(name.value, []).append(colour)
            for _, child in node.value: visit(child)
        elif isinstance(node.value, list):
            for child in node.value: visit(child)
    visit(root)
    return found


def make_recolour(source, kit, kit_path, new_name, theme):
    """(vcompmat bytes, vmat bytes, original colours, new colours) or None when the recolour would not show."""
    import native_finishes as finishes
    comp, mat = _read(source, kit_path), None
    if comp is None: return None
    data, guid, root = comp
    specific = finishes._specific_material(root)
    if specific is None: return None
    mat = _read(source, specific.value)
    if mat is None: return None
    m_data, m_guid, m_root = mat
    bindings = _colour_bindings(root)
    template = finishes._vector_params(m_root, allow_partial=True) or {}
    original = []
    for index in range(4):
        key = 'g_vColor%d' % index
        if bindings.get(key):
            colour = [c.value / 255 for c in bindings[key][0].value][:3]
        elif key in template:
            colour = [c.value for c in template[key].value][:3]
        else:
            return None
        original.append(colour + [1.0])
    changed = finishes.recolor(original, theme, fade=kit in finishes.FADE_BASES)
    if not visible_change(original, changed): return None
    if max(finishes.brightness(c) for c in changed) < 110 / 255: return None
    for index in range(4):
        key = 'g_vColor%d' % index
        for colour in bindings.get(key, ()):
            for channel, value in zip(colour.value, changed[index]): channel.value = max(0, min(255, round(value * 255)))
        if key in template:
            for channel, value in zip(template[key].value, changed[index]): channel.value = value
    owned = finishes.VMAT_DIR + new_name + '.vmat'
    specific.value = owned
    label = m_root.get('m_materialName')
    if label is not None: label.value = owned
    return (finishes._with_block(data, 'DATA', kv3.write_kv3(guid, root)),
            finishes._with_block(m_data, 'DATA', kv3.write_kv3(m_guid, m_root)), original, changed)


def clean_title(title):
    words = title.split()
    while len(words) > 1 and words[0].lower().strip(',') in COLOUR_WORDS: words = words[1:]
    return ' '.join(words)


def colour_title(base_title, theme):
    colour = {'Royal': 'Royal', 'Galaxy': 'Galaxy', 'Ocean': 'Ocean', 'Forest': 'Forest', 'Lava': 'Lava',
              'Toxin': 'Toxic', 'Toxic': 'Toxic'}.get(theme, theme)
    return '%s %s' % (colour, clean_title(base_title))


def official_rarities(source_text):
    """Paint kit rarity: paint_kits_rarity, else the highest tier list of a collection that holds it."""
    rarities = {}
    for tier_name, body in re.findall(r'"[a-z0-9_]+?_(common|uncommon|rare|mythical|legendary|ancient)"\s*\{([^{}]*)\}',
                                      source_text):
        for kit in re.findall(r'"\[([^\]]+)\]weapon_', body):
            if RANK[tier_name] > RANK.get(rarities.get(kit), -1): rarities[kit] = tier_name
    block = re.search(r'"paint_kits_rarity"\s*\{([^}]*)\}', source_text)
    if block:
        rarities.update({k: v for k, v in re.findall(r'"([^"]+)"\s+"([^"]+)"', block.group(1)) if v in RANK})
    return rarities


def gun_finishes(source_text):
    """{paint kit: set of guns it ships on} (no knives, no gloves)."""
    found = {}
    for kit, weapon in re.findall(r'"\[([^\]]+)\](weapon_[a-z0-9_]+)"', source_text):
        if 'knife' not in weapon and weapon != 'weapon_bayonet': found.setdefault(kit, set()).add(weapon)
    return found


def study(source, kits, kit_path, source_text, titles):
    """{kit: row} for every gun finish that can become a new skin."""
    shipped = gun_finishes(source_text)
    rarities = official_rarities(source_text)
    rows, patterns = {}, {}
    for kit in sorted(shipped):
        if kit not in kits or not (titles.get(kit) or '').strip() or 'chalice' in kit: continue
        found = inspect(source, kit_path(kit, kits[kit][1]))
        if found is None: continue
        params = found['params']
        recolourable, transferable = classify(kit, params)
        pattern = params.get('g_tPattern') or found['specific']
        patterns.setdefault(pattern, set()).update(shipped[kit])
        if recolourable or transferable:
            rows[kit] = {'guns': sorted(shipped[kit]), 'recolour': recolourable, 'transfer': transferable,
                         'style': params.get('F_PAINT_STYLE', 0), 'rarity': rarities.get(kit, 'rare'), 'pattern': pattern}
    for row in rows.values(): row['pattern_guns'] = sorted(patterns.get(row['pattern'], ()))
    return rows


def _score(row):
    return STYLE_SCORE.get(row['style'], 1) * 10 + RANK.get(row['rarity'], 2)


def plan(rows, guns, icons, families, works=lambda donor, mode, themes: True, seed='cs2gc-v1'):
    """{icon: [entry]} where entry = {tier, weapon, mode, donor | family, themes}. Deterministic."""
    used, gun_count, lineup, looks = set(), {}, {icon: [] for icon in icons}, set()
    pool = sorted(rows)
    # Two passes: every collection's chase first, so the 36 chases get the best finishes, then the rest.
    for first_pass, (index, icon) in [(p, item) for p in (True, False) for item in enumerate(icons)]:
        rng = random.Random('%s:%s:%d' % (seed, icon, first_pass))
        palette = IDENTITIES.get(icon, ('Azure', 'Amber', 'Emerald', 'Violet', 'Rose', 'Teal'))
        entries = lineup[icon]
        taken = {e['weapon'] for e in entries}
        chase_gun = CHASE_GUNS[index % len(CHASE_GUNS)]
        knife = KNIFE_CHASES.get(icon)
        for tier, count in (TIER_COUNTS[:1] if first_pass else TIER_COUNTS[1:]):
            for slot, mode in enumerate(SLOT_MODES[tier]):
                if tier == 'ancient' and knife and 'cgf_%s_ancient' % knife in families:
                    entries.append({'tier': tier, 'weapon': chase_gun, 'mode': 'knife_family', 'family': knife})
                    taken.add(chase_gun); continue
                fixed_guns = (chase_gun,) if tier == 'ancient' else None
                preferred = set(FEATURED_GUNS.get(tier, ()))

                def options(name):
                    row = rows[name]
                    if mode in ('family', 'fixed') and not row['recolour']: return []
                    if mode == 'transfer' and not row['transfer']: return []
                    if mode == 'transfer':
                        choices = [g for g in guns if g not in row['pattern_guns']]
                    elif row['transfer']:
                        choices = list(guns)
                    else:
                        choices = [g for g in row['guns'] if g in guns]
                    if fixed_guns: choices = [g for g in choices if g in fixed_guns]
                    return [g for g in choices if g not in taken and (name, g, tuple(themes)) not in looks]
                target = RANK[tier]

                def ranked(names):
                    names = list(names)
                    rng.shuffle(names)
                    # Finishes that can move between guns are scarce: recolour slots below Classified use the
                    # ones that must stay on their own gun first, keeping the movable ones for the transfer slots.
                    names.sort(key=lambda n: (
                        rows[n]['transfer'] and mode == 'fixed' and tier not in ('ancient', 'legendary'),
                        abs(RANK.get(rows[n]['rarity'], 2) - target) if tier not in ('ancient', 'legendary') else 0,
                        -_score(rows[n]) if tier in ('ancient', 'legendary', 'mythical') else 0))
                    return names
                themes = (list(palette) if tier == 'ancient' else list(palette[:4]) if mode == 'family'
                          else [palette[(slot + RANK[tier]) % 4]] if mode == 'fixed' else [])
                # The first donor whose new colours really show (works() makes and checks the materials).
                in_collection = {e.get('donor') for e in entries}
                donor = next((n for n in ranked(n for n in pool if n not in used and options(n))
                              if works(n, mode, themes)), None)
                if donor is None:  # every fitting finish is used: a second use, never twice in one collection
                    donor = next((n for n in ranked(n for n in pool if n not in in_collection and options(n))
                                  if works(n, mode, themes)), None)
                if donor is None: continue
                choices = options(donor)
                rng.shuffle(choices)
                choices.sort(key=lambda g: (g not in preferred, gun_count.get(g, 0)))
                weapon = choices[0]
                entries.append({'tier': tier, 'weapon': weapon, 'mode': mode, 'donor': donor, 'themes': themes})
                used.add(donor); taken.add(weapon); gun_count[weapon] = gun_count.get(weapon, 0) + 1
                looks.add((donor, weapon, tuple(themes)))
    return lineup


def kit_name(icon, entry, theme=None):
    if entry['mode'] == 'knife_family': return 'cgf_%s_ancient' % entry['family']
    base = 'gc3%s_%s_%s_%s_%s' % ({'family': 'f', 'fixed': 'r', 'transfer': 't'}[entry['mode']], icon, entry['donor'],
                                   entry['weapon'].removeprefix('weapon_'), entry['tier'])
    return base + ('_' + theme.lower() if theme else '')


def build(source_text, kits, titles, kit_path, source, families, lineup_path=None, icons=None, report=None):
    """(new kit entries [(name, title, values)], files {path: bytes}, loot lists text, [list names],
    [loot entries], {list name: icon}). families is extended in place with the new colour families."""
    import native_finishes as finishes
    from native_skins import CASE_ICONS, CASE_PREFIX, _collection_lists, paint_rarity_for_weapon, weapon_rarity_tags
    icons = list(icons or CASE_ICONS)
    report = report if report is not None else {}
    guns = sorted({w for found in gun_finishes(source_text).values() for w in found
                   if re.search(r'"name"\s+"%s"' % w, source_text) and w not in ('weapon_taser',)})
    stored = {}
    if lineup_path is not None and lineup_path.is_file():
        try: stored = json.loads(lineup_path.read_text(encoding='utf-8'))
        except ValueError: stored = {}
    rows = study(source, kits, kit_path, source_text, titles)
    new_kits, files, made, materials = [], {}, set(), {}

    def material(donor, theme):
        name = 'gc3m_%s_%s' % (donor, theme.lower())
        if name not in materials:
            made_files = make_recolour(source, donor, kit_path(donor, kits[donor][1]), name, theme)
            materials[name] = None
            if made_files:
                files[finishes.COMPMAT_DIR + name + '.vcompmat_c'], files[finishes.VMAT_DIR + name + '.vmat_c'] = made_files[:2]
                materials[name] = finishes.COMPMAT_DIR + name + '.vcompmat'
                report.setdefault('colours', {})[name] = {'from': made_files[2], 'to': made_files[3]}
        return materials[name]

    def works(donor, mode, themes):
        if mode == 'transfer': return True
        made_paths = [material(donor, theme) for theme in themes]
        return all(made_paths) if mode == 'fixed' else sum(map(bool, made_paths)) >= 3

    lineup = stored.get('lineup') if stored.get('version') == VERSION else None
    if lineup is None or any(e.get('donor') not in rows for entries in lineup.values() for e in entries if 'donor' in e) \
            or set(lineup) != set(icons):
        lineup = plan(rows, guns, icons, families, works)
    history = dict(stored.get('history') or {})
    for icon, entries in lineup.items():
        for entry in entries:
            if 'donor' in entry: history[kit_name(icon, entry)] = dict(entry, icon=icon)
    if lineup_path is not None:
        lineup_path.write_text(json.dumps({'version': VERSION, 'lineup': lineup, 'history': history},
                                          indent=1, sort_keys=True) + '\n', encoding='utf-8')
    base_rarities = weapon_rarity_tags(source_text)

    def values_for(donor, tier, weapon, path):
        values = {k: v for k, v in kits[donor][1].items()
                  if isinstance(v, str) and k not in ('name', 'description_string', 'description_tag')}
        values.update(composite_material_path=path, _rarity=paint_rarity_for_weapon(tier, weapon, base_rarities))
        return values

    def define(icon, entry):
        """The loot entry kit for one lineup entry (defining it), or None when its colours would not show."""
        donor, tier, weapon, mode = entry['donor'], entry['tier'], entry['weapon'], entry['mode']
        if donor not in kits: return None
        title = finishes.source_title(donor, titles)
        name = kit_name(icon, entry)
        if mode == 'transfer':
            if name not in made:
                new_kits.append((name, title, values_for(donor, tier, weapon, kit_path(donor, kits[donor][1]))))
                made.add(name)
            return name
        if mode == 'fixed':
            path = material(donor, entry['themes'][0])
            if path is None: return None
            if name not in made:
                new_kits.append((name, colour_title(title, entry['themes'][0]), values_for(donor, tier, weapon, path)))
                made.add(name)
            return name
        variants, first = [], None
        for theme in entry['themes']:
            path = material(donor, theme)
            if path is None: continue
            variant = kit_name(icon, entry, theme)
            if variant not in made:
                new_kits.append((variant, clean_title(title), values_for(donor, tier, weapon, path)))
                made.add(variant)
            variants.append(variant); first = first or path
        if len(variants) < 3: return None
        if name not in made:
            new_kits.append((name, clean_title(title), values_for(donor, tier, weapon, first)))
            made.add(name)
        families[name] = variants
        return name

    # Owned skins from earlier lineups keep rendering.
    for name, entry in sorted(history.items()):
        define(entry['icon'], entry)
    lists, specs, entries_out, icon_map, failed = [], [], [], {}, []
    for icon in icons:
        tiers = {tier: [] for tier, _ in TIER_COUNTS}
        for entry in lineup.get(icon, ()):
            kit = 'cgf_%s_ancient' % entry['family'] if entry['mode'] == 'knife_family' else define(icon, entry)
            if kit is None: failed.append((icon, entry)); continue
            tiers[entry['tier']].append('[%s]%s' % (kit, entry['weapon']))
        if any(len(tiers[tier]) != count for tier, count in TIER_COUNTS):
            report.setdefault('incomplete', []).append(icon)
            continue  # never sell a collection with holes
        name = CASE_PREFIX + icon
        lists.append(_collection_lists(name, tiers, [t for t, _ in TIER_COUNTS]))
        specs.append(name); icon_map[name] = icon
        entries_out += [item for tier, _ in TIER_COUNTS for item in tiers[tier]]
    # Planning tried more colours than the lineup uses; ship only the materials a skin points at.
    used_paths = {values['composite_material_path'] for _, _, values in new_kits}
    kept = {name for name, path in materials.items() if path in used_paths}
    files = {path: data for path, data in files.items()
             if not path.startswith((finishes.COMPMAT_DIR + 'gc3m_', finishes.VMAT_DIR + 'gc3m_'))
             or path.rsplit('/', 1)[1].split('.')[0] in kept}
    report['colours'] = {name: row for name, row in report.get('colours', {}).items() if name in kept}
    report['failed'] = [dict(entry, icon=icon) for icon, entry in failed]
    report['usable_finishes'] = len(rows)
    report['used_finishes'] = len({e['donor'] for es in lineup.values() for e in es if 'donor' in e})
    return new_kits, files, '\n'.join(lists), specs, entries_out, icon_map

"""Custom weapon skins (user request, 21 Oct): finishes CS2 only ships on knives, and our knife recolours, on
popular guns. Weapon finishes of these styles are generic patterns, so the game's own paint kit (or an existing
rk_ recolour kit from native_finishes.py) works on any gun; no new materials are needed.

Phase 1 is a grant-only "Custom Skins Test Case" holding every pair, to check them in game before they become
Armory collections. It never drops and is not sold. Nothing in the game's own files changes.
"""
import random
import re

from native_finishes import WEAPON_WORDS

TEST_CASE_NAME = 'crate_cs2gc_custom_skins_test'
TEST_CASE_TITLE = 'Custom Skins Test Case'
CASE_BASE = '4003'  # Operation Bravo Case: model and key, like the Black Market Case
WEAPONS = ('weapon_ak47', 'weapon_m4a1', 'weapon_m4a1_silencer', 'weapon_awp', 'weapon_deagle',
           'weapon_usp_silencer', 'weapon_glock', 'weapon_famas', 'weapon_galilar', 'weapon_p250')
# Official knife finishes (generic patterns) that no gun has.
KNIFE_FINISHES = ('am_doppler_phase1', 'am_doppler_phase2', 'am_doppler_phase3', 'am_doppler_phase4',
                  'am_ruby_marbleized', 'am_sapphire_marbleized', 'am_blackpearl_marbleized', 'am_emerald_marbleized',
                  'am_gamma_doppler_phase1', 'am_gamma_doppler_phase2', 'am_gamma_doppler_phase3',
                  'am_gamma_doppler_phase4', 'am_marble_fade', 'an_tiger_orange', 'am_zebra', 'aq_damascus',
                  'hy_webs', 'aa_fade', 'aq_oiled', 'aq_blued', 'hy_ocean_knife', 'am_marked_up', 'so_purple')
RECOLOURS_PER_WEAPON = 12
# Batch 2 (user: "test another batch now we know these work"): every other gun, plus the three finishes the user
# asked for by name on knives (Twilight Galaxy, Gold Brick, Blue Phosphor) on all guns.
TEST2_CASE_NAME = 'crate_cs2gc_custom_skins2_test'  # *_test: never a match drop
TEST2_CASE_TITLE = 'Custom Skins Test Case 2'
WEAPONS2 = ('weapon_aug', 'weapon_sg556', 'weapon_ssg08', 'weapon_scar20', 'weapon_g3sg1', 'weapon_mp9',
            'weapon_mac10', 'weapon_mp7', 'weapon_mp5sd', 'weapon_ump45', 'weapon_p90', 'weapon_bizon',
            'weapon_fiveseven', 'weapon_tec9', 'weapon_cz75a', 'weapon_elite', 'weapon_hkp2000', 'weapon_revolver',
            'weapon_nova', 'weapon_xm1014', 'weapon_mag7', 'weapon_sawedoff', 'weapon_negev', 'weapon_m249')
EXTRA_FINISHES = ('am_aqua_flecks', 'am_gold_brick', 'am_m4a1s_bluesmoke')
RECOLOURS2_PER_WEAPON = 8
EXTRA_RECOLOURS_PER_WEAPON = 4


def test_items(source_text, kit_names, recolours):
    """Loot entries "[kit]weapon" for the test case, deterministic.

    kit_names: paint kit names in the schema; recolours: rk_ recolour kit names (native_finishes entries)."""
    official = set(re.findall(r'"\[([^\]]+)\](weapon_[a-z0-9_]+)"', source_text))
    weapons = [w for w in WEAPONS if re.search(r'"name"\s+"%s"' % w, source_text)]
    fades = sorted(name for name in recolours if re.match(r'rk_(aa_fade|am_marble_fade|am_doppler|am_gamma_doppler)', name))
    items = []
    for weapon in weapons:
        items += ['[%s]%s' % (kit, weapon) for kit in KNIFE_FINISHES if kit in kit_names and (kit, weapon) not in official]
        picks = fades[:]
        random.Random(weapon).shuffle(picks)
        items += ['[%s]%s' % (kit, weapon) for kit in sorted(picks[:RECOLOURS_PER_WEAPON])]
    return sorted(set(items))


def test2_items(source_text, kit_names, recolours):
    """Batch 2: knife finishes on the remaining guns, the named extras on every gun, and a few recolours."""
    official = set(re.findall(r'"\[([^\]]+)\](weapon_[a-z0-9_]+)"', source_text))
    present = lambda w: re.search(r'"name"\s+"%s"' % w, source_text)
    fades = sorted(n for n in recolours if re.match(r'rk_(aa_fade|am_marble_fade|am_doppler|am_gamma_doppler)', n))
    extras = sorted(n for n in recolours if re.match(r'rk_(%s)_' % '|'.join(EXTRA_FINISHES), n))
    items = []
    for weapon in [w for w in WEAPONS2 if present(w)]:
        items += ['[%s]%s' % (k, weapon) for k in KNIFE_FINISHES if k in kit_names and (k, weapon) not in official]
        picks = fades[:]
        random.Random(weapon + '2').shuffle(picks)
        items += ['[%s]%s' % (k, weapon) for k in picks[:RECOLOURS2_PER_WEAPON]]
    for weapon in [w for w in WEAPONS + WEAPONS2 if present(w)]:
        items += ['[%s]%s' % (k, weapon) for k in EXTRA_FINISHES if k in kit_names and (k, weapon) not in official]
        picks = extras[:]
        random.Random(weapon + 'x').shuffle(picks)
        items += ['[%s]%s' % (k, weapon) for k in picks[:EXTRA_RECOLOURS_PER_WEAPON]]
    return sorted(set(items))


def test2_case_spec(items):
    return dict(name=TEST2_CASE_NAME, title=TEST2_CASE_TITLE, base=CASE_BASE, items=items,
                description='Test case 2: knife finishes on the rest of the guns, and Twilight Galaxy, Gold Brick '
                            'and Blue Phosphor on every gun. Only given by grant_custom_skins_test2_cases.cmd.')


def test_case_spec(items):
    return dict(name=TEST_CASE_NAME, title=TEST_CASE_TITLE, base=CASE_BASE, items=items,
                description='Test case: knife finishes and recolours on guns, before they become Armory '
                            'collections. Only given by grant_custom_skins_test_cases.cmd.')


# Phase 2 (user: "families sounds great"): custom Armory collections made of colour families. Each collection
# lists one family finish per gun; rolling it grants one colour of that family (GC: Schema::LoadSkinFamilies,
# from cs2_gc_skin_families.txt), so the collection stays small however many colours a family has.
# Family: (title, official finish used for the collection picture, official variant finishes).
FAMILIES = {
    'doppler': ('Doppler', 'am_doppler_phase2', ('am_doppler_phase1', 'am_doppler_phase2', 'am_doppler_phase3',
                                                'am_doppler_phase4', 'am_ruby_marbleized', 'am_sapphire_marbleized',
                                                'am_blackpearl_marbleized')),
    'gamma': ('Gamma Doppler', 'am_gamma_doppler_phase2', ('am_gamma_doppler_phase1', 'am_gamma_doppler_phase2',
                                                          'am_gamma_doppler_phase3', 'am_gamma_doppler_phase4',
                                                          'am_emerald_marbleized')),
    'marble_fade': ('Marble Fade', 'am_marble_fade', ('am_marble_fade',)),
    'fade': ('Fade', 'aa_fade', ('aa_fade', 'aa_fade_metallic', 'aa_fade_grassland')),
    'twilight_galaxy': ('Twilight Galaxy', 'am_aqua_flecks', ('am_aqua_flecks',)),
    'gold_brick': ('Gold Brick', 'am_gold_brick', ('am_gold_brick',)),
    'blue_phosphor': ('Blue Phosphor', 'am_m4a1s_bluesmoke', ('am_m4a1s_bluesmoke',)),
    'ultraviolet': ('Ultraviolet', 'so_purple', ('so_purple',)),
    'tiger_tooth': ('Tiger Tooth', 'an_tiger_orange', ('an_tiger_orange',)),
    'slaughter': ('Slaughter', 'am_zebra', ('am_zebra',)),
    'crimson_web': ('Crimson Web', 'hy_webs', ('hy_webs',)),
    'damascus': ('Damascus Steel', 'aq_damascus', ('aq_damascus',)),
    'case_hardened': ('Case Hardened', 'aq_oiled', ('aq_oiled',)),
    'blued': ('Blued Steel', 'aq_blued', ('aq_blued',)),
    'bright_water': ('Bright Water', 'hy_ocean_knife', ('hy_ocean_knife',)),
    'freehand': ('Freehand', 'am_marked_up', ('am_marked_up',)),
}
# Gun classes used for the ordinary skins in the collections.
TIERS = {'ancient': ('weapon_ak47', 'weapon_m4a1', 'weapon_m4a1_silencer', 'weapon_awp', 'weapon_deagle'),
         'legendary': ('weapon_usp_silencer', 'weapon_glock', 'weapon_aug', 'weapon_sg556', 'weapon_ssg08',
                       'weapon_p90', 'weapon_famas', 'weapon_galilar'),
         'mythical': ('weapon_p250', 'weapon_fiveseven', 'weapon_tec9', 'weapon_cz75a', 'weapon_elite',
                      'weapon_hkp2000', 'weapon_revolver', 'weapon_mp9', 'weapon_mac10', 'weapon_mp7',
                      'weapon_mp5sd', 'weapon_ump45'),
         'rare': ('weapon_bizon', 'weapon_nova', 'weapon_xm1014', 'weapon_mag7', 'weapon_sawedoff', 'weapon_negev',
                  'weapon_m249', 'weapon_scar20', 'weapon_g3sg1')}
COLLECTIONS_TEST_NAME = 'crate_cs2gc_collections_test'  # *_test: never a match drop
# User (22 Oct): many small collections, each like a real one: a few ordinary skins and ONE Covert chase — a top
# gun in a special finish family (e.g. AK-47 | Doppler). Unboxing the chase gives one colour of the family.
CHASE_GUNS = ('weapon_ak47', 'weapon_m4a1', 'weapon_m4a1_silencer', 'weapon_awp', 'weapon_usp_silencer',
              'weapon_deagle', 'weapon_glock')
GUN_TITLES = {'weapon_ak47': 'AK-47', 'weapon_m4a1': 'M4A4', 'weapon_m4a1_silencer': 'M4A1-S', 'weapon_awp': 'AWP',
              'weapon_usp_silencer': 'USP-S', 'weapon_deagle': 'Desert Eagle', 'weapon_glock': 'Glock-18'}
COLLECTION_COUNT = 40
# The chase skin's rarity follows its gun (user: "if it's an AK, have it be a red. If it's a USP ... a purple").
CHASE_TIERS = {'weapon_usp_silencer': 'legendary', 'weapon_glock': 'legendary'}
# Ordinary skins per tier: official generic patterns (solid, hydrographic, spray, patina) on guns that never had
# them, given the tier's rarity through alias paint kits cga_<finish>_<tier> that reuse the official material.
# Same layout as the stock Armory collections (Overpass 2024, Graphic Design, Train 2025): 16 skins —
# 1 Covert, 2 Classified, 3 Restricted, 4 Mil-Spec, 6 Industrial. A Classified chase (USP-S, Glock) stays the
# top skin: its collection has 4 Restricted, 5 Mil-Spec and 6 Industrial instead.
FILLER_TIERS = {'ancient': (('legendary', 2), ('mythical', 3), ('rare', 4), ('uncommon', 6)),
                'legendary': (('mythical', 4), ('rare', 5), ('uncommon', 6))}
FILLER_STYLES = ('1', '2', '3', '8')
FILLER_GUNS = tuple(w for tier in TIERS.values() for w in tier)


def collection_specs():
    """[(list name, title, chase gun, family)] — deterministic; every family on several top guns."""
    specs, used = [], set()
    families = list(FAMILIES)
    for index in range(COLLECTION_COUNT):
        family = families[index % len(families)]
        for step in range(len(CHASE_GUNS)):
            gun = CHASE_GUNS[(index // len(families) * 3 + index + step) % len(CHASE_GUNS)]
            if (gun, family) not in used: break
        used.add((gun, family))
        specs.append(('set_cs2gc_%s_%s' % (family, gun.removeprefix('weapon_')),
                      'The %s %s Collection' % (GUN_TITLES[gun], FAMILIES[family][0]), gun, family))
    return specs


COLLECTIONS = {name: (title, family) for name, title, _, family in collection_specs()}
CHASE_TEST_NAME = 'crate_cs2gc_chase_test'  # *_test: never a match drop
FAMILIES_FILE = 'cs2_gc_skin_families.txt'


def _quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'


def _collection_lists(name, tiers, order):
    """Tier lists then the top list, in the stock order (set_arabesque): the client resolves a nested
    list only once it is defined, so a top list written first shows as empty in the Armory."""
    lists = ['\t\t%s\n\t\t{\n%s\t\t}' % (_quote('%s_%s' % (name, t)), ''.join('\t\t\t%s\t\t"1"\n' % _quote(i)
             for i in tiers[t])) for t in reversed(order)]
    lists.append('\t\t%s\n\t\t{\n%s\t\t}' % (_quote(name), ''.join('\t\t\t%s\t\t"1"\n' % _quote(
        '%s_%s' % (name, t)) for t in reversed(order))))
    return '\n'.join(lists)


def collections(source_text, kits, recolours, kit_path, titles=None):
    """(new kit entries [(name, title, values)], unused, client_loot_lists text, families text,
    [collection list names], [loot entries], [chase entries]).

    kits: {name: (id, values)}; recolours: rk_ kit names; kit_path(name, values) -> vcompmat; titles: finish
    display names by kit name."""
    titles = titles or {}
    official = set(re.findall(r'"\[([^\]]+)\](weapon_[a-z0-9_]+)"', source_text))
    weapons = {w for w in FILLER_GUNS if re.search(r'"name"\s+"%s"' % w, source_text)}
    new_kits, families, lists, names, entries, chases, made = [], {}, [], [], [], [], set()

    def copy_values(name):
        values = {k: v for k, v in kits[name][1].items()
                  if isinstance(v, str) and k not in ('name', 'description_string', 'description_tag')}
        values['composite_material_path'] = kit_path(name, kits[name][1])
        return values

    # User: a family is only our colours (not the official original, e.g. no plain Fade), and every colour is
    # named just like the family ("Marble Fade", not "Marble Fade Galaxy"): variant kits cgv_<colour>_<tier>
    # reuse the recolour's material under the family title.
    from native_finishes import COMPMAT_DIR
    chase_tiers = {gun: CHASE_TIERS.get(gun, 'ancient') for gun in CHASE_GUNS}
    for family, (title, picture, bases) in FAMILIES.items():
        colours = sorted(r for r in recolours if any(r.startswith('rk_%s_' % b) for b in bases))
        if not colours: colours = [b for b in bases if b in kits]  # a family with no colours of ours yet
        if picture not in kits or not colours: continue
        for tier in sorted(set(chase_tiers.values())):
            name = 'cgf_%s_%s' % (family, tier)
            new_kits.append((name, title, dict(copy_values(picture), _rarity=tier)))
            made.add(name)
            variants = []
            for colour in colours:
                if colour in kits:  # an official finish used as is
                    variants.append(colour); continue
                base = max((b for b in bases if colour.startswith('rk_%s_' % b) and b in kits), key=len, default=None)
                if base is None: continue
                variant = 'cgv_%s_%s' % (colour.removeprefix('rk_'), tier)
                values = dict(copy_values(base), _rarity=tier)
                values['composite_material_path'] = COMPMAT_DIR + colour + '.vcompmat'
                new_kits.append((variant, title, values))
                variants.append(variant)
            if variants: families[name] = variants
    fillers = sorted(n for n, (_, v) in kits.items() if v.get('style') in FILLER_STYLES and n in titles
                     and titles[n] and not any(word in n for word in WEAPON_WORDS))
    for list_name, title, gun, family in collection_specs():
        top = chase_tiers[gun]
        chase = 'cgf_%s_%s' % (family, top)
        if chase not in families or gun not in weapons: continue
        rng = random.Random(list_name)
        tiers = {top: ['[%s]%s' % (chase, gun)]}
        taken = {gun}
        for tier, count in FILLER_TIERS[top]:
            picked = []
            for _ in range(count * 20 if fillers else 0):
                if len(picked) == count: break
                kit, weapon = rng.choice(fillers), rng.choice(sorted(weapons - taken) or sorted(weapons))
                if (kit, weapon) in official: continue
                alias = 'cga_%s_%s' % (kit, tier)
                if alias not in made:
                    new_kits.append((alias, titles[kit], dict(copy_values(kit), _rarity=tier)))
                    made.add(alias)
                picked.append('[%s]%s' % (alias, weapon)); taken.add(weapon)
            tiers[tier] = picked
        order = [t for t in ('ancient', 'legendary', 'mythical', 'rare', 'uncommon') if tiers.get(t)]
        lists.append(_collection_lists(list_name, tiers, order))
        names.append(list_name)
        entries += [i for t in order for i in tiers[t]]
        chases.append(tiers[top][0])
    return new_kits, '', '\n'.join(lists), families, names, entries, chases


COLLECTION_TOKENS_FILE = 'cs2_gc_collection_tokens.json'


def collection_item_sets(lists_text, names, families):
    """(item_sets text, localization tokens) making the custom collections real collections for the client, so its
    trade-up screen accepts their skins (user: "custom collections dont show in the tradeup menu").

    CS2 refuses the whole schema for an item set whose name is not "#CSGO_<set key>" with a localized string (26m),
    so every set uses exactly that token and the tokens go into the English language override that
    native_bot_names.py already mounts. A set lists what players own: each colour of a family, never the family kit.
    A skin is listed in one set only."""
    from native_tradeups import parse
    lists = {node.key: [child.key for child in node.children or []]
             for node in parse('"lists"\n{\n' + lists_text + '\n}').one('lists').children}
    seen, blocks, tokens = set(), [], {}
    for name in names:
        items = []
        for tier in lists.get(name, ()):
            for entry in lists.get(tier, ()):
                match = re.fullmatch(r'\[([^\]]+)\](\w+)', entry)
                if not match: continue
                for kit in families.get(match.group(1)) or [match.group(1)]:
                    item = '[%s]%s' % (kit, match.group(2))
                    if item not in seen: seen.add(item); items.append(item)
        if not items: continue
        title = CASE_COLLECTIONS.get(name) or name
        tokens['CSGO_' + name] = title
        tokens['CSGO_' + name + '_desc'] = 'A custom collection.'
        blocks.append('\t\t%s\n\t\t{\n\t\t\t"name"\t\t%s\n\t\t\t"set_description"\t\t%s\n'
                      '\t\t\t"is_collection"\t\t"1"\n\t\t\t"items"\n\t\t\t{\n%s\t\t\t}\n\t\t}' % (
                          _quote(name), _quote('#CSGO_' + name), _quote('#CSGO_' + name + '_desc'),
                          ''.join('\t\t\t\t%s\t\t"1"\n' % _quote(item) for item in items)))
    return '\n'.join(blocks), tokens


def family_text(families, drop_collections=()):
    """cs2_gc_skin_families.txt for the GC: family kit -> its colour kits."""
    return '"skin_families"\n{\n' + ''.join(
        '\t%s\n\t{\n%s\t}\n' % (_quote(name), ''.join('\t\t%s\t"1"\n' % _quote(v) for v in variants))
        for name, variants in sorted(families.items())) + '}\n' + (
        '"collection_drops"\n{\n' + ''.join('\t%s\t"1"\n' % _quote(name) for name in sorted(drop_collections)) + '}\n'
        if drop_collections else '')


# Custom weapon collections (user, 22 Oct: first "cases" in the case slot, then "I want it like this not a case,
# they are collections"): guns only, no gold, Armory collection tiles, the same layout as the collections. In each case the Covert chase and one Classified and one Restricted skin come in a colour range;
# the Classified/Restricted ranges are new recolours of classic patterns (rc_<pattern>_<theme> materials).
LEGACY_CASE_ICONS = ('ashfall', 'aurora', 'brimstone', 'cascade', 'cinder', 'eclipse', 'halcyon', 'kaleido', 'monsoon',
              'nebula', 'solstice', 'zephyr')  # the user's OfflineCS case pictures, tools/case_icons/cs2gc_<n>.png
NEW_CASE_ICONS=('tidewater','obelisk','zenith','rampart','ironclad','marauder',
                'nightwatch','outrider','quarry','redoubt','talisman','undertow')
NEWEST_CASE_ICONS = ('forged','phantom_blade','harbor','mosaic','kestrel','juggernaut','lodestar','fathom','cipher','driftwood','insignia','warden')
CASE_ICONS=LEGACY_CASE_ICONS+NEW_CASE_ICONS+NEWEST_CASE_ICONS
CASE_PREFIX = 'set_cs2gc_case_'  # user: "they are collections", Armory collection tiles, not crates
CLASSIC_STYLES = ('2', '3')  # hydrographic and spray-paint patterns: four colours, any gun
CLASSIC_THEMES = 8


CASE_COLLECTIONS = {CASE_PREFIX + icon: 'The %s Collection' % icon.replace('_', ' ').title() for icon in CASE_ICONS}


def legacy_custom_cases(source_text, kits, titles, kit_path, finish_source, families, made_kits):
    """(new kit entries, files {path: bytes}, loot lists text, [collection list names], [loot entries], {list: icon}).

    Despite the name these are Armory collections (loot lists), like Arabesque.

    families/made_kits: from collections() (the cgf_ chase families), extended in place with the new ones."""
    import native_finishes as finishes
    official = set(re.findall(r'"\[([^\]]+)\](weapon_[a-z0-9_]+)"', source_text))
    weapons = sorted(w for w in FILLER_GUNS if re.search(r'"name"\s+"%s"' % w, source_text))
    new_kits, files, lists, specs, entries, icons = [], {}, [], [], [], {}
    made = set(made_kits)

    def copy_values(name):
        values = {k: v for k, v in kits[name][1].items()
                  if isinstance(v, str) and k not in ('name', 'description_string', 'description_tag')}
        values['composite_material_path'] = kit_path(name, kits[name][1])
        return values

    def alias(kit, tier):
        name = 'cga_%s_%s' % (kit, tier)
        if name not in made:
            new_kits.append((name, titles[kit], dict(copy_values(kit), _rarity=tier))); made.add(name)
        return name

    def classic_family(base, tier):
        """cgc_<base>_<tier>, whose colours are new recolours of a classic pattern; None if it cannot be recoloured."""
        family = 'cgc_%s_%s' % (base, tier)
        if family in families: return family
        themes = list(finishes.THEMES) + list(finishes.DUO_THEMES)
        random.Random(base).shuffle(themes)
        variants = []
        for theme in themes[:CLASSIC_THEMES]:
            material = 'rc_%s_%s' % (base, theme.lower())
            if finishes.COMPMAT_DIR + material + '.vcompmat_c' not in files:
                made_files = finishes.make_finish(finish_source, base, kit_path(base, kits[base][1]), material, theme)
                if not made_files: continue
                files[finishes.COMPMAT_DIR + material + '.vcompmat_c'], files[finishes.VMAT_DIR + material + '.vmat_c'] = made_files
            variant = 'cgr_%s_%s_%s' % (base, theme.lower(), tier)
            values = dict(copy_values(base), _rarity=tier)
            values['composite_material_path'] = finishes.COMPMAT_DIR + material + '.vcompmat'
            new_kits.append((variant, titles[base], values)); variants.append(variant)
        if not variants: return None
        new_kits.append((family, titles[base], dict(copy_values(base), _rarity=tier)))
        families[family] = variants; made.add(family)
        return family

    fillers = sorted(n for n, (_, v) in kits.items() if v.get('style') in FILLER_STYLES and n in titles
                     and titles[n] and not any(word in n for word in WEAPON_WORDS))
    classics = [n for n in fillers if kits[n][1].get('style') in CLASSIC_STYLES]
    chases = [(gun, family) for family in FAMILIES for gun in CHASE_GUNS
              if CHASE_TIERS.get(gun, 'ancient') == 'ancient' and 'cgf_%s_ancient' % family in families]
    for index, icon in enumerate(LEGACY_CASE_ICONS):
        name = CASE_PREFIX + icon
        rng = random.Random(name)
        if not chases: break
        gun, family = chases[(index * 7) % len(chases)]
        if gun not in weapons: continue
        tiers = {'ancient': ['[cgf_%s_ancient]%s' % (family, gun)]}
        taken = {gun}
        ranged = {'legendary': 1, 'mythical': 1}
        for tier, count in FILLER_TIERS['ancient']:
            picked, tries = [], 0
            while len(picked) < count and tries < count * 40 and fillers:
                tries += 1
                weapon = rng.choice([w for w in weapons if w not in taken] or weapons)
                if ranged.get(tier) and classics:
                    base = rng.choice(classics)
                    family_kit = classic_family(base, tier) if (base, weapon) not in official else None
                    if family_kit:
                        ranged[tier] -= 1
                        picked.append('[%s]%s' % (family_kit, weapon)); taken.add(weapon); continue
                kit = rng.choice(fillers)
                if (kit, weapon) in official: continue
                picked.append('[%s]%s' % (alias(kit, tier), weapon)); taken.add(weapon)
            tiers[tier] = picked
        order = [t for t in ('ancient', 'legendary', 'mythical', 'rare', 'uncommon') if tiers.get(t)]
        lists.append(_collection_lists(name, tiers, order))
        entries += [i for t in order for i in tiers[t]]
        specs.append(name)
        icons[name] = icon
    return new_kits, files, '\n'.join(lists), specs, entries, icons


# Each collection has its own chase donor and palette. Nine donors are gun patterns;
# three retain the established knife patterns. All use the verified four-colour material path.
COLLECTION_DESIGNS = {
    'ashfall': ('weapon_ak47', 'am_ossify', ('Ember','Crimson','Amber','Ash')),
    'aurora': ('weapon_m4a1_silencer', 'am_gamma_doppler_phase2', ('Teal','Azure','Violet','Aurora')),
    'brimstone': ('weapon_deagle', 'am_crystallized', ('Crimson','Ember','Amber','Inferno')),
    'cascade': ('weapon_awp', 'am_bamboo_jungle', ('Teal','Azure','Glacier','Emerald')),
    'cinder': ('weapon_m4a1', 'aa_flames', ('Ember','Crimson','Amber','Sunset')),
    'eclipse': ('weapon_awp', 'am_fuschia', ('Violet','Cobalt','Magenta','Midnight')),
    'halcyon': ('weapon_m4a1_silencer', 'am_geometric_steps', ('Azure','Teal','Glacier','Rose')),
    'kaleido': ('weapon_ak47', 'am_ddpatdense_peacock', ('Magenta','Violet','Teal','Aurora')),
    'monsoon': ('weapon_m4a1', 'am_jorm_blue', ('Cobalt','Azure','Teal','Glacier')),
    'nebula': ('weapon_deagle', 'am_doppler_phase2', ('Violet','Magenta','Cobalt','Midnight')),
    'solstice': ('weapon_m4a1', 'am_kimono_sunrise', ('Amber','Ember','Rose','Sunset')),
    'zephyr': ('weapon_ak47', 'aa_fade', ('Lime','Teal','Azure','Emerald')),
}
DROP_ONLY_COLLECTIONS = frozenset(CASE_PREFIX + name for name in ('eclipse','monsoon','nightwatch','undertow'))
# Second art pass: gun donors with known four-channel palettes; no Blaze transfers.
# Six hand-picked gradient/colour palettes per collection. The original colourway
# and near copies are rejected by weapon_palettes before entering the random range.
REFINED_DESIGNS = {
    'ashfall': ('weapon_ak47','am_ossify',('Lava','Sunrise','Coral','Royal','Inferno','Sunset')),
    'aurora': ('weapon_m4a1_silencer','am_m4a1s_bluesmoke',('Ocean','Galaxy','Vapor','Frost','Glacier','Aurora')),
    'brimstone': ('weapon_deagle','am_crystallized',('Lava','Sunrise','Royal','Coral','Inferno','Sunset')),
    'cascade': ('weapon_awp','am_seastorm',('Ocean','Frost','Forest','Coral','Glacier','Teal')),
    'cinder': ('weapon_m4a1','am_jorm_orange',('Lava','Sunrise','Coral','Royal','Inferno','Sunset')),
    'eclipse': ('weapon_awp','am_aqua_flecks',('Galaxy','Vapor','Royal','Midnight','Rose','Violet')),
    'halcyon': ('weapon_m4a1_silencer','am_royal',('Ocean','Frost','Coral','Vapor','Glacier','Rose')),
    'kaleido': ('weapon_ak47','am_moro_textile_bright',('Candy','Galaxy','Vapor','Royal','Toxin','Rainbow')),
    'monsoon': ('weapon_m4a1','am_jorm_blue',('Ocean','Forest','Vapor','Frost','Aurora','Glacier')),
    'nebula': ('weapon_deagle','am_heist_plans_purple',('Galaxy','Vapor','Royal','Candy','Midnight','Aurora')),
    'solstice': ('weapon_m4a1','am_gold_brick',('Sunrise','Coral','Royal','Lava','Sunset','Candy')),
    'zephyr': ('weapon_ak47','am_geometric_steps',('Forest','Ocean','Frost','Toxin','Glacier','Aurora')),
}

# These donors are known four-colour gun patterns, not weapon-specific UV artwork.
GUN_PATTERN_DONORS = ('am_ossify','am_crystallized','am_bamboo_jungle','aa_flames','am_fuschia',
    'am_geometric_steps','am_ddpatdense_peacock','am_jorm_blue','am_kimono_sunrise',
    'am_chainmail','am_carbon_fiber','am_heist_plans_green','am_moro_textile_bright',
    'am_seastorm','am_electric_red','aa_wiring','aa_vertigogeo_neon','am_scales_bravo')
REFINED_DONORS = tuple(n for n in GUN_PATTERN_DONORS if n != 'aa_flames') + (
    'am_aqua_flecks','am_m4a1s_bluesmoke','am_gold_brick','am_royal','am_jorm_orange','am_jorm_green',
    'am_heist_plans_purple','am_turqoise_halftone','am_ossify_blue','am_czv2_mf','am_navy_shine','am_gyrate')



ADDITIONAL_DESIGNS = {
    'tidewater': ('weapon_awp','cg_pattern_tidal_contour',('Ocean','Frost','Coral','Forest','Glacier','Vapor')),
    'obelisk': ('weapon_deagle','cg_pattern_obsidian_fault',('Royal','Galaxy','Midnight','Lava','Frost','Coral')),
    'zenith': ('weapon_m4a1_silencer','cg_pattern_prismatic_facets',('Candy','Galaxy','Vapor','Royal','Toxin','Sunrise')),
    'rampart': ('weapon_ak47','cg_pattern_vector_lattice',('Forest','Lava','Royal','Toxin','Coral','Glacier')),
    'ironclad': ('weapon_sg556','soe_teal_glitter',('Frost','Royal','Ocean','Coral','Galaxy','Sunrise')),
    'marauder': ('weapon_galilar','am_zebra_dark',('Lava','Coral','Royal','Sunset','Midnight','Vapor')),
    'nightwatch': ('weapon_usp_silencer','am_heist_plans_yellow',('Galaxy','Midnight','Vapor','Royal','Ocean','Aurora')),
    'outrider': ('weapon_glock','am_knots_brown',('Lava','Sunrise','Coral','Ocean','Forest','Royal')),
    'quarry': ('weapon_famas','soe_metallic_green_2',('Frost','Royal','Ocean','Lava','Forest','Coral')),
    'redoubt': ('weapon_aug','am_crystallized_silver',('Lava','Royal','Forest','Sunrise','Vapor','Frost')),
    'talisman': ('weapon_p250','soe_pink_pearl',('Forest','Royal','Toxin','Ocean','Sunrise','Vapor')),
    'undertow': ('weapon_mp9','soe_iridescent_purple',('Ocean','Frost','Forest','Vapor','Midnight','Glacier')),
}

# Third batch of twelve new Armory collections (no new weapon cases).
ADDITIONAL_DESIGNS.update({
    'forged': ('weapon_ak47', 'am_metal_inlay', ('Lava', 'Crimson', 'Sunrise', 'Royal', 'Inferno', 'Coral')),
    'phantom_blade': ('weapon_m4a1_silencer', 'am_navy_shine', ('Violet', 'Galaxy', 'Royal', 'Midnight', 'Rose', 'Vapor')),
    'harbor': ('weapon_awp', 'am_seastorm', ('Ocean', 'Glacier', 'Frost', 'Teal', 'Forest', 'Vapor')),
    'mosaic': ('weapon_deagle', 'am_ddpatdense_peacock', ('Candy', 'Rainbow', 'Vapor', 'Sunrise', 'Royal', 'Aurora')),
    'kestrel': ('weapon_sg556', 'am_scales_bravo', ('Azure', 'Ocean', 'Frost', 'Sunrise', 'Royal', 'Glacier')),
    'juggernaut': ('weapon_negev', 'am_diamond_plate', ('Lava', 'Royal', 'Coral', 'Inferno', 'Sunrise', 'Midnight')),
    'lodestar': ('weapon_awp', 'am_aqua_flecks', ('Galaxy', 'Violet', 'Aurora', 'Royal', 'Midnight', 'Vapor')),
    'fathom': ('weapon_mp9', 'am_jorm_blue', ('Ocean', 'Frost', 'Teal', 'Forest', 'Glacier', 'Aurora')),
    'cipher': ('weapon_glock', 'aa_wiring', ('Toxin', 'Forest', 'Aurora', 'Teal', 'Galaxy', 'Royal')),
    'driftwood': ('weapon_ak47', 'am_knots_brown', ('Coral', 'Sunrise', 'Forest', 'Ocean', 'Royal', 'Frost')),
    'insignia': ('weapon_m4a1', 'am_gold_brick', ('Royal', 'Sunrise', 'Coral', 'Lava', 'Ocean', 'Vapor')),
    'warden': ('weapon_xm1014', 'am_chainmail', ('Midnight', 'Ocean', 'Royal', 'Lava', 'Frost', 'Galaxy')),
})

# Known-working knife-origin colour families on guns. These are eligible for
# either a chase or a Classified wave, never automatically forced into the chase.
KNIFE_WAVE_DONORS = ('am_doppler_phase2', 'am_gamma_doppler_phase2',
                     'am_marble_fade', 'aa_fade', 'an_tiger_orange',
                     'am_zebra', 'aq_damascus', 'hy_webs', 'aq_oiled')

FEATURED_KNIFE_CHASES = {'aurora':'am_gamma_doppler_phase2', 'nebula':'am_doppler_phase2',
                          'kaleido':'am_marble_fade', 'outrider':'an_tiger_orange'}
ADDITIONAL_DONORS=REFINED_DONORS+('am_metal_inlay','am_zebra_dark','am_heist_plans_yellow','am_knots_brown',
    'am_diamond_plate','am_crystallized_silver','am_mirage_flowers_metalic','am_seastorm_blood')



NEXT12_DONORS = {
    'forged': ('am_metal_inlay', 'am_chainmail', 'am_crystallized_silver'),
    'phantom_blade': ('am_navy_shine', 'am_royal', 'am_fuschia'),
    'harbor': ('am_seastorm', 'am_jorm_blue', 'am_bamboo_jungle'),
    'mosaic': ('am_ddpatdense_peacock', 'am_geometric_steps', 'am_moro_textile_bright'),
    'kestrel': ('am_scales_bravo', 'am_gyrate', 'am_carbon_fiber'),
    'juggernaut': ('am_diamond_plate', 'am_chainmail', 'am_crystallized_silver'),
    'lodestar': ('am_aqua_flecks', 'am_geometric_steps', 'am_navy_shine'),
    'fathom': ('am_jorm_blue', 'am_seastorm', 'am_bamboo_jungle'),
    'cipher': ('aa_wiring', 'aa_vertigogeo_neon', 'am_carbon_fiber'),
    'driftwood': ('am_knots_brown', 'am_jorm_orange', 'am_bamboo_jungle'),
    'insignia': ('am_gold_brick', 'am_metal_inlay', 'am_crystallized_silver'),
    'warden': ('am_chainmail', 'am_diamond_plate', 'am_zebra_dark'),
}

def custom_cases(source_text, kits, titles, kit_path, finish_source, families, made_kits, report=None, retained_titles=None):
    if report is None: report={}
    readable_titles=titles
    titles=retained_titles if retained_titles is not None else titles
    # Keep build27a definitions even when a repeated donor is replaced in the current pool.
    previous = _curated_custom_cases(source_text,kits,titles,kit_path,finish_source,families,made_kits,False)
    current = _curated_custom_cases(source_text,kits,titles,kit_path,finish_source,families,made_kits,True)
    definitions={entry[0]:entry for entry in previous[0]}
    definitions.update({entry[0]:entry for entry in current[0]})
    files=dict(previous[1]);files.update(current[1])
    old_refined=_curated_custom_cases(source_text,kits,titles,kit_path,finish_source,families,made_kits,True,
        refined=True,retained=(list(definitions.values()),files),palette_report={},tone_revision=1)
    current=_curated_custom_cases(source_text,kits,titles,kit_path,finish_source,families,made_kits,True,
        refined=True,retained=old_refined[:2],palette_report=report,tone_revision=3)
    if finish_source is not None:
        import native_patterns
        added,pattern_titles,pattern_files,pattern_report=native_patterns.plan(finish_source,kits,titles)
        effects=native_patterns.inspect_effects(finish_source,kits)
        report['pattern_assets']=pattern_report;report['effect_templates']=effects
        expanded_kits=dict(kits);expanded_kits.update(added)
        for effect,row in effects.items():
            if not row['status'].startswith('colour template ready'):
                expanded_kits.pop(effect,None)
        expanded_titles=dict(titles);expanded_titles.update(pattern_titles)
        current[1].update(pattern_files)
        expanded_source=native_patterns.GeneratedSource(finish_source,pattern_files)
    else:
        expanded_kits,expanded_titles,expanded_source=kits,titles,finish_source
    bases=sorted(kits,key=len,reverse=True)
    blocked=set()
    for entry in current[4]:
        kit,weapon=entry[1:].split(']')
        base=next((base for base in bases if '_'+base+'_' in '_'+kit+'_'),None)
        if base:blocked.add((kit_path(base,kits[base][1]).replace('\\','/').lower(),weapon,'coloured'))
    expanded=_curated_custom_cases(source_text,expanded_kits,expanded_titles,kit_path,expanded_source,families,made_kits,True,
        refined=True,retained=current[:2],palette_report=report,expansion=True,excluded_pairs=blocked,tone_revision=3)
    # Rebuild historical definitions for owned items, without republishing their pools.
    from retained_collection_lineups import build as retain_build31
    retained=retain_build31(source_text,expanded_kits,expanded_titles,kit_path,expanded_source,
        families,set(made_kits) | {n for n,_,_ in expanded[0]}, {})
    baseline=(expanded[0]+retained[0],dict(expanded[1],**retained[1]),
        current[2]+'\n'+expanded[2],current[3]+expanded[3],current[4]+expanded[4],
        dict(current[5],**expanded[5]))
    from next_collection_lineups import build as upgrade, replace_pools, rename_retained
    readable_titles=dict(expanded_titles,**readable_titles)
    authored=upgrade(source_text,expanded_kits,readable_titles,kit_path,expanded_source,
        families,set(made_kits) | {n for n,_,_ in baseline[0]},report,
        previous_entries=baseline[4])
    current=replace_pools(baseline,authored)
    # Report actual selected families, including fallback results, not just candidates.
    report['effects_in_pools']=[entry for entry in current[4] if any('_'+name+'_' in entry for name in
        ('soe_teal_glitter','soe_pink_pearl','soe_iridescent_purple','soe_metallic_green_2'))]
    report['original_patterns_in_pools']=[entry for entry in current[4] if '_cg_pattern_' in entry]
    # Repair blank names on all retained kits too, without changing inventory IDs.
    import native_finishes as finishes
    bases=sorted(kits,key=len,reverse=True)
    definitions=[]
    for name,title,values in current[0]:
        base=next((base for base in bases if '_'+base+'_' in '_'+name+'_'),None)
        # Keep each rolled variant's own colour-specific title. Only the
        # visible family placeholder uses the generic donor title.
        is_rolled_variant = name.startswith(('cw2v_', 'ccv_', 'cgv_'))
        is_fixed_recolour = name.startswith(('cwf_', 'nc31_', 'nc32_'))
        if base in finishes.CLEAN_COLLECTION_TITLES and not (is_rolled_variant or is_fixed_recolour):
            title=finishes.source_title(base,titles)
        elif not title or not title.strip():
            title=finishes.source_title(base or name,titles)
        definitions.append((name,title,values))
    return rename_retained(definitions,expanded_kits),*current[1:]


def weapon_rarity_tags(source_text):
    from inventory_item import collect,parse,as_dict
    sections=collect(parse(source_text))
    prefabs={name:as_dict(value) for name,value in sections.get('prefabs',{}).items() if isinstance(value,list)}
    def resolve(node,seen=()):
        if node.get('item_rarity'):return node['item_rarity']
        for name in node.get('prefab','').split():
            if name not in seen:
                found=resolve(prefabs.get(name,{}),seen+(name,))
                if found:return found
    return {as_dict(value).get('name'):resolve(as_dict(value)) or 'common'
            for value in sections.get('items',{}).values() if isinstance(value,list)}


def paint_rarity_for_weapon(target,weapon,base_rarities):
    order=('common','uncommon','rare','mythical','legendary','ancient')
    bonus=order.index(base_rarities.get(weapon,'common')) if base_rarities.get(weapon,'common') in order else 0
    return order[max(0,order.index(target)-bonus)]


def _curated_custom_cases(source_text, kits, titles, kit_path, finish_source, families, made_kits, distinct_patterns,
                          refined=False, retained=None, palette_report=None, tone_revision=2, expansion=False, excluded_pairs=None):
    """Curated collection loot lists; retain the previous kits/materials for owned inventory.

    No new crate definitions. Original official weapon/material combinations are
    excluded even when different kit names point at the same material.
    """
    import native_finishes as finishes
    if retained is None:
        old_kits, files, _, _, _, _ = legacy_custom_cases(
            source_text,kits,titles,kit_path,finish_source,families,made_kits)
    else:
        old_kits, files = retained
        files = dict(files)
    new_kits=list(old_kits)
    present={n for n,_,_ in new_kits} | set(made_kits)
    positions={name:i for i,(name,_,_) in enumerate(new_kits)}
    base_rarities=weapon_rarity_tags(source_text) if refined and tone_revision>=2 else {}
    official=set(re.findall(r'"\[([^\]]+)\](weapon_[a-z0-9_]+)"',source_text))
    weapons=sorted(w for w in FILLER_GUNS if re.search(r'"name"\s+"%s"'%w,source_text))
    material=lambda base:kit_path(base,kits[base][1]).replace('\\','/').lower()
    official_materials={(material(base),gun) for base,gun in official if base in kits}
    fillers=sorted(n for n,(_,v) in kits.items() if v.get('style') in FILLER_STYLES and titles.get(n)
                   and 'chalice' not in (n + ' ' + titles.get(n, '')).lower()
                   and not any(word in n for word in WEAPON_WORDS))
    donor_names=((ADDITIONAL_DONORS+tuple(n for n in kits if n.startswith('cg_pattern_'))+
                  ()) if expansion and tone_revision>=3 else
                  (ADDITIONAL_DONORS+tuple(n for n in kits if n.startswith('cg_pattern_'))+
                  ('soe_teal_glitter','soe_pink_pearl','soe_iridescent_purple','soe_metallic_green_2')) if expansion else
                  REFINED_DONORS if refined else GUN_PATTERN_DONORS)
    def usable_donor(n):
        return n in kits and 'chalice' not in (n + ' ' + titles.get(n, '')).lower()
    donors=list(dict.fromkeys(n for n in donor_names if usable_donor(n)))
    used=set(excluded_pairs or ()); counts={}; lists=[]; specs=[]; entries=[]; icons={}; checked_materials={}

    def copy_values(base,tier):
        values={k:v for k,v in kits[base][1].items() if isinstance(v,str) and k not in ('name','description_string','description_tag')}
        values.update(composite_material_path=kit_path(base,kits[base][1]),_rarity=tier)
        return values

    def add(name,title,values):
        if name not in present:
            positions[name]=len(new_kits)
            new_kits.append((name,title,values));present.add(name)
        elif refined and tone_revision>=2 and name in positions:
            new_kits[positions[name]]=(name,title,values)

    def colour_family(icon,slot,base,tier,themes,weapon):
        paint_tier=paint_rarity_for_weapon(tier,weapon,base_rarities) if base_rarities else tier
        family=('%s_%s_%s_%s_%s'%('cw2f' if refined else 'ccf',icon,slot,base,tier))
        variants=[]; first_path=None; seen_palettes=set()
        variants_to_make=[(theme,False) for theme in themes]
        if refined: variants_to_make += [(theme,True) for theme in themes[:2]]
        for theme,inverse in variants_to_make:
            suffix=theme.lower()+('_inverted' if inverse else '')
            material_name=('rwc_%s_%s_%s'%(base,suffix,tier) if refined else 'rc_%s_%s'%(base,suffix))
            path=finishes.COMPMAT_DIR+material_name+'.vcompmat'
            if material_name not in checked_materials:
                report={}
                options={'weapon_palette':tier,'weapon_inverse':inverse,'weapon_tone':tone_revision} if refined else {}
                made=finishes.make_finish(finish_source,base,kit_path(base,kits[base][1]),material_name,theme,
                                          report=palette_report if refined else report,**options)
                if not made:
                    checked_materials[material_name]=False
                    continue
                palette=report.get(base,{})
                before=palette.get('original_colors');after=palette.get('themes',{}).get(theme)
                if before and after and max(abs(a-b) for x,y in zip(before,after) for a,b in zip(x[:3],y[:3])) < .025:
                    checked_materials[material_name]=False
                    continue  # a renamed copy that barely changes is not new content
                files[path+'_c'],files[finishes.VMAT_DIR+material_name+'.vmat_c']=made
                checked_materials[material_name]=True
            if not checked_materials[material_name]:continue
            if refined:
                palette=(palette_report or {}).get(base+':'+tier,{}).get('themes',{}).get(theme+(' / inverted' if inverse else ''))
                if palette:
                    signature=tuple(round(c,4) for colour in palette for c in colour)
                    if signature in seen_palettes:continue
                    seen_palettes.add(signature)
            variant='%s_%s_%s_%s_%s_%s'%('cw2v' if refined else 'ccv',icon,slot,base,suffix,tier)
            values=copy_values(base,paint_tier);values['composite_material_path']=path
            add(variant,finishes.variant_title(base,theme,inverse,titles),values)
            variants.append(variant);first_path=first_path or path
        if len(variants)<(2 if refined else 1):return None
        values=copy_values(base,paint_tier);values['composite_material_path']=first_path
        add(family,finishes.source_title(base,titles),values)
        families[family]=variants
        return family

    def fixed_recolour(icon,slot,base,tier,themes,weapon):
        """One named fixed finish, NOT a family. Existing cw2 definitions remain for owned items."""
        if base.startswith('soe_'):
            return None  # no glitter/pearl/iridescent transfer or unsupported material fallback
        paint_tier=paint_rarity_for_weapon(tier,weapon,base_rarities) if base_rarities else tier
        theme=themes[(sum(ord(c) for c in icon+slot+weapon) % len(themes))]
        suffix=theme.lower()
        material_name='rwc_%s_%s_%s'%(base,suffix,tier)
        path=finishes.COMPMAT_DIR+material_name+'.vcompmat'
        if material_name not in checked_materials:
            made=finishes.make_finish(finish_source,base,kit_path(base,kits[base][1]),material_name,theme,
                                      report=palette_report,weapon_palette=tier,weapon_inverse=False,weapon_tone=2)
            checked_materials[material_name]=bool(made)
            if made:
                files[path+'_c'],files[finishes.VMAT_DIR+material_name+'.vmat_c']=made
        if not checked_materials[material_name]:return None
        kit='cwf_%s_%s_%s_%s_%s'%(icon,slot,base,suffix,tier)
        values=copy_values(base,paint_tier);values['composite_material_path']=path
        add(kit,finishes.variant_title(base,theme,False,titles),values)
        return kit

    # Generic donor fallbacks are only used when a particular material is unavailable.
    fallback=donors+[n for n in fillers if usable_donor(n) and kits[n][1].get('style') in CLASSIC_STYLES]
    for icon in ((NEW_CASE_ICONS+NEWEST_CASE_ICONS) if expansion else LEGACY_CASE_ICONS):
        # The new pools keep only TWO visible wave families. Knife-based donors
        # can be the chase in selected collections OR the pink wave in others.
        # Every other entry is a fixed finish; old paint kits are retained above.
        active_knife_donors=[b for b in KNIFE_WAVE_DONORS if b in kits] if refined and tone_revision>=3 else []
        preferred_knife=FEATURED_KNIFE_CHASES.get(icon) if refined and tone_revision>=3 else None
        knife_chase=bool(preferred_knife in active_knife_donors)
        name=CASE_PREFIX+icon
        gun,chase_base,themes=(ADDITIONAL_DESIGNS if expansion else REFINED_DESIGNS if refined else COLLECTION_DESIGNS)[icon]
        if gun not in weapons:continue
        chase=None
        if expansion and tone_revision>=3 and chase_base.startswith('soe_'):
            chase_base=next((candidate for candidate in ADDITIONAL_DONORS if candidate in kits), chase_base)
        if knife_chase:
            chase_candidates=[preferred_knife, chase_base]+fallback
        else:
            chase_candidates=[chase_base]+fallback
        for base in dict.fromkeys(chase_candidates):
            if not usable_donor(base):continue
            chase=colour_family(icon,'chase',base,'ancient',themes,gun)
            if chase:break
        if not chase:continue
        tiers={'ancient':['[%s]%s'%(chase,gun)]};taken={gun};collection_materials={material(base)}
        used.add((material(base),gun,'coloured'))
        for tier,count in FILLER_TIERS['ancient']:
            picked=[]
            for slot in range(count):
                chosen=None
                # Pink/purple rewards are distinct recolours too, instead of filler
                # carrying an inflated rarity. At blue, two slots get custom colours.
                colour = (refined or tier in ('legendary','mythical') or (tier=='rare' and slot<2))
                # Build29 draft: chase plus one pink slot keep colour waves; all other
                # visible slots become fixed themed recolours, never extra family entries.
                family_slot = not (tone_revision>=3 and refined) or (tier=='legendary' and slot==0)
                pool=(list(dict.fromkeys([d for d in NEXT12_DONORS[icon] if d in kits]+donors)) if icon in NEXT12_DONORS and colour else donors) if colour else fillers
                # Only the one Classified wave slot can pull a knife-origin
                # pattern when the chase is not already knife-derived.
                # Nothing is added to the visible slot count.
                if (refined and tone_revision>=3 and tier=='legendary' and slot==0
                        and not knife_chase and active_knife_donors):
                    pool=active_knife_donors
                candidates=[(b,w) for b in pool for w in weapons if w not in taken
                            and (not distinct_patterns or material(b) not in collection_materials)
                            and (material(b),w,'coloured' if colour else 'original') not in used
                            and (colour or (material(b),w) not in official_materials)]
                rng=random.Random(name+':'+tier+':'+str(slot))
                rng.shuffle(candidates)
                candidates.sort(key=lambda bw:(counts.get(bw[0],0),counts.get(bw[1],0)))
                for base,weapon in candidates:
                    if colour:
                        kit=(colour_family(icon,tier+str(slot),base,tier,themes,weapon)
                             if family_slot else fixed_recolour(icon,tier+str(slot),base,tier,themes,weapon))
                        if not kit:continue
                    else:
                        kit='cga_%s_%s'%(base,tier)
                        add(kit,titles[base],copy_values(base,tier))
                    chosen='[%s]%s'%(kit,weapon)
                    used.add((material(base),weapon,'coloured' if colour else 'original'))
                    counts[base]=counts.get(base,0)+1;counts[weapon]=counts.get(weapon,0)+1
                    taken.add(weapon);collection_materials.add(material(base));break
                if chosen:picked.append(chosen)
            tiers[tier]=picked
        # Never sell an incomplete collection when an installed schema is missing donors.
        if any(len(tiers[t])!=n for t,n in FILLER_TIERS['ancient']):continue
        if expansion and refined and tone_revision>=3 and icon in NEWEST_CASE_ICONS:
            continue  # retain draft definitions above, publish authored pools instead
        order=['ancient','legendary','mythical','rare','uncommon']
        lists.append(_collection_lists(name,tiers,order));specs.append(name)
        entries.extend(i for t in order for i in tiers[t]);icons[name]=icon
    return new_kits,files,'\n'.join(lists),specs,entries,icons


def collections_test_spec(list_names):
    return dict(name=COLLECTIONS_TEST_NAME, title='Custom Collections Test Case', base=CASE_BASE, items=[],
                loot_lists=list_names,
                description='Test case: rolls the custom collections like a real case. Only given by '
                            'grant_custom_collections_test_cases.cmd.')


def chase_test_spec(chases):
    return dict(name=CHASE_TEST_NAME, title='Custom Chase Test Case', base=CASE_BASE, items=chases,
                description='Test case: only the Covert chase skin of every custom collection, each in a random '
                            'colour of its family. Only given by grant_custom_chase_test_cases.cmd.')

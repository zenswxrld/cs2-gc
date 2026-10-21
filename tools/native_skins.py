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
CASE_ICONS = ('ashfall', 'aurora', 'brimstone', 'cascade', 'cinder', 'eclipse', 'halcyon', 'kaleido', 'monsoon',
              'nebula', 'solstice', 'zephyr')  # the user's OfflineCS case pictures, tools/case_icons/cs2gc_<n>.png
CASE_PREFIX = 'set_cs2gc_case_'  # user: "they are collections", Armory collection tiles, not crates
CLASSIC_STYLES = ('2', '3')  # hydrographic and spray-paint patterns: four colours, any gun
CLASSIC_THEMES = 8


CASE_COLLECTIONS = {CASE_PREFIX + icon: 'The %s Collection' % icon.title() for icon in CASE_ICONS}


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
    for index, icon in enumerate(CASE_ICONS):
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
DROP_ONLY_COLLECTIONS = frozenset(CASE_PREFIX + name for name in ('eclipse','monsoon'))
# These donors are known four-colour gun patterns, not weapon-specific UV artwork.
GUN_PATTERN_DONORS = ('am_ossify','am_crystallized','am_bamboo_jungle','aa_flames','am_fuschia',
    'am_geometric_steps','am_ddpatdense_peacock','am_jorm_blue','am_kimono_sunrise',
    'am_chainmail','am_carbon_fiber','am_heist_plans_green','am_moro_textile_bright',
    'am_seastorm','am_electric_red','aa_wiring','aa_vertigogeo_neon','am_scales_bravo')


def custom_cases(source_text, kits, titles, kit_path, finish_source, families, made_kits):
    """Curated collection loot lists; retain the previous kits/materials for owned inventory.

    No new crate definitions. Original official weapon/material combinations are
    excluded even when different kit names point at the same material.
    """
    import native_finishes as finishes
    old_kits, files, _, _, _, _ = legacy_custom_cases(
        source_text,kits,titles,kit_path,finish_source,families,made_kits)
    new_kits=list(old_kits)
    present={n for n,_,_ in new_kits} | set(made_kits)
    official=set(re.findall(r'"\[([^\]]+)\](weapon_[a-z0-9_]+)"',source_text))
    weapons=sorted(w for w in FILLER_GUNS if re.search(r'"name"\s+"%s"'%w,source_text))
    material=lambda base:kit_path(base,kits[base][1]).replace('\\','/').lower()
    official_materials={(material(base),gun) for base,gun in official if base in kits}
    fillers=sorted(n for n,(_,v) in kits.items() if v.get('style') in FILLER_STYLES and titles.get(n)
                   and not any(word in n for word in WEAPON_WORDS))
    donors=[n for n in GUN_PATTERN_DONORS if n in kits]
    used=set(); counts={}; lists=[]; specs=[]; entries=[]; icons={}; checked_materials={}

    def copy_values(base,tier):
        values={k:v for k,v in kits[base][1].items() if isinstance(v,str) and k not in ('name','description_string','description_tag')}
        values.update(composite_material_path=kit_path(base,kits[base][1]),_rarity=tier)
        return values

    def add(name,title,values):
        if name not in present:
            new_kits.append((name,title,values));present.add(name)

    def colour_family(icon,slot,base,tier,themes):
        family='ccf_%s_%s_%s_%s'%(icon,slot,base,tier)
        variants=[]; first_path=None
        for theme in themes:
            material_name='rc_%s_%s'%(base,theme.lower())
            path=finishes.COMPMAT_DIR+material_name+'.vcompmat'
            if material_name not in checked_materials:
                report={}
                made=finishes.make_finish(finish_source,base,kit_path(base,kits[base][1]),material_name,theme,report=report)
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
            variant='ccv_%s_%s_%s_%s_%s'%(icon,slot,base,theme.lower(),tier)
            values=copy_values(base,tier);values['composite_material_path']=path
            add(variant,titles.get(base,base.replace('_',' ').title()),values)
            variants.append(variant);first_path=first_path or path
        if not variants:return None
        values=copy_values(base,tier);values['composite_material_path']=first_path
        add(family,titles.get(base,base.replace('_',' ').title()),values)
        families[family]=variants
        return family

    # Generic donor fallbacks are only used when a particular material is unavailable.
    fallback=donors+[n for n in fillers if kits[n][1].get('style') in CLASSIC_STYLES]
    for icon in CASE_ICONS:
        name=CASE_PREFIX+icon
        gun,chase_base,themes=COLLECTION_DESIGNS[icon]
        if gun not in weapons:continue
        chase=None
        for base in dict.fromkeys([chase_base]+fallback):
            if base not in kits:continue
            chase=colour_family(icon,'chase',base,'ancient',themes)
            if chase:break
        if not chase:continue
        tiers={'ancient':['[%s]%s'%(chase,gun)]};taken={gun}
        used.add((material(base),gun,'coloured'))
        for tier,count in FILLER_TIERS['ancient']:
            picked=[]
            for slot in range(count):
                chosen=None
                # Pink/purple rewards are distinct recolours too, instead of filler
                # carrying an inflated rarity. At blue, two slots get custom colours.
                colour = tier in ('legendary','mythical') or (tier=='rare' and slot<2)
                pool=list(dict.fromkeys(donors+fillers)) if colour else fillers
                candidates=[(b,w) for b in pool for w in weapons if w not in taken
                            and (material(b),w,'coloured' if colour else 'original') not in used
                            and (colour or (material(b),w) not in official_materials)]
                rng=random.Random(name+':'+tier+':'+str(slot))
                rng.shuffle(candidates)
                candidates.sort(key=lambda bw:(counts.get(bw[0],0),counts.get(bw[1],0)))
                for base,weapon in candidates:
                    if colour:
                        kit=colour_family(icon,tier+str(slot),base,tier,themes)
                        if not kit:continue
                    else:
                        kit='cga_%s_%s'%(base,tier)
                        add(kit,titles[base],copy_values(base,tier))
                    chosen='[%s]%s'%(kit,weapon)
                    used.add((material(base),weapon,'coloured' if colour else 'original'))
                    counts[base]=counts.get(base,0)+1;counts[weapon]=counts.get(weapon,0)+1
                    taken.add(weapon);break
                if chosen:picked.append(chosen)
            tiers[tier]=picked
        # Never sell an incomplete collection when an installed schema is missing donors.
        if any(len(tiers[t])!=n for t,n in FILLER_TIERS['ancient']):continue
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

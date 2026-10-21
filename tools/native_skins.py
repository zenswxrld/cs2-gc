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
# Ordinary skins per tier: official generic patterns (solid, hydrographic, spray, patina) on guns that never had
# them, given the tier's rarity through alias paint kits cga_<finish>_<tier> that reuse the official material.
FILLER_TIERS = (('legendary', 2), ('mythical', 3), ('rare', 5))
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

    for family, (title, picture, bases) in FAMILIES.items():
        variants = [b for b in bases if b in kits]
        variants += sorted(r for r in recolours if any(r.startswith('rk_%s_' % b) for b in bases))
        if picture not in kits or not variants: continue
        name = 'cgf_%s_ancient' % family
        new_kits.append((name, title, dict(copy_values(picture), _rarity='ancient')))
        families[name] = variants
        made.add(name)
    fillers = sorted(n for n, (_, v) in kits.items() if v.get('style') in FILLER_STYLES and n in titles
                     and titles[n] and not any(word in n for word in WEAPON_WORDS))
    for list_name, title, gun, family in collection_specs():
        chase = 'cgf_%s_ancient' % family
        if chase not in made or gun not in weapons: continue
        rng = random.Random(list_name)
        tiers = {'ancient': ['[%s]%s' % (chase, gun)]}
        taken = {gun}
        for tier, count in FILLER_TIERS:
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
        order = [t for t in ('ancient', 'legendary', 'mythical', 'rare') if tiers.get(t)]
        lists.append('\t\t%s\n\t\t{\n%s\t\t}' % (_quote(list_name), ''.join('\t\t\t%s\t\t"1"\n' % _quote(
            '%s_%s' % (list_name, t)) for t in order)))
        for t in order:
            lists.append('\t\t%s\n\t\t{\n%s\t\t}' % (_quote('%s_%s' % (list_name, t)),
                                                     ''.join('\t\t\t%s\t\t"1"\n' % _quote(i) for i in tiers[t])))
        names.append(list_name)
        entries += [i for t in order for i in tiers[t]]
        chases.append(tiers['ancient'][0])
    family_text = '"skin_families"\n{\n' + ''.join(
        '\t%s\n\t{\n%s\t}\n' % (_quote(name), ''.join('\t\t%s\t"1"\n' % _quote(v) for v in variants))
        for name, variants in sorted(families.items())) + '}\n'
    return new_kits, '', '\n'.join(lists), family_text, names, entries, chases


def collections_test_spec(list_names):
    return dict(name=COLLECTIONS_TEST_NAME, title='Custom Collections Test Case', base=CASE_BASE, items=[],
                loot_lists=list_names,
                description='Test case: rolls the custom collections like a real case. Only given by '
                            'grant_custom_collections_test_cases.cmd.')


def chase_test_spec(chases):
    return dict(name=CHASE_TEST_NAME, title='Custom Chase Test Case', base=CASE_BASE, items=chases,
                description='Test case: only the Covert chase skin of every custom collection, each in a random '
                            'colour of its family. Only given by grant_custom_chase_test_cases.cmd.')

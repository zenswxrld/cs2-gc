"""Custom weapon skins (user request, 21 Oct): finishes CS2 only ships on knives, and our knife recolours, on
popular guns. Weapon finishes of these styles are generic patterns, so the game's own paint kit (or an existing
rk_ recolour kit from native_finishes.py) works on any gun; no new materials are needed.

Phase 1 is a grant-only "Custom Skins Test Case" holding every pair, to check them in game before they become
Armory collections. It never drops and is not sold. Nothing in the game's own files changes.
"""
import random
import re

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
COLLECTIONS = {
    'set_cs2gc_doppler': ('The Doppler Collection', ('doppler', 'gamma', 'marble_fade')),
    'set_cs2gc_spectrum': ('The Spectrum Collection', ('fade', 'twilight_galaxy', 'gold_brick', 'blue_phosphor',
                                                       'ultraviolet')),
    'set_cs2gc_classics': ('The Knife Classics Collection', ('tiger_tooth', 'slaughter', 'crimson_web', 'damascus',
                                                             'case_hardened', 'blued', 'bright_water', 'freehand')),
}
# Rarity tier per gun, the same in every collection (paint kit rarity; guns are "common", so it is the skin's).
TIERS = {'ancient': ('weapon_ak47', 'weapon_m4a1', 'weapon_m4a1_silencer', 'weapon_awp', 'weapon_deagle'),
         'legendary': ('weapon_usp_silencer', 'weapon_glock', 'weapon_aug', 'weapon_sg556', 'weapon_ssg08',
                       'weapon_p90', 'weapon_famas', 'weapon_galilar'),
         'mythical': ('weapon_p250', 'weapon_fiveseven', 'weapon_tec9', 'weapon_cz75a', 'weapon_elite',
                      'weapon_hkp2000', 'weapon_revolver', 'weapon_mp9', 'weapon_mac10', 'weapon_mp7',
                      'weapon_mp5sd', 'weapon_ump45'),
         'rare': ('weapon_bizon', 'weapon_nova', 'weapon_xm1014', 'weapon_mag7', 'weapon_sawedoff', 'weapon_negev',
                  'weapon_m249', 'weapon_scar20', 'weapon_g3sg1')}
COLLECTIONS_TEST_NAME = 'crate_cs2gc_collections_test'  # *_test: never a match drop
FAMILIES_FILE = 'cs2_gc_skin_families.txt'


def _quote(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'


def collections(source_text, kits, recolours, kit_path):
    """(family kit entries [(name, title, values)], item_sets text, client_loot_lists text, families text,
    [collection list names], [loot entries]).

    kits: {name: (id, values)} of the schema; recolours: rk_ kit names; kit_path(name, values) -> vcompmat."""
    weapons = {w for tier in TIERS.values() for w in tier if re.search(r'"name"\s+"%s"' % w, source_text)}
    family_kits, families, sets, lists, names, entries = [], {}, [], [], [], []
    for family, (title, picture, bases) in FAMILIES.items():
        variants = [b for b in bases if b in kits]
        variants += sorted(r for r in recolours if any(r.startswith('rk_%s_' % b) for b in bases))
        if picture not in kits or not variants: continue
        values = {k: v for k, v in kits[picture][1].items()
                  if isinstance(v, str) and k not in ('name', 'description_string', 'description_tag')}
        values['composite_material_path'] = kit_path(picture, kits[picture][1])
        for rarity in TIERS:
            name = 'cgf_%s_%s' % (family, rarity)
            family_kits.append((name, title, dict(values, _rarity=rarity)))
            families[name] = variants
    present = {name for name, _, _ in family_kits}
    for set_name, (title, members) in COLLECTIONS.items():
        tiers = {}
        for rarity, guns in TIERS.items():
            for family in members:
                kit = 'cgf_%s_%s' % (family, rarity)
                found = ['[%s]%s' % (kit, w) for w in guns if w in weapons] if kit in present else []
                if found: tiers.setdefault(rarity, []).extend(found)
        if not tiers: continue
        all_items = [item for rarity in TIERS for item in tiers.get(rarity, [])]
        entries += all_items
        names.append(set_name)
        sets.append('\t\t%s\n\t\t{\n\t\t\t"name"\t\t%s\n\t\t\t"set_description"\t\t%s\n\t\t\t"is_collection"\t\t"1"\n'
                    '\t\t\t"items"\n\t\t\t{\n%s\t\t\t}\n\t\t}' %
                    (_quote(set_name), _quote(title), _quote('Custom colour families: every finish comes in a '
                                                             'range of colours.'),
                     ''.join('\t\t\t\t%s\t\t"1"\n' % _quote(i) for i in all_items)))
        tier_lists = ['%s_%s' % (set_name, rarity) for rarity in TIERS if rarity in tiers]
        lists.append('\t\t%s\n\t\t{\n%s\t\t}' % (_quote(set_name), ''.join('\t\t\t%s\t\t"1"\n' % _quote(t)
                                                                        for t in tier_lists)))
        for rarity in TIERS:
            if rarity in tiers:
                lists.append('\t\t%s\n\t\t{\n%s\t\t}' % (_quote('%s_%s' % (set_name, rarity)),
                                                         ''.join('\t\t\t%s\t\t"1"\n' % _quote(i) for i in tiers[rarity])))
    family_text = '"skin_families"\n{\n' + ''.join(
        '\t%s\n\t{\n%s\t}\n' % (_quote(name), ''.join('\t\t%s\t"1"\n' % _quote(v) for v in variants))
        for name, variants in sorted(families.items())) + '}\n'
    return family_kits, '\n'.join(sets), '\n'.join(lists), family_text, names, entries


def collections_test_spec(list_names):
    return dict(name=COLLECTIONS_TEST_NAME, title='Custom Collections Test Case', base=CASE_BASE, items=[],
                loot_lists=list_names,
                description='Test case: rolls the custom Doppler, Spectrum and Knife Classics collections '
                            '(one colour from each family). Only given by grant_custom_collections_test_cases.cmd.')

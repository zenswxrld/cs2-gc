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

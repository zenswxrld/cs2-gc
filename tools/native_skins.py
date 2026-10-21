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


def test_case_spec(items):
    return dict(name=TEST_CASE_NAME, title=TEST_CASE_TITLE, base=CASE_BASE, items=items,
                description='Test case: knife finishes and recolours on guns, before they become Armory '
                            'collections. Only given by grant_custom_skins_test_cases.cmd.')

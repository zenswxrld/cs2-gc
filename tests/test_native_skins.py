import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import native_skins as skins

SCHEMA = '''"items_game" { "items" { "7" { "name" "weapon_ak47" } "4" { "name" "weapon_glock" } }
  "client_loot_lists" { "set_x" { "[aa_fade]weapon_glock" "1" } } }'''


class CustomSkins(unittest.TestCase):
    def test_test_case_has_knife_finishes_and_recolours_on_guns_but_no_official_pairs(self):
        recolours = ['rk_aa_fade_ocean_%d' % i for i in range(20)] + ['rk_am_zebra_lime']
        items = skins.test_items(SCHEMA, {'aa_fade', 'am_doppler_phase1', 'hy_webs'}, recolours)
        self.assertIn('[aa_fade]weapon_ak47', items)
        self.assertNotIn('[aa_fade]weapon_glock', items)  # Glock | Fade exists: stays in its own collection
        self.assertIn('[am_doppler_phase1]weapon_glock', items)
        self.assertFalse([i for i in items if 'weapon_m4a1' in i])  # weapons missing from the schema are skipped
        self.assertFalse([i for i in items if 'am_zebra_lime' in i])  # only fade/doppler recolours
        for weapon in ('weapon_ak47', 'weapon_glock'):
            self.assertEqual(len([i for i in items if i.startswith('[rk_') and i.endswith(']' + weapon)]),
                             skins.RECOLOURS_PER_WEAPON)
        self.assertEqual(items, skins.test_items(SCHEMA, {'aa_fade', 'am_doppler_phase1', 'hy_webs'}, recolours))
        self.assertEqual(skins.test_case_spec(items)['name'], 'crate_cs2gc_custom_skins_test')


if __name__ == '__main__':
    unittest.main()

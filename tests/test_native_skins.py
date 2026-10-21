import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import native_skins as skins
sys.path.insert(0, str(Path(__file__).resolve().parent))

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

    def test_batch_two_covers_other_guns_and_named_extras_on_every_gun(self):
        schema = SCHEMA.replace('"4" { "name" "weapon_glock" }', '"4" { "name" "weapon_glock" } "8" { "name" "weapon_aug" }')
        recolours = ['rk_aa_fade_ocean', 'rk_am_gold_brick_lava', 'rk_am_gold_brick_toxic']
        items = skins.test2_items(schema, {'aa_fade', 'am_gold_brick'}, recolours)
        self.assertIn('[aa_fade]weapon_aug', items)
        self.assertNotIn('[aa_fade]weapon_ak47', items)  # batch-one guns only get the extras here
        self.assertTrue({'[am_gold_brick]weapon_ak47', '[am_gold_brick]weapon_aug'} <= set(items))
        self.assertIn('[rk_am_gold_brick_lava]weapon_glock', items)
        self.assertTrue(skins.test2_case_spec(items)['name'].endswith('_test'))  # never a match drop

    def test_collections_list_one_family_finish_per_gun_by_tier_and_families_hold_every_colour(self):
        kits = {'am_doppler_phase1': ('1', {'name': 'am_doppler_phase1', 'style': '5'}),
                'am_doppler_phase2': ('2', {'name': 'am_doppler_phase2', 'style': '5', 'wear_default': '0.1'}),
                'aa_fade': ('3', {'name': 'aa_fade', 'style': '6'})}
        recolours = ['rk_am_doppler_phase1_lava', 'rk_aa_fade_ocean', 'rk_am_zebra_lime']
        family_kits, sets, lists, families, names, items = skins.collections(
            SCHEMA, kits, recolours, lambda name, values: 'weapons/paints/legacy/%s.vcompmat' % name)
        self.assertEqual(names, ['set_cs2gc_doppler', 'set_cs2gc_spectrum'])  # classics: no finish in this schema
        doppler = dict((n, v) for n, _, v in family_kits)['cgf_doppler_ancient']
        self.assertEqual(doppler['composite_material_path'], 'weapons/paints/legacy/am_doppler_phase2.vcompmat')
        self.assertEqual((doppler['_rarity'], doppler['wear_default']), ('ancient', '0.1'))
        self.assertIn('[cgf_doppler_ancient]weapon_ak47', items)  # AK is a Covert gun
        self.assertIn('[cgf_doppler_legendary]weapon_glock', items)
        self.assertIn('"set_cs2gc_doppler_ancient"', lists)
        self.assertIn('"The Doppler Collection"', sets)
        self.assertIn('"cgf_doppler_ancient"\n\t{\n\t\t"am_doppler_phase1"\t"1"\n\t\t"am_doppler_phase2"\t"1"\n'
                      '\t\t"rk_am_doppler_phase1_lava"\t"1"', families)
        self.assertNotIn('rk_am_zebra_lime', families)
        self.assertTrue(skins.collections_test_spec(names)['name'].endswith('_test'))

    def test_prepare_writes_families_collections_and_the_test_case(self):
        import json, tempfile
        import native_finishes as finishes, native_tradeups, vpk_pack
        from inventory_item import as_dict, collect, parse
        from test_native_finishes import GOLD, SCHEMA as KNIVES, vpk_files
        from test_native_tradeups import GAMEINFO
        schema = KNIVES.replace('"500" { "name" "weapon_bayonet" "prefab" "melee_unusual" }',
                                '"500" { "name" "weapon_bayonet" "prefab" "melee_unusual" }\n\t\t"7" { "name" "weapon_ak47" }'
                                ).replace('"paint_kits_rarity"', '"item_sets" { }\n\t"paint_kits_rarity"')
        with tempfile.TemporaryDirectory() as folder:
            game = Path(folder) / 'game'
            proxy = game / 'bin/win64'; proxy.mkdir(parents=True)
            info = game / 'csgo/gameinfo.gi'; info.parent.mkdir()
            native_tradeups.atomic_write(info, GAMEINFO)
            (proxy / 'gold_pools.txt').write_text(GOLD)
            directory, archive = vpk_pack.build(sorted(vpk_files().items()))
            (game / 'csgo/pak01_dir.vpk').write_bytes(directory)
            (game / 'csgo/pak01_000.vpk').write_bytes(archive)
            patched, _ = finishes.prepare(proxy, {'knife_finishes': 1}, schema)
            sections = collect(parse(patched))
            self.assertFalse(sections.get('item_sets'))  # an item_set without a #CSGO_ name token crashes CS2
            self.assertIn('set_cs2gc_spectrum', sections['client_loot_lists'])
            self.assertEqual(dict(sections['client_loot_lists'][skins.COLLECTIONS_TEST_NAME]), {'set_cs2gc_spectrum': '1', 'set_cs2gc_classics': '1'})  # Fade and Slaughter in the fixture
            kits = {as_dict(v)['name']: as_dict(v) for v in sections['paint_kits'].values()}
            self.assertEqual(sections['paint_kits_rarity']['cgf_fade_ancient'], 'ancient')
            self.assertEqual(kits['cgf_fade_ancient']['description_tag'], 'Fade')
            families = (proxy / skins.FAMILIES_FILE).read_text()
            self.assertIn('"aa_fade"', families)
            self.assertIn('"rk_aa_fade_crimson"', families)
            ids = json.loads((proxy / 'cs2_gc_finish_ids.json').read_text())
            self.assertIn('cgf_fade_ancient', ids)
            again, _ = finishes.prepare(proxy, {'knife_finishes': 1}, schema)
            self.assertEqual(again, patched)  # stable ids and output


if __name__ == '__main__':
    unittest.main()

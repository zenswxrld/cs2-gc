import re
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

    def test_collections_are_small_with_one_covert_chase_whose_family_holds_every_colour(self):
        kits = {'am_doppler_phase1': ('1', {'name': 'am_doppler_phase1', 'style': '5'}),
                'am_doppler_phase2': ('2', {'name': 'am_doppler_phase2', 'style': '5', 'wear_default': '0.1'}),
                'hy_granite': ('3', {'name': 'hy_granite', 'style': '2'}),
                'sp_palm': ('4', {'name': 'sp_palm', 'style': '3'}),
                'hy_ak47lam': ('5', {'name': 'hy_ak47lam', 'style': '2'})}
        titles = {'hy_granite': 'Granite', 'sp_palm': 'Palm', 'hy_ak47lam': 'Laminate'}
        schema = SCHEMA.replace('"4" { "name" "weapon_glock" }', '"4" { "name" "weapon_glock" } "8" { "name" "weapon_aug" }'
                                ' "9" { "name" "weapon_nova" }')
        new, _, lists, family_map, names, items, chases = skins.collections(
            schema, kits, ['rk_am_doppler_phase1_lava', 'rk_am_zebra_lime'],
            lambda name, values: 'weapons/paints/legacy/%s.vcompmat' % name, titles)
        families = skins.family_text(family_map)
        self.assertIn('set_cs2gc_doppler_ak47', names)
        self.assertEqual(chases[names.index('set_cs2gc_doppler_ak47')], '[cgf_doppler_ancient]weapon_ak47')
        self.assertIn('"set_cs2gc_doppler_ak47_ancient"\n\t\t{\n\t\t\t"[cgf_doppler_ancient]weapon_ak47"\t\t"1"\n\t\t}', lists)
        values = dict((n, v) for n, _, v in new)
        self.assertEqual(values['cgf_doppler_ancient']['composite_material_path'],
                         'weapons/paints/legacy/am_doppler_phase2.vcompmat')
        self.assertFalse([n for n in values if 'ak47lam' in n])  # weapon-named patterns are not fillers
        fillers = [i for i in items if i.startswith('[cga_')]
        self.assertTrue(fillers and all(re.match(r'\[cga_(hy_granite|sp_palm)_(legendary|mythical|rare|uncommon)\]', i) for i in fillers))
        self.assertEqual({v['_rarity'] for n, v in values.items() if n.startswith('cga_')}, {'legendary', 'mythical', 'rare', 'uncommon'})
        self.assertEqual({t for n, t, _ in new if n.startswith('cga_hy_granite_')}, {'Granite'})
        # Only our colours, each named like the family, at the chase's rarity.
        self.assertIn('"cgf_doppler_ancient"\n\t{\n\t\t"cgv_am_doppler_phase1_lava_ancient"\t"1"\n\t}', families)
        self.assertNotIn('"am_doppler_phase1"', families)
        self.assertEqual(dict((n, t) for n, t, _ in new)['cgv_am_doppler_phase1_lava_ancient'], 'Doppler')
        self.assertEqual(values['cgv_am_doppler_phase1_lava_ancient']['composite_material_path'],
                         'weapons/paints/cs2_gc/rk_am_doppler_phase1_lava.vcompmat')
        self.assertNotIn('am_zebra', families)
        self.assertEqual(len(skins.COLLECTIONS), skins.COLLECTION_COUNT)
        self.assertEqual(skins.COLLECTIONS['set_cs2gc_doppler_ak47'][0], 'The AK-47 Doppler Collection')
        self.assertTrue(skins.chase_test_spec(chases)['name'].endswith('_test'))

    def test_prepare_writes_families_collections_and_the_test_case(self):
        import json, tempfile
        import native_finishes as finishes, native_tradeups, vpk_pack
        from inventory_item import as_dict, collect, parse
        from test_native_finishes import GOLD, SCHEMA as KNIVES, vpk_files
        from test_native_tradeups import GAMEINFO
        schema = KNIVES.replace('"500" { "name" "weapon_bayonet" "prefab" "melee_unusual" }',
                                '"500" { "name" "weapon_bayonet" "prefab" "melee_unusual" }\n\t\t"7" { "name" "weapon_ak47" }'
                                ' "9" { "name" "weapon_awp" } "10" { "name" "weapon_nova" }'
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
            tests = dict(sections['client_loot_lists'][skins.COLLECTIONS_TEST_NAME])
            self.assertIn('set_cs2gc_fade_awp', tests)
            self.assertIn('set_cs2gc_fade_awp', sections['client_loot_lists'])
            self.assertIn(skins.CHASE_TEST_NAME, sections['client_loot_lists'])
            kits = {as_dict(v)['name']: as_dict(v) for v in sections['paint_kits'].values()}
            self.assertEqual(sections['paint_kits_rarity']['cgf_fade_ancient'], 'ancient')
            self.assertEqual(kits['cgf_fade_ancient']['description_tag'], 'Fade')
            families = (proxy / skins.FAMILIES_FILE).read_text()
            self.assertNotIn('"aa_fade"', families)  # not the plain Fade: only Fade colours of ours
            self.assertIn('"cgv_aa_fade_crimson_ancient"', families)
            self.assertEqual(kits['cgv_aa_fade_crimson_ancient']['description_tag'], 'Fade')
            ids = json.loads((proxy / 'cs2_gc_finish_ids.json').read_text())
            self.assertIn('cgf_fade_ancient', ids)
            again, _ = finishes.prepare(proxy, {'knife_finishes': 1}, schema)
            self.assertEqual(again, patched)  # stable ids and output

    def test_custom_cases_use_the_collection_layout_with_three_colour_ranges(self):
        import native_finishes as finishes
        kits = {'am_doppler_phase2': ('2', {'name': 'am_doppler_phase2', 'style': '5'})}
        guns = sorted({w for tier in skins.TIERS.values() for w in tier})
        for i in range(30):
            kits['hy_pattern%d' % i] = (str(100 + i), {'name': 'hy_pattern%d' % i, 'style': '2'})
        titles = {name: 'Pattern %d' % i for i, name in enumerate(n for n in kits if n.startswith('hy_'))}
        schema = '"items_game" { "items" { %s } }' % ' '.join('"%d" { "name" "%s" }' % (i, g) for i, g in enumerate(guns))
        families = {'cgf_doppler_ancient': ['cgv_am_doppler_phase1_lava_ancient']}
        original = finishes.make_finish
        finishes.make_finish = lambda source, kit, path, name, theme: (b'compmat:' + name.encode(), b'vmat')
        try:
            new, files, lists, specs, items, icons = skins.custom_cases(
                schema, kits, titles, lambda n, v: 'weapons/paints/legacy/%s.vcompmat' % n, None, families,
                {'cgf_doppler_ancient'})
        finally:
            finishes.make_finish = original
        self.assertEqual(len(specs), len(skins.CASE_ICONS))
        spec = specs[0]
        self.assertTrue(spec['name'].startswith(skins.CASE_PREFIX) and not spec['name'].endswith('_test'))
        counts = {t: lists.count('"[', lists.index('"%s_%s"' % (spec['name'], t)),
                                 lists.index('}', lists.index('"%s_%s"' % (spec['name'], t))))
                  for t in ('ancient', 'legendary', 'mythical', 'rare', 'uncommon')}
        self.assertEqual(counts, {'ancient': 1, 'legendary': 2, 'mythical': 3, 'rare': 4, 'uncommon': 6})
        case_items = [i for i in items if i]
        self.assertIn('[cgf_doppler_ancient]weapon_ak47', items)
        ranged = [i for i in items if i.startswith('[cgc_')]
        self.assertEqual(len([i for i in ranged if '_legendary]' in i]), len(specs))  # one Classified range per case
        self.assertEqual(len([i for i in ranged if '_mythical]' in i]), len(specs))
        some = next(k for k in families if k.startswith('cgc_'))
        self.assertEqual(len(families[some]), skins.CLASSIC_THEMES)
        self.assertTrue(all(v.startswith('cgr_') for v in families[some]))
        self.assertTrue(any(path.endswith('.vcompmat_c') and '/rc_hy_pattern' in path for path in files))
        self.assertEqual(icons[spec['name']], skins.CASE_ICONS[0])


if __name__ == '__main__':
    unittest.main()

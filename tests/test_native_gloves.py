import json
import colorsys
import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import kv3
from kv3 import Node
import native_finishes as finishes
import native_gloves as gloves
import native_tradeups
import vpk_pack
from inventory_item import as_dict, collect, parse
from test_native_finishes import ENGLISH, GOLD, GUID, SCHEMA, compmat, obj, string, vpk_files
from test_native_tradeups import GAMEINFO

GLOVE_ITEMS = '''"500" { "name" "weapon_bayonet" "prefab" "melee_unusual" }
		"4017" { "name" "crate_community_3" "prefab" "weapon_case" "associated_items" { "1307" "1" } }
		"5030" { "name" "sporty_gloves" "prefab" "hands_paintable" }
		"5034" { "name" "specialist_gloves" "prefab" "hands_paintable" }'''
SCHEMA_GLOVES = SCHEMA.replace('"500" { "name" "weapon_bayonet" "prefab" "melee_unusual" }', GLOVE_ITEMS).replace(
    '"1001" {', '"10037" { "name" "sporty_purple" "description_tag" "#PaintKit_sporty_purple_tag" }\n\t\t"1001" {')
GOLD_GLOVES = GOLD.replace('"500:59" "1"', '"500:59" "1" "5030:10037" "1"')
TINTS = [[0.33, 0.12, 0.45, 0], [0.36, 0.2, 0.6, 0], [0.22, 0.2, 0.25, 0], [0.29, 0.24, 0.35, 0],
         [0.2, 0.22, 0.24, 0], [0.47, 0.5, 0.6, 0], [0.88, 0.88, 0.88, 0], [0.17, 0.65, 0.78, 0]]


def glove_files():
    vectors = [obj(('m_name', string('g_vColorTint%d' % (i + 1))),
                   ('m_value', Node(kv3.ARRAY_TYPE_BYTE_LENGTH, [Node(kv3.FLOAT, v) for v in c], 0, kv3.FLOAT)))
               for i, c in enumerate(TINTS)]
    root = obj(('m_materialName', string('gloves/paints/sporty_purple.vmat')),
               ('m_shaderName', string('csgo_customglove.vfx')),
               ('m_vectorParams', Node(kv3.ARRAY_TYPE_BYTE_LENGTH, vectors, 0, kv3.OBJECT)))
    files = vpk_files()
    files['gloves/paints/sporty_purple.vcompmat_c'] = compmat('gloves/paints/sporty_purple.vmat')
    files['gloves/paints/sporty_purple.vmat_c'] = kv3.write_resource(0, [['DATA', kv3.write_kv3(GUID, root)]])
    files['gloves/paints/volatile_02/glove_specialist_dragon_red.vcompmat_c'] = b'shipped'
    files['resource/csgo_english.txt'] = ENGLISH.replace(
        '"Twilight Galaxy"', '"Twilight Galaxy"\n\t\t"PaintKit_sporty_purple_tag"\t"Pandora\'s Box"').encode()
    return files


class NativeGloves(unittest.TestCase):
    def test_gauntlet_case_has_glove_recolours_and_the_unreleased_finishes(self):
        with tempfile.TemporaryDirectory() as folder:
            game = Path(folder) / 'game'
            proxy = game / 'bin/win64'; proxy.mkdir(parents=True)
            info = game / 'csgo/gameinfo.gi'; info.parent.mkdir()
            native_tradeups.atomic_write(info, GAMEINFO)
            (proxy / 'gold_pools.txt').write_text(GOLD_GLOVES)
            directory, archive = vpk_pack.build(sorted(glove_files().items()))
            (game / 'csgo/pak01_dir.vpk').write_bytes(directory)
            (game / 'csgo/pak01_000.vpk').write_bytes(archive)
            patched, status = finishes.prepare(proxy, {'knife_finishes': 1}, SCHEMA_GLOVES)
            self.assertIn('Gauntlet Case', status)
            sections = collect(parse(patched))
            case = [as_dict(v) for v in sections['items'].values() if as_dict(v).get('name') == gloves.CASE_NAME][0]
            self.assertEqual(case['item_name'], 'Gauntlet Case')
            self.assertEqual(case['associated_items'], [('1307', '1')])  # the Huntsman key, like OfflineCS
            contents = dict(sections['client_loot_lists'][gloves.CASE_NAME + '_ancient'])
            self.assertIn('[ug_glove_specialist_dragon_red]specialist_gloves', contents)
            all_recolours = [k for k in contents if k.startswith('[rg_sporty_purple_')]
            recolours = [k for k in all_recolours if '_panels_' not in k]
            self.assertEqual(len(recolours), gloves.THEMES_PER_GLOVE)
            self.assertEqual(len(all_recolours), gloves.THEMES_PER_GLOVE * 4)
            for style in ('white','black','inverted'):
                self.assertEqual(sum('_panels_' + style in k for k in all_recolours), gloves.THEMES_PER_GLOVE)
            self.assertTrue(all(k.endswith(']sporty_gloves') for k in recolours))  # patterns stay on their glove
            self.assertNotIn('[sporty_purple]sporty_gloves', contents)  # official gloves stay in the regular cases
            kits = {as_dict(v)['name']: as_dict(v) for v in sections['paint_kits'].values()}
            self.assertEqual(kits['ug_glove_specialist_dragon_red']['composite_material_path'],
                             'gloves/paints/volatile_02/glove_specialist_dragon_red.vcompmat')
            self.assertEqual(kits['ug_glove_specialist_dragon_red']['description_tag'], 'Fire Chaser')
            name = recolours[0][1:recolours[0].index(']')]
            self.assertTrue(kits[name]['description_tag'].startswith("Pandora's Box "))
            self.assertEqual(sections['paint_kits_rarity'][name], 'ancient')
            source = finishes.Source(vpk=game / finishes.FOLDER / 'pak01_dir.vpk')
            _, blocks = kv3.read_resource(source.read(gloves.VMAT_DIR + name + '.vmat_c'))
            new = gloves._tints(kv3.read_kv3(dict(blocks)['DATA'])[1])
            values = [[round(v.value, 3) for v in new['g_vColorTint%d' % i].value] for i in range(1, 9)]
            self.assertNotEqual(values, TINTS)
            for index in (2,3,4,5,6):
                self.assertEqual(values[index], TINTS[index], 'structural channel must retain original colour')
            report=json.loads((proxy/gloves.PALETTE_REPORT).read_text())
            self.assertEqual(report['gloves/paints/sporty_purple.vcompmat']['accent_channels'], [1,2,8])
            # Tints multiply the glove's texture: brightness stays exactly as shipped.
            self.assertEqual([round(max(c[:3]), 2) for c in values], [round(max(c[:3]), 2) for c in TINTS])
            self.assertTrue(source.exists('panorama/images/econ/weapon_cases/%s_png.vtex_c' % gloves.CASE_NAME))
            self.assertEqual(source.read(finishes.ICON_DIR + 'sporty_gloves_%s_light_png.vtex_c' % name), b'RARE-ICON')
            reels = json.loads((proxy / finishes.REEL_FILE).read_text())
            self.assertTrue(reels[gloves.CASE_NAME] and all(p[0] in (5030, 5034) for p in reels[gloves.CASE_NAME]))
            self.assertTrue(all(p[0] in (500, 507) for p in reels[finishes.CASE_NAME]))
            ids = json.loads((proxy / 'cs2_gc_finish_ids.json').read_text())
            self.assertFalse(set(ids.values()) & {int(k) for k in collect(parse(SCHEMA_GLOVES))['paint_kits']})
            self.assertEqual(len(set(ids.values())), len(ids))
            again, status = finishes.prepare(proxy, {'knife_finishes': 1}, SCHEMA_GLOVES)
            self.assertEqual(again, patched)
            self.assertNotIn('RESTART', status)
            self.assertEqual(json.loads((proxy/'cs2_gc_finish_ids.json').read_text()),ids)
            variants_off,_=finishes.prepare(proxy, {'knife_finishes':1,'glove_panel_variants':0}, SCHEMA_GLOVES)
            off_sections=collect(parse(variants_off))
            off_contents=dict(off_sections['client_loot_lists'][gloves.CASE_NAME+'_ancient'])
            self.assertFalse(any('_panels_' in name for name in off_contents))
            off_kits={as_dict(v)['name'] for v in off_sections['paint_kits'].values()}
            self.assertTrue(all(key in off_kits for key in ids if key.startswith('rg_')))
            self.assertEqual(json.loads((proxy/'cs2_gc_finish_ids.json').read_text()),ids)
            off, status = finishes.prepare(proxy, {'knife_finishes': 1, 'glove_finishes': 0}, SCHEMA_GLOVES)
            self.assertNotIn(gloves.CASE_NAME, off)
            self.assertIn('Black Market Case', status)

    def test_accent_hue_changes_preserve_neutral_panels_value_saturation_and_alpha(self):
        colors=[[.05,.05,.05,0], [.9,.9,.9,.2], [.3,.31,.32,.3], [.08,.4,.8,.7], [.1,.11,.12,1]]
        result=gloves.recolor_accents(colors,'Magenta')
        for index in (0,1,2,4): self.assertEqual(result[index],colors[index])
        self.assertNotEqual(result[3][:3],colors[3][:3])
        self.assertEqual(result[3][3],colors[3][3])
        self.assertAlmostEqual(max(result[3][:3]),max(colors[3][:3]))
        self.assertLessEqual(colorsys.rgb_to_hsv(*result[3][:3])[1],colorsys.rgb_to_hsv(*colors[3][:3])[1])
        self.assertEqual(colors[3],[.08,.4,.8,.7], 'source palette must remain untouched')

    def test_panel_variants_change_neutrals_but_keep_the_same_accents(self):
        colors=[[.04,.04,.04,0], [.9,.9,.9,.3], [.08,.4,.8,.7]]
        base=gloves.recolor_accents(colors,'Magenta')
        for style in ('white','black','inverted'):
            result=gloves.recolor_accents(colors,'Magenta',panels=style)
            self.assertEqual(result[2],base[2])
            self.assertEqual([c[3] for c in result],[c[3] for c in colors])
        white=gloves.recolor_accents(colors,'Magenta',panels='white')
        black=gloves.recolor_accents(colors,'Magenta',panels='black')
        inverted=gloves.recolor_accents(colors,'Magenta',panels='inverted')
        self.assertGreater(min(white[0][:3]),.8)
        self.assertLess(max(black[1][:3]),.11)
        self.assertGreater(inverted[0][0],.8)
        self.assertLess(inverted[1][0],.15)
        self.assertNotEqual(white[0][:3],white[1][:3], 'preserve tonal differences instead of a flat white')

    def test_neutral_palettes_are_not_given_an_all_over_hue_and_bad_vectors_reject(self):
        neutral=[[v,v,v,0] for v in (0,.04,.2,.5,.9,1)]
        self.assertEqual(gloves.recolor_accents(neutral,'Crimson'),neutral)
        for invalid in ([[0,0,0]], [[math.nan,0,0,0]], [[2,0,0,0]]):
            with self.assertRaises(ValueError):gloves.recolor_accents(invalid,'Crimson')
        with self.assertRaises(ValueError):gloves.recolor_accents(neutral,'Crimson',panels='unknown')

    def test_only_eight_tint_glove_materials_are_recoloured(self):
        source = finishes.Source(folder=None)
        source.read = vpk_files().get
        self.assertIsNone(gloves.make_glove_finish(source, 'weapons/paints/legacy/aa_fade.vcompmat', 'x', 'Lime'))

    def test_approved_forest_ddpat_toxic_keeps_exact_legacy_palette(self):
        files = glove_files()
        path = 'gloves/paints/specialist_forest_brown.vcompmat'
        files[path + '_c'] = files['gloves/paints/sporty_purple.vcompmat_c']
        source = finishes.Source(folder=None)
        source.read = files.get
        for theme,panels in (('Toxic','original'), ('Toxic','white'), ('Magenta','original')):
            report = {}
            made = gloves.make_glove_finish(source,path,'test',theme,panels=panels,report=report)
            _,blocks = kv3.read_resource(made[1])
            tints = gloves._tints(kv3.read_kv3(dict(blocks)['DATA'])[1])
            actual = [[v.value for v in tints[name].value] for name in gloves.TINTS]
            expected = (finishes.recolor(TINTS,theme,keep_value=True) if (theme,panels) == ('Toxic','original')
                        else gloves.recolor_accents(TINTS,theme,panels=panels))
            for a,e in zip(actual,expected):
                for av,ev in zip(a,e): self.assertAlmostEqual(av,ev,places=6)
            self.assertEqual(report[path]['preserved_legacy_themes'],['Toxic'])


if __name__ == '__main__':
    unittest.main()

import json
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
            recolours = [k for k in contents if k.startswith('[rg_sporty_purple_')]
            self.assertEqual(len(recolours), gloves.THEMES_PER_GLOVE)
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
            off, status = finishes.prepare(proxy, {'knife_finishes': 1, 'glove_finishes': 0}, SCHEMA_GLOVES)
            self.assertNotIn(gloves.CASE_NAME, off)
            self.assertIn('Black Market Case', status)

    def test_only_eight_tint_glove_materials_are_recoloured(self):
        source = finishes.Source(folder=None)
        source.read = vpk_files().get
        self.assertIsNone(gloves.make_glove_finish(source, 'weapons/paints/legacy/aa_fade.vcompmat', 'x', 'Lime'))


if __name__ == '__main__':
    unittest.main()

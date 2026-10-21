import json
import colorsys
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import kv3
from kv3 import Node
import native_finishes as finishes
import native_tradeups
import vpk_pack
from inventory_item import as_dict, collect, parse
from test_native_tradeups import GAMEINFO

GUID = bytes(range(16))
SCHEMA = '''"items_game"
{
	"rarities" { "ancient" { "value" "6" } }
	"items"
	{
		"4003"
		{
			"name"		"crate_operation_ii"
			"image_inventory"		"econ/weapon_cases/crate_operation_ii"
			"model_player"		"models/props/crates/csgo_drop_crate_bravo.vmdl"
			"prefab"		"weapon_case"
			"associated_items" { "1203" "1" }
			"tool" { "restriction" "generic_valve_key" }
			"attributes" { "set supply crate series" { "attribute_class" "supply_crate_series" "value" "3" } }
		}
		"507" { "name" "weapon_knife_karambit" "prefab" "melee_unusual" }
		"500" { "name" "weapon_bayonet" "prefab" "melee_unusual" }
	}
	"paint_kits"
	{
		"38" { "name" "aa_fade" "description_tag" "#PaintKit_aa_fade_Tag" "style" "6" "wear_default" "0.2" }
		"59" { "name" "am_zebra" "description_tag" "#PaintKit_am_zebra_Tag" "style" "5" "use_legacy_model" "1" }
		"1001" { "name" "am_aqua_flecks" "description_tag" "#PaintKit_am_aqua_flecks_Tag" "style" "5" }
	}
	"paint_kits_rarity" { "aa_fade" "ancient" }
	"client_loot_lists" { "crate_series_3" { "[aa_fade]weapon_bayonet" "1" } }
	"revolving_loot_lists" { "3" "crate_series_3" }
}
'''
GOLD = '"gold_pools" { "4003" { "507:38" "1" "500:0" "1" "500:59" "1" } }'
ENGLISH = '"lang"\n{\n\t"Language"\t"English"\n\t"Tokens"\n\t{\n\t\t"PaintKit_aa_fade_Tag"\t"Fade"\n' \
          '\t\t"PaintKit_am_zebra_Tag"\t"Slaughter"\n\t\t"PaintKit_am_aqua_flecks_Tag"\t"Twilight Galaxy"\n\t}\n}\n'


def string(value): return Node(kv3.STRING, value)


def obj(*pairs): return Node(kv3.OBJECT, list(pairs))


def material(name, colors):
    vectors = [obj(('m_name', string('g_vColor%d' % i)),
                   ('m_value', Node(kv3.ARRAY_TYPE_BYTE_LENGTH, [Node(kv3.FLOAT, v) for v in c], 0, kv3.FLOAT)))
               for i, c in enumerate(colors)]
    root = obj(('m_materialName', string(name)), ('m_shaderName', string('csgo_customweapon.vfx')),
               ('m_textureParams', Node(kv3.ARRAY, [obj(('m_name',string('g_tPattern')),
                                                      ('m_pValue',string('textures/source_pattern.vtex')))])),
               ('m_floatParams', Node(kv3.ARRAY, [obj(('m_name',string('g_flRoughness')),
                                                    ('m_flValue',Node(kv3.FLOAT,.42)))])),
               ('m_vectorParams', Node(kv3.ARRAY_TYPE_BYTE_LENGTH, vectors, 0, kv3.OBJECT)))
    return kv3.write_resource(0, [['RERL', b'refs'], ['DATA', kv3.write_kv3(GUID, root)], ['INSG', b'sig']])


def compmat(vmat):
    container = obj(('m_nCompositeMaterialInputContainerSourceType', string('CONTAINER_SOURCE_TYPE_SPECIFIC_MATERIAL')),
                    ('m_strSpecificContainerMaterial', string(vmat)), ('m_strAlias', string('paint')))
    root = obj(('_class', string('CCompositeMaterialEditorDoc')),
               ('m_Points', Node(kv3.ARRAY, [obj(('m_vecCompositeInputContainers', Node(kv3.ARRAY, [container])))])))
    return kv3.write_resource(0, [['RED2', b'red'], ['DATA', kv3.write_kv3(GUID, root)]])


def png(width, height):
    raw = b''.join(b'\0' + b''.join(bytes((x * 3 % 256, y, 200, 255)) for x in range(width)) for y in range(height))
    def chunk(kind, body): return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def vpk_files():
    bright = [[0.9, 0.8, 0.7, 1], [0.95, 0.6, 0.4, 1], [0.9, 0.3, 0.45, 1], [0.4, 0.5, 0.85, 1]]
    files = {}
    for kit in ('aa_fade', 'am_zebra', 'am_aqua_flecks'):
        vmat = 'materials/models/weapons/customization/paints/vmats/%s.vmat' % kit
        files['weapons/paints/legacy/%s.vcompmat_c' % kit] = compmat(vmat)
        files[vmat + '_c'] = material(vmat, bright)
    files['resource/csgo_english.txt'] = ENGLISH.encode('utf-8')
    template = kv3.write_resource(1, [['RED2', b'red'], ['DATA', struct.pack('<HH4fHHHBBIII', 1, 4, 0, 0, 0, 0, 512, 384,
                                                                                    1, 28, 1, 0, 8, 0)]])
    files['panorama/images/econ/weapon_cases/crate_operation_ii_png.vtex_c'] = template + b'\0' * 64
    files['panorama/images/econ/weapon_cases/default_rare_item_png.vtex_c'] = b'RARE-ICON'
    files['panorama/images/econ/default_generated/weapon_knife_karambit_aa_fade_light_png.vtex_c'] = b'real'
    return files


class NativeFinishes(unittest.TestCase):
    def test_gold_brick_keeps_related_metal_tones_instead_of_ranked_two_tone(self):
        colors=[[1,.88,.5,1],[.98,.9,.6,.8],[.8,.7,.4,.5],[.7,.55,.15,0]]
        result=finishes.recolor_gold_brick(colors,'Toxic')
        original_hsv=[colorsys.rgb_to_hsv(*c[:3]) for c in colors]
        changed_hsv=[colorsys.rgb_to_hsv(*c[:3]) for c in result]
        for original,changed in zip(original_hsv,changed_hsv):
            self.assertAlmostEqual(original[2],changed[2])
            self.assertLessEqual(changed[1],original[1]+1e-8)
            self.assertTrue(60 < changed[0]*360 < 100, 'related lime tones, no unrelated purple field')
        self.assertEqual([c[3] for c in colors],[c[3] for c in result])
        for index in range(1,4):
            self.assertAlmostEqual(changed_hsv[index][0]-changed_hsv[0][0],
                                   original_hsv[index][0]-original_hsv[0][0])
        source=finishes.Source(folder=None); source.read=vpk_files().get
        report={}
        made=finishes.make_finish(source,'am_gold_brick','weapons/paints/legacy/aa_fade.vcompmat',
                                  'rk_am_gold_brick_toxic','Toxic',report=report)
        self.assertIsNotNone(made)
        self.assertEqual(report['am_gold_brick']['policy'],'related-metal-tones-v1')

    def test_recolour_changes_only_colours_and_names(self):
        source = finishes.Source(folder=None)
        originals = vpk_files()
        source.read = originals.get
        report = {}
        made = finishes.make_finish(source, 'aa_fade', 'weapons/paints/legacy/aa_fade.vcompmat', 'rk_aa_fade_violet', 'Violet',report=report)
        vcompmat, vmat = made
        _, blocks = kv3.read_resource(vmat)
        self.assertEqual([name for name, _ in blocks], ['RERL', 'DATA', 'INSG'])
        _, root = kv3.read_kv3(dict(blocks)['DATA'])
        self.assertEqual(root.get('m_materialName').value, finishes.VMAT_DIR + 'rk_aa_fade_violet.vmat')
        colours = finishes._vector_params(root)
        self.assertNotEqual([round(v.value, 3) for v in colours['g_vColor0'].value][:3], [0.9, 0.8, 0.7])
        self.assertEqual(report['aa_fade']['source_material'],
                         'materials/models/weapons/customization/paints/vmats/aa_fade.vmat')
        self.assertEqual(report['aa_fade']['shader'],'csgo_customweapon.vfx')
        for index in range(4):
            for actual,expected in zip(colours['g_vColor%d'%index].value,report['aa_fade']['themes']['Violet'][index]):
                self.assertAlmostEqual(actual.value,expected,places=6)
        # Restore the only allowed edits and compare the entire material DATA: textures,
        # shader, roughness and all other source properties must remain byte-identical.
        _,original_blocks=kv3.read_resource(originals[report['aa_fade']['source_material']+'_c'])
        original_data=dict(original_blocks)['DATA']
        guid,original_root=kv3.read_kv3(original_data)
        root.get('m_materialName').value=original_root.get('m_materialName').value
        original_colours=finishes._vector_params(original_root)
        for name,nodes in colours.items():
            for value,original in zip(nodes.value,original_colours[name].value):value.value=original.value
        self.assertEqual(kv3.write_kv3(guid,root),original_data)
        _, blocks = kv3.read_resource(vcompmat)
        self.assertEqual(finishes._specific_material(kv3.read_kv3(dict(blocks)['DATA'])[1]).value,
                         finishes.VMAT_DIR + 'rk_aa_fade_violet.vmat')

    def test_prepare_builds_the_vpk_and_a_knife_only_case(self):
        with tempfile.TemporaryDirectory() as folder:
            game = Path(folder) / 'game'
            proxy = game / 'bin/win64'; proxy.mkdir(parents=True)
            info = game / 'csgo/gameinfo.gi'; info.parent.mkdir()
            native_tradeups.atomic_write(info, GAMEINFO)
            (proxy / 'gold_pools.txt').write_text(GOLD)
            directory, archive = vpk_pack.build(sorted(vpk_files().items()))
            (game / 'csgo/pak01_dir.vpk').write_bytes(directory)
            (game / 'csgo/pak01_000.vpk').write_bytes(archive)
            patched, status = finishes.prepare(proxy, {'knife_finishes': 1}, SCHEMA)
            self.assertIn('Black Market Case', status)
            palettes=json.loads((proxy/finishes.PALETTE_REPORT).read_text())
            self.assertIn('aa_fade',palettes)
            self.assertIn('Violet',palettes['aa_fade']['themes'])
            self.assertIn('Game\tcs2_gc_finishes', native_tradeups.read_text(info))
            sections = collect(parse(patched))
            case = [as_dict(v) for v in sections['items'].values() if as_dict(v).get('name') == finishes.CASE_NAME][0]
            self.assertEqual(case['image_inventory'], finishes.CASE_IMAGE)
            contents = dict(sections['client_loot_lists'][finishes.CASE_NAME + '_ancient'])
            self.assertTrue(all('weapon_knife' in k or 'weapon_bayonet' in k for k in contents))  # knives only
            # Only custom finishes: no official knife finish, not even on another knife (they stay in regular cases).
            self.assertFalse([k for k in contents if not (k.startswith('[rk_') or k.startswith('[am_aqua_flecks]'))])
            self.assertIn('[am_aqua_flecks]weapon_bayonet', contents)
            self.assertTrue(any(k.startswith('[rk_aa_fade_') for k in contents))
            kits = {as_dict(v)['name']: as_dict(v) for v in sections['paint_kits'].values()}
            self.assertEqual(kits['rk_aa_fade_crimson']['composite_material_path'], finishes.COMPMAT_DIR + 'rk_aa_fade_crimson.vcompmat')
            self.assertEqual(kits['rk_am_zebra_crimson']['use_legacy_model'], '1')
            mod = game / finishes.FOLDER
            self.assertTrue((mod / 'pak01_dir.vpk').is_file())
            # Never ship a language file: overriding csgo_english.txt broke every string in the game.
            self.assertFalse((mod / 'resource').exists())
            self.assertEqual(kits['rk_aa_fade_crimson']['description_tag'], 'Fade Crimson')
            self.assertEqual(case['item_name'], 'Black Market Case')
            icon = (mod / ('panorama/images/' + finishes.CASE_IMAGE + '_png.vtex_c')).read_bytes()
            size = struct.unpack_from('<I', icon, 0)[0]
            self.assertEqual(len(icon) - size, 256 * 192 * 4)
            # Pairs without a shipped picture get the Rare Special Item icon, stored once in the VPK; shipped ones keep theirs.
            source = finishes.Source(vpk=mod / 'pak01_dir.vpk')
            self.assertEqual(source.read(finishes.ICON_DIR + 'weapon_bayonet_rk_aa_fade_crimson_light_png.vtex_c'), b'RARE-ICON')
            self.assertEqual(source.read(finishes.ICON_DIR + 'weapon_knife_karambit_am_aqua_flecks_heavy_png.vtex_c'), b'RARE-ICON')
            self.assertFalse(source.exists(finishes.ICON_DIR + 'weapon_knife_karambit_aa_fade_light_png.vtex_c'))
            self.assertLess((mod / 'pak01_000.vpk').stat().st_size, 400000)
            self.assertFalse(list(mod.glob('panorama/images/econ/default_generated/*')))  # never written loose
            sample = json.loads((proxy / finishes.REEL_FILE).read_text())[finishes.CASE_NAME]
            self.assertTrue(sample and all(pair[0] in (500, 507) for pair in sample))
            self.assertNotIn('crate_cs2gc_gauntlet', patched)  # no gloves in this schema: no Gauntlet Case
            ids = json.loads((proxy / 'cs2_gc_finish_ids.json').read_text())
            self.assertEqual(str(ids['rk_aa_fade_crimson']), [k for k, v in sections['paint_kits'].items()
                                                              if as_dict(v)['name'] == 'rk_aa_fade_crimson'][0])
            # Saved ids win over the order, so owned knives keep their finish when the list grows.
            moved = dict(ids, rk_aa_fade_crimson=39999)
            (proxy / 'cs2_gc_finish_ids.json').write_text(json.dumps(moved))
            again, _ = finishes.prepare(proxy, {'knife_finishes': 1}, SCHEMA)
            kept = {as_dict(v)['name']: k for k, v in collect(parse(again))['paint_kits'].items()}
            self.assertEqual(kept['rk_aa_fade_crimson'], '39999')
            (proxy / 'cs2_gc_finish_ids.json').write_text(json.dumps(ids))
            finishes.prepare(proxy, {'knife_finishes': 1}, SCHEMA)
            # Deterministic: a second run with the same files writes nothing new.
            before = (mod / 'pak01_dir.vpk').read_bytes()
            again, status = finishes.prepare(proxy, {'knife_finishes': 1}, SCHEMA)
            self.assertEqual(again, patched)
            self.assertNotIn('RESTART', status)
            self.assertEqual((mod / 'pak01_dir.vpk').read_bytes(), before)
            _, status = finishes.prepare(proxy, {'knife_finishes': 0}, SCHEMA)
            self.assertEqual(status, 'disabled')
            self.assertNotIn('cs2_gc_finishes', native_tradeups.read_text(info))

    def test_png_and_case_are_refused_twice(self):
        width, height, rows = finishes.read_png(png(3, 2))
        self.assertEqual((width, height, len(rows[0])), (3, 2, 12))
        with self.assertRaises(ValueError): finishes.patch_items_game(SCHEMA.replace('"items"', '"items" { "1" { "name" "crate_cs2gc_black_market" } }\n\t"x"'), [], [])


if __name__ == '__main__':
    unittest.main()

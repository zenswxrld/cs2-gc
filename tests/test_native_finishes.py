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
    def test_localized_titles_survive_escaped_quotes_and_multiline_descriptions(self):
        english = r'''"lang" { "Language" "English" "Tokens" {
        "desc" "Some \"quoted\" text\nnext line"
        "PaintKit_gsch_sport_ump45_Tag" "Crimson Foil"
        "PaintKit_aq_titanium_rainbow_Tag" "Rainbow Spoon"
        } }'''
        kits={'foil':('1',{'description_tag':'#PaintKit_gsch_sport_ump45_Tag'}),
              'spoon':('2',{'description_tag':'#PaintKit_aq_titanium_rainbow_Tag'})}
        self.assertEqual(finishes.titles_from(english,kits),
            {'foil':'Crimson Foil','spoon':'Rainbow Spoon'})

    def test_detail_policy_protects_silver_dark_ink_values_alpha_and_hue_relationships(self):
        from collection_detail import recolour_details,rolled_name
        original=[[.04,.04,.04,.2],[.8,.12,.05,.4],[.94,.94,.94,.6],[.4,.16,.08,.8]]
        changed=recolour_details(original,'Teal',finishes.THEMES,finishes.DUO_THEMES,finishes.GRADIENT_THEMES)
        self.assertEqual(changed[0],original[0]);self.assertEqual(changed[2],original[2])
        self.assertEqual([max(c[:3]) for c in changed],[max(c[:3]) for c in original])
        self.assertEqual([c[3] for c in changed],[c[3] for c in original])
        before=[colorsys.rgb_to_hsv(*c[:3])[0] for c in original]
        after=[colorsys.rgb_to_hsv(*c[:3])[0] for c in changed]
        self.assertAlmostEqual((before[1]-before[3])%1,(after[1]-after[3])%1)
        self.assertEqual(rolled_name('Crimson Foil','Teal'),'Teal Foil')
        neutral=[[.03,.03,.03,1],[.3,.3,.3,1],[.7,.7,.7,1],[.97,.97,.97,1]]
        painted=recolour_details(neutral,'Violet',finishes.THEMES,finishes.DUO_THEMES,finishes.GRADIENT_THEMES)
        self.assertEqual(sum(a!=b for a,b in zip(neutral,painted)),1)

    def test_detail_material_policy_preserves_every_non_colour_property(self):
        originals=vpk_files()
        source=finishes.Source(folder=None);source.read=originals.get
        report={}
        made=finishes.make_finish(source,'aa_fade','weapons/paints/legacy/aa_fade.vcompmat',
            'detail_test','Teal',report=report,weapon_palette='ancient',detail_policy=True)
        self.assertIsNotNone(made)
        self.assertEqual(report['aa_fade:ancient']['policy'],'source-detail-v1')
        _,oldblocks=kv3.read_resource(originals[report['aa_fade:ancient']['source_material']+'_c'])
        old_data=dict(oldblocks)['DATA'];_,old_root=kv3.read_kv3(old_data)
        _,newblocks=kv3.read_resource(made[1]);guid,root=kv3.read_kv3(dict(newblocks)['DATA'])
        root.get('m_materialName').value=old_root.get('m_materialName').value
        for key,node in finishes._vector_params(root).items():
            for value,old in zip(node.value,finishes._vector_params(old_root)[key].value):
                value.value=old.value
        self.assertEqual(kv3.write_kv3(guid,root),old_data)


    def test_weapon_palette_preserves_neutral_details_and_changes_accents(self):
        from weapon_palettes import recolour,is_new_colourway,invert_panels
        original=[[.08,.08,.08,.4],[.8,.2,.12,.6],[.94,.94,.94,.8],[.35,.1,.08,1]]
        changed=recolour(original,'Vapor','ancient',finishes.THEMES,finishes.DUO_THEMES,finishes.GRADIENT_THEMES)
        self.assertEqual(changed[0],original[0]);self.assertEqual(changed[2],original[2])
        self.assertEqual([c[3] for c in changed],[c[3] for c in original])
        self.assertTrue(is_new_colourway(original,changed))
        self.assertFalse(is_new_colourway(original,original))
        near=[[min(1,x+.01) if i<3 else x for i,x in enumerate(c)] for c in original]
        self.assertFalse(is_new_colourway(original,near))
        inverse=invert_panels(original,changed)
        self.assertGreater(max(inverse[0][:3]),.8);self.assertLess(max(inverse[2][:3]),.2)
        self.assertEqual(inverse[1],changed[1]);self.assertEqual(inverse[3],changed[3])
        self.assertEqual([c[3] for c in inverse],[c[3] for c in original])

    def test_weapon_material_edits_only_colours_and_owned_material_name(self):
        from weapon_palettes import is_new_colourway
        files=vpk_files()
        class Source:
            def read(self,path):return files.get(path)
        report={}
        made=finishes.make_finish(Source(),'aa_fade','weapons/paints/legacy/aa_fade.vcompmat',
                                  'test_weapon','Vapor',report=report,weapon_palette='ancient',weapon_inverse=True)
        self.assertIsNotNone(made)
        entry=report['aa_fade:ancient']
        self.assertTrue(is_new_colourway(entry['original_colors'],entry['themes']['Vapor / inverted']))
        self.assertEqual(entry['policy'],'weapon-accent-gradient-v2')
        _,blocks=kv3.read_resource(made[1]);guid,root=kv3.read_kv3(dict(blocks)['DATA'])
        _,oldblocks=kv3.read_resource(files[entry['source_material']+'_c'])
        olddata=dict(oldblocks)['DATA'];_,oldroot=kv3.read_kv3(olddata)
        root.get('m_materialName').value=oldroot.get('m_materialName').value
        for key,node in finishes._vector_params(root).items():
            for value,old in zip(node.value,finishes._vector_params(oldroot)[key].value):value.value=old.value
        self.assertEqual(kv3.write_kv3(guid,root),olddata,'textures, roughness, shader and wear inputs stay untouched')
        # Gun gradients must bypass the legacy Gold Brick knife-only palette handler.
        self.assertIsNotNone(finishes.make_finish(Source(),'am_gold_brick',
            'weapons/paints/legacy/aa_fade.vcompmat','gold_gradient','Lava',weapon_palette='ancient'))



    def test_finish_failure_stops_native_catalogue_preparation(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            game=Path(folder)/'game';proxy=game/'bin/win64';proxy.mkdir(parents=True)
            info=game/'csgo/gameinfo.gi';info.parent.mkdir();info.write_text(GAMEINFO)
            (proxy/'items_game.txt').write_text(SCHEMA)
            target=game/native_tradeups.FOLDER/'scripts/items/items_game.txt'
            target.parent.mkdir(parents=True);target.write_text('previous complete schema')
            with patch.object(finishes,'prepare',side_effect=ValueError('unsupported material test')):
                with self.assertRaisesRegex(ValueError,'launch stopped'):
                    native_tradeups.prepare(proxy,False,{'knife_finishes':1,'armory_rotation_enabled':True})
            self.assertEqual(target.read_text(),'previous complete schema')
            self.assertEqual(info.read_text(),GAMEINFO)


    def test_unsupported_donor_compmat_or_material_is_skipped(self):
        from unittest.mock import patch
        import copy
        def older(resource):
            version, blocks = kv3.read_resource(resource)
            return kv3.write_resource(version, [[name, struct.pack('<I',0x4b563304)+data[4:] if name=='DATA' else data] for name,data in blocks])
        original=vpk_files()
        comp='weapons/paints/legacy/aa_fade.vcompmat_c'
        mat='materials/models/weapons/customization/paints/vmats/aa_fade.vmat_c'
        for path in (comp,mat):
            files=copy.copy(original);files[path]=older(files[path])
            class Source:
                def read(self,path):return files.get(path)
            self.assertIsNone(finishes.make_finish(Source(),'aa_fade',comp[:-2],'test','Teal'))
            # Another verified donor remains available; one old format never cancels it.
            self.assertIsNotNone(finishes.make_finish(Source(),'am_zebra','weapons/paints/legacy/am_zebra.vcompmat','other','Teal'))

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

    def test_hardened_retains_metal_and_two_distinct_accents(self):
        colors = [[.945,.902,.867,1], [.757,.733,.698,.8],
                  [.753,.694,.631,.5], [.106,.106,.114,0]]
        for theme in list(finishes.THEMES) + list(finishes.DUO_THEMES) + list(finishes.GRADIENT_THEMES):
            result = finishes.recolor_hardened(colors, theme)
            self.assertEqual(result[0], colors[0])
            self.assertEqual(result[3], colors[3])
            for actual, original in zip(result, colors):
                self.assertAlmostEqual(max(actual[:3]), max(original[:3]))
                self.assertEqual(actual[3], original[3])
        crimson = finishes.recolor_hardened(colors, 'Crimson')
        hues = [colorsys.rgb_to_hsv(*c[:3])[0] * 360 for c in crimson]
        self.assertAlmostEqual(hues[1], 355)
        self.assertAlmostEqual(hues[2], 300)
        source = finishes.Source(folder=None)
        source.read = vpk_files().get
        report = {}
        self.assertIsNotNone(finishes.make_finish(source, 'aq_oiled',
            'weapons/paints/legacy/aa_fade.vcompmat', 'rk_aq_oiled_crimson', 'Crimson', report=report))
        self.assertEqual(report['aq_oiled']['policy'], 'hardened-metal-accents-v1')

    def test_teal_fade_stays_teal_instead_of_sweeping_into_green(self):
        source = finishes.Source(folder=None)
        source.read = vpk_files().get
        report = {}
        made = finishes.make_finish(source, 'aa_fade', 'weapons/paints/legacy/aa_fade.vcompmat',
                                    'rk_aa_fade_teal', 'Teal', report=report)
        self.assertIsNotNone(made)
        entry = report['aa_fade']
        colors = entry['themes']['Teal']
        for color, original in zip(colors, entry['original_colors']):
            hue = colorsys.rgb_to_hsv(*color[:3])[0] * 360
            self.assertTrue(171 - 1e-6 <= hue <= 185 + 1e-6, hue)
            self.assertEqual(color[3], original[3])
        # The shared recolour function still supports the wider sweep used by gloves.
        wide = finishes.recolor(entry['original_colors'], 'Teal', fade=True)
        self.assertLess(min(colorsys.rgb_to_hsv(*c[:3])[0] * 360 for c in wide), 150)

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

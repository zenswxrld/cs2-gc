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


DEAD_HAND = 'gloves/paints/volatile_02/glove_driver_fixture_red.vcompmat'
DEAD_HAND_VMAT = 'items/assets/paintkits/volatile_02/glove_driver_fixture_red.vmat'
DEAD_HAND_IDS = [[.404, .02, .18, .835], [.38, .047, .047, 0], [.263, .259, .259, .776], [.306, .012, .141, .812],
                 [.298, .102, .169, 1], [1, 1, 1, 0], [1, 1, 1, 0], [.282, .063, .063, 1]]


def vector(name, values):
    return obj(('m_name', string(name)),
               ('m_value', Node(kv3.ARRAY_TYPE_BYTE_LENGTH, [Node(kv3.FLOAT, v) for v in values], 0, kv3.FLOAT)))


def dead_hand_files():
    """The inspected Dead Hand layout: 'paint' names the finish material, copied into the white compositor."""
    loose = obj(('m_strName', string('m_strResourceMaterial')),
                ('m_nVariableType', string('LOOSE_VARIABLE_TYPE_RESOURCE_MATERIAL')),
                ('m_strResourceMaterial', string(DEAD_HAND_VMAT)))
    paint = obj(('m_nCompositeMaterialInputContainerSourceType', string('CONTAINER_SOURCE_TYPE_LOOSE_VARIABLES')),
                ('m_strAlias', string('paint')), ('m_vecLooseVariables', Node(kv3.ARRAY, [loose])))
    compositor = obj(('m_nCompositeMaterialInputContainerSourceType', string('CONTAINER_SOURCE_TYPE_SPECIFIC_MATERIAL')),
                     ('m_strSpecificContainerMaterial', string('workshop/paintkits/templates/glove_compositor.vmat')),
                     ('m_strAlias', string('paint_compositor')))
    copy = obj(('m_nMutatorCommandType', string('COMP_MAT_PROPERTY_MUTATOR_COPY_MATCHING_KEYS')),
               ('m_strCopyMatchingKeys_InputContainerSrc', string('paint')))
    procedure = obj(('m_vecCompositeInputContainers', Node(kv3.ARRAY, [paint, compositor])),
                    ('m_vecPropertyMutators', Node(kv3.ARRAY, [copy])))
    root = obj(('_class', string('CCompositeMaterialEditorDoc')),
               ('m_Points', Node(kv3.ARRAY, [obj(('m_vecCompositeMaterialAssemblyProcedures', Node(kv3.ARRAY, [procedure])))])))
    vectors = [vector('g_vId%dColor' % (i + 1), c) for i, c in enumerate(DEAD_HAND_IDS)]
    vectors += [vector('g_vSurfaceColorTint1', [.275, .027, .027, 0]), vector('g_vSurfaceColorTint2', [1, 1, 1, 0]),
                vector('g_vDamageBevelColorTint2', [.659, .824, .835, 0]), vector('g_vDamageMinMax1', [0, 1.439, 0, 0])]
    material = obj(('m_materialName', string(DEAD_HAND_VMAT)), ('m_shaderName', string('csgo_customglove_preview.vfx')),
                   ('m_floatParams', Node(kv3.ARRAY, [obj(('m_name', string('g_flSheenScale')),
                                                          ('m_flValue', Node(kv3.FLOAT, .667)))])),
                   ('m_vectorParams', Node(kv3.ARRAY_TYPE_BYTE_LENGTH, vectors, 0, kv3.OBJECT)),
                   ('m_textureParams', Node(kv3.ARRAY, [obj(('m_name', string('g_tTintId')),
                                                            ('m_pValue', string('items/tintid.vtex')))])))
    return {DEAD_HAND + '_c': kv3.write_resource(0, [['DATA', kv3.write_kv3(GUID, root)]]),
            DEAD_HAND_VMAT + '_c': kv3.write_resource(0, [['RERL', b'refs'], ['DATA', kv3.write_kv3(GUID, material)]])}


class NativeGloves(unittest.TestCase):
    def test_composite_diagnostic_keeps_nested_override_types_names_and_values(self):
        root=obj(('m_Points',Node(kv3.ARRAY,[obj(('color',Node(kv3.ARRAY,
            [Node(kv3.FLOAT,.2),Node(kv3.FLOAT,.8)])),('color',string('repeated-name')))])),
            ('binary',Node(kv3.BINARY_BLOB,b'private-bytes')))
        before=repr(root)
        data=gloves.diagnostic_node(root)
        fields=data['value'][0][1]['value'][0]['value']
        self.assertEqual([name for name,_ in fields],['color','color'])
        self.assertEqual(fields[0][1]['value'][1]['value'],.8)
        self.assertEqual(data['value'][1][1]['value'],{'binary_length':13})
        self.assertEqual(repr(root),before)

    def test_snow_leopard_panel_variants_preserve_dark_pattern_contrast(self):
        colors=[[.69,.65,.635,0],[.659,.655,.655,0],[.47,.388,.306,0],[.725,.71,.71,0],
                [.216,.216,.216,0],[.235,.212,.212,0],[.49,.467,.431,0],[.769,.757,.737,0]]
        for panels in ('white','black','inverted'):
            result=gloves.recolor_accents(colors,'Ember',panels=panels,protect_dark_neutrals=True)
            self.assertEqual(result[4:6],colors[4:6])
        self.assertGreater(gloves.recolor_accents(colors,'Ember',panels='white',protect_dark_neutrals=True)[1][0],.8)

    def test_schema_composite_paths_are_inspected_and_only_known_tint_format_is_recoloured(self):
        path='gloves/paints/volatile_02/fixture.vcompmat'
        schema=SCHEMA_GLOVES.replace('"name" "sporty_purple"','"name" "sporty_purple" "composite_material_path" "'+path+'"')
        files=glove_files();files[path+'_c']=files.pop('gloves/paints/sporty_purple.vcompmat_c')
        source=finishes.Source(folder=None);source.read=files.get;source.exists=lambda name:name in files
        inspection={}
        _,entries,pool,_=gloves.plan(schema,GOLD_GLOVES,{},source,{},[],inspection=inspection)
        self.assertTrue(any('[rg_sporty_purple_' in item for item in pool))
        self.assertEqual(inspection[path]['status'],'supported eight-tint material')
        self.assertEqual(len(inspection[path]['vectors']),8)
        self.assertIn('"composite_material_path" "'+path+'"',schema)

    def test_lunar_weave_muted_blues_become_ash_while_brown_stays(self):
        colors=[[.23,.18,.18,0],[.28,.35,.39,0],[.33,.30,.29,0],[.28,.30,.35,0],
                [.26,.33,.31,0],[.245,.27,.29,0],[.64,.56,.41,0],[.42,.29,.20,0]]
        path='gloves/paints/slick_black.vcompmat'
        result=gloves.recolor_accents(colors,'Ash',accent_saturation=gloves.ACCENT_THRESHOLDS[path],
                                      accent_hue_range=gloves.ACCENT_HUE_RANGES[path])
        self.assertEqual([i+1 for i,(a,b) in enumerate(zip(colors,result)) if a!=b],[2,4,5,6])
        for index in (1,3,4,5):
            self.assertLessEqual(colorsys.rgb_to_hsv(*result[index][:3])[1],.100001)
            self.assertEqual(max(colors[index][:3]),max(result[index][:3]))

    def test_racing_targets_muted_green_and_teal_rather_than_brown_accents(self):
        colors=[[.18,.22,.15,0],[.29,.27,.25,0],[.49,.45,.35,0],
                [.26,.33,.31,0],[.64,.56,.41,0],[.42,.29,.2,0]]
        result=gloves.recolor_accents(colors,'Cobalt',accent_saturation=.2,accent_hue_range=(75,180))
        self.assertEqual([i for i,(a,b) in enumerate(zip(colors,result)) if a!=b],[0,3])
        for index in (0,3):
            self.assertAlmostEqual(max(colors[index][:3]),max(result[index][:3]))
            self.assertTrue(210 < colorsys.rgb_to_hsv(*result[index][:3])[0]*360 < 245)

    def test_bronzed_muted_accents_are_recoloured_without_tinting_neutrals(self):
        colors=[[.66,.59,.50,0],[.81,.81,.84,0],[.53,.54,.56,0]]
        self.assertEqual(gloves.recolor_accents(colors,'Lime'),colors)
        result=gloves.recolor_accents(colors,'Lime',accent_saturation=.20)
        self.assertNotEqual(result[0],colors[0])
        self.assertEqual(result[1:],colors[1:])
        self.assertAlmostEqual(max(result[0][:3]),max(colors[0][:3]))
        self.assertAlmostEqual(colorsys.rgb_to_hsv(*result[0][:3])[1],colorsys.rgb_to_hsv(*colors[0][:3])[1])

    def test_no_accent_themes_leave_pool_but_keep_owned_variant_definitions(self):
        schema=SCHEMA_GLOVES.replace('sporty_purple','sporty_jaguar')
        files=glove_files()
        files['gloves/paints/sporty_jaguar.vcompmat_c']=files['gloves/paints/sporty_purple.vcompmat_c']
        source=finishes.Source(folder=None);source.read=files.get;source.exists=lambda path:path in files
        _,entries,case,_=gloves.plan(schema,GOLD_GLOVES,{},source,{},[])
        known={name:int(kit) for kit,name,_,_ in entries}
        self.assertTrue(any('[rg_sporty_jaguar_' in item for item in case))
        material_path='gloves/paints/sporty_purple.vmat_c'
        _,blocks=kv3.read_resource(files[material_path]);guid,root=kv3.read_kv3(dict(blocks)['DATA'])
        for vector in gloves._tints(root).values():
            for channel in vector.value[:3]:channel.value=.4
        files[material_path]=kv3.write_resource(0,[['DATA',kv3.write_kv3(guid,root)]])
        report={}
        _,retained,no_drops,_=gloves.plan(schema,GOLD_GLOVES,{},source,known,[],report=report)
        self.assertFalse(any('[rg_sporty_jaguar_' in item for item in no_drops))
        self.assertEqual({name:int(kit) for kit,name,_,_ in retained},known)
        self.assertEqual(report['gloves/paints/sporty_jaguar.vcompmat']['accent_channels'],[])
        _,new,_,_=gloves.plan(schema,GOLD_GLOVES,{},source,{},[])
        self.assertFalse(any(name.startswith('rg_sporty_jaguar_') for _,name,_,_ in new))

    def test_dead_hand_recolours_change_only_accent_colour_vectors_and_stay_out_of_the_terminal(self):
        schema = SCHEMA_GLOVES.replace('"5030" {', '"5031" { "name" "slick_gloves" "prefab" "hands_paintable" }\n\t\t"5030" {').replace(
            '"1001" {', '"1399" { "name" "glove_driver_fixture_red" "description_tag" "#PaintKit_fixture_Tag" '
                        '"composite_material_path" "%s" }\n\t\t"1001" {' % DEAD_HAND)
        gold = GOLD_GLOVES.replace('"5030:10037" "1"', '"5030:10037" "1" "5031:1399" "1"')
        files = glove_files(); files.update(dead_hand_files())
        source = finishes.Source(folder=None); source.read = files.get; source.exists = lambda name: name in files
        report, inspection = {}, {}
        made, entries, case, _ = gloves.plan(schema, gold, {'glove_driver_fixture_red': 'Wave Chaser'}, source, {}, [],
                                             report=report, inspection=inspection)
        dead = [item for item in case if item.startswith('[rg_glove_driver_fixture_red_')]
        self.assertEqual(len(dead), gloves.THEMES_PER_GLOVE)  # every theme, original panels only
        self.assertTrue(all(item.endswith(']slick_gloves') for item in dead))
        self.assertNotIn('[glove_driver_fixture_red]slick_gloves', case)  # the original stays in its terminal
        self.assertEqual(gloves.dead_hand_test_items(case), dead)  # grant-only test case: Dead Hand recolours only
        self.assertEqual(inspection[DEAD_HAND]['status'], 'supported Dead Hand finish material')
        self.assertEqual(report[DEAD_HAND]['accent_vectors'],
                         ['g_vId1Color', 'g_vId2Color', 'g_vId4Color', 'g_vId5Color', 'g_vId8Color', 'g_vSurfaceColorTint1'])
        name = dead[0][1:dead[0].index(']')]
        self.assertTrue([title for _, kit, title, _ in entries if kit == name][0].startswith('Wave Chaser '))
        _, blocks = kv3.read_resource(made[gloves.COMPMAT_DIR + name + '.vcompmat_c'])
        self.assertEqual(gloves._dead_hand_paint(kv3.read_kv3(dict(blocks)['DATA'])[1]).value, gloves.VMAT_DIR + name + '.vmat')
        _, blocks = kv3.read_resource(made[gloves.VMAT_DIR + name + '.vmat_c'])
        self.assertEqual([block for block, _ in blocks], ['RERL', 'DATA'])
        new = kv3.read_kv3(dict(blocks)['DATA'])[1]
        _, blocks = kv3.read_resource(files[DEAD_HAND_VMAT + '_c'])
        old = kv3.read_kv3(dict(blocks)['DATA'])[1]
        values = lambda root: {e.get('m_name').value: [round(v.value, 4) for v in e.get('m_value').value]
                               for e in root.get('m_vectorParams').value}
        before, after = values(old), values(new)
        changed = sorted(k for k in before if before[k] != after[k])
        self.assertEqual(changed, sorted(report[DEAD_HAND]['accent_vectors']))
        for key in changed:
            a, b = colorsys.rgb_to_hsv(*before[key][:3]), colorsys.rgb_to_hsv(*after[key][:3])
            self.assertAlmostEqual(a[2], b[2], 3)  # brightness kept
            self.assertLessEqual(b[1], a[1] + 1e-3)  # never more saturated than shipped
            self.assertEqual(before[key][3], after[key][3])  # tint-ID alpha kept
        # Textures, floats and every non-colour vector are untouched; only the name changes.
        new.get('m_materialName').value = DEAD_HAND_VMAT
        for entry in new.get('m_vectorParams').value:
            entry.get('m_value').value = [Node(kv3.FLOAT, v) for v in before[entry.get('m_name').value]]
        restored = values(new)
        self.assertEqual(restored, before)
        self.assertEqual(new.get('m_textureParams').value[0].get('m_pValue').value, 'items/tintid.vtex')
        self.assertAlmostEqual(new.get('m_floatParams').value[0].get('m_flValue').value, .667, 5)

    def test_dead_hand_test_case_is_generated_with_only_dead_hand_recolours(self):
        schema = SCHEMA_GLOVES.replace('"5030" {', '"5031" { "name" "slick_gloves" "prefab" "hands_paintable" }\n\t\t"5030" {').replace(
            '"1001" {', '"1399" { "name" "glove_driver_fixture_red" "description_tag" "#PaintKit_fixture_Tag" '
                        '"composite_material_path" "%s" }\n\t\t"1001" {' % DEAD_HAND)
        gold = GOLD_GLOVES.replace('"5030:10037" "1"', '"5030:10037" "1" "5031:1399" "1"')
        files = glove_files(); files.update(dead_hand_files())
        with tempfile.TemporaryDirectory() as folder:
            game = Path(folder) / 'game'
            proxy = game / 'bin/win64'; proxy.mkdir(parents=True)
            info = game / 'csgo/gameinfo.gi'; info.parent.mkdir()
            native_tradeups.atomic_write(info, GAMEINFO)
            (proxy / 'gold_pools.txt').write_text(gold)
            directory, archive = vpk_pack.build(sorted(files.items()))
            (game / 'csgo/pak01_dir.vpk').write_bytes(directory)
            (game / 'csgo/pak01_000.vpk').write_bytes(archive)
            patched, _ = finishes.prepare(proxy, {'knife_finishes': 1}, schema)
            sections = collect(parse(patched))
            test = dict(sections['client_loot_lists'][gloves.TEST_CASE_NAME + '_ancient'])
            gauntlet = dict(sections['client_loot_lists'][gloves.CASE_NAME + '_ancient'])
            self.assertEqual(len(test), gloves.THEMES_PER_GLOVE)
            self.assertTrue(set(test) < set(gauntlet))
            self.assertTrue(all(k.startswith('[rg_glove_driver_fixture_red_') for k in test))
            reels = json.loads((proxy / finishes.REEL_FILE).read_text())
            self.assertTrue(reels[gloves.TEST_CASE_NAME] and all(p[0] == 5031 for p in reels[gloves.TEST_CASE_NAME]))

    def test_camo_hand_wraps_get_no_new_panel_variants_and_owned_ones_render_as_original(self):
        schema = SCHEMA_GLOVES.replace('sporty_purple', 'handwrap_camo_grey')
        files = glove_files()
        files['gloves/paints/handwrap_camo_grey.vcompmat_c'] = files['gloves/paints/sporty_purple.vcompmat_c']
        source = finishes.Source(folder=None); source.read = files.get; source.exists = lambda path: path in files
        made, entries, case, _ = gloves.plan(schema, GOLD_GLOVES, {}, source, {}, [])
        self.assertTrue(case and not any('_panels_' in item for item in case))
        self.assertFalse(any('_panels_' in name for _, name, _, _ in entries))
        original = sorted(name for _, name, _, _ in entries)[0]
        owned = original + '_panels_white'
        made, entries, case, _ = gloves.plan(schema, GOLD_GLOVES, {}, source, {owned: 39000}, [])
        self.assertIn(('39000', owned), [(kit, name) for kit, name, _, _ in entries])  # still renders for its owner
        self.assertNotIn('[%s]sporty_gloves' % owned, case)
        def tints(name):
            _, blocks = kv3.read_resource(made[gloves.VMAT_DIR + name + '.vmat_c'])
            return {k: [round(x.value, 5) for x in v.value]
                    for k, v in gloves._tints(kv3.read_kv3(dict(blocks)['DATA'])[1]).items()}
        self.assertEqual(tints(owned), tints(original))  # same colours as the original panels

    def test_printed_dead_hand_gloves_get_matching_colours_and_skipped_ones_keep_owned_items(self):
        self.assertEqual(gloves.harmonious_themes(355), ['Crimson', 'Ember', 'Amber', 'Magenta', 'Rose', 'Ash',
                                                         'Sunset', 'Inferno'])
        schema = SCHEMA_GLOVES.replace('"5030" {', '"5031" { "name" "slick_gloves" "prefab" "hands_paintable" }\n\t\t"5030" {').replace(
            '"1001" {', '"1399" { "name" "glove_driver_fixture_red" "description_tag" "#PaintKit_fixture_Tag" '
                        '"composite_material_path" "%s" }\n\t\t"1001" {' % DEAD_HAND)
        gold = GOLD_GLOVES.replace('"5030:10037" "1"', '"5030:10037" "1" "5031:1399" "1"')
        files = glove_files(); files.update(dead_hand_files())
        source = finishes.Source(folder=None); source.read = files.get; source.exists = lambda name: name in files
        prefix = '[rg_glove_driver_fixture_red_'
        try:
            gloves.DEAD_HAND_PRINT_HUES['glove_driver_fixture_red'] = 190
            _, _, case, _ = gloves.plan(schema, gold, {}, source, {}, [])
            self.assertEqual(sorted(i[len(prefix):-len(']slick_gloves')] for i in case if i.startswith(prefix)),
                             sorted(t.lower() for t in gloves.harmonious_themes(190)))
            del gloves.DEAD_HAND_PRINT_HUES['glove_driver_fixture_red']
            gloves.DEAD_HAND_SKIP.add('glove_driver_fixture_red')
            owned = {'rg_glove_driver_fixture_red_lime': 39001}
            _, entries, case, _ = gloves.plan(schema, gold, {}, source, owned, [])
            self.assertFalse([i for i in case if i.startswith(prefix)])
            self.assertIn(('39001', 'rg_glove_driver_fixture_red_lime'), [(k, n) for k, n, _, _ in entries])
        finally:
            gloves.DEAD_HAND_PRINT_HUES.pop('glove_driver_fixture_red', None)
            gloves.DEAD_HAND_SKIP.discard('glove_driver_fixture_red')

    def test_dead_hand_finish_with_only_wear_edge_accents_is_not_offered(self):
        files = glove_files(); files.update(dead_hand_files())
        _, blocks = kv3.read_resource(files[DEAD_HAND_VMAT + '_c'])
        guid, root = kv3.read_kv3(dict(blocks)['DATA'])
        for entry in root.get('m_vectorParams').value:
            if entry.get('m_name').value.startswith(('g_vId', 'g_vSurface')):
                for channel in entry.get('m_value').value[:3]: channel.value = .9
        root.get('m_vectorParams').value.append(vector('g_vDamageBevelColorTint1', [.8, .4, .2, 0]))
        files[DEAD_HAND_VMAT + '_c'] = kv3.write_resource(0, [['DATA', kv3.write_kv3(GUID, root)]])
        source = finishes.Source(folder=None); source.read = files.get; source.exists = lambda name: name in files
        report = {}
        self.assertIsNotNone(gloves.make_dead_hand_finish(source, DEAD_HAND, 'rg_x', 'Teal', report=report))
        self.assertEqual(report[DEAD_HAND]['accent_channels'], [])  # wear-edge tint only: not sold as a recolour
        self.assertEqual(report[DEAD_HAND]['accent_vectors'], ['g_vDamageBevelColorTint1'])

    def test_dead_hand_muted_shades_of_an_accent_follow_it_but_cream_and_grey_stay(self):
        # Plum Quill: strong purple accents, muted purples (~.3) on the ostrich, plus cream and white.
        colours = [[.20, .08, .33, .7], [.16, .05, .38, 1], [.47, .41, .58, .5], [.43, .35, .52, .6],
                   [1, 1, 1, 1], [.87, .80, .72, 0], [.5, .5, .5, 1]]
        picked = gloves.dead_hand_accents(colours)
        self.assertEqual(picked, {0, 1, 2, 3})

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
            self.assertNotIn(gloves.TEST_CASE_NAME, patched)  # no Dead Hand recolours, no test case
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
            for style in ('white','black','inverted'):
                variant_name = name + '_panels_' + style
                self.assertEqual(kits[variant_name]['description_tag'], kits[name]['description_tag'])
                self.assertNotEqual(kits[variant_name]['name'], kits[name]['name'])
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
        self.assertGreaterEqual(min(black[0][:3]),.12)
        self.assertLessEqual(max(black[1][:3]),.20)
        self.assertGreater(black[1][0],black[0][0], 'charcoal retains source tonal ordering')
        self.assertGreater(inverted[0][0],.8)
        self.assertLess(inverted[1][0],.21)
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

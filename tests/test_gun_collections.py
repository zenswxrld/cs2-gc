import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import kv3
from kv3 import Node
import gun_collections as gc
import native_finishes as finishes
from test_native_finishes import GUID, compmat, material, obj, string

GREYS = [[.5, .5, .5, 1], [.3, .3, .3, 1], [.9, .9, .9, 1], [.2, .2, .2, 1]]


def exposed_compmat(vmat, colours):
    """A modern composite: a shared template material, colours in its exposed parameters."""
    loose = [obj(('m_strName', string('g_vColor%d' % i)), ('m_nVariableType', string('LOOSE_VARIABLE_TYPE_COLOR4')),
                 ('m_cValueColor4', Node(kv3.ARRAY, [Node(kv3.INT32, round(c * 255)) for c in colour[:3]])))
             for i, colour in enumerate(colours)]
    loose.append(obj(('m_strName', string('g_bIgnoreWeaponSizeScale')),
                     ('m_nVariableType', string('LOOSE_VARIABLE_TYPE_BOOLEAN')), ('m_bValueBoolean', Node(kv3.BOOLEAN, False))))
    containers = [obj(('m_nCompositeMaterialInputContainerSourceType', string('CONTAINER_SOURCE_TYPE_SPECIFIC_MATERIAL')),
                      ('m_strSpecificContainerMaterial', string(vmat)), ('m_strAlias', string('paint'))),
                  obj(('m_nCompositeMaterialInputContainerSourceType', string('CONTAINER_SOURCE_TYPE_LOOSE_VARIABLES')),
                      ('m_strAlias', string('exposed_params')), ('m_vecLooseVariables', Node(kv3.ARRAY, loose)))]
    root = obj(('_class', string('CCompositeMaterialEditorDoc')),
               ('m_Points', Node(kv3.ARRAY, [obj(('m_vecCompositeInputContainers', Node(kv3.ARRAY, containers)))])))
    return kv3.write_resource(0, [['RED2', b'red'], ['DATA', kv3.write_kv3(GUID, root)]])


def patterned(name, colours, pattern):
    vectors = [obj(('m_name', string('g_vColor%d' % i)),
                   ('m_value', Node(kv3.ARRAY_TYPE_BYTE_LENGTH, [Node(kv3.FLOAT, v) for v in c], 0, kv3.FLOAT)))
               for i, c in enumerate(colours)]
    root = obj(('m_materialName', string(name)), ('m_shaderName', string('csgo_customweapon.vfx')),
               ('m_textureParams', Node(kv3.ARRAY, [obj(('m_name', string('g_tPattern')), ('m_pValue', string(pattern)))])),
               ('m_vectorParams', Node(kv3.ARRAY_TYPE_BYTE_LENGTH, vectors, 0, kv3.OBJECT)))
    return kv3.write_resource(0, [['RERL', b'refs'], ['DATA', kv3.write_kv3(GUID, root)], ['INSG', b'sig']])


def read_root(data):
    _, blocks = kv3.read_resource(data)
    return gc.plain(kv3.read_kv3(dict(blocks)['DATA'])[1])


class Classify(unittest.TestCase):
    def test_texture_coloured_and_gun_layout_finishes(self):
        colours = {'g_vColor%d' % i: [.5, .5, .5] for i in range(4)}
        self.assertEqual(gc.classify('hy_camo', dict(colours, F_PAINT_STYLE=1, g_bIgnoreWeaponSizeScale=0)), (True, True))
        # Custom paint (Asiimov): no colours at all, painted for one gun.
        self.assertEqual(gc.classify('cu_ak47_asiimov', {'F_PAINT_STYLE': 6, 'g_bIgnoreWeaponSizeScale': 1}), (False, False))
        # Gunsmith: colour values exist but the look is the texture; gun layout.
        self.assertEqual(gc.classify('gs_x', dict(colours, F_PAINT_STYLE=8, g_bIgnoreWeaponSizeScale=1)), (False, False))
        # Case hardening takes its colour from a ramp texture.
        self.assertEqual(gc.classify('soch_x', dict(colours, F_CASE_HARDENING=1)), (False, True))
        # A hydrographic laid out for one gun can be recoloured on that gun only.
        self.assertEqual(gc.classify('hy_lam', dict(colours, F_PAINT_STYLE=1, g_bIgnoreWeaponSizeScale=1)), (True, False))
        self.assertEqual(gc.classify('hy_p90_dino', dict(colours, F_PAINT_STYLE=1)), (True, False))  # gun in the name
        self.assertEqual(gc.classify('so_x', dict(colours, g_bOverrideDefaultMasks=1)), (True, False))  # per-gun masks

    def test_exposed_parameters_override_the_template_material(self):
        vmat = 'workshop/paintkits/templates/so_extended_template.vmat'
        params = gc.effective_params(read_root(exposed_compmat(vmat, [[1, 0, 0, 1]] * 4)),
                                     read_root(material(vmat, GREYS)))
        self.assertEqual(params['g_vColor0'], [1, 0, 0])  # the composite's colour, not the template grey
        self.assertEqual(params['g_tPattern'], 'textures/source_pattern.vtex')
        self.assertEqual(params['g_bIgnoreWeaponSizeScale'], 0)


class Recolour(unittest.TestCase):
    def source(self, files):
        folder = tempfile.mkdtemp()
        for path, data in files.items():
            (Path(folder) / path).parent.mkdir(parents=True, exist_ok=True)
            (Path(folder) / path).write_bytes(data)
        return finishes.Source(folder=folder)

    def test_material_colours_change_including_greys(self):
        vmat = 'materials/x/hy_grey.vmat'
        source = self.source({'weapons/paints/legacy/hy_grey.vcompmat_c': compmat(vmat), vmat + '_c': material(vmat, GREYS)})
        made = gc.make_recolour(source, 'hy_grey', 'weapons/paints/legacy/hy_grey.vcompmat', 'gc3m_hy_grey_azure', 'Azure')
        self.assertIsNotNone(made)
        new_comp, new_vmat, before, after = made
        self.assertTrue(gc.visible_change(before, after))
        comp = read_root(new_comp)
        self.assertIn(finishes.VMAT_DIR + 'gc3m_hy_grey_azure.vmat', json.dumps(comp))
        params = gc.effective_params(comp, read_root(new_vmat))
        for i in range(4):
            r, g, b = params['g_vColor%d' % i]
            self.assertGreater(b, r + .1)  # every grey became blue

    def test_exposed_colours_are_the_ones_changed(self):
        vmat = 'workshop/paintkits/templates/so_extended_template.vmat'
        start = [[.6, .2, .1, 1], [.8, .5, .2, 1], [.3, .3, .3, 1], [.9, .9, .8, 1]]
        source = self.source({'weapons/paints/x/so_paisley.vcompmat_c': exposed_compmat(vmat, start),
                              vmat + '_c': material(vmat, GREYS)})
        new_comp, new_vmat, before, after = gc.make_recolour(
            source, 'so_paisley', 'weapons/paints/x/so_paisley.vcompmat', 'gc3m_so_paisley_teal', 'Teal')
        self.assertLess(gc.distance(before, start), 1 / 255 + 1e-9)  # read from the composite, not the grey template
        params = gc.effective_params(read_root(new_comp), read_root(new_vmat))
        self.assertGreater(gc.distance([p + [1] for p in (params['g_vColor%d' % i] for i in range(4))], start), gc.MIN_CHANGE)

    def test_a_recolour_that_barely_moves_is_refused(self):
        self.assertFalse(gc.visible_change(GREYS, [[c + .02 for c in colour[:3]] + [1] for colour in GREYS]))

    def test_titles_drop_the_original_colour(self):
        self.assertEqual(gc.colour_title('Red Quartz', 'Teal'), 'Teal Quartz')
        self.assertEqual(gc.clean_title('Crimson Web'), 'Web')
        self.assertEqual(gc.clean_title('Red'), 'Red')


def rows(count, **row):
    base = {'guns': ['weapon_p90'], 'recolour': True, 'transfer': True, 'style': 1, 'rarity': 'rare',
            'pattern': None, 'pattern_guns': ['weapon_p90']}
    return {'kit%03d' % i: dict(base, pattern='p%d' % i, **row) for i in range(count)}


GUNS = sorted(['weapon_ak47', 'weapon_m4a1', 'weapon_m4a1_silencer', 'weapon_awp', 'weapon_deagle', 'weapon_usp_silencer',
               'weapon_glock', 'weapon_p250', 'weapon_fiveseven', 'weapon_tec9', 'weapon_mp9', 'weapon_mac10', 'weapon_mp7',
               'weapon_ump45', 'weapon_p90', 'weapon_nova', 'weapon_xm1014', 'weapon_mag7', 'weapon_negev', 'weapon_famas'])


class Build(unittest.TestCase):
    def test_lineup_is_saved_and_owned_kits_keep_their_definitions(self):
        import native_skins
        names = ['hy_a%02d' % i for i in range(40)]
        files, kits, loot = {}, {}, []
        for i, name in enumerate(names):
            vmat = 'materials/x/%s.vmat' % name
            files['weapons/paints/legacy/%s.vcompmat_c' % name] = compmat(vmat)
            files[vmat + '_c'] = patterned(vmat, [[.8, .2, .1, 1], [.2, .6, .9, 1], [.9, .9, .3, 1], [.4, .1, .5, 1]],
                                           'textures/%s.vtex' % name)
            kits[name] = (str(100 + i), {'name': name, 'style': '2'})
            loot.append('"[%s]%s" "1"' % (name, GUNS[i % len(GUNS)]))
        text = ('"items_game" { "items" { %s } "client_loot_lists" { "set_x_rare" { %s } } }' %
                (' '.join('"%d" { "name" "%s" }' % (i + 1, g) for i, g in enumerate(GUNS)), ' '.join(loot)))
        source = Recolour().source(files)
        titles = {name: 'Red Pattern %d' % i for i, name in enumerate(names)}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / gc.LINEUP_FILE
            first = gc.build(text, kits, titles, finishes.kit_path, source, {}, lineup_path=path, icons=['ashfall'])
            self.assertEqual(first[3], [native_skins.CASE_PREFIX + 'ashfall'])
            self.assertEqual(len(first[4]), 16)
            saved = json.loads(path.read_text())
            self.assertEqual(len(saved['lineup']['ashfall']), 16)
            # A different saved lineup (e.g. after a change) still defines every kit it ever named.
            old_kit = next(k for k in saved['history'] if k.startswith('gc3r_'))
            saved['lineup']['ashfall'] = gc.plan(gc.study(source, kits, finishes.kit_path, text, titles), GUNS,
                                                 ['ashfall'], set(), seed='other')['ashfall']
            path.write_text(json.dumps(saved))
            second = gc.build(text, kits, titles, finishes.kit_path, source, {}, lineup_path=path, icons=['ashfall'])
            self.assertIn(old_kit, [name for name, _, _ in second[0]])
            self.assertEqual(json.loads(path.read_text())['lineup'], saved['lineup'])  # reused, not reshuffled
            used = {v['composite_material_path'] for _, _, v in first[0]}
            shipped = {p.removesuffix('_c') for p in first[1] if p.startswith(finishes.COMPMAT_DIR)}
            self.assertTrue(shipped and shipped <= used)  # no unused trial colours shipped
            recolours = [(n, t) for n, t, v in first[0] if n.startswith('gc3r_')]
            self.assertTrue(recolours and all(not t.startswith('Red ') for _, t in recolours))


class Plan(unittest.TestCase):
    def test_complete_collections_without_repeats_or_copies(self):
        pool = rows(60)
        pool.update({'own%02d' % i: dict(next(iter(rows(1).values())), transfer=False, guns=[GUNS[i % len(GUNS)]],
                                         pattern_guns=[GUNS[i % len(GUNS)]]) for i in range(30)})
        lineup = gc.plan(pool, GUNS, ['ashfall', 'nebula', 'cascade'], {'cgf_doppler_ancient'})
        donors = [e['donor'] for entries in lineup.values() for e in entries if 'donor' in e]
        self.assertEqual(len(donors), len(set(donors)))  # every finish once
        for icon, entries in lineup.items():
            self.assertEqual([sum(e['tier'] == t for e in entries) for t, _ in gc.TIER_COUNTS], [1, 2, 3, 4, 6])
            weapons = [e['weapon'] for e in entries]
            self.assertEqual(len(weapons), len(set(weapons)))
            self.assertIn(entries[0]['weapon'], gc.CHASE_GUNS)
            for entry in entries:
                if 'donor' not in entry: continue
                row = pool[entry['donor']]
                if not row['transfer']: self.assertIn(entry['weapon'], row['guns'])  # gun layout stays on its gun
                if entry['mode'] == 'transfer': self.assertNotIn(entry['weapon'], row['pattern_guns'])  # never a copy
                else: self.assertTrue(row['recolour'] and entry['themes'])
        self.assertEqual(lineup['nebula'][0], {'tier': 'ancient', 'weapon': lineup['nebula'][0]['weapon'],
                                               'mode': 'knife_family', 'family': 'doppler'})
        self.assertEqual(lineup['ashfall'][0]['mode'], 'family')
        self.assertEqual(len(lineup['ashfall'][0]['themes']), 6)

    def test_finishes_whose_colours_do_not_show_are_skipped(self):
        lineup = gc.plan(rows(40), GUNS, ['ashfall'], set(),
                         works=lambda donor, mode, themes: mode == 'transfer' or donor >= 'kit010')
        used = {e['donor'] for e in lineup['ashfall'] if e['mode'] != 'transfer'}
        self.assertTrue(used and all(d >= 'kit010' for d in used))

    def test_same_input_same_lineup(self):
        self.assertEqual(gc.plan(rows(40), GUNS, ['ashfall'], set()), gc.plan(rows(40), GUNS, ['ashfall'], set()))


class DetailRebuild(unittest.TestCase):
    def test_neutral_ink_metal_and_white_stay_unchanged_in_detail_material(self):
        start=[[.04,.04,.04,1],[.8,.12,.08,1],[.94,.94,.94,1],[.18,.18,.18,1]]
        vmat='materials/x/detail.vmat'
        root=kv3.read_kv3(dict(kv3.read_resource(material(vmat,start))[1])['DATA'])[1]
        root.value.append(('m_floatParams',Node(kv3.ARRAY,[
            obj(('m_name',string('g_flPearlescentScale')),('m_flValue',Node(kv3.FLOAT,1.5))),
            obj(('m_name',string('g_fGlitterIntensity')),('m_flValue',Node(kv3.FLOAT,.12)))])))
        original=kv3.write_resource(0,[['DATA',kv3.write_kv3(GUID,root)]])
        source=Recolour().source({'paint.vcompmat_c':exposed_compmat(vmat,start),vmat+'_c':original})
        made=gc.make_recolour(source,'detail','paint.vcompmat','gc4m_detail_teal','Teal',preserve_details=True)
        self.assertIsNotNone(made)
        before=gc.effective_params(read_root(exposed_compmat(vmat,start)),read_root(original))
        after=gc.effective_params(read_root(made[0]),read_root(made[1]))
        for i in (0,2,3):self.assertEqual(after['g_vColor%d'%i],before['g_vColor%d'%i])
        self.assertNotEqual(after['g_vColor1'],before['g_vColor1'])
        for key in before:
            if not key.startswith('g_vColor'):self.assertEqual(after[key],before[key],key)
        self.assertEqual(set(gc.observed_effects(after)),{'pearlescent','glitter'})

    def test_berries_palette_uses_target_guns_own_masks_and_effects(self):
        target='materials/x/target_fade.vmat'
        berry='materials/x/berries.vmat'
        colors=[[.84,.22,.22,1],[.73,.15,.20,1],[.39,.36,.36,1],[.28,.58,.92,1]]
        source=Recolour().source({'target.vcompmat_c':compmat(target),target+'_c':patterned(target,GREYS,'target-mask-pattern.vtex'),
          'berries.vcompmat_c':compmat(berry),berry+'_c':patterned(berry,colors,'not-the-target-mask.vtex')})
        made=gc.make_recolour(source,'target','target.vcompmat','gc4m_berry_target_teal','Teal',
            preserve_details=True,palette_source=('aa_fade_red_blue',{'composite_material_path':'berries.vcompmat'}))
        self.assertIsNotNone(made)
        params=gc.effective_params(read_root(made[0]),read_root(made[1]))
        self.assertEqual(params['g_tPattern'],'target-mask-pattern.vtex')
        self.assertNotEqual(params['g_vColor0'],params['g_vColor3'])
        self.assertEqual(params['g_vColor2'],gc.effective_params(read_root(compmat(berry)),read_root(source.read(berry+'_c')))['g_vColor2'])

    def test_authored_plans_keep_counts_unique_weapons_and_two_berry_families(self):
        from collection_rebuild import DESIGNS,audit
        pool=rows(120)
        pool['aa_awp_fade']=dict(next(iter(pool.values())),guns=['weapon_awp'],transfer=False)
        pool['aa_fade_m4a1s']=dict(next(iter(pool.values())),guns=['weapon_m4a1_silencer'],transfer=False)
        pool['aa_fade_red_blue']=dict(next(iter(pool.values())),guns=['weapon_fiveseven'],transfer=False)
        result=gc.plan(pool,GUNS,list(DESIGNS),set(),works=lambda *args:True,designs=DESIGNS)
        for icon,entries in result.items():
            self.assertEqual([sum(e['tier']==t for e in entries) for t,_ in gc.TIER_COUNTS],[1,2,3,4,6])
            self.assertEqual(len({e['weapon'] for e in entries}),16)
            self.assertEqual(entries[0]['weapon'],DESIGNS[icon]['weapon'])
            self.assertTrue(all(e.get('detail') for e in entries))
        berries=[e for entries in result.values() for e in entries if e.get('palette_source')]
        self.assertEqual({e['weapon'] for e in berries},{'weapon_awp','weapon_m4a1_silencer'})
        self.assertEqual(len(audit(result,pool)),4)
        for e in berries:self.assertIn('_berries',gc.kit_name('test',e,'Teal'))

    def test_audit_covers_all_collections_and_flags_legacy_whole_palette_and_copies(self):
        from collection_rebuild import audit
        icons=list(gc.IDENTITIES)
        result=gc.plan(rows(600),GUNS,icons,set())
        report=audit(result,rows(600))
        self.assertEqual(set(report),set(icons))
        self.assertEqual(len(report),36)
        self.assertTrue(all(any('whole-palette' in i['issue'] for i in row['issues']) for row in report.values()))


    def test_full_rebuild_preserves_legacy_definitions_and_names_rolled_variants(self):
        files,kits,loot={},{},[]
        for i in range(50):
            name='hy_detail_%02d'%i
            vmat='materials/x/'+name+'.vmat'
            files['weapons/paints/legacy/'+name+'.vcompmat_c']=compmat(vmat)
            files[vmat+'_c']=patterned(vmat,[[.8,.2,.1,1],[.2,.6,.9,1],[.9,.9,.3,1],[.4,.1,.5,1]],'textures/'+name+'.vtex')
            kits[name]=(str(i+100),{'name':name})
            loot.append('"[%s]%s" "1"'%(name,GUNS[i%len(GUNS)]))
        text='"items_game" { "items" { %s } "client_loot_lists" { "set_x_rare" { %s } } }'%(
            ' '.join('"%d" { "name" "%s" }'%(i+1,g) for i,g in enumerate(GUNS)),' '.join(loot))
        source=Recolour().source(files)
        titles={name:'Copper Pattern '+name for name in kits}
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/gc.LINEUP_FILE
            families,report={},{}
            made=gc.build(text,kits,titles,finishes.kit_path,source,families,lineup_path=path,icons=['forged'],report=report)
            saved=json.loads(path.read_text())
            self.assertEqual(report.get('rebuilt_collections'),['forged'],report.get('rebuild_unavailable'))
            self.assertEqual(len(made[4]),16)
            self.assertTrue(all(e.get('detail') for e in saved['lineup']['forged']))
            self.assertTrue(any(name.startswith('gc3') for name,_,_ in made[0]),'owned legacy definitions retained')
            self.assertTrue(any(name.startswith('gc4') for name,_,_ in made[0]))
            self.assertEqual(len([k for k in families if k.startswith('gc4')]),2)
            variants={v for k,values in families.items() if k.startswith('gc4') for v in values}
            names={name:title for name,title,_ in made[0]}
            self.assertTrue(all(any(names[v].startswith(theme+' ') for theme in ('Crimson','Amber','Cobalt','Teal','Violet','Ember')) for v in variants))
            self.assertEqual(gc.clean_title('The Fuschia Is Now'),'Chromatic Current')
            again=gc.build(text,kits,titles,finishes.kit_path,source,{},lineup_path=path,icons=['forged'])
            self.assertEqual(again[4],made[4])
            self.assertEqual(json.loads(path.read_text())['history'],saved['history'])

if __name__ == '__main__':
    unittest.main()

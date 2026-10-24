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
               'weapon_ump45', 'weapon_aug', 'weapon_sg556', 'weapon_hkp2000', 'weapon_cz75a', 'weapon_nova', 'weapon_xm1014', 'weapon_mag7', 'weapon_negev', 'weapon_famas'])


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
        start=[[.04,.04,.04,1],[.8,.12,.08,.37],[.94,.94,.94,1],[.18,.18,.18,1]]
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
        vectors=finishes._vector_params(kv3.read_kv3(dict(kv3.read_resource(made[1])[1])['DATA'])[1])
        original_vectors=finishes._vector_params(root)
        self.assertEqual(vectors['g_vColor1'].value[3],original_vectors['g_vColor1'].value[3])
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
        pool['am_gold_brick']=dict(next(iter(pool.values())),guns=['weapon_mac10'],transfer=True)
        pool['aa_awp_fade']=dict(next(iter(pool.values())),guns=['weapon_awp'],transfer=False)
        pool['aa_fade_m4a1s']=dict(next(iter(pool.values())),guns=['weapon_m4a1_silencer'],transfer=False)
        pool['aa_fade_red_blue']=dict(next(iter(pool.values())),guns=['weapon_fiveseven'],transfer=False)
        result=gc.plan(pool,GUNS,list(DESIGNS)[:4],set(),works=lambda *args:True,designs=DESIGNS)
        for icon,entries in result.items():
            self.assertEqual([sum(e['tier']==t for e in entries) for t,_ in gc.TIER_COUNTS],[1,2,3,4,6])
            self.assertEqual(len({e['weapon'] for e in entries}),16)
            self.assertEqual(entries[0]['weapon'],DESIGNS[icon]['weapon'])
            self.assertTrue(all(e.get('detail') for e in entries))
        self.assertEqual(result['forged'][0]['label'],'Gold Brick')
        self.assertEqual(result['forged'][0]['mode'],'fixed')
        self.assertEqual(result['forged'][0]['pattern_source'],'am_doppler_phase2')
        self.assertEqual(sum(e['mode']=='family' for e in result['forged']),2)
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
        self.assertTrue(all(any('existing generation' in i['issue'] for i in row['issues']) for row in report.values()))


    def test_full_rebuild_preserves_legacy_definitions_and_names_rolled_variants(self):
        files,kits,loot={},{},[]
        for i in range(50):
            name='hy_detail_%02d'%i
            vmat='materials/x/'+name+'.vmat'
            files['weapons/paints/legacy/'+name+'.vcompmat_c']=compmat(vmat)
            import colorsys
            palette=[]
            for color in ([.8,.2,.1],[.2,.6,.9],[.9,.9,.3],[.4,.1,.5]):
                h,s,v=colorsys.rgb_to_hsv(*color)
                palette.append([*colorsys.hsv_to_rgb((h+i*.17)%1,s,v),1])
            files[vmat+'_c']=patterned(vmat,palette,'textures/'+name+'.vtex')
            kits[name]=(str(i+100),{'name':name})
            loot.append('"[%s]%s" "1"'%(name,GUNS[i%len(GUNS)]))
        for name,pattern,colors in (
            ('am_gold_brick','textures/gold_noise.vtex',[[1,.87,.53,1],[1,.93,.58,1],[.94,.80,.42,1],[.73,.60,.18,1]]),
            ('am_doppler_phase2','textures/doppler_smoke.vtex',[[.38,.45,.72,1],[1,.31,.42,1],[.71,.51,.28,1],[1,.31,.42,1]])):
            vmat='materials/x/'+name+'.vmat'
            files['weapons/paints/legacy/'+name+'.vcompmat_c']=compmat(vmat)
            files[vmat+'_c']=patterned(vmat,colors,pattern)
            files[pattern+'_c']=b'owned synthetic texture fixture'
            kits[name]=('1000',{'name':name})
        loot.append('"[am_gold_brick]weapon_mac10" "1"')
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
            self.assertTrue(report['existing_material_repairs'],'existing gc3 inventory definitions must also benefit')
            self.assertTrue(all(e.get('detail') for e in saved['lineup']['forged']))
            self.assertTrue(any(name.startswith('gc3') for name,_,_ in made[0]),'owned legacy definitions retained')
            self.assertTrue(any(name.startswith('gc4') for name,_,_ in made[0]))
            self.assertEqual(len([k for k in families if k.startswith('gc4')]),2)
            variants={v for k,values in families.items() if k.startswith('gc4') for v in values}
            names={name:title for name,title,_ in made[0]}
            self.assertTrue(all(any(names[v].startswith(theme+' ') for theme in ('Crimson','Amber','Cobalt','Teal','Violet','Ember','Ash')) for v in variants))
            self.assertEqual(gc.clean_title('The Fuschia Is Now'),'Chromatic Current')
            again=gc.build(text,kits,titles,finishes.kit_path,source,{},lineup_path=path,icons=['forged'])
            self.assertEqual(again[4],made[4])
            self.assertEqual(json.loads(path.read_text())['history'],saved['history'])

    def test_gold_brick_uses_doppler_smoke_without_altering_gold_palette_or_masks(self):
        gold='materials/x/gold.vmat';doppler='materials/x/doppler.vmat'
        colors=[[1,.87,.53,.4],[1,.93,.58,1],[.94,.80,.42,1],[.73,.60,.18,1]]
        files={'gold.vcompmat_c':compmat(gold),gold+'_c':patterned(gold,colors,'gold-noise.vtex'),
               'doppler.vcompmat_c':compmat(doppler),doppler+'_c':patterned(doppler,GREYS,'doppler-smoke.vtex'),
               'doppler-smoke.vtex_c':b'actual source texture fixture'}
        source=Recolour().source(files)
        made=gc.make_recolour(source,'am_gold_brick','gold.vcompmat','owned_gold','Gold',
             preserve_details=True,pattern_source=('am_doppler_phase2',{'composite_material_path':'doppler.vcompmat'}))
        self.assertIsNotNone(made)
        before=gc.effective_params(read_root(compmat(gold)),read_root(files[gold+'_c']))
        after=gc.effective_params(read_root(made[0]),read_root(made[1]))
        self.assertEqual(after['g_tPattern'],'doppler-smoke.vtex')
        for i in range(4):self.assertEqual(after['g_vColor%d'%i],before['g_vColor%d'%i])
        before.pop('g_tPattern');after.pop('g_tPattern')
        self.assertEqual(before,after)

    def test_second_batch_uses_only_theme_pool_and_two_premium_families(self):
        from collection_rebuild import DESIGNS,eligible
        designs={icon:DESIGNS[icon] for icon in ('kestrel','juggernaut','lodestar','fathom')}
        pool={}
        for design in designs.values():
            for name in design['allow']:
                pool[name]=dict(next(iter(rows(1).values())),title=name,effects=['pearlescent'],style=4)
        for name,weapon in (('hy_feathers_aug','weapon_aug'),('hy_p250_crackshot','weapon_p250'),
                            ('ht_white_edges','weapon_glock'),('soe_pink_pearl','weapon_cz75a'),
                            ('cu_famas_holo_ocean','weapon_famas'),('soe_teal_glitter','weapon_hkp2000')):
            pool[name].update(transfer=False,guns=[weapon],pattern_guns=[weapon])
        pool['soe_tropical']=dict(next(iter(rows(1).values())),effects=['iridescent'],title='Tropical floral flowers')
        result=gc.plan(pool,GUNS,list(designs),{},works=lambda *args:True,designs=designs)
        for icon,entries in result.items():
            self.assertEqual([sum(e['tier']==t for e in entries) for t,_ in gc.TIER_COUNTS],[1,2,3,4,6],icon)
            self.assertEqual(len({e['weapon'] for e in entries}),16,icon)
            self.assertEqual(sum(e['mode']=='family' for e in entries),2,icon)
            self.assertTrue(all(e['tier'] in ('ancient','legendary') for e in entries if e['mode']=='family'))
            self.assertTrue(all(e['donor'] in designs[icon]['allow'] for e in entries))
            self.assertFalse(eligible('soe_tropical',pool['soe_tropical'],designs[icon],'legendary'))
        famas=next(e for e in result['fathom'] if e['donor']=='cu_famas_holo_ocean')
        self.assertEqual(famas['weapon'],'weapon_famas')
        self.assertEqual(famas['themes'],['Violet','Emerald','Coral','Amber'])
        self.assertNotIn('Cobalt',famas['themes'])

    def test_stardust_family_has_three_distinct_changes_without_repeating_cobalt(self):
        from collection_rebuild import DESIGNS,recolour,visible_accent_change
        from collection_detail import palettes_distinct
        # Neutral pearl with one muted warm accent: neighbouring warm names
        # barely change it and must not silently remove the entire family.
        colors=[[.302,.302,.302,1],[.255,.255,.255,1],[.816,.855,.859,1],[.737,.643,.592,1]]
        themes=DESIGNS['lodestar']['palette'][:4]
        self.assertNotIn('Cobalt',themes)
        accepted=[]
        for theme in themes:
            changed=recolour(colors,theme)
            if visible_accent_change(colors,changed) and all(palettes_distinct(changed,p) for p in accepted):
                accepted.append(changed)
        self.assertGreaterEqual(len(accepted),3)

    def test_feedback_retains_approved_chase_and_downgrades_nova(self):
        from collection_rebuild import feedback
        entries=[dict(detail=1,tier=t,weapon=GUNS[i],mode='fixed',donor='kit000',themes=['Teal'],label='Slot'+str(i))
                 for i,(t,_) in enumerate([(tier,j) for tier,count in gc.TIER_COUNTS for j in range(count)])]
        entries[0].update(mode='family',label='Veil Piercer')
        entries[2].update(weapon='weapon_nova',label='Wraith Edge')
        before=dict(entries[0]);lineup={'phantom_blade':entries,'forged':[{'label':'Gold Brick'}]}
        result=feedback(lineup,{'cu_usp_printstream':{},'hy_geometric_steps_pearl':{}},lambda *args:True,{})
        self.assertEqual(result['phantom_blade'][0],dict(before,feedback_revision=1))
        self.assertEqual(result['forged'],lineup['forged'])
        nova=next(e for e in result['phantom_blade'] if e.get('label')=='Wraith Edge')
        self.assertEqual(nova['tier'],'mythical')
        self.assertEqual(result['phantom_blade'][1]['themes'],['Inverse'])
        self.assertEqual(sum(e['mode']=='family' for e in result['phantom_blade']),2)
        self.assertEqual(feedback(result,{},lambda *args:False,{}),result)

    def test_blaze_uses_authored_brightness_and_keeps_black_backing(self):
        start=[[.431,.071,.039,1],[.133,.008,.004,1],[.110,.110,.110,1],[.353,.235,.016,1]]
        vmat='materials/x/blaze.vmat';original=patterned(vmat,start,'flamegraphic.vtex')
        guid,root=kv3.read_kv3(dict(kv3.read_resource(original)[1])['DATA'])
        root.value.append(('m_floatParams',Node(kv3.ARRAY,[obj(('m_name',string('g_flColorBrightness')),
            ('m_flValue',Node(kv3.FLOAT,3.0)))])))
        original=kv3.write_resource(0,[['DATA',kv3.write_kv3(guid,root)]])
        source=Recolour().source({'blaze.vcompmat_c':compmat(vmat),vmat+'_c':original})
        made=gc.make_recolour(source,'aa_flames','blaze.vcompmat','gc3m_aa_flames_teal','Teal',preserve_details=True)
        self.assertIsNotNone(made,'source brightness must not trigger flat legacy fallback')
        params=gc.effective_params(read_root(made[0]),read_root(made[1]))
        for a,b in zip(params['g_vColor2'],start[2][:3]):self.assertAlmostEqual(a,b)
        self.assertEqual(params['g_tPattern'],'flamegraphic.vtex')
        self.assertEqual(params['g_flColorBrightness'],3.0)
        self.assertGreater(max(params['g_vColor0']),max(params['g_vColor2'])*3)

class RemainingCollections(unittest.TestCase):
    def pool(self):
        from remaining_collection_designs import POOLS
        pool={}
        for group,names in POOLS.items():
            for name in names.split():
                pool[name]=dict(next(iter(rows(1).values())),title=name,style=4,
                               colors=[[.8,.15,.1,1],[.1,.5,.8,1],[.9,.65,.2,1],[.5,.1,.7,1]],
                               effects=[],pattern='textures/'+name+'.vtex')
        for design in __import__('remaining_collection_designs').designs().values():
            for role in ('chase','family'):
                forced=design.get(role,{})
                if forced and forced['donor'] not in pool:
                    pool[forced['donor']]=dict(next(iter(rows(1).values())),title=forced['donor'],style=4,effects=['pearlescent'],pattern=forced['donor'])
        return pool

    def test_all_28_are_complete_themed_and_use_two_premium_families(self):
        from remaining_collection_designs import designs
        designs=designs();pool=self.pool()
        result=gc.plan(pool,GUNS,list(designs),{},works=lambda *args:True,designs=designs)
        self.assertEqual(len(result),28)
        for icon,entries in result.items():
            self.assertEqual([sum(e['tier']==t for e in entries) for t,_ in gc.TIER_COUNTS],[1,2,3,4,6],icon)
            self.assertEqual(len({e['weapon'] for e in entries}),16,icon)
            self.assertEqual(sum(e['mode']=='family' for e in entries),2,icon)
            self.assertTrue(all(e['mode']!='knife_family' for e in entries))
            self.assertTrue(all(e['donor'] in designs[icon]['allow'] for e in entries))
            self.assertTrue(all(e['donor'] in designs[icon]['premium'] for e in entries if e['tier'] in ('ancient','legendary')))
            self.assertTrue(all(e['mode']=='fixed' for e in entries if e['tier'] in ('mythical','rare')))
            self.assertTrue(all(e['mode'] in ('fixed','transfer') for e in entries if e['tier']=='uncommon'))

    def test_rebuild_keeps_the_eight_reviewed_pools_and_gold_brick(self):
        from collection_rebuild import DESIGNS,upgrade
        from remaining_collection_designs import designs
        pending=designs();lineup={}
        for icon,design in DESIGNS.items():
            lineup[icon]=[dict(detail=0 if icon in pending else design.get('revision',1),
                              donor='am_crystallized',weapon=GUNS[i],tier=tier,mode='fixed',
                              themes=['Teal'],label='Gold Brick' if icon=='forged' and i==0 else 'saved',
                              feedback_revision=1)
                          for i,(tier,_) in enumerate([(t,j) for t,n in gc.TIER_COUNTS for j in range(n)])]
        approved={icon:entries for icon,entries in lineup.items() if icon not in pending}
        report={}
        result=upgrade(lineup,self.pool(),GUNS,list(lineup),{},lambda *args:True,report)
        self.assertEqual(set(report['rebuilt_collections']),set(pending),report.get('rebuild_unavailable'))
        self.assertEqual({icon:result[icon] for icon in approved},approved)

    def test_insufficient_theme_pool_retains_whole_saved_collection(self):
        from collection_rebuild import upgrade
        saved={'rampart':[{'detail':0,'donor':'unavailable','weapon':'weapon_ak47'}]*16}
        report={}
        result=upgrade(saved,{},GUNS,['rampart'],{},lambda *args:True,report)
        self.assertEqual(result,saved)
        self.assertEqual(report['rebuild_unavailable'][0]['collection'],'rampart')

    def test_all_28_can_plan_with_similarity_filter_and_audit_has_no_near_matches(self):
        from remaining_collection_designs import designs
        from collection_rebuild import recolour
        from collection_similarity import Guard,audit
        pool=self.pool();planned_designs=designs()
        def palette(donor,theme,entry):
            return recolour(pool[donor]['colors'],theme) if theme else pool[donor]['colors']
        guard=Guard(pool,palette)
        result=gc.plan(pool,GUNS,list(planned_designs),{},works=lambda *args:True,
                       designs=planned_designs,accept=guard.allowed)
        for icon,entries in result.items():self.assertEqual(len(entries),16,icon)
        self.assertFalse(audit(result,pool,palette)['near_matches'])

class VisualSimilarity(unittest.TestCase):
    def fixture(self):
        from collection_rebuild import recolour
        pool={'am_jorm_blue':dict(next(iter(rows(1).values())),guns=['weapon_p90'],style=4,
                    colors=[[.8,.05,.05,1]]*4),
              'am_jorm_green':dict(next(iter(rows(1).values())),guns=['weapon_awp'],style=4,
                    colors=[[.8,.05,.05,1]]*4)}
        def palette(donor,theme,entry):
            return recolour(pool[donor]['colors'],theme) if theme else pool[donor]['colors']
        from collection_similarity import Guard
        return pool,palette,Guard(pool,palette)

    def test_different_names_and_ids_do_not_hide_same_weapon_pattern_copy(self):
        pool,palette,guard=self.fixture()
        # Equivalent geometry under a different source name is still rejected.
        self.assertIsNone(guard.allowed('am_jorm_green','weapon_p90','transfer',[]))
        self.assertIsNotNone(guard.allowed('am_jorm_green','weapon_negev','transfer',[]))
        # A visibly distinct fixed colourway on that geometry is allowed.
        self.assertEqual(guard.allowed('am_jorm_green','weapon_p90','fixed',['Teal']),['Teal'])

    def test_weak_recolour_and_brightness_clipping_are_near_matches(self):
        from collection_similarity import near,effective
        base=[[.4,.4,.4,1]]*4
        self.assertTrue(near(base,[[.41,.4,.4,1]]*4))
        # A tiny isolated accent is insufficient, even if one channel moved.
        self.assertTrue(near(base,[[.69,.4,.4,1]]+base[1:]))
        self.assertTrue(near(effective([[.7,.7,.7]]*4,3),effective([[.9,.9,.9]]*4,3)))

    def test_family_rolls_are_checked_individually_and_other_customs_are_reserved(self):
        pool,palette,guard=self.fixture()
        allowed=guard.allowed('am_jorm_green','weapon_p90','family',['Crimson','Teal','Violet','Emerald'])
        self.assertEqual(allowed,['Teal','Violet','Emerald'])
        guard.allowed('am_jorm_green','weapon_negev','fixed',['Teal'],commit=True)
        self.assertIsNone(guard.allowed('am_jorm_blue','weapon_negev','fixed',['Teal']))

    def test_audit_checks_every_collection_and_flags_close_originals(self):
        from collection_similarity import audit
        pool,palette,_=self.fixture()
        lineup={icon:[{'donor':'am_jorm_green','weapon':'weapon_p90','mode':'transfer','tier':'rare','themes':[]}]
                for icon in gc.IDENTITIES}
        report=audit(lineup,pool,palette)
        self.assertEqual(report['collections'],36)
        self.assertEqual(report['slots'],36)
        self.assertEqual(len(report['near_matches']),36)

if __name__ == '__main__':
    unittest.main()

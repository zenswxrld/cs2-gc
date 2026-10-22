import copy
import colorsys
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import native_finishes as finishes
import native_skins
import next_collection_lineups as lineups
from collection_donors import catalog, candidates, previous_materials
from collection_detail import recolour_details, rolled_name
from inventory_item import collect,parse

def fixtures():
    guns=set(lineups.WEAPON_ORDER)|{d.chase for d in lineups.all_designs().values()}
    kits={'hy_new_%03d'%i:(str(500+i),{'name':'hy_new_%03d'%i,'style':'2'}) for i in range(230)}
    for title,(name,gun) in lineups.REQUIRED.items():
        kits[name]=(str(len(kits)+500),{'name':name,'style':'9'})
    items=' '.join('"%d" { "name" "%s" }'%(i,g) for i,g in enumerate(sorted(guns)))
    sources=' '.join('"[%s]%s" "1"'%(name,
        next((gun for _,(base,gun) in lineups.REQUIRED.items() if base==name),'weapon_p250')) for name in kits)
    schema='"items_game" { "items" { '+items+' } "item_sets" { "set_timed_drops_cool" { "items" { '+sources+' } } } }'
    return schema,kits

def make(source,base,path,name,theme,report=None,**kwargs):
    if theme in finishes.THEMES:hue,saturation,_=finishes.THEMES[theme]
    elif theme in finishes.DUO_THEMES:hue,_,saturation=finishes.DUO_THEMES[theme]
    else:hues,saturation=finishes.GRADIENT_THEMES[theme];hue=hues[0]
    report[base+':'+kwargs['weapon_palette']]={'source_material':path.replace('.vcompmat','.vmat'),
        'themes':{theme:[[*colorsys.hsv_to_rgb(hue/360,saturation,v),1] for v in (.3,.5,.7,.9)]}}
    return b'comp:'+name.encode(),b'mat:'+name.encode()

class CollectionUpgrade(unittest.TestCase):
    def generate(self,schema=None,kits=None,maker=make,previous=()):
        original_schema,original_kits=fixtures()
        report={};families={}
        with patch.object(finishes,'make_finish',side_effect=maker):
            output=lineups.build(schema or original_schema,original_kits if kits is None else kits,{},
                lambda n,v:'paints/'+n+'.vcompmat',None,families,set(),report,previous_entries=previous)
        return output,families,report

    def test_complete_pools_have_correct_rarities_fixed_names_and_colour_family_names(self):
        output,families,report=self.generate()
        definitions,files,lists,names,items,icons=output
        self.assertEqual(len(names),36);self.assertEqual(len(items),576)
        self.assertEqual(len(families),72)
        parsed=collect(parse('"items_game" { "client_loot_lists" { '+lists+' } }'))['client_loot_lists']
        lookup={n:(title,values) for n,title,values in definitions}
        self.assertEqual(len(lookup),len(definitions))
        for icon,row in report['collection_upgrade'].items():
            self.assertEqual(row['status'],'ready',row)
            name='set_cs2gc_case_'+icon
            self.assertEqual([len(parsed[name+'_'+t]) for t in lineups.RARITIES],[1,2,3,4,6])
            self.assertEqual(sum(s['family'] for s in row['skins']),2)
            self.assertEqual(len({s['weapon'] for s in row['skins']}),16)
            self.assertEqual(len({s['material_template'] for s in row['skins']}),16)
            for skin in row['skins']:
                self.assertEqual(lookup[skin['kit']][0],skin['title'])
                self.assertIn(lookup[skin['kit']][1]['composite_material_path']+'_c',files)
                for variant,theme in zip(skin['variants'],skin['themes']):
                    self.assertEqual(lookup[variant][0],rolled_name(skin['title'],theme))

    def test_real_families_never_fall_back_to_marble_fade_serum_or_other_finishes(self):
        _,kits=fixtures()
        kits.pop('gsch_sport_ump45')
        output,families,report=self.generate(kits=kits)
        for icon in ('forged','juggernaut','insignia'):
            self.assertEqual(report['next_12'][icon]['status'],'unavailable')
            self.assertEqual(report['next_12'][icon]['skins'],[])
            self.assertIn('gsch_sport_ump45',report['next_12'][icon]['reason'])
            self.assertNotIn('set_cs2gc_case_'+icon,output[3])
            self.assertFalse(any(n.startswith('nc32_'+icon+'_') for n in families))
        for icon in ('phantom_blade','mosaic','lodestar'):
            skin=report['next_12'][icon]['skins'][1]
            self.assertEqual((skin['donor'],skin['weapon']),
                ('aq_titanium_rainbow_galilar','weapon_galilar'))

    def test_catalog_uses_weekly_armory_and_keeps_weapon_artwork_on_source_weapon(self):
        schema,kits=fixtures()
        schema=schema.replace('set_timed_drops_cool','set_community_1')
        self.assertEqual(catalog(schema,kits,lambda n,v:n),{})
        schema,kits=fixtures()
        rows=catalog(schema,kits,lambda n,v:n)
        pool=candidates(rows,'forged','weapon_deagle',set(),{},set())
        self.assertNotIn('gsch_sport_ump45',[d.name for d in pool])
        self.assertNotIn('aq_titanium_rainbow_galilar',[d.name for d in pool])
        self.assertIn('gsch_sport_ump45',[d.name for d in candidates(rows,'forged','weapon_ump45',set(),{},set())])

    def test_new_twelve_exclude_prior_donor_materials_and_balance_reuse(self):
        previous=['[cwf_ashfall_rare0_hy_new_000_teal_rare]weapon_p250']
        _,_,report=self.generate(previous=previous)
        counts={}
        for row in report['next_12'].values():
            for skin in row['skins']:
                if skin['required_family']:
                    continue
                self.assertNotEqual(skin['donor'],'hy_new_000')
                counts[skin['source_material']]=counts.get(skin['source_material'],0)+1
        self.assertTrue(counts);self.assertLessEqual(max(counts.values()),2)

    def test_missing_and_identical_materials_publish_no_partial_pools(self):
        def duplicate(source,base,path,name,theme,report=None,**kw):
            report[base+':'+kw['weapon_palette']]={'themes':{theme:[[.2,.3,.4,1]]*4}}
            return b'comp',b'mat'
        for maker in (lambda *a,**kw:None,duplicate,lambda *a,**kw:(b'comp',b'mat')):
            output,families,report=self.generate(maker=maker)
            self.assertEqual(output,([],{},'',[],[],{}));self.assertEqual(families,{})

    def test_replacement_retains_owned_definitions_files_and_other_active_pools(self):
        tiers={t:['[old_'+t+']weapon_p250'] for t in lineups.RARITIES}
        lists=native_skins._collection_lists('set_cs2gc_case_forged',tiers,lineups.RARITIES)
        baseline=([('old','Owned',{})],{'old.vmat_c':b'owned'},lists,
            ['set_cs2gc_case_forged','other'],['[old_rare]weapon_p250','[other]weapon_awp'],
            {'set_cs2gc_case_forged':'forged','other':'other'})
        new=([('new','Fresh',{})],{'new.vmat_c':b'new'},'',
            ['set_cs2gc_case_forged'],['[new]weapon_ak47'],{'set_cs2gc_case_forged':'forged'})
        out=lineups.replace_pools(baseline,new)
        self.assertEqual(out[0],baseline[0]+new[0])
        self.assertEqual(out[1]['old.vmat_c'],b'owned')
        self.assertNotIn('[old_rare]weapon_p250',out[4])
        self.assertIn('[other]weapon_awp',out[4])
        self.assertEqual(lineups.replace_pools(baseline,([],{},'',[],[],{}))[:2],baseline[:2])

    def test_owned_legacy_names_change_without_changing_identity_or_material(self):
        values={'composite_material_path':'unchanged','_rarity':'rare'}
        entries=[('cwf_ashfall_rare0_am_chainmail_teal_rare','Old',values),
            ('cw2v_ashfall_chase_am_chainmail_ember_ancient','Old',values)]
        result=lineups.rename_retained(entries,{'am_chainmail':('1',{})})
        self.assertEqual([e[0] for e in result],[e[0] for e in entries])
        self.assertTrue(all(e[2] is values for e in result))
        self.assertEqual(result[0][1],lineups.OLDER_NAMES['ashfall'].split('|')[6])
        self.assertTrue(result[1][1].startswith('Ember '))

    def test_family_colours_reject_near_identical_labels(self):
        from collection_detail import palettes_distinct
        palette=lambda hue,sat:[[ *colorsys.hsv_to_rgb(hue/360,sat,.8),1]]*4
        self.assertFalse(palettes_distinct(palette(270,.75),palette(272,.62)))
        self.assertFalse(palettes_distinct(palette(226,.74),palette(226,.78)))
        self.assertTrue(palettes_distinct(palette(270,.75),palette(226,.74)))
        self.assertTrue(palettes_distinct(palette(226,.74),palette(210,.1)))

    def test_determinism_and_inputs_unchanged(self):
        schema,kits=fixtures();before=copy.deepcopy(kits)
        self.assertEqual(self.generate(schema,kits),self.generate(schema,kits))
        self.assertEqual(kits,before)

if __name__=='__main__':
    unittest.main()

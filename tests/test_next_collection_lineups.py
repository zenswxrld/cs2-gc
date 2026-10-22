import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import native_finishes as finishes
import native_skins
import next_collection_lineups as lineups
from inventory_item import collect, parse


def fixtures():
    donors = set(lineups.FALLBACKS)
    for design in lineups.DESIGNS.values():
        donors.update(design.chase_donors + design.wave)
    kits = {n: (str(i+100), {'name': n, 'style': '5'}) for i,n in enumerate(sorted(donors))}
    guns = set(lineups.WEAPON_ORDER) | {d.chase for d in lineups.DESIGNS.values()}
    schema = '"items_game" { "items" { %s } }' % ' '.join(
        '"%d" { "name" "%s" }' % (i,g) for i,g in enumerate(sorted(guns)))
    return schema, kits


def make(source, base, path, name, theme, report=None, **kwargs):
    # Different accepted palettes; the real material mutation has its own tests.
    value = (sum(map(ord, theme)) % 100) / 100
    if report is not None:
        report[base+':'+kwargs['weapon_palette']] = {'themes': {theme: [[value,.2,.3,1]]*4}}
    return b'compmat:'+name.encode(), b'vmat:'+name.encode()


class NextCollections(unittest.TestCase):
    def generate(self, schema=None, kits=None, families=None, make_finish=make):
        original_schema, original_kits = fixtures()
        if families is None:
            families = {}
        report = {}
        with patch.object(finishes, 'make_finish', side_effect=make_finish):
            result = lineups.build(schema or original_schema, original_kits if kits is None else kits,
                {}, lambda n,v: 'source/'+n+'.vcompmat', None, families, set(), report)
        return result, families, report

    def test_native_loot_lists_and_previews_have_192_visible_skins_and_two_families_each(self):
        result, families, report = self.generate()
        new, files, lists, names, entries, icons = result
        self.assertEqual(len(names),12)
        self.assertEqual(len(entries),192)
        self.assertEqual(len(families),24)
        self.assertEqual(len(icons),12)
        lookup={n:(title,values) for n,title,values in new}
        self.assertEqual(len(lookup),len(new))
        parsed=collect(parse('"items_game" { "client_loot_lists" { '+lists+' } }'))['client_loot_lists']
        previews=finishes.collection_previews(lists,names,{n:i+30000 for i,n in enumerate(lookup)})
        for name in names:
            self.assertEqual([len(parsed[name+'_'+t]) for t in lineups.RARITIES],[1,2,3,4,6])
            self.assertEqual(len(previews[name]),16)
            row=report['next_12'][icons[name]]
            self.assertEqual(sum(s['family'] for s in row['skins']),2)
            self.assertEqual(len({s['weapon'] for s in row['skins']}),16)
            self.assertEqual(len({s['source_material'] for s in row['skins']}),16)
            self.assertEqual(len({s['title'] for s in row['skins']}),16)
            for skin in row['skins']:
                self.assertEqual(lookup[skin['kit']][0],skin['title'])
                self.assertEqual(lookup[skin['kit']][1]['_rarity'],skin['rarity'])
                self.assertIn(lookup[skin['kit']][1]['composite_material_path']+'_c',files)
                for variant,theme in zip(skin['variants'],skin['themes']):
                    self.assertEqual(lookup[variant][0],theme+' '+skin['title'])

    def test_missing_materials_never_publish_half_collections_or_orphan_families(self):
        _,kits=fixtures()
        kits={n:v for n,v in kits.items() if n in ('am_metal_inlay','am_chainmail')}
        old={'owned_family':['owned_blue','owned_red']}
        result,families,report=self.generate(kits=kits,families=copy.deepcopy(old))
        self.assertEqual(result,([],{},'',[],[],{}))
        self.assertEqual(families,old)
        self.assertTrue(all(r['status']=='unavailable' and not r['skins'] for r in report['next_12'].values()))

    def test_family_rejects_duplicate_palettes_instead_of_rolling_identical_colours(self):
        def duplicate(source,base,path,name,theme,report=None,**kwargs):
            report[base+':'+kwargs['weapon_palette']]={'themes':{theme:[[.1,.2,.3,1]]*4}}
            return b'comp',b'mat'
        result,families,_=self.generate(make_finish=duplicate)
        self.assertEqual(result,([],{},'',[],[],{}))
        self.assertEqual(families,{})

    def test_missing_weapon_skips_only_its_collection_and_reports_it(self):
        schema,kits=fixtures()
        schema=schema.replace('"name" "weapon_xm1014"','"name" "weapon_absent"')
        result,_,report=self.generate(schema=schema,kits=kits)
        self.assertEqual(len(result[3]),11)
        self.assertEqual(len(result[4]),176)
        self.assertEqual(report['next_12']['warden']['reason'],'required weapon missing from installed schema')

    def test_fallbacks_are_reported_and_rolls_do_not_repeat_across_the_new_collections(self):
        _,kits=fixtures()
        kits.pop('am_metal_inlay')
        result,_,report=self.generate(kits=kits)
        self.assertEqual(len(result[3]),12)
        self.assertEqual(report['next_12']['forged']['skins'][0]['donor'],'am_gold_brick')
        rolls=[]
        for row in report['next_12'].values():
            for skin in row['skins']:
                rolls.extend((skin['source_material'],skin['weapon'],skin['rarity'],t) for t in skin['themes'])
        self.assertEqual(len(rolls),len(set(rolls)))

    def test_deterministic_output_and_source_schema_kit_values_are_unchanged(self):
        schema,kits=fixtures()
        before=copy.deepcopy(kits)
        first=self.generate(schema=schema,kits=kits)
        second=self.generate(schema=schema,kits=kits)
        self.assertEqual(first,second)
        self.assertEqual(kits,before)


if __name__=='__main__':
    unittest.main()

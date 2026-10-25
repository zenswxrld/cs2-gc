"""Full-pool migration, approval locks and all-weapon coverage."""
import sys,unittest
from copy import deepcopy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from collection_catalogue import apply
from collection_catalogue_designs import LINEUPS,PROFILES
from collection_review import counts,refine
from collection_polish import polish
from collection_rebuild import feedback
from popular_chases import CHASES,apply as popular
import gun_collections as gc

def rows():
    result={}
    for entries in LINEUPS.values():
        for entry in entries:
            row=result.setdefault(entry['donor'],{'guns':[],'effects':['pearlescent'],'transfer':True})
            row['guns'].append(entry['weapon'])
    return result

class Catalogue(unittest.TestCase):
    def test_texture_art_uses_real_evidence_and_still_flags_other_duplicate_skins(self):
        from collection_similarity import Guard,audit
        row={'guns':['weapon_ak47'],'style':6,'pattern':'native-art','colors':[[1,1,1,1]]*4,'texture_authored':True}
        pool={'art_a':dict(row),'art_b':dict(row)}
        actual=[[.2,.1,.8,1]]*4
        guard=Guard(pool,lambda *a:actual)
        self.assertFalse(guard.matches('art_a','weapon_ak47',actual))
        entry={'donor':'art_a','weapon':'weapon_ak47','mode':'fixed','themes':['Violet'],'tier':'rare'}
        other=dict(entry,donor='art_b')
        self.assertTrue(audit({'first':[entry],'second':[other]},pool,lambda *a:actual)['near_matches'])

    def test_named_family_colours_have_a_separate_distinctness_gate(self):
        from collection_similarity import audit,near
        from collection_detail import palettes_distinct
        first=[[.2,.03,.03,1]]*4;second=[[.2,.13,.03,1]]*4
        self.assertTrue(near(first,second));self.assertTrue(palettes_distinct(first,second))
        row={'guns':['weapon_ak47'],'style':4,'pattern':'art','colors':[]}
        entry={'donor':'art','weapon':'weapon_ak47','mode':'family','themes':['Crimson','Amber'],'tier':'legendary'}
        result=audit({'pool':[entry]},{'art':row},lambda d,t,e:first if t=='Crimson' else second)
        self.assertFalse(result['near_matches'])

    def test_all_36_complete_native_gun_pools_and_tier_budget(self):
        self.assertEqual(len(LINEUPS),36)
        self.assertEqual(set(LINEUPS),set(gc.IDENTITIES))
        self.assertEqual(len({e['donor'] for es in LINEUPS.values() for e in es}),576)
        weapons=set()
        for icon,entries in LINEUPS.items():
            with self.subTest(icon=icon):
                self.assertEqual(counts(entries),[1,2,3,4,6])
                self.assertEqual(len({e['weapon'] for e in entries}),16)
                self.assertTrue(1<=sum(e['mode']=='family' for e in entries)<=2)
                self.assertTrue(all(e['all_collection_revision']==2 for e in entries))
                self.assertTrue(all(e['mode'] in ('fixed','family') for e in entries))
                self.assertTrue(all(len(e['themes'])>=3 for e in entries if e['mode']=='family'))
                weapons.update(e['weapon'] for e in entries)
        self.assertEqual(len(weapons),34)
        self.assertTrue({'weapon_m249','weapon_negev','weapon_nova','weapon_sawedoff','weapon_xm1014',
            'weapon_mag7','weapon_bizon','weapon_mp5sd','weapon_mp7','weapon_mp9','weapon_ump45',
            'weapon_p90','weapon_g3sg1','weapon_scar20','weapon_revolver','weapon_elite'}<=weapons)

    def test_approved_chases_and_gold_wood_inputs_stay(self):
        for entries in LINEUPS.values():
            self.assertFalse(any(e['donor']=='aq_titanium_rainbow_galilar' and e['weapon']=='weapon_galilar' for e in entries))
            self.assertFalse(any(e['donor']=='gsch_sport_ump45' and e['weapon']=='weapon_ump45' for e in entries))
        for icon,(donor,weapon,label,mode,themes) in CHASES.items():
            chase=next(e for e in LINEUPS[icon] if e['tier']=='ancient')
            self.assertEqual((chase['donor'],chase['weapon'],chase['label'],chase['mode'],tuple(chase['themes'])),
                (donor,weapon,label,mode,themes))
        gold=next(e for e in LINEUPS['forged'] if e['label']=='Gold Brick')
        self.assertEqual((gold['tier'],gold['weapon'],gold['donor'],gold['pattern_source'],gold['themes']),
            ('ancient','weapon_ak47','am_gold_brick','am_doppler_phase2',['Gold']))
        self.assertTrue(any(e['label']=='Rainbow Spoon' and e['weapon']=='weapon_deagle' for e in LINEUPS['phantom_blade']))
        self.assertTrue(any(e['label']=='Foil' and e['weapon']=='weapon_ak47' for e in LINEUPS['insignia']))
        self.assertTrue(any(e['label']=='Composite Armour' and e['themes']==['Teal'] for e in LINEUPS['ironclad']))

    def test_rerun_does_not_reapply_legacy_slot_migrations(self):
        before=deepcopy(LINEUPS)
        self.assertEqual(refine(before,rows(),lambda *a:True,{}),before)
        self.assertEqual(popular(before,rows(),lambda *a:True,{}),before)
        self.assertEqual(feedback(before,rows(),lambda *a:True,{}),before)
        report={}
        self.assertEqual(apply(before,rows(),lambda *a:True,report),before)
        self.assertEqual(report['all_collection_rebuild']['collections'],36)
        self.assertEqual(report['all_collection_rebuild']['slots'],576)

    def test_unavailable_material_keeps_entire_previous_pool(self):
        icon='cascade';prior=deepcopy(LINEUPS[icon]);prior[-1]['label']='Previous skin'
        rejected=LINEUPS[icon][5]['donor'];report={}
        result=apply({icon:prior},rows(),lambda donor,*a:donor!=rejected,report)
        self.assertEqual(result[icon],prior)
        self.assertTrue(report['all_collection_rebuild']['unavailable'])

    def test_newer_approved_skin_is_never_overwritten(self):
        icon='rampart';prior=deepcopy(LINEUPS[icon]);prior[0]['label']='Later approved chase'
        report={};result=apply({icon:prior},rows(),lambda *a:True,report)
        self.assertEqual(result[icon],prior)
        self.assertIn('newer approved',report['all_collection_rebuild']['unavailable'][0]['reason'])

    def test_historical_kit_names_are_not_reused_for_different_donors(self):
        names={}
        outcomes=set()
        for icon,entries in LINEUPS.items():
            for entry in entries:
                name=gc.kit_name(icon,entry)
                self.assertNotIn(name,names)
                names[name]=entry
                for theme in entry['themes']:
                    key=(entry['donor'],entry['weapon'],theme,entry.get('palette_source'),entry.get('pattern_source'),entry.get('effect_source'))
                    self.assertNotIn(key,outcomes)
                    outcomes.add(key)

if __name__=='__main__':unittest.main()


"""Signature families stay on requested weapons and emit real roll manifests."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import gun_collections as gc
from collection_polish import install,polish
from collection_policies import history_entry
from test_gun_collections import GUNS,rows

class SignatureFamilies(unittest.TestCase):
    def lineup(self):
        lineup={}
        for icon in ('phantom_blade','insignia'):
            lineup[icon]=[dict(detail=1,tier=tier,weapon=GUNS[i],mode='fixed',
                 donor='background',themes=['Teal'],label='Saved '+str(i),feedback_revision=1)
                 for i,(tier,_) in enumerate([(t,j) for t,n in gc.TIER_COUNTS for j in range(n)])]
            # Leave both requested weapons available outside the protected chase.
            lineup[icon][0]['weapon']='weapon_awp'
            for index,entry in enumerate(lineup[icon][1:],1):
                if entry['weapon']=='weapon_awp':entry['weapon']=GUNS[0]
        return lineup

    def pool(self):
        base=dict(next(iter(rows(1).values())),effects=['pearlescent'])
        return {name:dict(base) for name in ('background','aq_deagle_case_hardened_2','gsch_ak_djiin')}

    def test_requested_weapons_get_random_families_and_survive_palette_reruns(self):
        report={}
        result=polish(self.lineup(),self.pool(),lambda *args:True,report)
        for icon,donor,weapon in (('phantom_blade','aq_deagle_case_hardened_2','weapon_deagle'),
                                  ('insignia','gsch_ak_djiin','weapon_ak47')):
            entries=result[icon]
            signature=next(e for e in entries if e.get('signature_finish'))
            self.assertEqual((signature['donor'],signature['weapon'],signature['mode']),(donor,weapon,'family'))
            self.assertTrue(signature['random_on_pull'])
            self.assertGreaterEqual(len(signature['themes']),3)
            self.assertEqual([sum(e['tier']==t for e in entries) for t,_ in gc.TIER_COUNTS],[1,2,3,4,6])
            self.assertEqual(len({e['weapon'] for e in entries}),16)
        foil=next(e for e in result['insignia'] if e.get('signature_finish'))
        self.assertNotIn('Amber',foil['themes'])
        self.assertEqual(polish(result,self.pool(),lambda *args:True,{}),result)

    def test_build_emits_variants_in_family_manifest_and_preserves_old_colours(self):
        from collection_rebuild import recolour
        lineup=self.lineup();pool=self.pool()
        text='"items_game" { "items" { '+ ' '.join('"%d" { "name" "%s" }'%(i+1,g) for i,g in enumerate(GUNS))+ ' } }'
        kits={name:(str(i+1),{'name':name}) for i,name in enumerate(pool)}
        def make(source,donor,path,new_name,theme,**kw):
            colors=recolour([[.9,.1,.05,1],[.05,.1,.8,1],[.8,.4,.1,1],[.1,.8,.3,1]],theme)
            return b'composite',b'material',[],colors
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/gc.LINEUP_FILE
            path.write_text(json.dumps({'version':gc.VERSION,'lineup':lineup,'history':{}}))
            families={}
            with patch.object(gc,'study',return_value=pool),patch.object(gc,'make_recolour',side_effect=make):
                made=gc.build(text,kits,{},lambda *args:'paint.vcompmat',object(),families,
                              lineup_path=path,icons=list(lineup),report={})
            saved=json.loads(path.read_text())
            names={name:title for name,title,_ in made[0]}
            for icon in lineup:
                entry=next(e for e in saved['lineup'][icon] if e.get('signature_finish'))
                key=gc.kit_name(icon,entry)
                self.assertIn(key,families)
                self.assertGreaterEqual(len(families[key]),3)
                self.assertTrue(all(v in names for v in families[key]))
                self.assertTrue(all(names[v].endswith(entry['label']) for v in families[key]))
                self.assertTrue(any('['+key+']'+entry['weapon'] in value for value in made[4]))
        history={'family':{'mode':'family','themes':['Ember']}}
        history_entry(history,'family',{'mode':'family','themes':['Cobalt','Teal','Violet']})
        self.assertEqual(history['family']['themes'],['Ember','Cobalt','Teal','Violet'])


class ClientReview(unittest.TestCase):
    def entries(self,weapons):
        return [dict(detail=1,tier=tier,weapon=weapons[i],donor='background',mode='fixed',themes=['Cobalt'],label='Saved')
           for i,(tier,_) in enumerate([(t,j) for t,n in gc.TIER_COUNTS for j in range(n)])]

    def test_insignia_tiers_and_foil_remain_complete_unique_and_stable(self):
        weapons=['weapon_famas','weapon_hkp2000','weapon_awp','weapon_usp_silencer','weapon_fiveseven','weapon_ak47',
                 'weapon_mac10','weapon_scar20','weapon_galilar','weapon_nova','weapon_m4a1_silencer','weapon_deagle',
                 'weapon_ump45','weapon_ssg08','weapon_negev','weapon_xm1014']
        entries=self.entries(weapons)
        entries[0].update(donor='am_scales_bravo',mode='family',themes=['Amber','Cobalt','Violet'],label='High Command')
        entries[1].update(mode='family',themes=['Cobalt','Violet','Ash'])
        entries[2]['donor']='am_awp_glory'
        entries[5].update(donor='hye_ak47_nouveau',themes=['Royal'],label='Laurel Steel')
        pool={name:dict(next(iter(rows(1).values())),effects=['pearl']) for name in
              ('background','am_scales_bravo','am_awp_glory','hye_ak47_nouveau','gsch_ak_djiin','awp_queens_gambit')}
        result=polish({'insignia':entries},pool,lambda *args:True,{})
        new=result['insignia']
        self.assertEqual([sum(e['tier']==t for e in new) for t,_ in gc.TIER_COUNTS],[1,2,3,4,6])
        self.assertEqual(len({e['weapon'] for e in new}),16)
        self.assertEqual(sum(e['mode']=='family' for e in new),2)
        self.assertEqual(new[0]['donor'],'awp_queens_gambit')
        self.assertEqual(next(e for e in new if e['weapon']=='weapon_famas')['tier'],'mythical')
        self.assertEqual(next(e for e in new if e['weapon']=='weapon_ak47')['themes'],['Cobalt','Teal','Ash'])
        self.assertEqual(polish(result,pool,lambda *args:True,{}),result)

    def test_negev_plate_moves_down_and_m249_remains_milspec(self):
        from collection_review import refine
        weapons=['weapon_negev','weapon_glock','weapon_scar20','weapon_m4a1','weapon_tec9','weapon_fiveseven',
                 'weapon_galilar','weapon_m4a1_silencer','weapon_ak47','weapon_m249','weapon_elite','weapon_cz75a',
                 'weapon_sg556','weapon_g3sg1','weapon_usp_silencer','weapon_mac10']
        entries=self.entries(weapons);entries[0].update(donor='am_diamond_plate',mode='family')
        result=refine({'juggernaut':entries},{'cu_m4_asimov':{}},lambda *args:True,{})
        new=result['juggernaut']
        self.assertEqual([sum(e['tier']==t for e in new) for t,_ in gc.TIER_COUNTS],[1,2,3,4,6])
        self.assertEqual(len({e['weapon'] for e in new}),16)
        self.assertEqual(new[0]['weapon'],'weapon_m4a1')
        self.assertEqual(next(e for e in new if e['weapon']=='weapon_negev')['tier'],'mythical')
        self.assertEqual(next(e for e in new if e['weapon']=='weapon_m249')['tier'],'rare')
        self.assertEqual(refine(result,{'cu_m4_asimov':{}},lambda *args:True,{}),result)

    def test_repeated_manowar_awps_use_different_actual_artwork(self):
        from collection_review import refine
        lineup={icon:[dict(detail=1,donor='am_awp_glory',weapon='weapon_awp',tier='legendary',
                          mode='fixed',themes=['Cobalt'])] for icon in ('insignia','ironclad','rampart','redoubt')}
        pool={name:{} for name in ('awp_queens_gambit','cu_awp_asimov','cu_awp_cobra','cu_awp_chroma_pink')}
        result=refine(lineup,pool,lambda *args:True,{})
        self.assertEqual(len({entries[0]['donor'] for entries in result.values()}),4)
        self.assertFalse(any(e['donor']=='am_awp_glory' for es in result.values() for e in es))
        self.assertEqual(refine(lineup,pool,lambda *args:False,{}),lineup)

if __name__=='__main__':unittest.main()


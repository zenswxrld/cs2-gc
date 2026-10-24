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

if __name__=='__main__':unittest.main()

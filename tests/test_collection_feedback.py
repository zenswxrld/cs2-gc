"""Client-reported regressions: material alpha, complete palettes and roll history."""
import os,subprocess,sys,unittest
from copy import deepcopy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from collection_catalogue_designs import LINEUPS
from collection_catalogue import apply
from collection_feedback import MODES,bindings
from collection_policies import history_entry
from test_collection_material import bc7_solid

class ClientFeedback(unittest.TestCase):
    def test_scope_and_axia_roll_colours(self):
        targets=[e for es in LINEUPS.values() for e in es if e.get('client_review_revision')]
        self.assertEqual({e['donor'] for e in targets},set(MODES))
        self.assertEqual(len(targets),13)
        axia=next(e for e in LINEUPS['undertow'] if e['donor']=='gsch_axia_glock')
        self.assertEqual(axia['mode'],'family')
        self.assertEqual(axia['themes'],['Crimson','Emerald','Violet'])
        self.assertTrue(axia['random_on_pull'])
        self.assertNotIn('Cobalt',axia['themes'])

    def test_review_marker_does_not_block_approved_chase_migration(self):
        current=deepcopy(LINEUPS['talisman'])
        for e in current:e.pop('client_review_revision',None)
        rows={e['donor']:{'guns':[e['weapon']]} for e in current}
        report={};actual=apply({'talisman':current},rows,lambda *a:True,report)
        self.assertEqual(actual['talisman'],LINEUPS['talisman'])
        self.assertFalse(report['all_collection_rebuild']['unavailable'])

    def test_existing_axia_blue_stays_defined_but_outside_new_roll_family(self):
        e=deepcopy(next(e for e in LINEUPS['undertow'] if e['donor']=='gsch_axia_glock'))
        history={'family':dict(e,themes=['Cobalt'])}
        history_entry(history,'family',e)
        self.assertEqual(history['family']['themes'],['Cobalt','Crimson','Emerald','Violet'])
        self.assertNotIn('Cobalt',e['themes'])

    @unittest.skipUnless(os.environ.get('CS2_GC_TEXTURE_DECODER'),'native decoder required')
    def test_zero_alpha_material_rgb_is_recoloured_with_exact_mask_and_neutrals(self):
        path=os.environ['CS2_GC_TEXTURE_DECODER']
        payload=bc7_solid(254,2,2,0)+bc7_solid(126,126,126,0)
        def run(mode,hue='178'):
            return subprocess.run([path,'4','8',hue,'.7',str(mode)],input=payload,capture_output=True,check=True).stdout
        original=subprocess.run([path,'4','8'],input=payload,capture_output=True,check=True).stdout
        import json
        audit=json.loads(subprocess.run([path,'4','8','--audit'],input=payload,capture_output=True,check=True).stdout)
        self.assertEqual(audit['zero_alpha_chromatic_pixels'],16)
        self.assertEqual(audit['zero_alpha_neutral_pixels'],16)
        self.assertEqual(run(2),original,'legacy behavior stays unchanged for unflagged skins')
        for mode in (4,5,9):
            result=run(mode)
            self.assertNotEqual(result[:64],original[:64])
            self.assertEqual(result[64:],original[64:],'neutral trim stays intact')
            self.assertEqual(result[3::4],original[3::4],'alpha is material data')
        inverse=run(8)
        self.assertNotEqual(inverse[64:67],original[64:67])
        self.assertEqual(inverse[:64],original[:64],'inversion only affects neutral art')
        self.assertEqual(inverse[3::4],original[3::4])

    def test_secondary_colour_inputs_are_explicitly_scoped(self):
        self.assertEqual(bindings('glock_ghost_protocol_red','g_tPattern'),('g_tPattern','g_tOverlay'))
        self.assertEqual(bindings('gsch_axia_glock','g_tPattern'),('g_tPattern','g_tCaseHardeningColorRamp'))
        self.assertEqual(bindings('cu_ak47_rubber','g_tPattern'),('g_tPattern',))

if __name__=='__main__':unittest.main()

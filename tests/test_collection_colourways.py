"""Client palette feedback, exact texture detail and complete trade-up membership."""
import colorsys,os,subprocess,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from collection_catalogue_designs import LINEUPS
from collection_colourways import recipe
from native_skins import collection_item_sets,_collection_lists,CASE_PREFIX
from native_tradeups import parse
from gun_collections import kit_name,TIER_COUNTS

class ColourwayReview(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('CS2_GC_TEXTURE_DECODER'),'native decoder required')
    def test_shades_change_painted_ink_but_keep_neutral_pixels_and_mask_alpha(self):
        from test_collection_material import bc7_solid
        payload=bc7_solid(244,10,10,0)+bc7_solid(128,128,128,80)
        results=[]
        for shade in range(1,5):
            child=subprocess.run([os.environ['CS2_GC_TEXTURE_DECODER'],'8','4','338','.8','10','38',str(shade)],input=payload,capture_output=True)
            self.assertEqual(child.returncode,0,child.stderr)
            pixels=child.stdout;self.assertEqual(len(pixels),128)
            self.assertEqual(pixels[3],0)
            self.assertEqual(pixels[16:20],bytes([128,128,128,80]))
            results.append(colorsys.rgb_to_hsv(*(v/255 for v in pixels[:3])))
        self.assertGreater(results[0][2],results[2][2])
        self.assertGreater(results[3][1],results[0][1])

    def test_feedback_repairs_include_overlay_backing_and_two_separate_ink_roles(self):
        from collection_art_sources import SOURCES
        from collection_channel_palettes import channels
        for collection,donor,theme in (('halcyon','cu_p2000_fire_elemental','Rose'),('solstice','soe_pink_cranes','Amber'),('outrider','cu_usp_black_lotus','Ember')):
            entry=next(e for e in LINEUPS[collection] if e['donor']==donor)
            self.assertIn(theme,entry['themes'])
            main,accent,saturation=recipe(donor,theme)
            self.assertNotEqual(main,accent,'do not flatten multicolour artwork')
            self.assertGreater(saturation,.5)
        self.assertEqual(SOURCES['soe_pink_cranes'],'overlay')
        backing=channels('soe_pink_cranes','Amber')
        self.assertIsNotNone(backing)
        self.assertLess(max(backing[0][:3]),.1,'exposed plastic stays charcoal, not mustard')
    @unittest.skipUnless(os.environ.get('CS2_GC_TEXTURE_DECODER'),'native decoder required')
    def test_two_ink_mapping_keeps_neutral_trim_value_and_material_alpha(self):
        from test_collection_material import bc7_solid
        tool=os.environ['CS2_GC_TEXTURE_DECODER']
        payload=bc7_solid(244,10,10,0)*2+bc7_solid(10,10,244,80)+bc7_solid(126,126,126,0)
        original=subprocess.run([tool,'4','16'],input=payload,capture_output=True,check=True).stdout
        result=subprocess.run([tool,'4','16','24','.82','10','276'],input=payload,capture_output=True,check=True).stdout
        self.assertEqual(result[3::4],original[3::4])
        self.assertEqual(result[-64:],original[-64:],'neutral trim is byte exact')
        for p in range(0,len(result),4):
            self.assertLessEqual(abs(max(result[p:p+3])-max(original[p:p+3])),1,'preserve authored value detail')
        base=colorsys.rgb_to_hsv(*(v/255 for v in result[:3]))[0]*360
        accent=colorsys.rgb_to_hsv(*(v/255 for v in result[128:131]))[0]*360
        self.assertLess(abs(base-24),12)
        self.assertLess(abs(accent-276),12)
        invalid=subprocess.run([tool,'4','16','24','.82','10'],input=payload,capture_output=True)
        self.assertNotEqual(invalid.returncode,0,'two-colour mode requires its accent')

    def test_targeted_palette_and_approved_signature_guards(self):
        neon=next(e for e in LINEUPS['aurora'] if e['donor']=='cu_ak_neon_rider')
        self.assertEqual(neon['themes'],['Ember','Violet','Crimson'])
        self.assertTrue(all(recipe(neon['donor'],t) for t in neon['themes']))
        tropical=next(e for e in LINEUPS['tidewater'] if e['donor']=='soe_tropical')
        self.assertEqual(tropical['themes'],['Rose'])
        from collection_channel_palettes import channels
        self.assertIsNotNone(channels('soe_tropical','Rose'))
        self.assertIsNone(recipe('gs_ak47_bloodsport','Ember'))
        gold=next(e for e in LINEUPS['forged'] if e['label']=='Gold Brick')
        self.assertEqual(gold['themes'],['Gold'])
        self.assertEqual(gold['pattern_source'],'am_doppler_phase2')

    def test_all_36_tradeup_sets_expand_rolls_to_real_colours_at_every_tier(self):
        families={};lists=[];expected={}
        for icon,entries in LINEUPS.items():
            name=CASE_PREFIX+icon;tiers={tier:[] for tier,_ in TIER_COUNTS};expected[name]=set()
            for e in entries:
                kit=kit_name(icon,e)
                tiers[e['tier']].append('[%s]%s'%(kit,e['weapon']))
                variants=[kit_name(icon,e,t) for t in e['themes']] if e['mode']=='family' else [kit]
                if e['mode']=='family':families[kit]=variants
                expected[name].update('[%s]%s'%(k,e['weapon']) for k in variants)
            lists.append(_collection_lists(name,tiers,[t for t,_ in TIER_COUNTS]))
        text,tokens=collection_item_sets('\n'.join(lists),list(expected),families)
        sets=parse('"item_sets" { '+text+' }').one('item_sets').children
        self.assertEqual(len(sets),36)
        members=[]
        for block in sets:
            self.assertEqual(block.text('name'),'#CSGO_'+block.key)
            self.assertIn('CSGO_'+block.key,tokens)
            actual={n.key for n in block.one('items').children}
            self.assertEqual(actual,expected[block.key])
            self.assertTrue(block.text('is_collection')=='1')
            self.assertFalse(any('['+family+']' in item for family in families for item in actual))
            members.extend(actual)
        self.assertEqual(len(members),len(set(members)),'one collection per concrete outcome')

    def test_missing_tradeup_list_fails_instead_of_silently_hiding_collection(self):
        with self.assertRaisesRegex(ValueError,'no loot list'):
            collection_item_sets('',[CASE_PREFIX+'aurora'],{})

if __name__=='__main__':unittest.main()

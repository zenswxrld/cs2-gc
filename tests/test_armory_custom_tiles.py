import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import rotate_armory


@unittest.skipUnless(shutil.which('node'), 'Node required for Panorama fixtures')
class CustomCollectionTiles(unittest.TestCase):
    def run_js(self, source):
        result=subprocess.run(['node','-e',source],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_custom_collection_overrides_stale_native_donor_title_and_loot(self):
        script='''const assert=require('assert');
const m_tileWidth=250,m_tileHeight=200;
const m_localRotation={categories:{'lootlist:set_cs2gc_case_forged':'collection'},
 collectionNames:{'lootlist:set_cs2gc_case_forged':'The Forged Collection'}};
const _OpenFullScreenInspectItem=()=>{};
const _GetLootListForReward=()=>['new-chase','new-filler'];
const aShopItemsData=[{item_name:'lootlist:set_cs2gc_case_forged',callout:'The Old Collection',
 ui_set_image:'old_set',lootlist:['old-chase'],ui_order:'3'}];
''' + rotate_armory.PREPARE + '''
const entry=aShopItemsData[0];
assert.equal(entry.callout,'The Forged Collection');
assert.equal(entry.ui_set_image,'set_cs2gc_case_forged');
assert.deepEqual(entry.lootlist,['new-chase','new-filler']);
assert.equal(entry.ui_order,'2');assert.equal(entry.lootlist_item_type,'weapon');
assert.equal(entry.tile_width,250);assert.equal(entry.tile_height,200);
'''
        self.run_js(script)

    def test_custom_png_emblems_bypass_svg_fallback_without_affecting_official_sets(self):
        script='''const assert=require('assert');
let path=null,fallbacks=0,svgs=0;
const IconUtil={SetupFallbackItemSetIcon:()=>fallbacks++,SetItemSetSVGImage:()=>svgs++};
const image={SetImage:value=>path=value};
''' + rotate_armory.INSERT.replace('__SETTINGS__',json.dumps({})) + '''
_LocalSetCollectionIcon(image,'set_cs2gc_case_warden');
assert.equal(path,'file://{images}/econ/set_icons/set_cs2gc_case_warden.png');
assert.equal(fallbacks,0);assert.equal(svgs,0);
_LocalSetCollectionIcon(image,'set_arabesque');
assert.equal(fallbacks,1);assert.equal(svgs,1);
'''
        self.run_js(script)


if __name__=='__main__':
    unittest.main()

from pathlib import Path
import shutil
import subprocess
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import gameplay_config
import native_endmatch
import native_item_sales
import premier_rating


@unittest.skipUnless(shutil.which('node'), 'Node required for Panorama fixtures')
class NativeLocalFeatures(unittest.TestCase):
    def run_js(self, code):
        result = subprocess.run(['node', '-e', code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_results_follow_real_cache_exclude_old_items_and_do_not_grant(self):
        script = '''const assert = require('assert');
let ids = ['1000000000001'], rank = 4207, wins = 10, level = 1, next = 0;
const jobs = [], nodes = {};
function make(id) {
 const panel = {id, style:{}, children:[], IsValid:()=>true,
  FindChildTraverse:id=>nodes[id]};
 if (id) nodes[id] = panel;
 return panel;
}
const _m_cP = make('root'); make('id-eom-layout');
const _m_data = {_m_arrPanelObjects:[{name:'victory'},{name:'stock-xp'}]};
const MyPersonaAPI = {IsInventoryValid:()=>true,GetXuid:()=> 'local',GetCurrentLevel:()=>level};
const FriendsListAPI = {GetFriendCompetitiveRank:()=>rank, GetFriendCompetitiveWins:()=>wins};
const InventoryAPI = {GetUnacknowledgeItemsCount:()=>ids.length, GetUnacknowledgeItemByIndex:i=>ids[i],
 GetItemPickupMethod:id=>id === '1000000000003' ? 'xpshopredeem' : 'drop',
 GetItemName:id=>'Reward '+id, GetItemRarityColor:()=> '#00aaff'};
const GameStateAPI = {IsDemoOrHltv:()=>false,IsQueuedMatchmaking:()=>false};
const EndOfMatch = {SwitchToPanel:id=>assert.equal(id,'eom-local-results'),StartDisplayTimer:()=>{},ShowNextPanel:()=>next++};
const $ = {Schedule:(delay,fn)=>{jobs.push({delay,fn});return jobs.length;},
 CreatePanel:(kind,parent,id,props)=>{const panel=make(id);panel.kind=kind;panel.props=props;parent.children.push(panel);return panel;}};
''' + native_endmatch.SCRIPT.replace('__PLACEMENTS__', '10') + '''
_LocalResultsInitialize();
jobs.find(job=>job.delay===0).fn();
assert.equal(_m_data._m_arrPanelObjects[1].name,'eom-local-results');
ids.push('1000000000002','1000000000003'); rank=4518; level=2;
_m_data._m_arrPanelObjects[1].Start();
assert.equal(nodes['local-results-level'].text, 'Profile level 2');
assert.equal(nodes['local-results-rating'].text, 'CS Rating  4518   (+311)');
assert.equal(nodes['local-results-items'].children.length,1);
_LocalResultsRefresh(); assert.equal(nodes['local-results-items'].children.length,1);
assert.equal(nodes['local-results-items'].children[0].children[0].props.itemid, '1000000000002');
m_localResultsOpen = false;
ids.push('1000000000004'); _LocalResultsRefresh();
assert.equal(nodes['local-results-items'].children.length,1);
'''
        self.run_js(script)

    def test_sale_requires_native_confirmation_and_local_item(self):
        source = '''    function _PopulateContextMenu(id, populateFilterText) {
        let validEntries = ItemContextEntries.FilterEntries(id, populateFilterText);
}'''
        data = {'enabled':True,'flat':{'60':1},'rarity':[0,1,2,5,10,25,50],'gold':150,'stickerPercent':50}
        script = '''const assert = require('assert'); let confirm, deleted = 0, button;
const elParent = {}, ItemContextEntries = {FilterEntries:()=>[]};
const InventoryAPI = {GetItemDefinitionName:()=> 'case', GetItemDefinitionIndexFromDefinitionName:()=>60,
 GetItemName:()=> 'Case', DeleteItem:()=>deleted++};
const UiToolkitAPI = {ShowGenericPopupYesNo:(title,text,icon,yes,no)=>{confirm={yes,no,text};}};
const $ = {CreatePanel:(type,parent,id,props)=>{const p={SetPanelEvent:(event,fn)=>p.activate=fn}; if(type==='Button')button=p; return p;},DispatchEvent:()=>{}};
''' + native_item_sales.patch(source, data) + '''
assert.equal(_LocalSalePrice('42'),0);
_PopulateContextMenu('1000000000001',''); button.activate();
assert.equal(deleted,0); confirm.no(); assert.equal(deleted,0);
assert.ok(confirm.text.includes('1 stars')); confirm.yes(); assert.equal(deleted,1);
'''
        self.run_js(script)

    def test_changed_result_script_fails_closed(self):
        with self.assertRaises(ValueError): native_endmatch.patch('unrecognized client', gameplay_config.DEFAULTS)


class Ratings(unittest.TestCase):
    def test_variation_bounds_signs_and_persistable_delta(self):
        config = dict(gameplay_config.DEFAULTS)
        state = premier_rating.initial(config)
        low = premier_rating.apply(state,'wins',config,lambda n:0)
        high = premier_rating.apply(state,'wins',config,lambda n:n-1)
        self.assertEqual(low['last_change'],221)
        self.assertEqual(high['last_change'],379)
        self.assertEqual(state['wins'],0)
        loss = premier_rating.apply(state,'losses',config,lambda n:0)
        self.assertEqual(loss['last_change'],-179)
        self.assertEqual(premier_rating.apply(state,'ties',config)['last_change'],0)
        config['premier_rating_variation']=10000
        self.assertLess(premier_rating.apply(state,'losses',config,lambda n:n-1)['last_change'],0)
        self.assertGreater(premier_rating.apply(state,'wins',config,lambda n:0)['last_change'],0)

if __name__ == '__main__': unittest.main()

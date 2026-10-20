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
const GameStateAPI = {GetMapBSPName:()=> 'de_test',IsDemoOrHltv:()=>false,IsQueuedMatchmaking:()=>false};
const EndOfMatch = {SwitchToPanel:id=>assert.equal(id,'eom-local-results'),StartDisplayTimer:()=>{},ShowNextPanel:()=>next++};
const GameInterfaceAPI = {ConsoleCommand:()=>{}};
const $ = {RegisterForUnhandledEvent:()=>{}, Schedule:(delay,fn)=>{jobs.push({delay,fn});return jobs.length;},
 CreatePanel:(kind,parent,id,props)=>{const panel=make(id);panel.kind=kind;panel.props=props;parent.children.push(panel);return panel;}};
''' + native_endmatch.SCRIPT.replace('__PLACEMENTS__', '10').replace('__DURATION__','20').replace('__DELAY__','45') + '''
_LocalResultsInitialize();
jobs.find(job=>job.delay===0).fn();
assert.equal(_m_data._m_arrPanelObjects[1].name,'eom-local-results');
ids.push('1000000000002','1000000000003'); _LocalCollectDrops();
// An inventory popup acknowledges rewards before the end screen starts.
ids = ['1000000000001']; rank=4518; level=2;
_m_data._m_arrPanelObjects[1].Start();
assert.equal(nodes['local-results-level'], undefined);  // XP and rating use the stock panels now
assert.equal(nodes['local-results-items'].children.length,1);
_LocalResultsRefresh(); assert.equal(nodes['local-results-items'].children.length,1);
assert.equal(nodes['local-results-items'].children[0].children[0].props.itemid, '1000000000002');
m_localResultsOpen = false;
ids.push('1000000000004'); _LocalResultsRefresh();
assert.equal(nodes['local-results-items'].children.length,1);
// The start-of-match baseline for the stock XP/rating panels is recorded once and cleared per match.
EndOfMatch.LocalBaseline = null; m_localResultsOpen = false; level = 3; rank = 4600;
_LocalResultsCapture();
assert.deepEqual(EndOfMatch.LocalBaseline, {level: 3, xp: 0, rating: 4600, wins: 10});
// No drops: the tab hides itself and the sequence moves on.
m_localResultsDrops = []; ids = []; make('rb--eom-local-results'); const before = next;
_m_data._m_arrPanelObjects[1].Start();
assert.equal(next, before + 1); assert.equal(nodes['rb--eom-local-results'].visible, false);
'''
        self.run_js(script)

    def test_sale_requires_native_confirmation_and_local_item(self):
        source = '''    function _PopulateContextMenu(id, populateFilterText) {
        let validEntries = ItemContextEntries.FilterEntries(id, populateFilterText);
        marketEntries = validEntries.map(e=>e.name);
        if (!validEntries.length) {}
}'''
        data = {'enabled':True,'flat':{'60':1},'rarity':[0,1,2,5,10,25,50],'gold':150,'stickerPercent':50}
        script = '''const assert = require('assert'); let confirm, deleted = 0, button, marketEntries;
const elParent = {}, ItemContextEntries = {FilterEntries:()=>[{name:'sell'},{name:'inspect'}]};
const InventoryAPI = {GetItemDefinitionName:()=> 'case', GetItemDefinitionIndexFromDefinitionName:()=>60,
 GetItemName:()=> 'Case', DeleteItem:()=>deleted++};
const UiToolkitAPI = {ShowGenericPopupYesNo:(title,text,icon,yes,no)=>{confirm={yes,no,text};}};
const $ = {CreatePanel:(type,parent,id,props)=>{const p={AddClass:()=>{},SetPanelEvent:(event,fn)=>p.activate=fn}; if(type==='Button')button=p; return p;},DispatchEvent:()=>{}};
''' + native_item_sales.patch(source, data) + '''
assert.equal(_LocalSalePrice('42'),0);
_PopulateContextMenu('1000000000001',''); assert.deepEqual(marketEntries,['inspect']); button.activate();
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

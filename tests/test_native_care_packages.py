import sys
from pathlib import Path
import unittest
import subprocess
import shutil
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import native_care_packages as care
import native_knife_reel as reel
import skip_key_select
import native_item_sales
import gameplay_config

@unittest.skipUnless(shutil.which('node'),'Node required')
class NativeCarePackages(unittest.TestCase):
    def run_js(self,source):
        result=subprocess.run(['node','-e',source],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_native_claim_requires_three_choices_and_removes_weekly_text(self):
        source='''let m_redeemableBalance=3,m_schTimer,m_timeoutScheduleHandle=99,m_timeStamp=10;
    function GetPersonalStore() {return store;}
    function OnRedeem() {let szItemList='';
        StoreAPI.StoreRedeemFreeRewards(szItemList);\n}
    function _UpdateTime() { weekly++; }
    function OnInventoryUpdated() { updated++; }
    function _CreateItemPanel(itemId, index, bFirstTime, claimedItemId = '') {
        ItemTileStore.Init(elGhostItem, oItemData);
        elGhostItem.Data().itemid = itemId;
    }
    function _OnGhostItemActivate(itemId) {
        if (!InventoryAPI.IsFauxItemID(itemId)) { return true; }
    }
'''
        script='''const assert=require('assert');let count=2,sent=0,pulses=0,weekly=0,updated=0,cancelled=0;
let store={generation_time:10,redeemable_balance:3,items:['3000000000001','3004294967297','3008589934593','3012884901889']};
const title={},vars={},panel={FindChildrenWithClassTraverse:()=>[title],SetDialogVariable:(key,value)=>vars[key]=value,RemoveClass:()=>{}};
const $={GetContextPanel:()=>panel,Schedule:()=>1,CancelScheduled:()=>cancelled++};
const _GetSelectedItems=()=>Array.from({length:count},(_,i)=>({item_id:store.items[i]})),_PulseItems=()=>pulses++;
const GameInterfaceAPI={GetSettingString:()=> 'a'.repeat(32),ConsoleCommand:()=>sent++};
const StoreAPI={StoreRedeemFreeRewards:()=>sent++};
''' +care.patch(source)+'''
OnRedeem(); assert.equal(sent,0);assert.equal(pulses,1);
count=4;OnRedeem();assert.equal(sent,0);
count=3;OnRedeem();assert.equal(sent,1);
_UpdateTime();assert.equal(title.text,'CARE PACKAGE');assert.equal(vars['frame-badge-text'],'CHOOSE 3 OF 4 REWARDS');assert.equal(weekly,0);
store={generation_time:11,redeemable_balance:3,items:store.items};OnInventoryUpdated();assert.equal(cancelled,1);
store={generation_time:0,redeemable_balance:0,items:[]};m_redeemableBalance=0;_UpdateTime();assert.equal(vars['frame-badge-text'],'REWARDS CLAIMED');
store={generation_time:9,redeemable_balance:2,items:['123']};count=2;OnRedeem();assert.equal(sent,2);
'''
        self.run_js(script)

    def test_catalogue_preview_decode_preserves_unique_choice_tokens(self):
        script="""const assert=require('assert');let itemId='3008590589965',seen;
const InventoryAPI={GetFauxItemIDFromDefAndPaintIndex:(def,paint)=>{seen=[def,paint];return 'faux';}};
const _LocalCarePackage=()=>true;
"""+care.PREVIEW+"""
assert.deepEqual(seen,[13,10]);assert.equal(itemId,'faux');assert.equal(choiceToken,'3008590589965');
"""
        self.run_js(script)

    def test_native_faux_claimed_flag_is_cleared_only_for_pending_local_rewards(self):
        source="""    function GetPersonalStore() {return store;}
    function OnRedeem() {
        StoreAPI.StoreRedeemFreeRewards(szItemList);\n}
    function _UpdateTime() {}
    function OnInventoryUpdated() {}
    function _CreateItemPanel(itemId, index, bFirstTime, claimedItemId = '') {
        const oItemData={id:itemId,isDropItem:true};
        ItemTileStore.Init(elGhostItem, oItemData);
        elGhostItem.Data().itemid = itemId;
    }
    function _OnGhostItemActivate(itemId) {
        if (!InventoryAPI.IsFauxItemID(itemId)) {}
    }
"""
        script="""const assert=require('assert');let store={items:['3000000000007']};const data={},classes={};
const elGhostItem={Data:()=>data,SetHasClass:(key,value)=>classes[key]=value};
const InventoryAPI={GetFauxItemIDFromDefAndPaintIndex:()=> 'faux',IsFauxItemID:()=>true};
// Native ItemTileStore.SetClaimed treats every faux preview as already claimed.
const ItemTileStore={Init:()=>{classes['item-claimed']=true;classes['item-claimslot-expired']=true;}};
"""+care.patch(source)+"""
_CreateItemPanel('3000000000007',0,false);
assert.equal(classes['item-claimed'],false);assert.equal(classes['item-claimslot-expired'],false);
assert.equal(data.itemid,'3000000000007');
store={items:['123']};_CreateItemPanel('123',0,false);assert.equal(classes['item-claimed'],true);
"""
        self.run_js(script)

    def test_native_free_case_popup_uses_keyless_path_without_changing_terminals_or_real_items(self):
        source='''function init(caseId){
            const associatedItemCount = InventoryAPI.GetAssociatedItemsCount(caseId);
return associatedItemCount;
}
function choose(lootListCount){
'''+reel.ANCHOR+''' }
'''+reel.FUNCTION+''' }
function tile(itemId){
'''+reel.TILE+''' return true; }}
function _SetUpCaseOpeningScroll(){}
'''
        script='''const assert=require('assert');let terminal=false;
const InventoryAPI={GetAssociatedItemsCount:()=>1,GetItemAttributeValue:()=>terminal};
'''+reel.patch(source,{},keyless=True)+'''
assert.equal(init('1000000000001'),0);
terminal=true;assert.equal(init('1000000000001'),1);
terminal=false;assert.equal(init('123'),1);
'''
        self.run_js(script)

    def test_sale_settings_include_glove_prefabs_and_real_key_index(self):
        source='''"items_game" { "prefabs" { "hands_paintable" {} "weapon_case_base" {} }
        "items" { "5032" { "name" "leather_handwraps" "prefab" "hands_paintable" }
        "100" { "name" "crate_test" "prefab" "weapon_case_base" "associated_item" "101"
        "attributes" { "set supply crate series" { "value" "1" } } } "101" { "name" "key" } } }'''
        data=native_item_sales.settings(source,gameplay_config.DEFAULTS)
        self.assertIn('5032',data['goldDefinitions'])
        self.assertEqual(data['flat']['101'],5)

    def test_changed_native_reward_screen_fails_closed(self):
        with self.assertRaises(ValueError):care.patch('unrecognized client')

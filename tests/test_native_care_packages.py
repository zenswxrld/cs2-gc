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
    function OnRedeem() {
        let szItemList = _GetSelectedItems().map(item => item.item_id).join(',');
        StoreAPI.StoreRedeemFreeRewards(szItemList);
    }
    function _RedemptionTimedOut() {
    }
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
const claims=[],favourites=[];const $={GetContextPanel:()=>panel,Schedule:()=>1,CancelScheduled:()=>cancelled++,Msg:text=>claims.push(text)};
const TournamentsAPI={SetTournamentFavorite:(id,on)=>favourites.push([id,on])};
const StoreAPI={StoreRedeemFreeRewards:()=>sent++};
const InventoryAPI={GetFauxItemIDFromDefAndPaintIndex:()=>'faux',IsItemInfoValid:()=>true,IsValidItemID:()=>true};
const _GetSelectedItems=()=>Array(count).fill({item_id:'3000000000001'}),_PulseItems=()=>pulses++;
''' +care.patch(source)+'''
OnRedeem(); assert.equal(sent,0);assert.equal(pulses,1);
count=4;OnRedeem();assert.equal(sent,0);
count=3;OnRedeem();assert.equal(sent,0,'local claims never call the native claim');assert.equal(claims.length,1);
assert.deepEqual(favourites,[[4200000000000000+10*16+1,true]]);
_UpdateTime();assert.equal(title.text,'CARE PACKAGE');assert.equal(vars['frame-badge-text'],'CHOOSE 3 OF 4 REWARDS');assert.equal(weekly,0);
store={generation_time:11,redeemable_balance:3,items:store.items};OnInventoryUpdated();assert.equal(cancelled,1);
store={generation_time:0,redeemable_balance:0,items:[]};m_redeemableBalance=0;_UpdateTime();assert.equal(vars['frame-badge-text'],'REWARDS CLAIMED');
store={generation_time:9,redeemable_balance:2,items:['123']};count=2;OnRedeem();assert.equal(sent,1,'official stores still use the native claim');
assert.equal(claims.length,1);
'''
        self.run_js(script)


    def test_claimed_package_stays_on_show_with_only_the_taken_rewards_marked(self):
        source="""    function GetPersonalStore() {return store;}
    function OnRedeem() {
        let szItemList = '';
        StoreAPI.StoreRedeemFreeRewards(szItemList);
    }
    function _RedemptionTimedOut() {}
    function _UpdateTime() {}
    function OnInventoryUpdated() {}
    function _CreateItemPanel(itemId, index, bFirstTime, claimedItemId = '') {
        ItemTileStore.Init(elGhostItem, oItemData);
        elGhostItem.Data().itemid = itemId;
    }
    function _OnGhostItemActivate(itemId) {
        if (!InventoryAPI.IsFauxItemID(itemId)) {}
    }
"""
        script="""const assert=require('assert');const data={},classes={},oItemData={};let shown;
const taken=3000000000000+68719476736;
let store={items:[String(taken+7),String(taken+4294967296+9),String(3000000000000+2*4294967296+11),String(taken+3*4294967296+13)]};
const elGhostItem={Data:()=>data,SetHasClass:(key,value)=>classes[key]=value};
const InventoryAPI={GetFauxItemIDFromDefAndPaintIndex:(def,paint)=>{shown=[def,paint];return 'faux';},IsFauxItemID:()=>true};
const ItemTileStore={Init:()=>{classes['item-claimed']=true;classes['item-claimslot-expired']=true;}};
"""+care.patch(source)+"""
assert.ok(_LocalCarePackage(),'the claimed view is still the local package');
_CreateItemPanel(store.items[0],0,false);
assert.equal(classes['item-claimed'],true);assert.equal(classes['item-claimslot-expired'],false);assert.deepEqual(shown,[7,0]);
_CreateItemPanel(store.items[2],2,false);
assert.equal(classes['item-claimed'],false,'the reward not taken is not shown as claimed');assert.deepEqual(shown,[11,0]);
store={items:['17293822569102709458','52275636417']};assert.ok(!_LocalCarePackage(),'Valve stores are untouched');
"""
        self.run_js(script)

    def test_catalogue_preview_decode_preserves_unique_choice_tokens(self):
        script="""const assert=require('assert');let itemId='3008590589965',seen;
const InventoryAPI={GetFauxItemIDFromDefAndPaintIndex:(def,paint)=>{seen=[def,paint];return 'faux';}};
const GetPersonalStore=()=>null,$={};
"""+care.HELPER+"""
const _LocalCarePackageStub=true;
"""+care.PREVIEW.replace('_LocalCarePackage()','_LocalCarePackageStub')+"""
assert.deepEqual(seen,[13,10]);assert.equal(itemId,'faux');assert.equal(choiceToken,'3008590589965');
"""
        self.run_js(script)

    def test_native_faux_claimed_flag_is_cleared_only_for_pending_local_rewards(self):
        source="""    function GetPersonalStore() {return store;}
    function OnRedeem() {
        let szItemList = '';
        StoreAPI.StoreRedeemFreeRewards(szItemList);
    }
    function _RedemptionTimedOut() {}
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

    def test_local_claim_prints_the_line_the_dll_claims_from(self):
        # Build 27 log: StoreRedeemFreeRewards(choice tokens) produced no 9219 frame at all.
        source="""    function GetPersonalStore() {return store;}
    function OnRedeem() {
        let szItemList = _GetSelectedItems().map(item => item.item_id).join(',');
        StoreAPI.StoreRedeemFreeRewards(szItemList);
        m_timeoutScheduleHandle = 1;
    }
    function _RedemptionTimedOut() {
        m_timeoutScheduleHandle = null;
    }
    function _UpdateTime() {}
    function OnInventoryUpdated() {}
    function _CreateItemPanel(itemId, index, bFirstTime, claimedItemId = '') {
        ItemTileStore.Init(elGhostItem, oItemData);
        elGhostItem.Data().itemid = itemId;
    }
    function _OnGhostItemActivate(itemId) {
        if (!InventoryAPI.IsFauxItemID(itemId)) {}
    }
"""
        script="""const assert=require('assert');let m_redeemableBalance=3,m_timeoutScheduleHandle,throwing=false;const sent=[],logs=[];
let store={generation_time:7,redeemable_balance:3,items:['3000000004186','3004381212712','3008680177725','3012884906436']};
let selected=['3000000004186','3004381212712','3012884906436'];
const _GetSelectedItems=()=>selected.map(item_id=>({item_id}));const _PulseItems=()=>{};
const $={Msg:text=>logs.push(text)};const favourites=[];
const TournamentsAPI={SetTournamentFavorite:(id,on)=>favourites.push([id,on])};
const StoreAPI={StoreRedeemFreeRewards:list=>sent.push(list)};
const InventoryAPI={GetFauxItemIDFromDefAndPaintIndex:(def,paint)=>'F'+def+'p'+paint,
    IsItemInfoValid:id=>{if(throwing)throw new Error('x');return id[0]==='F';},IsValidItemID:id=>id[0]==='F'};
"""+care.patch(source)+"""
OnRedeem();
// The exact line the DLL parses (ParseCareConsoleClaims); nothing goes to the native claim.
assert.deepEqual(logs,['cs2_gc care: claim generation=7 balance=3 tokens=3000000004186,3004381212712,3012884906436']);
assert.deepEqual(sent,[]);
// Slots 0, 1 and 3 (tokens carry slot << 32): mask 0b1011, generation 7; exact as a Panorama number (< 2^53).
assert.deepEqual(favourites,[[4200000000000000+7*16+11,true]]);
assert.ok(Number.isSafeInteger(4200000000000000+4294967295*16+15));
_RedemptionTimedOut();assert.ok(logs[logs.length-1].includes('claim timed out'));
store={generation_time:1,redeemable_balance:2,items:['52275636417']};selected=['52275636417'];
OnRedeem();assert.deepEqual(sent,['52275636417'],'official stores keep the native claim and item ids');
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

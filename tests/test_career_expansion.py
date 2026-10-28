import sys,tempfile,unittest,json,subprocess,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import chicken_cosmetics,companions,native_profile_pins,unboxing_stats
import native_local_play
import glove_refresh,collectible_rewards
import music_store,colour_families,colorsys
from native_tradeups import parse


class Expansion(unittest.TestCase):
    def test_music_catalogue_adds_capsule_only_kits_and_supported_stattrak(self):
        schema='''"items_game" { "music_definitions" { "1" { "name" "one" "loc_name" "#one" } "2" { "name" "two" "loc_name" "#two" } }
        "items" { "200" { "name" "coupon one" "loot_list_name" "coupon loot list one" } }
        "client_loot_lists" { "coupon loot list one" { "[one]musickit" "1" } "st_capsule" { "will_produce_stattrak" "1" "nested" "1" } "nested" { "[two]musickit" "1" } } }'''
        changed=music_store.patch_schema(schema)
        kits,offers,st,capsules=music_store.catalogue(changed)
        self.assertEqual(set(offers),{('one',False),('two',False),('two',True)})
        self.assertEqual(offers[('one',False)][0],'200')
        self.assertEqual(st,{'two'})
        self.assertEqual(music_store.patch_schema(changed),changed)
        import price_sheet as sheet
        tree=[('store',[('entries',[(name,[('item_link',name),('prices',[('AUD',price)])]) for name,price in
            [('coupon - normal_musickit_capsule',710),('coupon - normal_stattrak_musickit_capsule',1135)]]),('store_banner_layout',[])])]
        self.assertEqual(music_store.add_store(tree,changed),3)
        self.assertEqual(music_store.add_store(tree,changed),0)
        entries=dict(sheet.section(tree,'store','entries'))
        self.assertEqual(dict(dict(entries[offers[('two',True)][1]])['prices'])['AUD'],1135)

    def test_shades_keep_detail_neutrals_and_alpha_without_flattening(self):
        original=[[.1,.4,.6,.25],[.2,.2,.2,.9],[.03,.03,.03,0]]
        coloured=[[.6,.15,.35,.25],list(original[1]),list(original[2])]
        shades={name:colour_families.tone(coloured,'Rose_'+name,original) for name in colour_families.SHADES}
        self.assertGreater(max(shades['Light'][0][:3]),max(shades['Deep'][0][:3]))
        self.assertGreater(colorsys.rgb_to_hsv(*shades['Vivid'][0][:3])[1],colorsys.rgb_to_hsv(*shades['Light'][0][:3])[1])
        for result in shades.values():
            self.assertEqual(result[1:],original[1:])
            self.assertEqual([c[3] for c in result],[c[3] for c in original])
        self.assertEqual(len(colour_families.expand(['Rose','Rose'])),5)
        ash=[[.45,.48,.5,.25],list(original[1]),list(original[2])]
        light=colour_families.tone(ash,'Ash_Light',original)
        deep=colour_families.tone(ash,'Ash_Deep',original)
        vivid=colour_families.tone(ash,'Ash_Vivid',original)
        self.assertGreater(max(light[0][:3]),max(deep[0][:3]))
        self.assertLessEqual(colorsys.rgb_to_hsv(*vivid[0][:3])[1],.101)

    def test_glove_only_schema_update_keeps_other_paints_and_ids(self):
        original='"items_game" { "paint_kits" { "1" { "name" "stock" } "30000" { "name" "rg_fixture" "description_string" "Old" "description_tag" "Old" } } "paint_kits_rarity" {} "client_loot_lists" { "crate_cs2gc_gauntlet_ancient" { "old" "1" } } }'
        entries=[('30000','rg_fixture','Midnight',{}),('30001','rg_fixture_panels_dark','Midnight Dark',{})]
        changed=glove_refresh.patch_schema(original,entries,['[rg_fixture]slick_gloves','[rg_fixture_panels_dark]slick_gloves'])
        root=parse(changed).one('items_game')
        self.assertEqual(root.one('paint_kits').one('1').text('name'),'stock')
        self.assertEqual(root.one('paint_kits').one('30000').text('description_tag'),'Midnight')
        self.assertEqual(root.one('paint_kits').one('30001').text('name'),'rg_fixture_panels_dark')
        self.assertEqual(glove_refresh.patch_schema(changed,entries,['[rg_fixture]slick_gloves','[rg_fixture_panels_dark]slick_gloves']),changed)

    def test_collectible_progress_comes_from_saved_native_matches(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);(p/'cs2_gc_inventory.txt').write_text('"inventory" { "match_reward_total" "50" "career_collectible_mask" "3" }')
            self.assertEqual(collectible_rewards.snapshot(p),dict(matches=50,paid=3))

    def test_accessories_extend_existing_sections_without_replacing_stock(self):
        original='"items_game" { "items" { "42" { "name" "stock" } } "client_loot_lists" { "stock" { "stock" "1" } } "seasonaloperations" { "11" { } } }'
        changed=chicken_cosmetics.patch(original,armory=True)
        root=parse(changed).one('items_game')
        self.assertEqual(root.one('items').one('42').text('name'),'stock')
        self.assertEqual(len(root.one('items').children),11)
        self.assertEqual(chicken_cosmetics.patch(changed,armory=True),changed)
        self.assertEqual(root.one('seasonaloperations').one('11').one('operational_point_redeemable').text('points'),'3')
        # Off by default: the accessories stay defined (owned ones keep working) but leave the Armory.
        hidden=chicken_cosmetics.patch(changed)
        self.assertEqual(len(parse(hidden).one('items_game').one('items').children),11)
        self.assertNotIn('operational_point_redeemable',hidden)
        self.assertEqual(chicken_cosmetics.patch(original),hidden)
        self.assertEqual(chicken_cosmetics.patch(hidden,armory=True),changed)
        with self.assertRaises(ValueError):chicken_cosmetics.patch(original.replace('"42"','"55000"'))

    def test_owned_pins_follow_prefabs_and_ignore_unowned_or_non_collectibles(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            (p/'items_game.txt').write_text('"items_game" { "prefabs" { "coin" { "item_class" "collectible_item" } } "prefabs" { "pin" { "prefab" "coin" } } "items" { "1" { "prefab" "pin" } "2" { "prefab" "coin" } "3" { "item_class" "weapon_ak47" } } }')
            (p/'cs2_gc_inventory.txt').write_text('"inventory" { "items" { "1" { "def_index" "1" } "2" { "def_index" "3" } "3" { "def_index" "1" } } }')
            self.assertEqual(native_profile_pins.owned_definitions(p),[1])

    def test_multiple_pet_snapshot_and_owned_accessory(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            (p/'cs2_gc_inventory.txt').write_text('"inventory" { "pet_active" "2" "items" { "1" { "def_index" "4948" "pet" "23 3 0 0 2 0" } "2" { "def_index" "4948" "pet" "24 5 2 3 2 55000" } "3" { "def_index" "55000" } } }')
            view=companions.snapshot(p)
            self.assertEqual(view['selected'],'1000000000002')
            self.assertEqual([pet['stage_name'] for pet in view['pets']],['Egg','Pullet'])
            self.assertEqual(view['accessories'],[55000])
            self.assertEqual(len(view['catalogue']),10)
            # Existing inventory is never invented as historical openings.
            self.assertEqual(unboxing_stats.snapshot(p)['total'],0)

    def test_unknown_pin_source_fails_closed(self):
        with self.assertRaises(ValueError):native_profile_pins.patch('changed native source',[1])

    @unittest.skipUnless(shutil.which('node'),'Node unavailable')
    def test_both_captain_orders_ban_six_maps_and_offer_starting_side(self):
        maps=['de_a','de_b','de_c','de_d','de_e','de_f','de_g']
        setup=r'''
        const panels={},pending=[],launches=[];let map='',session=null;
        function panel(id){const p={id,text:'',style:{},enabled:true,events:{},classes:{},children:{},
            IsValid:()=>!p.deleted,SetPanelEvent:(k,f)=>p.events[k]=f,SetImage:()=>{},SetImageFromPanel:()=>{},
            AddClass:k=>p.classes[k]=true,SetHasClass:(k,v)=>p.classes[k]=v,SwitchClass:(k,v)=>p.classes[k]=v,
            SetDialogVariable:()=>{},FindChild:id=>p.children[id],FindChildInLayoutFile:id=>p.children[id],
            DeleteAsync:()=>p.deleted=true,BLoadLayout:(path)=>{p.loaded=path;nativeLayout(p);return true;}};
            if(id)panels[id]=p;return p;}
        function nativeLayout(root){
            const ids=['id-team-vote-middle','id-team-vote-spider-graph','PartyChat','id-team-vote-title-phase',
                'id-team-vote-title-spinner','id-pick-vote-team','id-team-vote-map-icon','id-team-vote-map-image'];
            for(let i=2;i<=7;i++)ids.push('id-team-vote-phasebar-'+i);
            for(let i=0;i<7;i++)ids.push('id-map-vote-btn-'+i,'id-map-vote-btn-ref-'+i);
            for(let i=0;i<2;i++)ids.push('id-team-vote-btn-'+i,'id-team-vote-btn-ref-'+i);
            ids.forEach(id=>root.children[id]=panel(id));
            for(let i=2;i<=7;i++)root.children['id-team-vote-phasebar-'+i].children['id-team-phase-bar-inner']=panel('');
            for(const kind of ['map','team'])for(let i=0;i<(kind==='map'?7:2);i++){
                const parent=root.children['id-'+kind+'-vote-btn-'+i],btn=panel('');
                parent.children['id-pickban-btn']=btn;btn.children['id-pickban-map-btn-bg']=panel('');}
        }
        const $={Msg:()=>{},DispatchEvent:()=>{},CreatePanel:(type,parent,id)=>panel(id),GetContextPanel:()=>panel('context'),Localize:s=>s,Schedule:(delay,f)=>pending.push(f)};
        const cfg={mapgroups:{mg_active:{maps:Object.fromEntries(MAPS.map(m=>[m,{}]))}}};MAPS.forEach(m=>cfg.mapgroups['mg_'+m]={});
        const GameTypesAPI={GetConfig:()=>cfg},PartyListAPI={GetCount:()=>1};
        const InventoryAPI={GetItemInventoryImage:()=>'/agent'},LoadoutAPI={GetItemID:()=> '1'};
        const LobbyAPI={BIsHost:()=>true,StopMatchmaking:()=>{},GetSessionSettings:()=>session,IsSessionActive:()=>true,
            UpdateSessionSettings:s=>session={options:s.update.Options,game:s.update.Game},StartMatchmaking:()=>launches.push(session)};
        const GameStateAPI={GetMapBSPName:()=>map},GameInterfaceAPI={ConsoleCommand:()=>{}};
        function GetGameType(){return 0;}
        function GetMGDetails(name){return {nameID:name,icon_image_path:name};}
        const UiToolkitAPI={ShowGenericPopupOk:()=>{throw Error('Unexpected error');}};
        Math.random=()=>FIRST;
        '''
        check=r'''
        _LocalOpenVeto();
        const root=panels.LocalPremierVeto;
        if(!root.style.ignoreParentFlow||root.style.position!=='0px 0px 0px')throw Error('Veto overlay must be outside the parent layout flow');
        if(root.loaded!=='file://{resources}/layout/popups/popup_premier_pick_ban.xml')throw Error('Must load actual Premier layout');
        const buttons=MAPS.map((m,i)=>root.children['id-map-vote-btn-'+i].children['id-pickban-btn']);
        for(let i=0;i<12;i++){
            if(buttons.filter(p=>p.classes['premier-pickban-veto']).length===6)break;
            if(pending.length)pending.shift()();
            else {const choice=buttons.find(p=>p.enabled);if(!choice)throw Error('No ban available');choice.events.onactivate();}
        }
        if(buttons.filter(p=>p.classes['premier-pickban-veto']).length!==6)throw Error('Expected six bans');
        if((panels.LocalVetoHistory.text.match(/YOU:|BOTS:/g)||[]).length!==6)throw Error('Expected six history entries');
        const before=panels.LocalVetoHistory.text;buttons[0].events.onactivate();
        if(before!==panels.LocalVetoHistory.text)throw Error('Late map click changed completed draft');
        if(FIRST===0){if(!panels.LocalVetoStart)throw Error('Bot side choice missing');panels.LocalVetoStart.events.onactivate();}
        else {const ct=root.children['id-team-vote-btn-0'].children['id-pickban-btn'];if(!ct.enabled)throw Error('Human side choice missing');ct.events.onactivate();}
        while(!launches.length&&pending.length)pending.shift()();
        if(launches.length!==1||launches[0].game.mode_ui!=='premier')throw Error('Must launch selected local Premier match');
        const selected=buttons.findIndex(p=>p.classes['premier-pickban-pick']);
        if(launches[0].game.map!==MAPS[selected])throw Error('Wrong decider launched');
        '''
        for first in (0,.9):
            source='const MAPS='+json.dumps(maps)+';const FIRST='+str(first)+';'+setup+native_local_play.SCRIPT.replace('__MAPS__',json.dumps(maps))+check
            subprocess.run(['node','-e',source],check=True,capture_output=True,text=True)


if __name__=='__main__':unittest.main()

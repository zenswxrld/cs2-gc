"""Installed night-map availability and a local BO1 Premier veto, using the listen-server path."""
import json,re
from pathlib import Path
from native_resources import install_override

SCRIPT=r'''
    let m_localVetoMap='',m_localVeto=null,m_localStarting=false;
    const m_localInstalled=__MAPS__;
    function _LocalPremierPool() {
        const cfg=GameTypesAPI.GetConfig(),active=cfg.mapgroups&&cfg.mapgroups.mg_active;
        const entries=active&&active.maps||{},names=Array.isArray(entries)?entries:Object.keys(entries);
        return names.filter(m=>m_localInstalled.includes(m)&&GetMGDetails('mg_'+m)).slice(0,7);
    }
    function _LocalMapName(map) {
        const group=GetMGDetails('mg_'+map);return group?$.Localize(group.nameID):map;
    }
    function _LocalStartSelected(map,team) {
        if(m_localStarting||!m_localInstalled.includes(map)||PartyListAPI.GetCount()>1||!LobbyAPI.BIsHost())return;
        m_localStarting=true;m_localVetoMap=map;
        const settings={update:{Options:{action:'custommatch',server:'listen',practicesettings_grenades:0,practicesettings_infammo:0,practicesettings_infwarmup:0,practicesettings_annotations:0},
            Game:{mode:'competitive',mode_ui:'premier',type:GetGameType('competitive'),mapgroupname:'mg_'+map,map:map,gamemodeflags:16,prime:0}},delete:{Options:{challengekey:1}}};
        LobbyAPI.StopMatchmaking();let attempts=0;
        function ready() {
            const s=LobbyAPI.GetSessionSettings();
            if(s&&s.options&&s.game&&s.options.server==='listen'&&s.options.action==='custommatch'&&s.game.mode==='competitive'&&s.game.map===map&&s.game.mapgroupname==='mg_'+map&&Number(s.game.gamemodeflags)===16) {
                if(m_localVeto){m_localVeto.DeleteAsync(0);m_localVeto=null;}
                LobbyAPI.StartMatchmaking('','','','');m_localStarting=false;
                let waits=0;
                function join() {if(GameStateAPI.GetMapBSPName()===map){GameInterfaceAPI.ConsoleCommand('jointeam '+team);return;}if(++waits<180)$.Schedule(1,join);}
                $.Schedule(1,join);return;
            }
            if(++attempts>30){m_localStarting=false;UiToolkitAPI.ShowGenericPopupOk('Local Premier','The local session did not become ready. Cancel and try again.','',()=>{});return;}
            if(!LobbyAPI.IsSessionActive())LobbyAPI.CreateSession();
            if(LobbyAPI.BIsHost())LobbyAPI.UpdateSessionSettings(settings);$.Schedule(.1,ready);
        }
        ready();
    }
    function _LocalOpenVeto() {
        $.Msg('[CS2GC Premier] opening local veto');
        if(m_localVeto||m_localStarting)return;
        const maps=_LocalPremierPool();
        if(maps.length!==7){UiToolkitAPI.ShowGenericPopupOk('Local Premier','Seven installed Active Duty maps are required for this local veto.','',()=>{});return;}
        if(PartyListAPI.GetCount()>1){UiToolkitAPI.ShowGenericPopupOk('Local Premier','Leave your party before starting a local bot match.','',()=>{});return;}
        const root=$.CreatePanel('Panel',$.GetContextPanel(),'LocalPremierVeto');m_localVeto=root;
        root.style.ignoreParentFlow=true;root.style.position='0px 0px 0px';
        root.style.width='100%';root.style.height='100%';root.style.backgroundColor='#0c1219fa';root.style.zIndex='1000';
        if(!root.BLoadLayout('file://{resources}/layout/popups/popup_premier_pick_ban.xml',false,false))
            throw Error('The installed Premier layout could not be loaded.');
        root.AddClass('show');
        const find=id=>root.FindChildInLayoutFile(id);
        const middle=find('id-team-vote-middle');
        if(!middle||!find('id-map-vote-btn-6'))throw Error('The installed Premier layout contract changed.');
        // The native layout is shared; only this local panel is driven by our draft.
        const graph=find('id-team-vote-spider-graph');
        if(graph){graph.SetPanelEvent('oncanvaslayout',()=>{});graph.visible=false;}
        const chat=find('PartyChat');if(chat)chat.visible=false;
        const status=find('id-team-vote-title-phase');
        const history=$.CreatePanel('Label',root,'LocalVetoHistory');
        history.AddClass('stratum-regular-condensed');history.style.horizontalAlign='center';
        history.style.verticalAlign='bottom';history.style.marginBottom='80px';history.style.fontSize='16px';
        history.style.color='#aab8c1';
        const actions=$.CreatePanel('Panel',root,'LocalVetoActions');actions.style.flowChildren='right';
        actions.style.horizontalAlign='center';actions.style.verticalAlign='bottom';actions.style.marginBottom='24px';
        function button(parent,id,value,fn){const p=$.CreatePanel('Button',parent,id);p.AddClass('PopupButton');
            const label=$.CreatePanel('Label',p,'');label.AddClass('stratum-medium-condensed');label.text=value;
            p.SetPanelEvent('onactivate',fn);return p;}
        function renderPhase(phase,human) {
            root.SwitchClass('pick-ban-phase','premier-pickban-phase-'+phase);
            root.SetHasClass('your-turn',human);
            middle.SwitchClass('bg-fade',human?'premier-pickban__middle--light':'premier-pickban__middle--dark');
            find('id-team-vote-title-spinner').SetHasClass('hide',human);
            const labels=['OPENING BANS','OPPOSING BANS','FINAL BAN','DECIDER','STARTING SIDE','READY'];
            for(let i=2;i<=7;i++) {
                const bar=find('id-team-vote-phasebar-'+i);
                bar.SetDialogVariable('section-label',labels[i-2]);bar.SetDialogVariable('section-time','');
                bar.SetHasClass('premier-pickban__progress--ban',i===phase&&phase<5);
                bar.SetHasClass('premier-pickban__progress--pick',i===phase&&phase>=5);
                bar.SetHasClass('premier-pickban__progress--pre',i>phase);
                bar.SetHasClass('premier-pickban__progress--post',i<phase);
                bar.FindChildInLayoutFile('id-team-phase-bar-inner').style.width=i<phase?'100%':'0%';
            }
        }
        const humanFirst=Math.random()<.5,turns=[humanFirst,humanFirst,!humanFirst,!humanFirst,!humanFirst,humanFirst];
        const banned=[],buttons={};let step=0,ended=false,side=2;
        function advance(map) {
            if(ended||banned.includes(map))return;
            banned.push(map);buttons[map].enabled=false;buttons[map].checked=false;
            buttons[map].SetHasClass('premier-pickban-veto',true);
            buttons[map].SetDialogVariable('btm-line',turns[step]?'YOUR BAN':'OPPOSING BAN');
            $.DispatchEvent('CSGOPlaySoundEffect','UI.Premier.MapSelect','MOUSE');
            history.text+=(step?'   ·   ':'')+(turns[step]?'YOU: ':'BOTS: ')+_LocalMapName(map);step++;show();
        }
        function show() {
            const remaining=maps.filter(m=>!banned.includes(m));
            if(step===6) {
                ended=true;renderPhase(6,!humanFirst);status.text='DECIDER: '+_LocalMapName(remaining[0]);
                maps.forEach((m,i)=>{const chosen=m===remaining[0],parent=find('id-map-vote-btn-'+i);
                    parent.SetHasClass('premier-pickban__map-btn--picked',chosen);parent.SetHasClass('not-picked',!chosen);
                    buttons[m].SetHasClass('premier-pickban-pick',chosen);buttons[m].enabled=false;
                    find('id-map-vote-btn-ref-'+i).visible=false;});
                find('id-pick-vote-team').AddClass('show');
                find('id-team-vote-map-icon').SetImage('file://{images}/map_icons/map_icon_'+remaining[0]+'.svg');
                find('id-team-vote-map-icon').AddClass('show');
                find('id-team-vote-map-image').style.backgroundImage='url("file://{images}/map_icons/screenshots/360p/'+remaining[0]+'.png")';
                if(!humanFirst) {
                    status.text+=' · CHOOSE YOUR STARTING SIDE';
                    [3,2].forEach((team,i)=>{const btn=find('id-team-vote-btn-'+i).FindChild('id-pickban-btn');
                        btn.enabled=true;btn.SetPanelEvent('onactivate',()=>_LocalStartSelected(remaining[0],team));});
                } else {
                    side=Math.random()<.5?2:3;renderPhase(7,true);
                    status.text+=' · YOU START '+(side===2?'T':'CT');
                    [3,2].forEach((team,i)=>find('id-team-vote-btn-'+i).FindChild('id-pickban-btn').SetHasClass('premier-pickban-pick',side===team));
                    button(actions,'LocalVetoStart','START MATCH',()=>_LocalStartSelected(remaining[0],side));
                }
                return;
            }
            const human=turns[step];renderPhase(step<2?2:step<5?3:4,human);status.text=(human?'YOUR BAN':'OPPOSING CAPTAIN IS BANNING')+' · '+(6-step)+' bans remaining';
            maps.forEach(m=>buttons[m].enabled=human&&!banned.includes(m));
            if(!human)$.Schedule(.65,()=>{if(root.IsValid()&&m_localVeto===root)advance(remaining[Math.floor(Math.random()*remaining.length)]);});
        }
        maps.forEach((map,i)=>{
            const parent=find('id-map-vote-btn-'+i),p=parent.FindChild('id-pickban-btn');
            p.SetDialogVariable('map-name',_LocalMapName(map));p.SetDialogVariable('btm-line','');p.SetDialogVariable('status','');
            p.FindChildInLayoutFile('id-pickban-map-btn-bg').style.backgroundImage='url("file://{images}/map_icons/screenshots/360p/'+map+'.png")';
            p.SetPanelEvent('onactivate',()=>{p.checked=false;if(!ended&&turns[step]&&!banned.includes(map))advance(map);});buttons[map]=p;
            find('id-map-vote-btn-ref-'+i).SetImageFromPanel(parent,false);
        });
        [3,2].forEach((team,i)=>{
            const parent=find('id-team-vote-btn-'+i),p=parent.FindChild('id-pickban-btn'),name=team===3?'ct':'t';
            p.enabled=false;p.SetDialogVariable('map-name',team===3?'COUNTER-TERRORISTS':'TERRORISTS');
            p.SetDialogVariable('btm-line','');p.SetDialogVariable('status','');
            const image=InventoryAPI.GetItemInventoryImage(LoadoutAPI.GetItemID(name,'customplayer'));
            p.FindChildInLayoutFile('id-pickban-map-btn-bg').style.backgroundImage='url("file://{images}'+image+'.png")';
            find('id-team-vote-btn-ref-'+i).SetImageFromPanel(parent,false);
        });
        button(actions,'LocalVetoCancel','CANCEL',()=>{if(m_localStarting)return;root.DeleteAsync(0);m_localVeto=null;m_localVetoMap='';});show();
    }
'''

def patch(source,maps):
    anchors=[('    function StartSearch() {', '''    function StartSearch() {
        $.Msg('[CS2GC Premier] GO server='+m_serverSetting+' mode='+m_gameModeSetting+' workshop='+m_isWorkshop);
        if (m_serverSetting === "listen" && m_gameModeSetting === "premier" && !m_isWorkshop) {
            try { _LocalOpenVeto(); }
            catch(error) {
                if(m_localVeto){m_localVeto.DeleteAsync(0);m_localVeto=null;}
                $.Msg('[CS2GC Premier] veto failed: '+String(error));
                UiToolkitAPI.ShowGenericPopupOk('Local Premier','Could not open the local veto: '+String(error),'',()=>{});
            }
            return;
        }'''),
        ('    function _IsGameModeAvailable(serverType, gameMode) {','    function _IsGameModeAvailable(serverType, gameMode) {\n        if (serverType === "listen" && gameMode === "premier") { _SetGameModeRadioButtonVisible(gameMode,true); _SetGameModeRadioButtonAvailableTooltip(gameMode,true,""); return true; }'),
        ('    function _GetAvailableMapGroups(gameMode, isPlayingOnValveOfficial) {','    function _GetAvailableMapGroups(gameMode, isPlayingOnValveOfficial) {\n        if (gameMode === "premier" && !isPlayingOnValveOfficial) return _LocalPremierPool().map(m=>"mg_"+m);'),
        ("            return Object.keys(mapgroup);", "            const groups=Object.keys(mapgroup);\n            if (gameMode === 'competitive' && !isPlayingOnValveOfficial) m_localInstalled.filter(m=>m.indexOf('_night')>=0).forEach(m=>{const g='mg_'+m;if(GetMGDetails(g)&&!groups.includes(g))groups.push(g);});\n            return groups;"),
        ("            selectedMaps = 'mg_lobby_mapveto';\n            primePreference = 1;", "            selectedMaps = m_serverSetting === 'listen' ? 'mg_'+(m_localVetoMap||_LocalPremierPool()[0]||'de_ancient') : 'mg_lobby_mapveto';\n            if(m_serverSetting === 'listen')gameModeFlags=16;\n            primePreference = m_serverSetting === 'listen' ? 0 : 1;"),
        ("        LobbyAPI.UpdateSessionSettings(settings);\n    }\n    function _SessionSettingsUpdate", "        if(m_serverSetting === 'listen' && m_gameModeSetting === 'premier')settings.update.Game.map=m_localVetoMap||'';\n        LobbyAPI.UpdateSessionSettings(settings);\n    }\n    function _SessionSettingsUpdate")]
    for old,new in anchors:
        if source.count(old)!=1:raise ValueError('Installed local-play contract changed: '+old[:65])
        source=source.replace(old,new,1)
    marker='    function StartSearch() {'
    return source.replace(marker,SCRIPT.replace('__MAPS__',json.dumps(maps))+marker,1)

def prepare(directory,config):
    game=Path(directory).resolve().parents[1]
    maps=sorted(p.stem for p in (game/'csgo/maps').glob('de_*.vpk') if re.fullmatch(r'de_[a-z0-9_]+',p.stem) and not p.stem.endswith('_vanity'))
    return install_override(directory,enabled=True,folder='cs2_gc_local_play',comment='cs2_gc local premier and night maps',owner='cs2-gc-local-play-v1',
        asset='panorama/scripts/mainmenu_play.vts_c',patch=lambda source:patch(source,maps))

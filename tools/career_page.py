"""Authored Panorama career view; installed CS2 vectors and native typography."""
import json
from career_achievements import progress
from career_browser import SCRIPT as BROWSER
from career_extras import SCRIPT as EXTRAS

SCRIPT=r'''"use strict";
var NewsPanel;
(function(NewsPanel) {
    const saved=__SNAPSHOT__,fields={},tabs=[],filters=[];
    let refresh=null,overview=null,achievementPane=null,companionPane=null,settingsPane=null;
    const icons={star:'ui/icon_star',kill:'equipment/ak47',headshot:'ui/kill_headshot',bomb:'equipment/c4',
        defuse:'equipment/defuser',flash:'equipment/flashbang',smoke:'equipment/smokegrenade',grenade:'equipment/hegrenade',
        molotov:'equipment/molotov',knife:'equipment/knife',taser:'equipment/taser',pistol:'equipment/glock',
        rifle:'equipment/ak47',sniper:'equipment/awp',smg:'equipment/p90',shotgun:'equipment/nova',heavy:'equipment/m249'};
    function panel(parent,id,flow) {const p=$.CreatePanel('Panel',parent,id);if(flow)p.style.flowChildren=flow;return p;}
    function label(parent,id,text,size,color) {
        const p=$.CreatePanel('Label',parent,id);p.text=text;p.style.fontSize=size+'px';p.style.color=color||'#e1e4e7';return p;
    }
    function hint(p,text) {
        p.SetPanelEvent('onmouseover',()=>UiToolkitAPI.ShowTextTooltip(p.id,text));
        p.SetPanelEvent('onmouseout',()=>UiToolkitAPI.HideTextTooltip());
    }
    function metric(parent,key,title,description) {
        const p=panel(parent,'LocalStat_'+key,'down');p.style.width='24%';p.style.marginRight='1%';
        p.style.padding='10px 14px';p.style.height='72px';p.style.backgroundColor='#ffffff05';p.style.borderLeft='2px solid #ffffff18';
        label(p,'',title,12,'#9aa5ae').AddClass('stratum-regular-condensed');fields[key]=label(p,'','—',27);hint(p,description||title);
    }
    function row(parent,id) {const p=panel(parent,id,'right');p.style.width='100%';p.style.marginTop='8px';return p;}
    function heading(parent,text) {const p=label(parent,'',text,18,'#cdd4da');p.AddClass('stratum-regular-condensed');p.style.marginTop='18px';}
    function button(parent,id,text,onactivate) {
        const p=$.CreatePanel('Button',parent,id);p.style.padding='8px 16px';p.style.marginRight='8px';
        const caption=label(p,'',text,16,'#a7b1b9');caption.AddClass('stratum-regular-condensed');
        p.SetPanelEvent('onactivate',onactivate);return {panel:p,caption};
    }
    function selectTab(name) {
        overview.visible=name==='overview';achievementPane.visible=name==='achievements';
        if(companionPane)companionPane.visible=name==='companions';
        if(settingsPane)settingsPane.visible=name==='settings';
        tabs.forEach(t=>{t.p.caption.style.color=t.key===name?'#e9f1f6':'#89959e';t.p.panel.style.borderBottom=t.key===name?'2px solid #72b5d8':'2px solid #ffffff00';});
    }
__BROWSER__
__EXTRAS__
    function build() {
        const root=$.GetContextPanel().FindChildInLayoutFile('NewsPanelLister');if(!root)return;
        root.RemoveAndDeleteChildren();root.RemoveClass('history');
        root.style.flowChildren='right';root.style.width='92%';root.style.maxWidth='1680px';root.style.height='800px';root.style.horizontalAlign='center';
        root.style.marginTop='20px';root.style.padding='0px';root.style.backgroundColor='#ffffff00';root.style.overflow='squish squish';
        const host=panel(root,'CareerMain','down');host.style.width='69%';host.style.height='100%';host.style.padding='22px 28px';host.style.backgroundColor='#171e25f2';
        const header=row(host,'CareerHeader');header.style.marginTop='0px';
        label(header,'','STATS & ACHIEVEMENTS',27).AddClass('stratum-regular-condensed');
        const summary=label(header,'AchievementSummary','',14,'#bdc9d2');summary.style.marginLeft='24px';summary.style.verticalAlign='center';
        const nav=row(host,'CareerTabs');nav.style.borderBottom='1px solid #ffffff16';
        tabs.push({key:'overview',p:button(nav,'CareerOverviewTab','OVERVIEW',()=>selectTab('overview'))});
        tabs.push({key:'achievements',p:button(nav,'CareerAchievementsTab','ACHIEVEMENTS',()=>selectTab('achievements'))});
        tabs.push({key:'companions',p:button(nav,'CareerCompanionsTab','COMPANIONS',()=>selectTab('companions'))});
        tabs.push({key:'settings',p:button(nav,'CareerSettingsTab','SETTINGS',()=>selectTab('settings'))});
        overview=panel(host,'CareerOverviewPane','down');overview.style.width='100%';
        heading(overview,'PROFILE');let r=row(overview,'LocalOverview');
        metric(r,'level','PROFILE LEVEL');metric(r,'rating','PREMIER RATING');metric(r,'wins','PREMIER WINS');metric(r,'xp','CURRENT LEVEL XP');
        heading(overview,'COMBAT & OBJECTIVES');r=row(overview,'LocalSaved');
        metric(r,'matches','MATCHES COMPLETED');metric(r,'kills','KILLS');metric(r,'headshots','HEADSHOTS');metric(r,'mvps','MVPS');
        r=row(overview,'LocalObjectives');metric(r,'plants','BOMB PLANTS');metric(r,'defuses','BOMB DEFUSES');metric(r,'missions','MISSIONS COMPLETED');
        metric(r,'achievement_stars','ACHIEVEMENT STARS','One-time rewards paid for career achievements. These do not advance gameplay-star milestones.');
        heading(overview,'UTILITY & SPECIAL KILLS');r=row(overview,'LocalUtility');
        metric(r,'enemies_flashed','ENEMIES FLASHED','Enemy blinded for at least one second by your flash. Each enemy counts once per flash.');
        metric(r,'flash_assists','FLASH ASSISTS','A teammate kills an enemy you flashed and the server records a flash assist.');
        metric(r,'smoke_kills','SMOKE KILLS','Enemy kills where the server confirms your bullet went through smoke.');
        metric(r,'blind_kills','KILLS WHILE BLINDED','Enemy kills where the server confirms YOU were blinded by a flashbang.');
        r=row(overview,'LocalSpecial');metric(r,'noscope_kills','NO-SCOPES');metric(r,'wallbang_kills','WALLBANGS');metric(r,'grenade_kills','HE KILLS');metric(r,'fire_kills','FIRE KILLS');
        label(overview,'','Career totals refresh on launch. New utility counters start with this update.',12,'#8c99a4').style.marginTop='16px';
        achievementPane=panel(host,'CareerAchievementsPane','down');achievementPane.style.width='100%';
        const categories=row(achievementPane,'CareerCategories');
        ['All','Combat','Utility','Weapons','Objectives','Career'].forEach(category=>filters.push({key:category,p:button(categories,'CareerCategory'+category,category.toUpperCase(),()=>selectFilter(category))}));
        label(achievementPane,'','One-time rewards are credited automatically. Hover for the exact conditions.',12,'#8c99a4').style.marginTop='8px';
        buildBrowser(achievementPane);
        buildClosest(overview);buildUnboxing(root);buildCompanions(host);buildLocalSettings(host);
        selectTab('overview');selectFilter('All');update();
    }
    function update() {
        const xuid=MyPersonaAPI.GetXuid();
        const values={level:Math.max(0,Number(MyPersonaAPI.GetCurrentLevel())||0),rating:Math.max(0,Number(FriendsListAPI.GetFriendCompetitiveRank(xuid,'Premier'))||0),
            wins:Math.max(0,Number(FriendsListAPI.GetFriendCompetitiveWins(xuid,'Premier'))||0),
            xp:typeof MyPersonaAPI.GetCurrentXp==='function'?Math.max(0,Number(MyPersonaAPI.GetCurrentXp())||0):'—',
            matches:saved.matches,missions:saved.missions_completed,achievement_stars:saved.achievement_stars};
        Object.keys(saved.combat).forEach(key=>values[key]=saved.combat_available?saved.combat[key]:'—');
        Object.keys(fields).forEach(key=>fields[key].text=String(values[key]===undefined?'—':values[key]));
        const completed=updateBrowser(values);
        updateClosest();
        const header=$.GetContextPanel().FindChildInLayoutFile('AchievementSummary');
        if(header)header.text=completed+' / '+saved.achievements.length+' completed   ·   '+saved.achievement_stars+' ★ earned';
        if(refresh===null)refresh=$.Schedule(2,()=>{refresh=null;update();});
    }
    build();
})(NewsPanel || (NewsPanel = {}));
'''

def patch(source,data):
    if source.count('var NewsPanel;')!=1 or 'BlogAPI.RequestRSSFeed();' not in source:
        raise ValueError('Installed News page script changed; no patch written')
    data=dict(data);data.setdefault('unlocked',[]);data.setdefault('achievement_stars',0);data.setdefault('recent_unlocks',[])
    if 'achievements' not in data:
        data['achievements']=progress(dict(matches=data.get('matches',0),combat_stats=data.get('combat',{}),
            missions_completed=data.get('missions_completed',0),local_achievements=data['unlocked']))
    return SCRIPT.replace('__BROWSER__',BROWSER).replace('__EXTRAS__',EXTRAS).replace('__SNAPSHOT__',json.dumps(data,separators=(',',':'),ensure_ascii=True))

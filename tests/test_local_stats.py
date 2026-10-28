import json,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from gsi_rewards import Rewards
from local_stats import snapshot,achievements
from native_stats import patch

class Stats(unittest.TestCase):
    def test_unlocked_achievements_survive_rating_falling(self):
        state={'premier':{'rating':21000,'wins':10}}
        state['local_achievements']=achievements(state)
        state['premier']['rating']=9000
        self.assertIn('rating:20000',achievements(state))
        self.assertNotIn('kills:100',achievements(state))
    def test_combat_totals_use_only_new_local_live_deltas_and_survive_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            r=Rewards(folder)
            p={'auth':{'token':r.state['token']},'provider':{'appid':730,'steamid':'local','timestamp':1},
               'map':{'name':'de_test','mode':'competitive','phase':'live','round':1},
               'player':{'steamid':'local','team':'T','activity':'playing','match_stats':{'kills':10,'mvps':1},'state':{'round_killhs':0}}}
            r.accept(p)
            self.assertFalse(snapshot(folder)['combat_available'],'existing scoreboard is a baseline')
            p['provider']['timestamp']=2;p['player']['match_stats']['kills']=12;p['player']['state']['round_killhs']=1
            r.accept(p);r.accept(p)
            self.assertEqual(snapshot(folder)['combat']['kills'],2)
            self.assertEqual(snapshot(folder)['combat']['headshots'],1)
            p['player']['steamid']='bot';p['player']['match_stats']['kills']=100
            r.accept(p)
            self.assertEqual(snapshot(folder)['combat']['kills'],2)
            r=Rewards(folder)
            self.assertEqual(snapshot(folder)['combat']['kills'],2)
            self.assertNotIn('token',json.dumps(snapshot(folder)))
            self.assertNotIn('local_player',json.dumps(snapshot(folder)))
            self.assertNotIn(r.state['token'],json.dumps(snapshot(folder)))

    @unittest.skipUnless(shutil.which('node'),'Node required')
    def test_native_page_renders_real_values_and_unearned_achievements_stay_locked(self):
        setup='''const assert=require('assert');const panels={};let timers=0;
function panel(id){return {id,style:{},text:'',events:{},SetPanelEvent(k,v){this.events[k]=v;},AddClass(){},SetImage(){},RemoveAndDeleteChildren(){},RemoveClass(){},FindChildInLayoutFile(name){return panels[name];}};}
panels.NewsPanelLister=panel('NewsPanelLister');
const $={GetContextPanel:()=>panel('root'),CreatePanel:(type,parent,id)=>{const p=panel(id);if(id)panels[id]=p;return p;},Schedule:()=>++timers};
const MyPersonaAPI={GetXuid:()=> 'self',GetCurrentLevel:()=>7,GetCurrentXp:()=>1200};
const FriendsListAPI={GetFriendCompetitiveRank:()=>15000,GetFriendCompetitiveWins:()=>12};
const commands=[];const GameInterfaceAPI={GetSettingString:()=>'',ConsoleCommand:cmd=>commands.push(cmd)};
let tooltip='';const UiToolkitAPI={ShowTextTooltip:(id,text)=>tooltip=text,HideTextTooltip:()=>tooltip=''};
'''
        data=dict(matches=3,xp=100,bonus_stars=50,missions_completed=0,combat_available=True,
                  combat=dict(kills=4,headshots=2,mvps=1,plants=0,defuses=0))
        code=patch('var NewsPanel; BlogAPI.RequestRSSFeed();',data)
        checks="""assert.equal(timers,1);
assert(panels.CareerGroupStatus_matches.text.includes('1 / 3 tiers completed'));
assert(panels.CareerGroupStatus_kills.text.includes('4 / 100'));
assert(panels.CareerGroupStatus_rating.text.startsWith('1 / 2'));
assert.equal(Object.keys(panels).filter(k=>k.startsWith('CareerGroup_')).length,27);
assert.equal(panels.LocalAchievements.style.flowChildren,'down');
assert.equal(panels.CareerBrowser.style.flowChildren,'right');
panels.CareerGroup_kills.events.onmouseover();assert(tooltip.includes('100'));assert(tooltip.includes('10 stars'));
panels.CareerGroup_kills.events.onactivate();assert.equal(panels.CareerDetailTitle.text,'Kills');
assert.equal(panels.CareerDetailProgress.text,'4 / 100');assert.equal(panels.CareerDetailReward.text,'+10 ★');
panels.CareerTier_kills_2.events.onactivate();assert.equal(panels.CareerDetailProgress.text,'4 / 2500');
assert.equal(panels.CareerDetailReward.text,'+50 ★');
panels.CareerAchievementsTab.events.onactivate();assert.equal(panels.CareerOverviewPane.visible,false);
panels.CareerCategoryUtility.events.onactivate();assert.equal(panels.CareerGroup_kills.visible,false);
assert.equal(panels.CareerDetailTitle.text,'Enemies flashed');
assert(panels.CareerDetailDescription.text.includes('at least 1 second'));
assert.equal(panels.CareerRecentHeading.text,'UNLOCKED ACHIEVEMENTS');
panels.CareerRecent0.events.onactivate();assert.equal(panels.CareerGroup_matches.visible,true);
assert.equal(panels.CareerDetailTier.text,'TIER I · First finish');
assert(panels.CareerDetailStatus.text.includes('REWARD PENDING'));
panels.CareerSettingsTab.events.onactivate();assert.equal(panels.CareerSettingsPane.visible,true);
panels.Viewmodel_viewmodel_fov.text='60; quit';panels.ViewmodelApply.events.onactivate();assert.equal(commands.length,0);
panels.ViewmodelReset.events.onactivate();panels.ViewmodelApply.events.onactivate();
assert.equal(commands.length,5);assert(commands.includes('viewmodel_fov 60'));assert(commands.includes('viewmodel_presetpos 0'));
"""
        with tempfile.TemporaryDirectory() as folder:
            script=Path(folder)/'career-ui.js';script.write_text(setup+code+checks,encoding='utf-8')
            result=subprocess.run(['node',str(script)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        with self.assertRaises(ValueError):patch('different client',data)

if __name__=='__main__':unittest.main()

import shutil,subprocess,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from native_mission_launch import patch_progress

SOURCE='''    function Init(srcText) {
        let missionData = undefined;
        if (IsThePauseMenuPanel()) missionData = MissionsAPI.GetRecurringMission(false);
        $.GetContextPanel().Data().m_oMissionData = missionData;
        if (IsTheInGamePanel()) {
            if (!GameStateAPI.GetActiveQuestID()) {
                $.GetContextPanel().AddClass('hidden'); return;
            }
        }
        $.GetContextPanel().RemoveClass('hidden');
        UpdateProgressBar(missionData);
    }
'''

class MissionProgress(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'),'Node required')
    def test_local_hud_shows_live_account_progress_with_no_server_quest_and_no_double_count(self):
        setup='''const assert=require('assert');let saved=7,shown=-1,hidden=true,timers=[];const data={};
const panel={Data:()=>data,AddClass:()=>hidden=true,RemoveClass:()=>hidden=false};
const $={GetContextPanel:()=>panel,Schedule:(t,fn)=>{timers.push(fn);return timers.length;}};
const MissionsAPI={GetRecurringMission:live=>({progress_saved:live?saved:0,progress_this_match:8,map:'de_cache'})};
const GameTypesAPI={GetConfig:()=>({mapgroups:{}})};const GameStateAPI={GetActiveQuestID:()=>0,GetMapBSPName:()=> 'de_cache'};
function IsThePauseMenuPanel(){return false;}function IsTheInGamePanel(){return true;}
function UpdateProgressBar(m){shown=m.progress_saved+m.progress_this_match;}
'''
        check="Init('test');assert.equal(shown,7);assert.equal(hidden,false);assert.equal(timers.length,1);Init('event');assert.equal(timers.length,1);saved=8;timers.shift()();assert.equal(shown,8);assert.equal(timers.length,1);"
        result=subprocess.run(['node','-e',setup+patch_progress(SOURCE)+check],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_unknown_or_already_patched_layout_fails_closed(self):
        for source in ('changed',patch_progress(SOURCE)):
            with self.assertRaises(ValueError):patch_progress(source)

    @unittest.skipUnless(shutil.which('node'),'Node required')
    def test_main_menu_keeps_local_card_through_offline_status_and_schema_refresh_gap(self):
        source=SOURCE.replace('        let missionData = undefined;',
            '        if (MyPersonaAPI.GetElevatedState() != "elevated")\n            return;\n        let missionData = undefined;')
        source=source.replace('        if (IsTheInGamePanel()) {',
            '''        if (!missionData) { $.GetContextPanel().AddClass('hidden'); return; }
            if (!MyPersonaAPI.IsConnectedToGC()) {
                $.GetContextPanel().AddClass('hidden');
                return;
            }
        if (IsTheInGamePanel()) {''')
        setup='''const assert=require('assert');let present=true,now=1000,shown=0,hidden=true;
Date.now=()=>now;const data={};const panel={Data:()=>data,AddClass:()=>hidden=true,RemoveClass:()=>hidden=false};
const $={GetContextPanel:()=>panel,Schedule:()=>1};
const MyPersonaAPI={GetElevatedState:()=> 'none',IsConnectedToGC:()=>false};
const MissionsAPI={GetRecurringMission:()=>present?{progress_saved:4,progress_this_match:0}:null};
function IsTheInGamePanel(){return false;}function IsThePauseMenuPanel(){return false;}
function UpdateProgressBar(m){shown=m.progress_saved;}
'''
        checks="Init('first');assert.equal(shown,4);assert(!hidden);present=false;now+=2000;Init('refresh');assert(!hidden);assert.equal(shown,4);now+=16000;Init('expired');assert(hidden);present=true;Init('restored');assert(!hidden);"
        result=subprocess.run(['node','-e',setup+patch_progress(source)+checks],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()

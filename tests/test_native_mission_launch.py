import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import native_mission_launch as mission

@unittest.skipUnless(shutil.which('node'),'Node required')
class MissionLaunch(unittest.TestCase):
    def test_listen_session_and_matching_map_mode_without_official_search(self):
        script='''const assert=require('assert');let data={gamemode:'deathmatch',mapgroup:'delta'},settings,starts=0,difficulty;
const $={GetContextPanel:()=>({Data:()=>({m_oMissionData:data})}),DispatchEvent:()=>{}};
const GameTypesAPI={GetConfig:()=>({gameTypes:{gungame:{gameModes:{deathmatch:{}}},classic:{gameModes:{competitive:{}}}},mapgroups:{delta:{maps:{de_mirage:1,de_dust2:1}}}}),SetCustomBotDifficulty:v=>difficulty=v};
const GameInterfaceAPI={GetSettingString:()=>'-1'};
const LobbyAPI={StopMatchmaking:()=>{},CreateSession:()=>{},BIsHost:()=>true,UpdateSessionSettings:v=>settings=v,StartMatchmaking:()=>starts++};
let alerts=0;const UiToolkitAPI={ShowGenericPopupOk:()=>alerts++};function IsSearching(){return false;}
'''+mission.REPLACEMENT+'''
PlayMission();assert.equal(starts,1);assert.equal(settings.update.Options.server,'listen');
assert.equal(settings.update.Game.mode,'deathmatch');assert.equal(settings.update.Game.type,'gungame');
assert.ok(['de_mirage','de_dust2'].includes(settings.update.Game.map));
assert.equal(settings.update.Game.mapgroupname,'mg_'+settings.update.Game.map);
assert.equal(settings.update.Game.gamemodeflags,32);assert.equal(difficulty,2);
assert.equal(settings.update.Options.practicesettings_infwarmup,0);
data={gamemode:'competitive',map:'de_inferno'};PlayMission();assert.equal(starts,2);
assert.equal(settings.update.Game.map,'de_inferno');assert.equal(settings.update.Game.gamemodeflags,16);
data={gamemode:'deathmatch',mapgroup:'missing'};PlayMission();assert.equal(starts,2);assert.equal(alerts,1);
data={gamemode:'unsupported',map:'de_mirage'};PlayMission();assert.equal(starts,2);assert.equal(alerts,2);
'''
        r=subprocess.run(['node','-e',script],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)

    def test_source_contract_fail_closed(self):
        source='before\n'+mission.START+'\nserver: "official"\n'+"LobbyAPI.StartMatchmaking('', '', '', '');\n}\n"+mission.END+'\nafter'
        patched=mission.patch(source)
        self.assertNotIn('server: "official"',patched)
        self.assertTrue(patched.endswith('after'))
        for invalid in ['changed',source.replace('official','other'),patched]:
            with self.assertRaises(ValueError):mission.patch(invalid)

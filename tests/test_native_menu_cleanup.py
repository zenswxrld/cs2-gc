import sys
from pathlib import Path
import unittest
import subprocess
import shutil
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import native_mainmenu
import native_scoreboard

@unittest.skipUnless(shutil.which('node'),'Node required')
class MenuCleanup(unittest.TestCase):
    def run_js(self,source):
        result=subprocess.run(['node','-e',source],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_promotion_is_hidden_but_mission_is_untouched(self):
        source="var MainMenu={}; function outer(){\n    function _OnShowMainMenu() {}\nMainMenu.show=_OnShowMainMenu;} outer();"
        script="""const assert=require('assert');let mission={visible:true},promo={visible:true,style:{}};
const left={FindChildTraverse:id=>id==='id-mainmenu-rush-tile-panel'?promo:mission};
const $={GetContextPanel:()=>({FindChildInLayoutFile:id=>left})};
"""+native_mainmenu.patch(source)+"""
MainMenu.show();assert.equal(promo.visible,false);assert.equal(promo.style.visibility,'collapse');assert.equal(mission.visible,true);
"""
        self.run_js(script)

    def test_bot_name_without_engine_prefix_and_human_restoration(self):
        script="""const assert=require('assert');let fake=true,name='[BOT] player<&>';
const stock={visible:true};let clean;
const elPanel={FindChildTraverse:id=>id==='name'?stock:clean};
const oPlayer={m_xuid:'bot',m_elPlayer:{SetDialogVariableInt:()=>{}},GetGameStat:key=>fake};
const GameStateAPI={IsDemoOrHltv:()=>false,IsQueuedMatchmakingMode_Team:()=>false};
const MockAdapter={GetPlayerName:()=>name};
const $={CreatePanel:(kind,parent,id,props)=>{assert.equal(props.html,false);clean={};return clean;}};
function draw(){
"""+native_scoreboard.NAME_ANCHOR+native_scoreboard.NAME_INJECT+"""}
draw();assert.equal(stock.visible,false);assert.equal(clean.text,'player<&>');
fake=false;draw();assert.equal(stock.visible,true);assert.equal(clean.visible,false);
"""
        self.run_js(script)

    def test_changed_mainmenu_fails_closed(self):
        with self.assertRaises(ValueError):native_mainmenu.patch('changed')

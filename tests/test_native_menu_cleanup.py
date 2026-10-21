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
const data={}; const stock={visible:true,Data:()=>data,text:'{g:player_name:player_slot}'};let clean;
const elPanel={FindChildTraverse:id=>id==='name'?stock:clean};
const oPlayer={m_xuid:'bot',m_elPlayer:{SetDialogVariableInt:()=>{}},GetGameStat:key=>fake};
const GameStateAPI={IsDemoOrHltv:()=>false,IsQueuedMatchmakingMode_Team:()=>false};
const MockAdapter={GetPlayerName:()=>name};
const $={HTMLEscape:value=>value.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')};
function draw(){
"""+native_scoreboard.NAME_ANCHOR+native_scoreboard.NAME_INJECT+"""}
draw();assert.equal(stock.visible,true);assert.equal(stock.text,'player&lt;&amp;&gt;');
name='';draw();assert.equal(stock.text,'{g:player_name:player_slot}');
name='<span class="decorated-player-name">BOT Other &amp; &#x3c;3</span>';draw();assert.equal(stock.text,'Other &amp; &lt;3');
fake=false;draw();assert.equal(stock.visible,true);assert.equal(stock.text,'{g:player_name:player_slot}');
"""
        self.run_js(script)

    def test_rewards_only_open_in_inventory_after_map_unloads(self):
        source="""    function _OnShowMainMenu() {}
function check(){
        if (GameStateAPI.IsLocalPlayerPlayingMatch()) return;
        if (!$('#MainMenuNavBarHome').checked)
            return;
        const objStore = InventoryAPI.GetCacheTypeElementJSOByIndex("PersonalStore", 0);
        opened++;
}
"""
        script="""const assert=require('assert');let opened=0,inventory=false,map='de_mirage',playing=false;
const $=id=>({checked:id==='#MainMenuNavBarHome'?!inventory:inventory});
const GameStateAPI={IsLocalPlayerPlayingMatch:()=>playing,GetMapBSPName:()=>map};
const InventoryAPI={GetCacheTypeElementJSOByIndex:()=>({})};
"""+native_mainmenu.patch(source,care_packages=True,hide_promo=False)+"""
check();assert.equal(opened,0);inventory=true;check();assert.equal(opened,0);
map='';playing=true;check();assert.equal(opened,0);playing=false;inventory=false;check();assert.equal(opened,0);
inventory=true;check();assert.equal(opened,1);
"""
        self.run_js(script)

    def test_changed_mainmenu_fails_closed(self):
        with self.assertRaises(ValueError):native_mainmenu.patch('changed')

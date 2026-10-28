import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import launch_setup as setup
import package_release as package
import native_resources
import bundled_bots
import bot_skins


def exports(data, target=None):
    if data == b'original' or (data.startswith(b'proxy') and target == 'steam_api64_real'):
        return ['SteamAPI_Init','SteamAPI_RunCallbacks']
    raise ValueError('Not a supported Steam library')


class ReleaseSetup(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bin = self.root/'game/bin/win64'
        self.bin.mkdir(parents=True)

    def payload(self):
        path = self.bin/'cs2_gc_payload'
        path.mkdir()
        (path/'steam_api64.dll').write_bytes(b'proxy-v1')

    @patch.object(setup,'export_names',side_effect=exports)
    def test_first_launch_saves_original_and_upgrade_preserves_state(self,_):
        self.payload()
        (self.bin/'steam_api64.dll').write_bytes(b'original')
        states = {name:b'player data' for name in ('cs2_gc_inventory.txt','cs2_gc_finish_ids.json',
                                                  'cs2_gc_gameplay.cfg','cs2_gc.cfg')}
        for name,data in states.items():
            (self.bin/name).write_bytes(data)
        setup.install_proxy(self.bin)
        self.assertEqual((self.bin/'steam_api64_real.dll').read_bytes(),b'original')
        self.assertEqual((self.bin/'steam_api64.dll').read_bytes(),b'proxy-v1')
        (self.bin/'cs2_gc_payload/steam_api64.dll').write_bytes(b'proxy-v2')
        setup.install_proxy(self.bin)
        self.assertEqual((self.bin/'steam_api64_real.dll').read_bytes(),b'original')
        self.assertEqual((self.bin/'steam_api64.dll').read_bytes(),b'proxy-v2')
        for name,data in states.items():
            self.assertEqual((self.bin/name).read_bytes(),data)

    @patch.object(setup,'export_names',side_effect=exports)
    def test_missing_original_is_an_actionable_error_not_a_second_proxy(self,_):
        self.payload()
        (self.bin/'steam_api64.dll').write_bytes(b'proxy-old')
        with self.assertRaisesRegex(setup.SetupError,'original steam_api64.dll is missing'):
            setup.install_proxy(self.bin)
        self.assertFalse((self.bin/'steam_api64_real.dll').exists())
        self.assertEqual((self.bin/'steam_api64.dll').read_bytes(),b'proxy-old')

    @patch.object(setup,'export_names',side_effect=exports)
    def test_bad_saved_original_is_never_replaced(self,_):
        self.payload()
        (self.bin/'steam_api64_real.dll').write_bytes(b'proxy-old')
        with self.assertRaisesRegex(setup.SetupError,'matching original'):
            setup.install_proxy(self.bin)
        self.assertEqual((self.bin/'steam_api64_real.dll').read_bytes(),b'proxy-old')

    def test_version_and_package_checks_detect_mixed_or_missing_files(self):
        path = self.root/'game/csgo/pak01_dir.vpk'
        path.parent.mkdir(parents=True)
        path.write_bytes(b'matching game')
        expected = {'files':{'game/csgo/pak01_dir.vpk':setup.digest(path)},'steam_build':'25966348'}
        setup.verify_build(self.root,expected)
        path.write_bytes(b'new Steam update')
        with self.assertRaisesRegex(setup.SetupError,'Unsupported CS2 files'):
            setup.verify_build(self.root,expected)
        path.unlink()
        with self.assertRaisesRegex(setup.SetupError,'BOTH depot'):
            setup.verify_build(self.root,expected)
        with self.assertRaisesRegex(setup.SetupError,'Missing or changed mod file'):
            setup.verify_package(self.root,{'files':{'game/bin/win64/gold_pools.txt':'missing'}})
        with self.assertRaisesRegex(setup.SetupError,'manifest path'):
            setup.verify_package(self.root,{'files':{'../outside':'bad'}})

    def test_large_schema_is_extracted_and_saved_state_is_not_modified(self):
        schema = b'"items_game" {'+b' '*(8*1024*1024)+b'}'
        inventory = self.bin/'cs2_gc_inventory.txt'
        inventory.write_bytes(b'saved inventory')
        (self.bin/'items_game.txt').write_bytes(b'old schema')
        setup.ensure_schema(self.bin,lambda:schema)
        self.assertEqual((self.bin/'items_game.txt').read_bytes(),schema)
        self.assertEqual((self.bin/'items_game.txt.before-launcher').read_bytes(),b'old schema')
        self.assertEqual(inventory.read_bytes(),b'saved inventory')
        setup.ensure_schema(self.bin,lambda:schema)
        self.assertEqual((self.bin/'items_game.txt.before-launcher').read_bytes(),b'old schema')

    def test_crc_failure_restores_normal_panorama_limit(self):
        limit = native_resources.MAX_ASSET
        with patch.object(native_resources,'vpk_file',side_effect=ValueError('checksum mismatch')):
            with self.assertRaisesRegex(ValueError,'checksum'):
                setup.ensure_schema(self.bin)
        self.assertEqual(native_resources.MAX_ASSET,limit)
        self.assertFalse((self.bin/'items_game.txt').exists())

    def test_existing_profile_is_reused_and_fresh_profile_is_initialized_once(self):
        runner_calls = []
        def runner(command,**kwargs):
            runner_calls.append(command)
            replay = self.bin/'cs2_gc_replay'
            replay.mkdir(exist_ok=True)
            for name in ('4004.bin','2501.bin'):
                (replay/name).write_bytes(b'own profile')
            return SimpleNamespace(returncode=0)
        self.assertTrue(setup.ensure_profile(self.bin,2000933,runner))
        self.assertFalse(setup.ensure_profile(self.bin,2000933,runner))
        self.assertEqual(len(runner_calls),1)
        self.assertEqual(runner_calls[0][-1],'2000933')

    def test_profile_failure_or_timeout_does_not_touch_inventory(self):
        inventory = self.bin/'cs2_gc_inventory.txt'
        inventory.write_bytes(b'preserve')
        with self.assertRaisesRegex(setup.SetupError,'Steam profile initialization failed'):
            setup.ensure_profile(self.bin,2000933,lambda *a,**k:SimpleNamespace(returncode=1))
        self.assertEqual(inventory.read_bytes(),b'preserve')

    def test_package_excludes_saved_state_and_original_game_library(self):
        root = Path(__file__).resolve().parents[1]
        files = package.project_files(root)
        self.assertTrue(any(name.endswith('collection_icons/set_cs2gc_case_forged.png') for _,name in files))
        self.assertTrue(any(name.endswith('weapon_patterns/obsidian_fault.png') for _,name in files))
        self.assertFalse(any(Path(name).name in package.EXCLUDED_NAMES for _,name in files))

    def test_launcher_starts_adjacent_game_with_explicit_working_directory(self):
        root = Path(__file__).resolve().parents[1]
        source = (root/'cs2_gc/proxy/debug_launcher.cpp').read_text()
        self.assertNotIn('L" -applaunch',source)
        self.assertIn('directory/L"cs2.exe"',source)
        self.assertIn('nullptr,directory.c_str(),&startup,&child',source)
        self.assertIn('cs2_gc_python/python.exe',source)
        self.assertIn('cs2_gc_launch_error.txt',source)
        self.assertIn('GetExitCodeProcess',source)

    def test_profile_helper_only_requests_read_only_data(self):
        root = Path(__file__).resolve().parents[1]
        source = (root/'cs2_gc/proxy/profile_bootstrap.cpp').read_text()
        self.assertIn('k_EMsgGCClientHello,hello.bytes()',source)
        self.assertIn('k_EMsgGCStoreGetUserData,{}',source)
        self.assertNotIn('k_EMsgGCStorePurchase',source)
        self.assertIn('cache.owner.id!=steamId',source)
        self.assertIn('SaveIfMissing',source)


    def bot_payload(self):
        game = self.root/'game'
        (game/'csgo').mkdir(exist_ok=True)
        (game/'csgo/gameinfo.gi').write_text('"GameInfo" {}')
        payload = self.bin/'cs2_gc_payload/bots'
        payload.mkdir(parents=True)
        files = {'addons/metamod/bin/server.dll':b'metamod',
                 'addons/counterstrikesharp/api/CounterStrikeSharp.API.dll':b'api',
                 'addons/counterstrikesharp/dotnet/host/fxr.dll':b'runtime'}
        for name in ('BotRandomizer','BotAI','BotAimImprover','BotBuy','BotState','NadeSystem'):
            files['addons/counterstrikesharp/plugins/'+name+'/'+name+'.dll'] = name.encode()
        data = io.BytesIO()
        with zipfile.ZipFile(data,'w') as archive:
            for name,content in files.items():
                archive.writestr(name,content)
        data = data.getvalue()
        (payload/'bot_improver.zip').write_bytes(data)
        (payload/'bundle.json').write_text(json.dumps({'version':'v1.4.6','asset':'test.zip',
                                                       'sha256':hashlib.sha256(data).hexdigest()}))
        for tier in bot_skins.PRESET_TIERS:
            path = payload/'resources/overrides'/tier/'botprofile.db'
            path.parent.mkdir(parents=True)
            path.write_bytes(('preset '+tier).encode())
        cfg = payload/'resources/cfg'
        cfg.mkdir()
        for mode in ('normal','ffa'):
            (cfg/('my_bot_%s_config_rules_unchanged.cfg'%mode)).write_text('bot_difficulty 4\nbind F1 nope\nbot_quota 9\n')
        return game,payload

    def test_bundled_bots_install_without_network_and_preserve_existing_config(self):
        game,payload = self.bot_payload()
        cfg = game/'csgo/cfg'
        cfg.mkdir()
        personal = cfg/'gamemode_casual_server.cfg'
        personal.write_text('my own server config')
        with patch.object(bot_skins,'_get',side_effect=AssertionError('No runtime network')), \
             patch('fair_bot_policy.require_game_closed'), \
             patch.object(bot_skins,'_mount') as mount, patch.object(bot_skins,'recurate') as curate:
            self.assertTrue(bundled_bots.ensure(self.bin))
            self.assertEqual(curate.call_count,1)
            self.assertTrue((game/bot_skins.PLUGIN_DIR/'BotRandomizer.dll').is_file())
            self.assertEqual(personal.read_text(),'my own server config')
            self.assertNotIn('bind F1',(cfg/'cs2_gc_bot_improver.cfg').read_text())
            self.assertNotIn('bot_difficulty',(cfg/'cs2_gc_bot_improver.cfg').read_text())
            self.assertIn('exec cs2_gc_premier_bots',(cfg/'gamemode_competitive_server.cfg').read_text())
            self.assertFalse(bundled_bots.ensure(self.bin))
            self.assertEqual(curate.call_count,1)
            # An interrupted/deleted plugin is repaired on the next launch.
            (game/bot_skins.PLUGIN_DIR/'BotRandomizer.dll').unlink()
            self.assertTrue(bundled_bots.ensure(self.bin))
            self.assertEqual(curate.call_count,2)

    def test_bot_setup_preserves_foreign_addons_and_respects_disable_preference(self):
        game,payload = self.bot_payload()
        foreign = game/'csgo/addons/metamod'
        foreign.mkdir(parents=True)
        marker = foreign/'personal.txt'
        marker.write_text('preserve')
        with self.assertRaisesRegex(ValueError,'ownership record'):
            bundled_bots.ensure(self.bin)
        self.assertEqual(marker.read_text(),'preserve')
        (self.bin/'cs2_gc_bot_plugins_disabled').touch()
        self.assertFalse(bundled_bots.ensure(self.bin))
        self.assertEqual(marker.read_text(),'preserve')

    def test_bot_checksum_failure_does_not_install_any_addon(self):
        game,payload = self.bot_payload()
        (payload/'bot_improver.zip').write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError,'checksum'):
            bundled_bots.ensure(self.bin)
        self.assertFalse((game/'csgo/addons').exists())


    def test_bootstrap_resolves_only_exports_present_in_supported_game(self):
        import re
        root = Path(__file__).resolve().parents[1]
        source = (root/'cs2_gc/proxy/profile_bootstrap.cpp').read_text()
        exports = {line.strip().split('=')[0] for line in
                   (root/'data/steam_api64_exports.def').read_text().splitlines()
                   if line.startswith('    ')}
        requested = set(re.findall(r'GetProcAddress\(module,"([^"]+)"\)',source))
        self.assertTrue(requested)
        self.assertFalse(requested-exports,'Bootstrap requests missing DLL exports: '+str(requested-exports))
        self.assertIn('SteamAPI_InitFlat',requested)
        self.assertNotIn('SteamAPI_Init',requested)
        self.assertIn('SteamErrorMessage=char[1024]',source)
        self.assertIn('initialized=initResult==0',source)


    def test_profile_error_dialog_includes_helper_failure_reason(self):
        def runner(command,**kwargs):
            kwargs['stdout'].write('Steam initialization failed (result=2): Steam is not running.\n')
            return SimpleNamespace(returncode=1)
        with self.assertRaisesRegex(setup.SetupError,'result=2.*Steam is not running'):
            setup.ensure_profile(self.bin,2000933,runner)


if __name__ == '__main__':
    unittest.main()

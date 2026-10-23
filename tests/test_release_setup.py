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


if __name__ == '__main__':
    unittest.main()

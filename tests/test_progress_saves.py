import json,sys,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import progress_saves as saves,settings_editor

class ProgressSaves(unittest.TestCase):
    def fixture(self,directory):
        proxy=Path(directory)/'game/bin/win64';proxy.mkdir(parents=True)
        files={'cs2_gc_inventory.txt':b'"inventory" { "items" {} "loadout" {} }',
               'cs2_gc_gsi_state.json':b'{"token":"private-test","total":123,"matches":7,"premier":{"rating":12000}}',
               'cs2_gc_rewards.txt':b'123\n','cs2_gc_matches.txt':b'7\n',
               'cs2_gc_finish_ids.json':b'{"finish":90000}',
               'cs2_gc_gun_collections.json':b'{"history":{"owned-finish":{}}}'}
        for name,data in files.items():(proxy/name).write_bytes(data)
        return proxy,files

    def test_transfer_keeps_inventory_rank_counters_and_finish_history_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            proxy,before=self.fixture(tmp);folder=Path(tmp)/'saves'
            saved=saves.snapshot(proxy,folder)
            (proxy/'cs2_gc_rewards.txt').write_bytes(b'456\n')
            state=json.loads(before['cs2_gc_gsi_state.json']);state['total']=456
            (proxy/'cs2_gc_gsi_state.json').write_text(json.dumps(state))
            (proxy/'cs2_gc_mission_session.txt').write_text('1 2 3')
            (proxy/'cs2_gc_prepare_cache.json').write_text('{}')
            rollback=saves.restore(proxy,saved,folder)
            restored=saves.read_files(proxy)
            self.assertEqual(json.loads(restored.pop('cs2_gc_gsi_state.json')),json.loads(before['cs2_gc_gsi_state.json']))
            self.assertEqual(restored,{n:d for n,d in before.items() if n!='cs2_gc_gsi_state.json'})
            self.assertEqual(saves.load_snapshot(rollback)['cs2_gc_rewards.txt'],b'456\n')
            self.assertFalse((proxy/'cs2_gc_mission_session.txt').exists())
            self.assertFalse((proxy/'cs2_gc_prepare_cache.json').exists())

    def test_modified_or_unsafe_archive_changes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            proxy,before=self.fixture(tmp);saved=saves.snapshot(proxy,Path(tmp)/'saves')
            for extra in ('cs2_gc_inventory.txt','../outside','steam_api64.dll'):
                bad=Path(tmp)/(extra.replace('/','_')+'.zip')
                bad.write_bytes(saved.read_bytes())
                with zipfile.ZipFile(bad,'a') as archive:archive.writestr(extra,b'changed')
                with self.assertRaises(ValueError):saves.restore(proxy,bad,Path(tmp)/'saves')
                self.assertEqual(saves.read_files(proxy),before)

    def test_failed_multifile_restore_rolls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            proxy,before=self.fixture(tmp);folder=Path(tmp)/'saves';saved=saves.snapshot(proxy,folder)
            altered=before['cs2_gc_inventory.txt'].replace(b'"loadout"',b'"loadout-altered"')
            (proxy/'cs2_gc_inventory.txt').write_bytes(altered)
            original=saves.atomic;failed=[False]
            def interrupted(path,data):
                if path.name=='cs2_gc_matches.txt' and not failed[0]:failed[0]=True;raise OSError('simulated interruption')
                return original(path,data)
            with patch.object(saves,'atomic',side_effect=interrupted):
                with self.assertRaises(OSError):saves.restore(proxy,saved,folder)
            self.assertEqual((proxy/'cs2_gc_inventory.txt').read_bytes(),altered)

    def test_active_helper_blocks_snapshot_and_settings_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            proxy,_=self.fixture(tmp)
            with saves.InstanceLock(proxy) as lock:
                self.assertTrue(lock)
                with patch('fair_bot_policy.require_game_closed'):
                    with self.assertRaisesRegex(ValueError,'helper'):
                        with saves.closed(proxy):pass
            path=settings_editor.ensure(proxy);path.write_text('kill_stars = 9\n')
            text=settings_editor.ensure(proxy).read_text()
            self.assertTrue(text.startswith('kill_stars = 9\n'))
            self.assertIn('mvp_stars = 5',text)
            self.assertEqual(settings_editor.ensure(proxy).read_text(),text)

    def test_restore_can_repair_a_broken_or_fresh_destination_and_preserves_old_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            source,_=self.fixture(Path(tmp)/'source');folder=Path(tmp)/'saves';saved=saves.snapshot(source,folder)
            dest=Path(tmp)/'fresh/game/bin/win64';dest.mkdir(parents=True)
            saves.restore(dest,saved,folder)
            self.assertEqual(saves.read_files(dest)['cs2_gc_inventory.txt'],saves.read_files(source)['cs2_gc_inventory.txt'])
            (dest/'cs2_gc_inventory.txt').write_bytes(b'corrupt inventory')
            recovery=saves.restore(dest,saved,folder)
            with zipfile.ZipFile(recovery) as archive:self.assertEqual(archive.read('cs2_gc_inventory.txt'),b'corrupt inventory')

if __name__=='__main__':unittest.main()

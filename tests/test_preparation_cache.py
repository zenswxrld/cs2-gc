import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from preparation_cache import PreparationCache, FILENAME
import prepare_native


class PreparationCaching(unittest.TestCase):
    def fixture(self, root):
        game=Path(root)/'game'
        proxy=game/'bin/win64'
        helpers=Path(root)/'helpers'
        for p in (proxy,helpers,game/'csgo',game/'cs2_gc_native/scripts/items'):
            p.mkdir(parents=True,exist_ok=True)
        (proxy/'items_game.txt').write_text('schema',encoding='utf-8')
        (game/'csgo/pak01_dir.vpk').write_bytes(b'original directory')
        (game/'csgo/gameinfo.gi').write_text('mounts',encoding='utf-8')
        (game/'cs2_gc_native/pak01_dir.vpk').write_bytes(b'prepared directory')
        (game/'cs2_gc_native/pak01_000.vpk').write_bytes(b'prepared data')
        (game/'cs2_gc_native/scripts/items/items_game.txt').write_text('complete override',encoding='utf-8')
        (game/'cs2_gc_native/cs2_gc_schema_stamp.txt').write_text('validated stamp',encoding='utf-8')
        (helpers/'native_finishes.py').write_text('generator',encoding='utf-8')
        (proxy/'cs2_gc_finish_ids.json').write_text('{"owned":30001}',encoding='utf-8')
        return game,proxy,helpers

    def test_warm_cache_reuses_outputs_and_detects_changed_or_missing_packs(self):
        with tempfile.TemporaryDirectory() as root:
            game,proxy,helpers=self.fixture(root)
            cache=PreparationCache(proxy,{'enabled':True},helpers)
            self.assertFalse(cache.hit())
            cache.save()
            self.assertTrue(cache.hit())
            pack=game/'cs2_gc_native/pak01_000.vpk'
            pack.write_bytes(b'changed data')
            self.assertFalse(cache.hit())
            cache.save()
            pack.unlink()
            self.assertFalse(cache.hit())

    def test_schema_helpers_artwork_config_and_game_updates_invalidate_cache(self):
        with tempfile.TemporaryDirectory() as root:
            game,proxy,helpers=self.fixture(root)
            art=helpers/'collection_icons/icon.png'
            art.parent.mkdir();art.write_bytes(b'art')
            cache=PreparationCache(proxy,{'enabled':True},helpers)
            for path in (proxy/'items_game.txt',helpers/'native_finishes.py',art,game/'csgo/pak01_dir.vpk'):
                cache.save()
                self.assertTrue(cache.hit())
                path.write_bytes(path.read_bytes()+b' changed')
                self.assertFalse(cache.hit(),str(path))
            cache.save()
            self.assertFalse(PreparationCache(proxy,{'enabled':False},helpers).hit())

    def test_finish_id_edits_mount_edits_and_missing_schema_invalidate_cache(self):
        with tempfile.TemporaryDirectory() as root:
            game,proxy,helpers=self.fixture(root)
            cache=PreparationCache(proxy,{},helpers)
            for path in (proxy/'cs2_gc_finish_ids.json',game/'csgo/gameinfo.gi',
                         game/'cs2_gc_native/cs2_gc_schema_stamp.txt'):
                cache.save()
                path.write_bytes(path.read_bytes()+b' changed')
                self.assertFalse(cache.hit())
            cache.save()
            (game/'cs2_gc_native/scripts/items/items_game.txt').unlink()
            self.assertFalse(cache.hit())

    def test_bot_reshuffle_does_not_invalidate_other_complete_native_packs(self):
        with tempfile.TemporaryDirectory() as root:
            game,proxy,helpers=self.fixture(root)
            bot=game/'cs2_gc_bots/pak01_000.vpk'
            bot.parent.mkdir();bot.write_bytes(b'names')
            cache=PreparationCache(proxy,{},helpers)
            cache.save()
            bot.write_bytes(b'new shuffled names')
            self.assertTrue(cache.hit())

    def test_corrupt_cache_falls_back_to_regeneration(self):
        with tempfile.TemporaryDirectory() as root:
            _,proxy,helpers=self.fixture(root)
            cache=PreparationCache(proxy,{},helpers)
            for value in ('not json','[]','null'):
                cache.path.write_text(value,encoding='utf-8')
                self.assertFalse(cache.hit())

    def test_launcher_skips_generation_on_hit_but_keeps_bot_names_and_signatures_fresh(self):
        with tempfile.TemporaryDirectory() as root:
            _,proxy,helpers=self.fixture(root)
            cache=PreparationCache(proxy,{},helpers)
            with contextlib.ExitStack() as stack:
                stack.enter_context(patch.object(prepare_native,'load',return_value={'mixed_stattrak_tradeups':1}))
                stack.enter_context(patch.object(prepare_native,'PreparationCache',return_value=cache))
                actions={name:stack.enter_context(patch.object(prepare_native,name,return_value='ready')) for name in
                    ('recipes','armory','scoreboard','store','confirmation','sales','results','offers','key_select',
                     'stock_results','mainmenu','care_packages','missions','knife_reel','bot_names',
                     'ensure_first_game_path','signatures')}
                output=io.StringIO()
                with contextlib.redirect_stdout(output):
                    prepare_native.prepare(proxy)
                    prepare_native.prepare(proxy)
                self.assertEqual(actions['recipes'].call_count,1)
                self.assertEqual(actions['armory'].call_count,1)
                self.assertEqual(actions['bot_names'].call_count,2)
                self.assertEqual(actions['signatures'].call_count,2)
                self.assertIn('Preparation cache: hit',output.getvalue())
                with contextlib.redirect_stdout(io.StringIO()):
                    prepare_native.prepare(proxy,force_rebuild=True)
                self.assertEqual(actions['recipes'].call_count,2)

    def test_failed_build_never_saves_a_complete_preparation_cache(self):
        with tempfile.TemporaryDirectory() as root:
            _,proxy,helpers=self.fixture(root)
            cache=PreparationCache(proxy,{},helpers)
            with patch.object(prepare_native,'load',return_value={'mixed_stattrak_tradeups':1}), \
                 patch.object(prepare_native,'PreparationCache',return_value=cache), \
                 patch.object(prepare_native,'recipes',side_effect=ValueError('failed')):
                with contextlib.redirect_stdout(io.StringIO()),self.assertRaises(ValueError):
                    prepare_native.prepare(proxy)
            self.assertFalse((proxy/FILENAME).exists())


if __name__=='__main__':
    unittest.main()

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import vpk_pack
import native_resources


class VpkPack(unittest.TestCase):
    def test_pack_round_trips_through_the_vpk_reader_and_skips_bookkeeping_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'scripts/items').mkdir(parents=True)
            (root / 'panorama/scripts').mkdir(parents=True)
            (root / 'scripts/items/items_game.txt').write_bytes(b'schema' * 4000)
            (root / 'panorama/scripts/scoreboard.vts_c').write_bytes(b'abc')
            (root / 'cs2_gc_native_manifest.json').write_text('{}')
            (root / 'cs2_gc_schema_stamp.txt').write_text('stamp')
            self.assertTrue(vpk_pack.pack(root))
            self.assertFalse(vpk_pack.pack(root))  # unchanged content is not rewritten
            vpk = root / 'pak01_dir.vpk'
            self.assertTrue((root / 'pak01_000.vpk').is_file())
            self.assertEqual(native_resources.vpk_file(vpk, 'scripts/items/items_game.txt'), b'schema' * 4000)
            self.assertEqual(native_resources.vpk_file(vpk, 'panorama/scripts/scoreboard.vts_c'), b'abc')
            with self.assertRaises(ValueError):
                native_resources.vpk_file(vpk, 'cs2_gc_native_manifest.json')
            (root / 'panorama/scripts/scoreboard.vts_c').write_bytes(b'changed')
            self.assertTrue(vpk_pack.pack(root))
            self.assertEqual(native_resources.vpk_file(vpk, 'panorama/scripts/scoreboard.vts_c'), b'changed')

    def test_kill_switch_removes_vpks_and_blocks_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            game = Path(folder)
            (game / 'bin/win64').mkdir(parents=True)
            mod = game / 'cs2_gc_native'
            (mod / 'scripts').mkdir(parents=True)
            (mod / 'scripts/a.txt').write_bytes(b'data')
            self.assertTrue(vpk_pack.pack(mod))
            self.assertTrue((mod / 'pak01_dir.vpk').exists())
            (game / 'bin/win64' / vpk_pack.KILL_SWITCH).write_text('x')
            self.assertTrue(vpk_pack.pack(mod))
            self.assertFalse((mod / 'pak01_dir.vpk').exists() or (mod / 'pak01_000.vpk').exists())
            self.assertFalse(vpk_pack.pack(mod))
            self.assertTrue((mod / 'scripts/a.txt').exists())


if __name__ == '__main__':
    unittest.main()

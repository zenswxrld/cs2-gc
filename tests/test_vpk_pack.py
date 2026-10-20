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
            game = Path(folder)
            (game / 'bin/win64').mkdir(parents=True)
            root = game / 'cs2_gc_native'
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
            self.assertTrue(vpk_pack.status(game / 'bin/win64').startswith('OFF'))
            (game / 'bin/win64' / vpk_pack.KILL_SWITCH).unlink()
            vpk_pack.pack(mod)
            self.assertIn('cs2_gc_native', vpk_pack.status(game / 'bin/win64'))

    def test_signatures_list_our_folders_with_the_directory_checksum_and_keep_valve_entries(self):
        import vpk_signatures
        with tempfile.TemporaryDirectory() as folder:
            game = Path(folder)
            proxy = game / 'bin/win64'; proxy.mkdir(parents=True)
            original = '"vpk.signatures"\r\n{\r\n"pakxx" "off"\r\n"pak01"\r\n{\r\n\t"csgo" "MD5:7ff6546070bd65d225450fd1cb8e2751"\r\n}\r\n}\r\n'
            (proxy / 'vpk.signatures').write_bytes(original.encode())
            for name in ('cs2_gc_native', 'cs2_gc_offers'):
                mod = game / name; mod.mkdir(); (mod / 'a.txt').write_bytes(name.encode())
                vpk_pack.pack(mod)
            self.assertIn('RESTART', vpk_signatures.update(proxy))
            text = (proxy / 'vpk.signatures').read_text()
            digest = vpk_signatures.directory_checksum(game / 'cs2_gc_offers/pak01_dir.vpk')
            self.assertIn('"cs2_gc_offers" "MD5:' + digest + '"', text)
            self.assertIn('"csgo" "MD5:7ff6546070bd65d225450fd1cb8e2751"', text)
            self.assertTrue(text.rstrip().endswith('}'))
            self.assertEqual((proxy / 'vpk.signatures.cs2_gc_backup').read_bytes(), original.encode())
            self.assertIn('installed', vpk_signatures.update(proxy))  # idempotent
            self.assertEqual(text.count('cs2_gc_offers'), 1)
            (proxy / vpk_pack.KILL_SWITCH).write_text('x')
            for name in ('cs2_gc_native', 'cs2_gc_offers'): vpk_pack.pack(game / name)
            vpk_signatures.update(proxy)
            self.assertEqual((proxy / 'vpk.signatures').read_bytes(), original.encode())


if __name__ == '__main__':
    unittest.main()

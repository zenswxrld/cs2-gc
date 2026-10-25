import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import artwork_archive as aa
import native_resources,vpk_pack

class ArtworkArchives(unittest.TestCase):
    def test_small_archive_matches_the_existing_native_builder_exactly(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'scripts').mkdir()
            data=[('scripts/a.txt',b'repeated artwork'*100),('b.bin',b'1234'),('c.bin',b'1234')]
            for path,content in data:(root/path).write_bytes(content)
            self.assertTrue(aa.pack(root));self.assertFalse(aa.pack(root))
            wanted,archive=vpk_pack.build(sorted(data))
            self.assertEqual((root/'pak01_dir.vpk').read_bytes(),wanted)
            self.assertEqual((root/'pak01_000.vpk').read_bytes(),archive)

    def test_split_archives_deduplicate_roundtrip_shrink_and_kill_switch(self):
        with tempfile.TemporaryDirectory() as directory:
            game=Path(directory);proxy=game/'bin/win64';proxy.mkdir(parents=True)
            root=game/'cs2_gc_native';root.mkdir()
            data={'a.bin':b'A'*24,'b.bin':b'B'*24,'c.bin':b'C'*24,'d.bin':b'A'*24}
            for path,content in data.items():(root/path).write_bytes(content)
            with patch.object(aa,'ARCHIVE_LIMIT',32):
                self.assertTrue(vpk_pack.pack(root))
                self.assertEqual(len(aa.owned_archives(root)),3)
                for path,content in data.items():
                    self.assertEqual(native_resources.vpk_file(root/'pak01_dir.vpk',path),content)
                self.assertFalse(vpk_pack.pack(root))
                (root/'b.bin').unlink();(root/'c.bin').unlink()
                self.assertTrue(vpk_pack.pack(root))
                self.assertEqual(len(aa.owned_archives(root)),1)
                self.assertEqual(native_resources.vpk_file(root/'pak01_dir.vpk','d.bin'),b'A'*24)
                (root/'b.bin').write_bytes(b'B'*24);vpk_pack.pack(root)
                (proxy/vpk_pack.KILL_SWITCH).write_text('x')
                self.assertTrue(vpk_pack.pack(root))
                self.assertFalse(aa.owned_archives(root))
                self.assertFalse((root/'pak01_dir.vpk').exists())
                self.assertTrue((root/'a.bin').is_file())

if __name__=='__main__':unittest.main()


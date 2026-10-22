import sys
from pathlib import Path
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from care_package_bridge import CarePackageBridge


class CareBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.cfg = self.directory / 'csgo' / 'cfg'
        self.cfg.mkdir(parents=True)
        self.log = self.cfg.parent / 'console.log'
        self.nonce = 'a' * 32
        (self.directory / 'cs2_gc_console_boot.txt').write_text(self.nonce)
        self.request = self.directory / 'cs2_gc_care_request.txt'

    def line(self, generation=123, mask=13, nonce=None):
        return f'[Console] cs2gc_{nonce or self.nonce}_care_{generation}_{mask} 1.000000\n'

    def test_reads_early_click_and_preserves_pending(self):
        self.log.write_text('old\n')
        (self.directory / 'cs2_gc_care_boot.txt').write_text(self.nonce + ' 4')
        self.log.write_text('old\n' + self.line())
        bridge = CarePackageBridge(self.directory,self.cfg,42)
        bridge.poll()
        self.assertEqual(self.request.read_text(),f'42 123 13 {self.nonce}\n')
        self.log.write_text('old\n' + self.line() + self.line(124,7))
        bridge.poll()
        self.assertIn('123 13',self.request.read_text())
        self.request.unlink()
        bridge.poll()
        self.assertIn('124 7',self.request.read_text())

    def test_rejects_old_session_partial_invalid_and_echoed_commands(self):
        bad = (self.line(nonce='b'*32) + self.line(0) + self.line(2**32) +
               self.line(mask=15) + self.line().rstrip() + '"\n')
        self.log.write_text(bad + self.line().rstrip('\n'))
        bridge = CarePackageBridge(self.directory,self.cfg,42)
        bridge.poll()
        self.assertFalse(self.request.exists())
        with self.log.open('a') as output: output.write('\n')
        bridge.poll()
        self.assertTrue(self.request.exists())

    def test_recovers_log_truncation_and_processing_backpressure(self):
        self.log.write_text('x'*200 + '\n')
        bridge = CarePackageBridge(self.directory,self.cfg,42)
        bridge.poll()
        processing = self.directory / 'cs2_gc_care_processing.txt'
        processing.write_text('busy')
        self.log.write_text(self.line())
        bridge.poll()
        self.assertFalse(self.request.exists())
        processing.unlink()
        bridge.poll()
        self.assertTrue(self.request.exists())

    def test_no_nonce_no_claim(self):
        (self.directory / 'cs2_gc_console_boot.txt').unlink()
        self.log.write_text(self.line())
        CarePackageBridge(self.directory,self.cfg,42).poll()
        self.assertFalse(self.request.exists())

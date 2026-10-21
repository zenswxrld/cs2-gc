from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import reset_profile


class ResetProfile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.dir = Path(self.tmp.name)
        for name in reset_profile.STATE: (self.dir / name).write_text('x')
        (self.dir / 'cs2_gc_inventory.txt').write_text(
            '"inventory"\n{\n\t"armory_credits"\t"7"\n\t"progression" { "level" "12" "xp" "300" "reward_total" "5000" }\n'
            '\t"level_reward_total"\t"11"\n\t"items" { }\n}\n', encoding='utf-8')

    def tearDown(self): self.tmp.cleanup()

    def test_progress_reset_keeps_items_and_stars_but_returns_to_level_one(self):
        backup, moved = reset_profile.reset(self.dir, 'progress')
        text = (self.dir / 'cs2_gc_inventory.txt').read_text()
        self.assertIn('"progression" { "level" "1" "xp" "0" "reward_total" "0" }', text)
        self.assertNotIn('level_reward_total', text)
        self.assertIn('"armory_credits"\t"7"', text)
        self.assertIn('"level" "12"', (backup / 'cs2_gc_inventory.txt').read_text())
        self.assertEqual(sorted(moved), sorted(reset_profile.STATE))
        self.assertFalse(any((self.dir / name).exists() for name in reset_profile.STATE))

    def test_full_reset_moves_the_inventory_too(self):
        backup, moved = reset_profile.reset(self.dir, 'all')
        self.assertFalse((self.dir / 'cs2_gc_inventory.txt').exists())
        self.assertTrue((backup / 'cs2_gc_inventory.txt').exists())


if __name__ == '__main__':
    unittest.main()

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import native_bot_names as bots

PROFILES = ''.join('Elite+Rifle Bot{0}\n\tVoicePitch = 9{1}\nEnd\n\n'.format(i, i % 10) for i in range(12))
SOURCE = ('// botprofile.db\r\n\r\nDefault\n\tSkill = 50\nEnd\n\nTemplate Elite\n\tSkill = 100\nEnd\n\n'
          'Template Rifle\n\tWeaponPreference = ak47\nEnd\n\n' + PROFILES + 'Easy Albert // note\nEnd\n')


class BotNames(unittest.TestCase):
    def test_native_labels_keep_names_and_all_other_localization(self):
        source = ('\ufeff"lang" { "Tokens" {\n"Other" "Do not change"\n'
            '"SFUI_bot_decorated_name" "BOT %s1"\n'
            '"SFUI_bot_decorated_name_controlled" "BOT %s1 (%s2)"\n} }')
        expected = source.replace('BOT %s1', '%s1')
        self.assertEqual(bots.patch_labels(source), expected)
        self.assertEqual(bots.patch_labels(expected), expected)
        with self.assertRaises(ValueError): bots.patch_labels(source.replace('%s1', ''))
        with self.assertRaises(ValueError): bots.patch_labels(source + '\n"SFUI_bot_decorated_name" "BOT %s1"')

    def test_only_profile_names_change_and_names_are_unique(self):
        patched = bots.patch(SOURCE, 5)
        self.assertEqual(patched.count('\n'), SOURCE.count('\n'))
        before, after = SOURCE.splitlines(), patched.splitlines()
        changed = [(a, b) for a, b in zip(before, after) if a != b]
        self.assertEqual(len(changed), 13)
        names = [b.split()[1] for _, b in changed]
        self.assertEqual(len(set(n.lower() for n in names)), 13)
        for a, b in changed:
            self.assertEqual(a.split()[0], b.split()[0])  # templates kept
        self.assertIn('// note', after[before.index('Easy Albert // note')])
        self.assertIn('\tWeaponPreference = ak47', patched)
        self.assertEqual(bots.patch(SOURCE, 5), patched)
        self.assertNotEqual(bots.patch(SOURCE, 6), patched)

    def test_unknown_layout_is_refused(self):
        with self.assertRaises(ValueError): bots.patch(SOURCE.replace('End\n\nEasy', 'Easy'), 1)
        with self.assertRaises(ValueError): bots.patch('Default\nEnd\n', 1)
        with self.assertRaises(ValueError): bots.patch(SOURCE + 'Odd line with words\n', 1)

    def test_launcher_reshuffles_and_helper_reuses_the_seed(self):
        with tempfile.TemporaryDirectory() as folder:
            first = bots._seed(folder, True)
            self.assertEqual(bots._seed(folder, False), first)
            self.assertEqual(bots._seed(folder, False), first)

    def test_many_profiles_get_numbered_names(self):
        self.assertEqual(len(set(bots._names(400, 3))), 400)


if __name__ == '__main__':
    unittest.main()

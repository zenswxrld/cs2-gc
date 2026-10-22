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



class CollectionItemSets(unittest.TestCase):
    """Custom collections become real collections for the client's trade-up screen (localized #CSGO_ names)."""

    def test_sets_list_owned_colours_once_with_localized_names(self):
        import native_skins
        lists = ('\t\t"set_cs2gc_case_eclipse_ancient"\n\t\t{\n\t\t\t"[fam]weapon_ak47"\t\t"1"\n\t\t}\n'
                 '\t\t"set_cs2gc_case_eclipse_rare"\n\t\t{\n\t\t\t"[plain]weapon_p90"\t\t"1"\n\t\t}\n'
                 '\t\t"set_cs2gc_case_eclipse"\n\t\t{\n\t\t\t"set_cs2gc_case_eclipse_ancient"\t\t"1"\n'
                 '\t\t\t"set_cs2gc_case_eclipse_rare"\t\t"1"\n\t\t}\n'
                 '\t\t"set_cs2gc_case_cinder_rare"\n\t\t{\n\t\t\t"[plain]weapon_p90"\t\t"1"\n\t\t}\n'
                 '\t\t"set_cs2gc_case_cinder"\n\t\t{\n\t\t\t"set_cs2gc_case_cinder_rare"\t\t"1"\n\t\t}')
        text, tokens = native_skins.collection_item_sets(
            lists, ['set_cs2gc_case_eclipse', 'set_cs2gc_case_cinder'], {'fam': ['fam_red', 'fam_blue']})
        self.assertIn('"name"\t\t"#CSGO_set_cs2gc_case_eclipse"', text)
        self.assertIn('"set_description"\t\t"#CSGO_set_cs2gc_case_eclipse_desc"', text)
        for item in ('[fam_red]weapon_ak47', '[fam_blue]weapon_ak47', '[plain]weapon_p90'):
            self.assertEqual(text.count('"%s"' % item), 1)
        self.assertNotIn('[fam]weapon_ak47', text)
        self.assertNotIn('set_cs2gc_case_cinder"', text)  # its only skin is already in Eclipse: no empty set
        self.assertEqual(tokens, {'CSGO_set_cs2gc_case_eclipse': 'The Eclipse Collection',
                                  'CSGO_set_cs2gc_case_eclipse_desc': 'A custom collection.'})

    def test_language_override_adds_collection_names_with_or_without_bot_labels(self):
        source = ('"lang"\n{\n"Tokens"\n{\n"SFUI_bot_decorated_name"\t"BOT %s1"\n'
                  '"SFUI_bot_decorated_name_controlled"\t"BOT %s1 (%s2)"\n}\n}')
        tokens = {'CSGO_set_cs2gc_case_eclipse': 'The Eclipse Collection'}
        both = bots.patch_labels(source, True, tokens)
        self.assertIn('"CSGO_set_cs2gc_case_eclipse"\t"The Eclipse Collection"', both)
        self.assertIn('"SFUI_bot_decorated_name"\t"%s1"', both)
        names_only = bots.patch_labels(source, False, tokens)
        self.assertIn('The Eclipse Collection', names_only)
        self.assertIn('"BOT %s1"', names_only)  # bot labels untouched when bot_hide_tag = 0
        # A changed bot label format must not cost the collection names (their item sets need them).
        changed = bots.patch_labels(source.replace('%s1', ''), True, tokens)
        self.assertIn('The Eclipse Collection', changed)
        self.assertEqual(bots.patch_labels(both, True, tokens).count('CSGO_set_cs2gc_case_eclipse'), 1)


if __name__ == '__main__':
    unittest.main()

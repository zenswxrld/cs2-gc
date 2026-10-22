import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import bot_skins

CATALOG = {
    'weapons': [{'designerName': 'weapon_ak47', 'defIndex': 7, 'paints': [{'paintKit': 282}, {'paintKit': 1}]},
                {'designerName': 'weapon_taser', 'defIndex': 31, 'paints': [{'paintKit': 5}]}],
    'knives': [{'defIndex': 500, 'paints': [{'finish': 'Fade'}, {'finish': 'Night'}]}],
    'knifeFinishPreferences': [{'finish': 'Fade', 'weight': 3}, {'finish': 'Night', 'weight': 4}],
    'gloves': [{'defIndex': 5034, 'paintKit': 10033}, {'defIndex': 5034, 'paintKit': 10034}, {'defIndex': 5030, 'paintKit': 9}],
    'stickerCategories': ['Valve', '2014 EMS One Katowice', 'Pinups Capsule', '2014 ESL One Cologne'],
    'stickerKits': [{'defIndex': 1, 'category': 0}, {'defIndex': 2, 'category': 1}, {'defIndex': 3, 'category': 2},
                    {'defIndex': 4, 'category': 3}, {'defIndex': 5, 'category': 1}],
}
TITLES = {282: 'Redline', 1: 'Groundwater', 5: 'Zeus thing', 10033: 'Crimson Kimono', 10034: 'Emerald Web', 9: 'Plain'}


class Curate(unittest.TestCase):
    def test_popular_only_with_categories_renumbered_and_fallbacks(self):
        result, report = bot_skins.curate(CATALOG, TITLES)
        guns = {w['designerName']: [p['paintKit'] for p in w['paints']] for w in result['weapons']}
        self.assertEqual(guns, {'weapon_ak47': [282], 'weapon_taser': [5]})  # no popular Zeus: full list kept
        self.assertEqual([g['paintKit'] for g in result['gloves']], [10033, 10034])
        self.assertEqual(result['stickerCategories'], ['2014 EMS One Katowice', '2014 ESL One Cologne'])
        self.assertEqual([(s['defIndex'], s['category']) for s in result['stickerKits']], [(2, 0), (4, 1), (5, 0)])
        # Every remaining category has stickers (the plugin refuses an empty one).
        self.assertEqual({s['category'] for s in result['stickerKits']}, set(range(len(result['stickerCategories']))))
        weights = {p['finish']: p['weight'] for p in result['knifeFinishPreferences']}
        self.assertEqual(weights, {'Night': 1, 'Fade': 14})
        self.assertIn('weapon_ak47', report['missing'])


class Files(unittest.TestCase):
    def test_archive_paths_stay_inside_and_plugin_folder_is_found(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('BotRandomizer/BotRandomizer.dll', b'x')
            archive.writestr('BotRandomizer/cosmetic_catalog.json', b'{}')
        data = buffer.getvalue()
        self.assertEqual(bot_skins._plugin_root(data), 'BotRandomizer/')
        with tempfile.TemporaryDirectory() as root:
            written = bot_skins._extract(data, Path(root), 'BotRandomizer/')
            self.assertEqual(sorted(written), ['BotRandomizer.dll', 'cosmetic_catalog.json'])
        evil = io.BytesIO()
        with zipfile.ZipFile(evil, 'w') as archive: archive.writestr('../escape.txt', b'x')
        with tempfile.TemporaryDirectory() as root, self.assertRaises(RuntimeError):
            bot_skins._extract(evil.getvalue(), Path(root) / 'inside')

    def test_metamod_mount_is_reversible_and_keeps_other_addons(self):
        source = ('"GameInfo"\n{\n\t"FileSystem"\n\t{\n\t\t"SearchPaths"\n\t\t{\n\t\t\tGame\tother_addon\n'
                  '\t\t\tGame\tcsgo\n\t\t}\n\t}\n}\n')
        with tempfile.TemporaryDirectory() as root:
            game = Path(root)
            (game / 'csgo').mkdir()
            (game / 'csgo/gameinfo.gi').write_text(source, encoding='utf-8', newline='')
            bot_skins._mount(game, True)
            mounted = (game / 'csgo/gameinfo.gi').read_text(encoding='utf-8')
            self.assertIn('Game\tcsgo/addons/metamod // cs2_gc bot skins (Metamod)', mounted)
            self.assertLess(mounted.index('csgo/addons/metamod'), mounted.index('Game\tcsgo\n'))
            self.assertIn('other_addon', mounted)
            self.assertEqual((game / 'csgo/gameinfo.gi.cs2_gc_bot_skins_backup').read_text(encoding='utf-8'), source)
            bot_skins._mount(game, False)
            self.assertEqual((game / 'csgo/gameinfo.gi').read_text(encoding='utf-8'), source)

    def test_foreign_framework_install_is_left_alone(self):
        with tempfile.TemporaryDirectory() as root:
            game = Path(root)
            (game / 'csgo/addons/metamod').mkdir(parents=True)
            (game / 'csgo/gameinfo.gi').write_text('"GameInfo" {}', encoding='utf-8')
            proxy = game / 'bin/win64'; proxy.mkdir(parents=True)
            with self.assertRaises(RuntimeError): bot_skins.install(proxy)


if __name__ == '__main__':
    unittest.main()

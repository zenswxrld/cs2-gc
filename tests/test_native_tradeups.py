from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import native_tradeups as native

GAMEINFO = '''\ufeff"GameInfo"
{
 FileSystem {
  SearchPaths {
   Game_LowViolence csgo_lv
   Game csgo/addons/other_mod // keep this addon
   Game csgo
   Game core
   Mod csgo
  }
 }
 Engine2 { "OtherSetting" "unchanged" }
}
'''


def schema_text():
    recipes = []
    for tracked in (False, True):
        for i, rarity in enumerate(native.RARITIES):
            quality = 'strange' if tracked else 'unique,tournament'
            kill = '"kill" { "field" "*kill_eater_score_type" "operator" "string==" "value" "0" }' if tracked else ''
            count = 5 if rarity == 'ancient' else 10
            recipes.append(f'''"{i + (10 if tracked else 0)}" {{
              "name" "#RT_MP_A" "category" "crafting" "filter" "-3" "disabled" "0" "di_A" "{count}"
              "input_items" {{ "{count}" {{ "conditions" {{
                "0" {{ "field" "*rarity" "operator" "string==" "value" "{rarity}" }}
                "1" {{ "field" "*quality" "operator" "string==" "value" "{quality}" }}
                "2" {{ "field" "craft_class" "operator" "string==" "value" "weapon" }} {kill}
              }} }} }}
              "output_items" {{ "unchanged" {{ "value" "strange" }} }}
            }}''')
    return '"items_game" { "items" { "1" { "name" "keep\\\\path" } } "recipes" { ' + '\n'.join(recipes) + ' } "other" "unchanged" }'


class NativeTradeUps(unittest.TestCase):
    def test_shared_native_recipes_allow_both_first_variants_without_extra_recipes(self):
        original = schema_text()
        changed, details = native.patch_recipes(original)
        recipes = native.parse(changed).one('items_game').one('recipes')
        self.assertEqual(len(recipes.children), 12)
        self.assertEqual(len(details['normal_recipes']), 6)
        self.assertEqual(native.patch_recipes(changed)[0], changed)
        for tracked in (False, True):
            for i, rarity in enumerate(native.RARITIES):
                recipe = recipes.one(str(i + (10 if tracked else 0)))
                self.assertEqual(recipe.text('disabled'), '1' if tracked else '0')
                conditions = recipe.one('input_items').children[0].one('conditions')
                quality = next(n for n in conditions.children if n.text('field') == '*quality').text('value')
                self.assertEqual(quality, 'strange' if tracked else 'unique,strange,tournament')
                self.assertEqual(recipe.one('output_items').one('unchanged').text('value'), 'strange')
        # Every other byte is preserved: exactly these six quality values and six disable flags changed.
        expected = original.replace('"value" "unique,tournament"', '"value" "unique,strange,tournament"')
        for i in range(10, 16):
            start = expected.index(f'"{i}" {{\n              "name"')
            end = expected.index('"disabled" "0"', start)
            expected = expected[:end] + expected[end:].replace('"disabled" "0"', '"disabled" "1"', 1)
        self.assertEqual(changed, expected)

    def test_ambiguous_or_changed_schema_is_rejected(self):
        for bad in (schema_text().replace('unique,tournament', 'unusual', 1),
                    schema_text().replace('"di_A" "10"', '"di_A" "9"', 1),
                    '"items_game" { "recipes" { } }', schema_text() + ' }'):
            with self.assertRaises((ValueError, KeyError)): native.patch_recipes(bad)

    def test_gameinfo_addon_mount_is_reversible_and_preserves_all_other_paths(self):
        for original in (GAMEINFO, GAMEINFO.replace('\n', '\r\n')):
            changed = native.mount_gameinfo(original)
            self.assertIn(native.MOUNT, changed)
            self.assertLess(changed.index(native.MOUNT), changed.index('Game_LowViolence'))
            self.assertEqual(native.mount_gameinfo(changed), changed)
            self.assertEqual(native.mount_gameinfo(changed, False), original)
        with self.assertRaises(ValueError): native.mount_gameinfo(GAMEINFO.replace('Game core', 'Game cs2_gc_native'))

    def test_prepare_keeps_source_and_other_addons_saves_backup_and_disables_cleanly(self):
        with tempfile.TemporaryDirectory() as folder:
            game = Path(folder) / 'game'
            proxy = game / 'bin/win64'; proxy.mkdir(parents=True)
            info = game / 'csgo/gameinfo.gi'; info.parent.mkdir()
            native.atomic_write(info, GAMEINFO)
            source = proxy / 'items_game.txt'; source.write_text(schema_text(), encoding='utf-8', newline='')
            self.assertIn('RESTART', native.prepare(proxy))
            self.assertIn('Mod\tcs2_gc_native', native.read_text(info))
            self.assertEqual(native.read_text(source), schema_text())
            self.assertEqual(native.read_text(info.with_name(info.name + '.cs2_gc_native_backup')), GAMEINFO)
            target = game / native.FOLDER / 'scripts/items/items_game.txt'
            before = target.stat().st_mtime_ns
            self.assertIn('installed', native.prepare(proxy))
            self.assertEqual(target.stat().st_mtime_ns, before)
            mounted = native.read_text(info).replace('Game core', 'Game my_new_addon\n   Game core')
            native.atomic_write(info, mounted)
            self.assertIn('disabled', native.prepare(proxy, False))
            self.assertNotIn(native.MOUNT, native.read_text(info))
            self.assertNotIn('Mod\tcs2_gc_native', native.read_text(info))
            self.assertIn('Game my_new_addon', native.read_text(info))
            self.assertEqual(native.read_text(source), schema_text())

    def test_external_schema_edits_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            game = Path(folder) / 'game'
            proxy = game / 'bin/win64'; proxy.mkdir(parents=True)
            info = game / 'csgo/gameinfo.gi'; info.parent.mkdir()
            info.write_text(GAMEINFO); (proxy / 'items_game.txt').write_text(schema_text())
            native.prepare(proxy)
            target = game / native.FOLDER / 'scripts/items/items_game.txt'
            target.write_text('externally edited')
            with self.assertRaises(ValueError): native.prepare(proxy)
            self.assertEqual(target.read_text(), 'externally edited')


if __name__ == '__main__': unittest.main()

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
import grant_test_items as tool


class TestGrants(unittest.TestCase):
    def test_additive_grant_preserves_profile_currency_and_original_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            schema, inventory, pools = (root / name for name in ('schema.txt', 'inventory.txt', 'gold.txt'))
            schema.write_text('"items_game" { "items" { } }')
            pools.write_text('"gold_pools" { }')
            before = ('"inventory" { "next_id" "2" // keep this comment\n'
                      '"armory_credits" "0" "xp_tracks" "100 400" '
                      '"progression" { "level" "2" "xp" "123" "reward_total" "5123" } '
                      '"items" { "1" { "def_index" "7" "paint_kit" "10" "wear" "0.2" '
                      '"seed" "1" "stattrak" "0" } } }')
            inventory.write_text(before)
            added = [[('def_index', '9'), ('paint_kit', '20'), ('wear', '0.3'), ('seed', '2'), ('stattrak', '0')]]
            with patch.object(tool, 'test_items', return_value=added):
                count, backup = tool.grant(schema, inventory, pools)
            self.assertEqual(count, 1)
            self.assertEqual(backup.read_text(), before)
            after = inventory.read_text()
            self.assertIn('"next_id" "3"', after)
            self.assertIn('"armory_credits" "0" "xp_tracks" "100 400"', after)
            self.assertIn('"level" "2" "xp" "123" "reward_total" "5123"', after)
            self.assertIn('// keep this comment', after)
            items = tool.as_dict(tool.as_dict(tool.parse(after))['inventory'])['items']
            self.assertEqual([item[0] for item in items], ['1', '2'])

    def test_care_package_preview_next_ids_follow_the_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            inventory = Path(directory) / 'inventory.txt'
            item = '"def_index" "7" "paint_kit" "0" "wear" "0" "seed" "0" "stattrak" "0"'
            previews = ' '.join('"%d" { %s }' % (i, item) for i in range(10, 14))
            inventory.write_text('"inventory" { "next_id" "14" "items" { "1" { %s } } "last_care_generation" "2" '
                                 '"care_packages" { "2" { "next_id" "14" "items" { %s } } } }' % (item, previews))
            count, _ = tool.add_items(inventory, [[('def_index', '9'), ('paint_kit', '0'), ('wear', '0'),
                                                   ('seed', '0'), ('stattrak', '0')]] * 2)
            self.assertEqual(count, 2)
            root = tool.as_dict(tool.as_dict(tool.parse(inventory.read_text()))['inventory'])
            self.assertEqual(root['next_id'], '16')
            self.assertEqual(tool.as_dict(tool.as_dict(root['care_packages'])['2'])['next_id'], '16')
            self.assertEqual([key for key, _ in root['items']], ['1', '14', '15'])
            self.assertEqual(len(tool.as_dict(tool.as_dict(root['care_packages'])['2'])['items']), 4)

    def test_custom_cases_are_added_by_generated_schema_name(self):
        import grant_custom_cases as cases
        schema = '"items_game" { "items" { "5024" { "name" "crate_cs2gc_gauntlet" } "5023" { "name" "crate_cs2gc_black_market" } } }'
        added = cases.case_items(schema, {cases.CASES['gauntlet']: 3, cases.CASES['black_market']: 1})
        self.assertEqual([dict(item)['def_index'] for item in added], ['5024'] * 3 + ['5023'])
        with self.assertRaises(ValueError): cases.case_items('"items_game" { "items" { } }', {cases.CASES['gauntlet']: 1})
        self.assertEqual(cases.case_items('"items_game" { "items" { } }', {cases.CASES['gauntlet']: 0}), [])

    def test_invalid_id_does_not_overwrite_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            schema, inventory, pools = (root / name for name in ('schema.txt', 'inventory.txt', 'gold.txt'))
            schema.write_text('"items_game" { }')
            pools.write_text('"gold_pools" { }')
            before = '"inventory" { "next_id" "1" "items" { "1" { } } }'
            inventory.write_text(before)
            with patch.object(tool, 'test_items', return_value=[]), self.assertRaises(ValueError):
                tool.grant(schema, inventory, pools)
            self.assertEqual(inventory.read_text(), before)


if __name__ == '__main__':
    unittest.main()

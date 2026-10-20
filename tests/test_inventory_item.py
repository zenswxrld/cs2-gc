import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("inventory_item", Path(__file__).parents[1] / "tools/inventory_item.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

# Synthetic schema shaped like items_game.txt; not real game data.
SCHEMA = '''"items_game"
{
    "rarities" { "common" { "value" "1" } "uncommon" { "value" "2" } "mythical" { "value" "4" }
                 "legendary" { "value" "5" } "ancient" { "value" "6" } }
    "prefabs" { "rifle_prefab" { "item_rarity" "uncommon" } "pistol_prefab" { "item_rarity" "common" } }
    "items" { "7" { "name" "weapon_ak" "prefab" "rifle_prefab" } "36" { "name" "weapon_pistol" "prefab" "pistol_prefab" }
              "99" { "name" "weapon_none" } }
    "paint_kits" { "282" { "name" "kit_mythical" "wear_remap_min" "0.10" "wear_remap_max" "0.70" }
                   "801" { "name" "kit_legendary" } "5" { "name" "kit_ancient" } "6" { "name" "kit_norarity" } }
    "paint_kits_rarity" { "kit_mythical" "mythical" "kit_legendary" "legendary" "kit_ancient" "ancient" }
    "paint_kits" { "1000" { "name" "kit_late" } }
    "paint_kits_rarity" { "kit_late" "mythical" }
}'''


class InventoryItemTests(unittest.TestCase):
    def entry(self, weapon, kit):
        return tool.find_entry(tool.collect(tool.parse(SCHEMA)), weapon, kit)

    def test_rarity_is_finish_plus_weapon_minus_one_capped(self):
        self.assertEqual(self.entry("weapon_ak", "kit_mythical")["rarity"], 5)
        self.assertEqual(self.entry("weapon_ak", "kit_legendary")["rarity"], 6)
        self.assertEqual(self.entry("weapon_ak", "kit_ancient")["rarity"], 6)  # 7 capped to Covert
        self.assertEqual(self.entry("weapon_pistol", "kit_mythical")["rarity"], 4)

    def test_indices_ranges_and_repeated_sections(self):
        entry = self.entry("weapon_ak", "kit_mythical")
        self.assertEqual((entry["def_index"], entry["paint_kit"]), (7, 282))
        self.assertEqual((entry["wear_min"], entry["wear_max"]), (0.1, 0.7))
        self.assertEqual(self.entry("weapon_ak", "kit_late")["paint_kit"], 1000)  # from the repeated section

    def test_unknown_or_incomplete_entries_rejected(self):
        for weapon, kit in (("nope", "kit_mythical"), ("weapon_ak", "nope"), ("weapon_none", "kit_mythical"),
                            ("weapon_ak", "kit_norarity")):
            with self.assertRaises(ValueError):
                self.entry(weapon, kit)

    def test_render_validates_and_formats(self):
        entry = self.entry("weapon_ak", "kit_mythical")
        text = tool.render(entry, 3, 0.15, 661)
        self.assertIn('"def_index"\t"7"', text)
        self.assertIn('"paint_kit"\t"282"', text)
        self.assertIn('"rarity"\t"5"', text)
        self.assertIn('"wear"\t"0.15"', text)
        with self.assertRaises(ValueError):
            tool.render(entry, 1, 0.9, 1)   # outside the finish's wear range
        with self.assertRaises(ValueError):
            tool.render(entry, 1, 0.2, 0)   # seed out of range

    def test_malformed_schema_rejected(self):
        for bad in ('"a" {', '"a" }', '{ }', '"a"'):
            with self.assertRaises(ValueError):
                tool.parse(bad)
        with self.assertRaises(ValueError):
            tool.collect(tool.parse('"other" { }'))

    def test_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "items_game.txt"
            path.write_text(SCHEMA)
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                self.assertEqual(tool.main([str(path), "weapon_ak", "kit_legendary", "--id", "4", "--wear", "0.2", "--seed", "12"]), 0)
            self.assertIn('"4"', out.getvalue())
            self.assertIn('"rarity"\t"6"', out.getvalue())
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(tool.main([str(path), "weapon_ak", "nope"]), 1)


if __name__ == "__main__":
    unittest.main()

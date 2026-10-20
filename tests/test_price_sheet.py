import contextlib
import importlib.util
import io
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

spec = importlib.util.spec_from_file_location("price_sheet", Path(__file__).parents[1] / "tools/price_sheet.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

# Synthetic data shaped like the real sheet and items_game.txt; not real game data.
PRICES = [("USD", 249), ("AUD", 355), ("EUR", 219)]
SHEET = [("store", [
    ("store_banner_layout", [("1201", [("custom_format", "single")]), ("7042", [("custom_format", "coupon"), ("w", 18.5)])]),
    ("store_metadata", [("categories", [("Misc", [("label_token", "#Store_Misc"), ("home", 1), ("default", 1)])])]),
    ("entries", [
        ("Weapon Case Key", [("item_link", "Weapon Case Key"), ("category_tags", "Misc"), ("prices", list(PRICES))]),
        ("Name Tag", [("item_link", "Name Tag"), ("category_tags", "Misc"), ("prices", list(PRICES))]),
    ]),
    ("currencies", [("USD", 88888), ("AUD", tool.UInt64(2**40))]),
])]

ITEMS_GAME = '''"items_game"
{
    "prefabs"
    {
        "weapon_case_base" { }
        "weapon_case" { "prefab" "weapon_case_base" "associated_item" "1203" }
        "weapon_case_souvenirpkg" { "prefab" "weapon_case_base" }
        "sticker_capsule" { "prefab" "weapon_case_base" }
    }
    "items"
    {
        "1203" { "name" "Weapon Case Key" }
        "9000" { "name" "extra_key" }
        "4001" { "name" "crate_one" "prefab" "weapon_case"
                 "attributes" { "set supply crate series" { "value" "1" } } }
        "4002" { "name" "crate_two" "prefab" "weapon_case" "associated_items" { "9000" "1" }
                 "attributes" { "set supply crate series" { "value" "2" } } }
        "4003" { "name" "souvenir" "prefab" "weapon_case_souvenirpkg"
                 "attributes" { "set supply crate series" { "value" "3" } } }
        "4004" { "name" "capsule" "prefab" "sticker_capsule"
                 "attributes" { "set supply crate series" { "value" "4" } } }
        "4005" { "name" "no_series" "prefab" "weapon_case" }
        "4006" { "name" "keyless" "prefab" "weapon_case_base"
                 "attributes" { "set supply crate series" { "value" "5" } } }
    }
}'''


class PriceSheetTests(unittest.TestCase):
    def message(self, tree=None):
        return tool.build_message(tool.encode_kv(tree if tree is not None else SHEET))

    def test_kv_round_trip_including_floats_and_64_bit_values(self):
        raw = tool.encode_kv(SHEET)
        self.assertEqual(tool.encode_kv(tool.decode_kv(raw)), raw)
        decoded = tool.decode_kv(raw)
        currencies = dict(dict(decoded)["store"])["currencies"]
        self.assertIsInstance(dict(currencies)["AUD"], tool.UInt64)  # stays 64-bit
        self.assertNotIsInstance(dict(currencies)["USD"], tool.UInt64)

    def test_container_round_trip_and_header(self):
        raw = tool.encode_kv(SHEET) * 20
        container = tool.compress(raw)
        self.assertEqual(container[:4], b"LZMA")
        self.assertEqual(struct.unpack_from("<II", container, 4), (len(raw), len(container) - 17))
        self.assertEqual(container[12:17].hex(), "5d00000400")
        self.assertEqual(tool.decompress(container), raw)

    def test_bad_containers_rejected(self):
        good = tool.compress(b"hello world" * 50)
        for bad in (b"", b"LZMA", b"NOPE" + good[4:], good[:20],
                    good[:4] + struct.pack("<II", 1 << 30, 5) + good[12:],
                    good[:4] + struct.pack("<II", 999, len(good) - 17) + good[12:]):
            with self.assertRaises((ValueError, tool.lzma.LZMAError)):
                tool.decompress(bad)

    def test_message_carries_result_and_a_content_derived_version(self):
        message = self.message()
        result, version, container = tool.read_message(message)
        self.assertEqual(result, 1)
        raw = tool.decompress(container)
        self.assertEqual(version, struct.pack("<I", zlib.crc32(raw)))
        with self.assertRaises(ValueError):
            tool.read_message(tool.write_field(1, 0, 1))  # no price sheet field
        with self.assertRaises(ValueError):
            tool.read_message(b"\x42\x09abc")  # field overruns the message

    def test_find_cases_picks_only_keyed_standard_cases(self):
        sections = tool.items_game.collect(tool.items_game.parse(ITEMS_GAME))
        self.assertEqual(sorted(tool.find_cases(sections)),
                         [("crate_one", "Weapon Case Key"), ("crate_two", "extra_key")])

    def test_add_entries_only_adds_missing_ones(self):
        tree = tool.decode_kv(tool.encode_kv(SHEET))
        added = tool.add_entries(tree, ["crate_one", "Weapon Case Key", "crate_one", None, "extra_key"], "Weapon Case Key")
        self.assertEqual(added, 2)  # crate_one once, extra_key; the existing key and duplicates are skipped
        entries = dict(tool.section(tree, "store", "entries"))
        self.assertEqual(dict(entries["crate_one"])["item_link"], "crate_one")
        self.assertEqual(dict(entries["crate_one"])["category_tags"], "Misc")
        self.assertEqual(dict(dict(entries["crate_one"])["prices"]), dict(PRICES))
        with self.assertRaises(ValueError):
            tool.add_entries(tree, ["x"], "No Such Entry")

    def test_unrecognised_sheets_are_refused_not_edited(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "2501.bin"
            # a sheet whose KeyValues carry an unsupported type byte
            bad_raw = b"\x00store\x00\x09x\x00\x0b\x0b"
            path.write_bytes(tool.write_field(1, 0, 1) + tool.write_field(8, 2, tool.compress(bad_raw)))
            with self.assertRaises(ValueError):
                tool.load_sheet(path)
            with self.assertRaisesRegex(ValueError, "no section"):
                tool.section([("other", [])], "store", "entries")

    def test_cli_adds_cases_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temp:
            sheet = Path(temp) / "2501.bin"
            sheet.write_bytes(self.message())
            games = Path(temp) / "items_game.txt"
            games.write_text(ITEMS_GAME)
            out = Path(temp) / "new.bin"
            with contextlib.redirect_stdout(io.StringIO()) as captured:
                self.assertEqual(tool.main(["add-cases", str(sheet), str(games), "--out", str(out)]), 0)
            self.assertIn("2 cases found", captured.getvalue())
            entries = tool.section(tool.load_sheet(out), "store", "entries")
            self.assertEqual([k for k, _ in entries], ["Weapon Case Key", "Name Tag", "crate_one", "crate_two", "extra_key"])
            before = out.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(tool.main(["add-cases", str(sheet), str(games), "--out", str(out)]), 1)
                self.assertEqual(tool.main(["dump", str(Path(temp) / "missing.bin")]), 1)
            self.assertEqual(out.read_bytes(), before)
            with contextlib.redirect_stdout(io.StringIO()) as dumped:
                self.assertEqual(tool.main(["dump", str(out), "--limit", "2"]), 0)
            self.assertIn("5 store entries", dumped.getvalue())


if __name__ == "__main__":
    unittest.main()

import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("inspect_cs2", Path(__file__).parents[1] / "tools/inspect_cs2.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def write_pe(path, machine=0x8664, magic=0x20B):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = bytearray(512)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 128)
    data[128:132] = b"PE\0\0"
    struct.pack_into("<HHI", data, 132, machine, 1, 123456)
    struct.pack_into("<H", data, 148, 240)
    struct.pack_into("<H", data, 152, magic)
    path.write_bytes(data)


class InspectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "steamapps/common/Counter-Strike Global Offensive"
        for relative in probe.MODULES:
            write_pe(self.root / relative)

    def test_complete_build_fingerprints_and_whitelisted_metadata(self):
        inf = self.root / "game/csgo/steam.inf"
        inf.write_text("PatchVersion=1.2.3\nappID=730\nPrivateAccountValue=do-not-copy\n")
        manifest = self.root.parent.parent / "appmanifest_730.acf"
        manifest.write_text('"AppState" { "buildid" "1234" "LastOwner" "do-not-copy" }')
        report = probe.inspect(self.root)
        self.assertTrue(report["layout_complete"])
        self.assertEqual(report["runtime_compatibility"], "unverified")
        self.assertEqual(report["steam_build_id"], "1234")
        self.assertEqual(report["steam_inf"], {"PatchVersion": "1.2.3", "appID": "730"})
        first = self.root / probe.MODULES[0]
        self.assertEqual(report["modules"][0]["sha256"], hashlib.sha256(first.read_bytes()).hexdigest())
        self.assertNotIn(str(self.root), json.dumps(report))
        self.assertNotIn("do-not-copy", json.dumps(report))

    def test_missing_and_32bit_modules_are_not_ready(self):
        (self.root / probe.MODULES[0]).unlink()
        write_pe(self.root / probe.MODULES[1], machine=0x14C, magic=0x10B)
        report = probe.inspect(self.root)
        self.assertFalse(report["layout_complete"])
        self.assertFalse(report["modules"][0]["present"])
        self.assertFalse(report["modules"][1]["x64"])

    def test_malformed_pe_is_a_reported_error(self):
        path = self.root / probe.MODULES[0]
        for data in (b"", b"MZ", b"MZ" + bytes(62), b"Z" * 100):
            with self.subTest(data=data):
                path.write_bytes(data)
                report = probe.inspect(self.root)
                self.assertFalse(report["layout_complete"])
                self.assertIn("error", report["modules"][0])

    def test_refuses_game_directory_outputs_and_existing_files(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(probe.main([str(self.root), "--out", str(self.root / "report.json")]), 1)
        self.assertFalse((self.root / "report.json").exists())
        output = Path(self.temp.name) / "report.json"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(probe.main([str(self.root), "--out", str(output)]), 0)
        original = output.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(probe.main([str(self.root), "--out", str(output)]), 1)
        self.assertEqual(original, output.read_bytes())

    def test_empty_directory_returns_incomplete_not_success(self):
        empty = Path(self.temp.name) / "empty"
        empty.mkdir()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(probe.main([str(empty)]), 2)


if __name__ == "__main__":
    unittest.main()

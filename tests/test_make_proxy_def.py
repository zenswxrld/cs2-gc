import contextlib
import importlib.util
import io
from pathlib import Path
import struct
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("make_proxy_def", Path(__file__).parents[1] / "tools/make_proxy_def.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

RVA = 0x1000  # section virtual address == file offset + (RVA - 0x400)


def fake_dll(names, machine=0x8664, magic=0x20B, forwarder_index=None):
    # Synthetic fixture: a minimal PE with one section holding an export directory.
    section = bytearray()
    count = len(names)
    dir_size = 40
    functions_off = dir_size
    names_off = functions_off + 4 * count
    ordinals_off = names_off + 4 * count
    strings_off = ordinals_off + 2 * count
    strings = bytearray()
    name_rvas = []
    for name in names:
        name_rvas.append(RVA + strings_off + len(strings))
        strings += name.encode() + b"\0"
    section += struct.pack("<IIHHIIIIIII", 0, 0, 0, 0, 0, 1, count, count, RVA + functions_off, RVA + names_off,
                           RVA + ordinals_off)
    for index in range(count):
        target = RVA + 0x800  # code, outside the export directory
        if index == forwarder_index:
            target = RVA + 4  # inside the export directory: a forwarder string
        section += struct.pack("<I", target)
    for rva in name_rvas:
        section += struct.pack("<I", rva)
    for index in range(count):
        section += struct.pack("<H", index)
    section += strings
    section = bytes(section).ljust(0x900, b"\0")

    header = bytearray(0x400)
    header[:2] = b"MZ"
    struct.pack_into("<I", header, 0x3C, 0x80)
    header[0x80:0x84] = b"PE\0\0"
    optional_size = 240
    struct.pack_into("<HHIIIHH", header, 0x84, machine, 1, 0, 0, 0, optional_size, 0)
    struct.pack_into("<H", header, 0x98, magic)
    struct.pack_into("<II", header, 0x98 + 112, RVA, dir_size + 10 * count + len(strings))
    sect = 0x98 + optional_size
    header[sect:sect + 8] = b".edata\0\0"
    struct.pack_into("<IIII", header, sect + 8, len(section), RVA, len(section), 0x400)
    return bytes(header) + section


class ProxyDefTests(unittest.TestCase):
    def test_names_read_from_export_table(self):
        names = ["SteamAPI_Init", "SteamInternal_FindOrCreateUserInterface", "SteamAPI_Shutdown"]
        self.assertEqual(tool.export_names(fake_dll(names)), names)

    def test_forwarders_and_override(self):
        names = ["SteamAPI_Init", *tool.OVERRIDDEN]
        text = tool.render(names, "steam_api64_real")
        self.assertIn("    SteamAPI_Init = steam_api64_real.SteamAPI_Init\n", text)
        self.assertIn("    SteamInternal_FindOrCreateUserInterface\n", text)
        for name in tool.OVERRIDDEN:
            self.assertIn(f"    {name}\n", text)
            self.assertNotIn(f"{name} =", text)

    def test_missing_override_and_bad_target_rejected(self):
        with self.assertRaisesRegex(ValueError, "does not export"):
            tool.render(["SteamAPI_Init"], "steam_api64_real")
        with self.assertRaisesRegex(ValueError, "does not export"):
            tool.render(["SteamInternal_FindOrCreateUserInterface"], "steam_api64_real")  # only one override
        with self.assertRaises(ValueError):
            tool.render(list(tool.OVERRIDDEN), "evil;name")

    def test_rejects_bad_modules(self):
        good = ["a_one", *tool.OVERRIDDEN]
        with self.assertRaises(ValueError):
            tool.export_names(fake_dll(good, machine=0x14C))
        with self.assertRaises(ValueError):
            tool.export_names(fake_dll(good, magic=0x10B))
        with self.assertRaisesRegex(ValueError, "forwarder"):
            tool.export_names(fake_dll(good, forwarder_index=0))
        with self.assertRaises(ValueError):
            tool.export_names(b"not a pe" * 64)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            tool.export_names(fake_dll(["same", "same"]))
        with self.assertRaisesRegex(ValueError, "Unusable"):
            tool.export_names(fake_dll(["bad name;"]))

    def test_truncated_files_never_crash(self):
        data = fake_dll(["SteamAPI_Init", *tool.OVERRIDDEN])
        for cut in range(0, len(data), 13):
            with contextlib.suppress(ValueError):
                tool.export_names(data[:cut])

    def test_cli_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temp:
            dll = Path(temp) / "steam_api64.dll"
            dll.write_bytes(fake_dll(["SteamAPI_Init", *tool.OVERRIDDEN]))
            out = Path(temp) / "out.def"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(tool.main([str(dll), "--out", str(out)]), 0)
            before = out.read_text()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(tool.main([str(dll), "--out", str(out)]), 1)
            self.assertEqual(out.read_text(), before)


if __name__ == "__main__":
    unittest.main()

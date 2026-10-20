import contextlib
import importlib.util
import io
from pathlib import Path
import struct
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("extract_gc_protocol",
                                              Path(__file__).parents[1] / "tools/extract_gc_protocol.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def varint(value):
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def field(number, payload):
    if isinstance(payload, int):
        return varint(number << 3) + varint(payload)
    return varint(number << 3 | 2) + varint(len(payload)) + payload


def enum_proto(name, values):
    body = field(1, name.encode())
    for label, number in values:
        body += field(2, field(1, label.encode()) + field(2, number & ((1 << 64) - 1)))
    return field(5, body)


def descriptor(filename, enums):
    # Synthetic fixture: shaped like a FileDescriptorProto, not real game data.
    blob = field(1, filename.encode()) + b"".join(enum_proto(n, v) for n, v in enums.items())
    return blob + field(12, b"proto2")


def fake_dll(descriptors, machine=0x8664):
    header = bytearray(256)
    header[:2] = b"MZ"
    struct.pack_into("<I", header, 0x3C, 128)
    header[128:132] = b"PE\0\0"
    struct.pack_into("<HHI", header, 132, machine, 1, 777)
    return bytes(header) + b"\x00\xff junk \x0a\x03abc" + b"".join(d + b"\x00\x00\xfe" for d in descriptors)


FULL = {
    "EGCBaseClientMsg": [("k_EMsgGCClientWelcome", 4004), ("k_EMsgGCClientHello", 4006)],
    "EGCBaseMsg": [("k_EMsgGCSystemMessage", 4001)],
    "ESOMsg": [("k_ESOMsg_Create", 21), ("k_ESOMsg_CacheSubscribed", 24)],
    "EGCItemMsg": [("k_EMsgGCBase", 1000)],
    "ECsgoGCMsg": [("k_EMsgGCCStrike15_v2_Base", 9100)],
    "EGCMsgResponse": [("k_EGCMsgResponseOK", 0)],
    "GCConnectionStatus": [("GCConnectionStatus_HAVE_SESSION", 0), ("GCConnectionStatus_NO_SESSION", 2)],
}


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)

    def write(self, data):
        path = self.dir / "client.dll"
        path.write_bytes(data)
        return path

    def test_ids_come_from_embedded_descriptors(self):
        half = dict(list(FULL.items())[:3])
        rest = dict(list(FULL.items())[3:])
        path = self.write(fake_dll([descriptor("gcsystemmsgs.proto", half), descriptor("other.proto", rest)]))
        text = tool.generate(path, "123")
        self.assertIn("inline constexpr std::uint32_t k_EMsgGCClientHello = 4006;", text)
        self.assertIn("namespace ESOMsg", text)
        self.assertIn("k_EMsgGCCStrike15_v2_Base = 9100;", text)
        self.assertIn("// other.proto", text)
        self.assertIn("steam build id (supplied by the user): 123", text)
        self.assertIn("coff timestamp: 777", text)

    def test_missing_enum_fails_loudly(self):
        partial = {k: v for k, v in FULL.items() if k != "ESOMsg"}
        path = self.write(fake_dll([descriptor("fixture_a.proto", partial)]))
        with self.assertRaisesRegex(ValueError, "ESOMsg"):
            tool.generate(path)

    def test_rejects_non_x64_and_non_pe(self):
        with self.assertRaises(ValueError):
            tool.generate(self.write(fake_dll([descriptor("fixture_a.proto", FULL)], machine=0x14C)))
        with self.assertRaises(ValueError):
            tool.generate(self.write(b"not a pe at all" * 20))

    def test_hostile_enumerator_names_and_truncation(self):
        bad = dict(FULL, ESOMsg=[("k_ok", 1), ("bad name; evil", 2)])
        with self.assertRaisesRegex(ValueError, "Unusable"):
            tool.generate(self.write(fake_dll([descriptor("fixture_a.proto", bad)])))
        blob = descriptor("fixture_a.proto", FULL)
        for cut in range(0, len(blob), 7):  # truncated blobs must never crash the scanner
            tool.embedded_enums(fake_dll([blob[:cut]]))

    def test_negative_enum_numbers_do_not_become_huge(self):
        bad = dict(FULL, EGCMsgResponse=[("k_neg", -1)])
        with self.assertRaisesRegex(ValueError, "does not fit"):
            tool.generate(self.write(fake_dll([descriptor("fixture_a.proto", bad)])))

    def test_cli_never_overwrites_and_validates_build_id(self):
        dll = self.write(fake_dll([descriptor("fixture_a.proto", FULL)]))
        out = self.dir / "gc.h"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(tool.main([str(dll), "--out", str(out)]), 0)
        before = out.read_text()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(tool.main([str(dll), "--out", str(out)]), 1)
            self.assertEqual(tool.main([str(dll), "--out", str(self.dir / "x.h"), "--build-id", "1;rm"]), 1)
        self.assertEqual(out.read_text(), before)


if __name__ == "__main__":
    unittest.main()

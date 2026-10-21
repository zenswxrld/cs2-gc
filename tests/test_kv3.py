import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import kv3
from kv3 import Node


def color(name, values):
    return Node(kv3.OBJECT, [('m_name', Node(kv3.STRING, name)),
                             ('m_value', Node(kv3.ARRAY_TYPE_BYTE_LENGTH, [Node(kv3.FLOAT, v) for v in values], 0, kv3.FLOAT))])


class KV3(unittest.TestCase):
    def test_version5_round_trip_and_resource_blocks(self):
        root = Node(kv3.OBJECT, [
            ('m_materialName', Node(kv3.STRING, 'materials/x.vmat')),
            ('m_intParams', Node(kv3.ARRAY, [Node(kv3.OBJECT, [('m_name', Node(kv3.STRING, 'F_PAINT_STYLE')),
                                                               ('m_nValue', Node(kv3.INT32, 5))])])),
            ('m_vectorParams', Node(kv3.ARRAY, [color('g_vColor0', [0.5, 0.25, 1.0, 1.0])])),
            ('m_flag', Node(kv3.BOOLEAN_TRUE, True)), ('m_empty', Node(kv3.ARRAY, [])),
            ('m_big', Node(kv3.UINT64, 2 ** 40)), ('m_double', Node(kv3.DOUBLE, 1.5)), ('m_null', Node(kv3.NULL, None)),
        ])
        guid = bytes(range(16))
        block = kv3.write_kv3(guid, root)
        self.assertEqual(kv3.read_kv3(block), (guid, root))
        data = kv3.write_resource(0, [['RED2', b'abc'], ['DATA', block]])
        version, blocks = kv3.read_resource(data)
        self.assertEqual([name for name, _ in blocks], ['RED2', 'DATA'])
        self.assertEqual(blocks[0][1], b'abc')
        self.assertEqual(kv3.read_kv3(blocks[1][1])[1], root)

    def test_lz4_block(self):
        # literal "abc" then a 6-byte match at offset 3 -> "abcabcabc"
        self.assertEqual(kv3.lz4_block_decompress(bytes([0x32]) + b'abc' + bytes([3, 0]), 9), b'abcabcabc')


if __name__ == '__main__':
    unittest.main()

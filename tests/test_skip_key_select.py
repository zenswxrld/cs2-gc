import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import skip_key_select

SOURCE = """x;
                    $.DispatchEvent('ContextMenuEvent', '');
                    return;
                }
                $.DispatchEvent('ShowSelectItemForCapabilityPopup', id, '', 'decodable');
y = InventoryAPI.GetChosenActionItemIDByIndex(a, 'decodable', i);
"""


class SkipKeySelect(unittest.TestCase):
    def test_single_key_opens_the_unlock_popup_and_others_keep_the_picker(self):
        patched = skip_key_select.patch(SOURCE)
        self.assertIn("tool_id: InventoryAPI.GetChosenActionItemIDByIndex(id, 'decodable', 0)", patched)
        self.assertIn("GetChosenActionItemsCount(id, 'decodable') === 1", patched)
        self.assertTrue(patched.rstrip().endswith("GetChosenActionItemIDByIndex(a, 'decodable', i);"))
        self.assertEqual(patched.count("ShowSelectItemForCapabilityPopup"), 1)  # still the fallback
        with self.assertRaises(ValueError): skip_key_select.patch(patched)
        with self.assertRaises(ValueError): skip_key_select.patch('nothing here')


if __name__ == '__main__':
    unittest.main()

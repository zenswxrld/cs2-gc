import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import native_knife_reel as reel

SOURCE = """    function _ShowUnlockAnimation() {
        const caseId = InspectShared.GetPopupSetting('item_id');
        const lootListCount = InventoryAPI.GetLootListItemsCount(caseId);
        if (lootListCount <= 1) {
            _SetUpCaseOpeningCountdown();
        }
        else {
            _SetUpCaseOpeningScroll();
        }
    }
"""


class KnifeReel(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node required')
    def test_only_the_black_market_case_swaps_the_countdown_for_a_knife_reel(self):
        script = '''const assert = require('assert'); let calls = [], data = {}, name = 'crate_cs2gc_black_market';
const InspectShared = {GetPopupSetting: () => '9'};
const InventoryAPI = {GetLootListItemsCount: () => 1, GetItemDefinitionName: () => name,
                      GetFauxItemIDFromDefAndPaintIndex: (d, p) => d + ':' + p};
const $ = {GetContextPanel: () => ({Data: () => data})};
function _SetUpCaseOpeningCountdown() { calls.push('countdown'); }
function _SetUpCaseOpeningScroll() { calls.push('scroll'); }
''' + reel.patch(SOURCE, [[507, 38], [500, 30001]]) + '''
_ShowUnlockAnimation();
assert.deepEqual(calls, ['scroll']);
assert.deepEqual(data.aItemsInLootlist, [{id: '507:38', weight: 1}, {id: '500:30001', weight: 1}]);
assert.equal(data.unusualItemImagePath, '');
name = 'crate_operation_ii'; calls = []; _ShowUnlockAnimation(); assert.deepEqual(calls, ['countdown']);
'''
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_layout_change_is_refused(self):
        with self.assertRaises(ValueError): reel.patch('nothing', [])
        with self.assertRaises(ValueError): reel.patch(reel.patch(SOURCE, []), [])


if __name__ == '__main__':
    unittest.main()

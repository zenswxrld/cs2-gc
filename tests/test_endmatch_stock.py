import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import native_endmatch_stock as stock
import gameplay_config

RANK = """    function _DisplayMe() {
        if (!_m_cP || !_m_cP.IsValid())
            return;
""" + stock.RANK_ANCHOR + """
        return oXpData;
    }
"""
SKILL = """    function _DisplayMe() {
        if (!_m_cP || !_m_cP.IsValid())
            return false;
        _Reset();
""" + stock.SKILL_ANCHOR + """
        return localPlayerUpdate;
    }
""" + stock.SKILL_START + """
            shown = true;
        }
        else { skipped = true; }
    }
"""
MOCKS = """
const assert = require('assert');
let engineReady = false, level = 7, xp = 4800, rating = 11300, wins = 12, queued = false, scheduled = [];
const _m_cP = {IsValid: () => true, _data: {m_retries: 0}, Data() { return this._data; }};
function _Reset() {}
const MockAdapter = {bXpDataReady: () => engineReady, XPDataJSO: () => 'engine', bSkillgroupDataReady: () => engineReady,
                     SkillgroupDataJSO: () => ({me: 'engine'}), GetLocalPlayerXuid: () => 'me'};
const MyPersonaAPI = {GetElevatedState: () => 'elevated', GetXpPerLevel: () => 5000, GetCurrentLevel: () => level,
                      GetCurrentXp: () => xp, GetXuid: () => 'me'};
const FriendsListAPI = {GetFriendCompetitiveWins: () => wins, GetFriendCompetitiveRank: () => rating};
const GameStateAPI = {IsDemoOrHltv: () => false, IsQueuedMatchmaking: () => queued};
const $ = {Schedule: (delay, fn) => scheduled.push(fn)};
var EndOfMatch = {LocalBaseline: {level: 7, xp: 4000, rating: 11000, wins: 11}};
let shown = false, skipped = false;
"""


@unittest.skipUnless(shutil.which('node'), 'Node required for the end-of-match fixtures')
class StockEndOfMatch(unittest.TestCase):
    def run_node(self, script):
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_xp_bar_uses_local_progress_across_a_level_up(self):
        self.run_node(MOCKS + stock.patch_rank(RANK) + """
level = 8; xp = 300;
assert.deepEqual(_DisplayMe(), {current_level: 7, current_xp: 4000, xp_progress_data: [{xp_points: 1300, xp_category: 1}]});
level = 7; xp = 4000; assert.equal(_DisplayMe(), false);         // nothing earned: stock skip
engineReady = true; assert.equal(_DisplayMe(), 'engine');          // real data wins
engineReady = false; queued = true; level = 9; assert.equal(_DisplayMe(), false);
""")

    def test_rating_reveal_uses_the_local_change_and_waits_for_it(self):
        config = gameplay_config.DEFAULTS
        self.run_node(MOCKS + stock.patch_skillgroup(SKILL, config) + """
assert.deepEqual(_DisplayMe(), {old_rank: 11000, new_rank: 11300, num_wins: 12, rank_change: 300, rank_type: 'Premier'});
EndOfMatch.LocalBaseline = {level: 1, xp: 0, rating: 0, wins: 4}; wins = 5; rating = 0;
assert.deepEqual(_DisplayMe(), {old_rank: 0, new_rank: 0, num_wins: 5, rank_change: 0, rank_type: 'Premier'});
// No update yet: Start waits (up to 8 half-second retries), then shows once the rating arrives.
wins = 4; Start(); assert.equal(scheduled.length, 1); assert.equal(shown || skipped, false);
wins = 5; scheduled.pop()(); assert.equal(shown, true);
""")

    def test_layout_changes_are_refused(self):
        with self.assertRaises(ValueError): stock.patch_rank('function _DisplayMe() {}')
        with self.assertRaises(ValueError): stock.patch_skillgroup(SKILL.replace(stock.SKILL_START, ''), gameplay_config.DEFAULTS)
        with self.assertRaises(ValueError): stock.patch_rank(stock.patch_rank(RANK))


if __name__ == '__main__':
    unittest.main()

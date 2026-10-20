import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('gsi_rewards', Path(__file__).resolve().parents[1] / 'tools/gsi_rewards.py')
gsi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gsi)


class BotRewards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.rewards = gsi.Rewards(self.tmp.name)
        self.packet = {'auth': {'token': self.rewards.state['token']},
                       'provider': {'appid': 730, 'steamid': 'local-test-player', 'timestamp': 100},
                       'map': {'name': 'de_dust2', 'phase': 'live', 'round': 0},
                       'player': {'steamid': 'local-test-player', 'team': 'T', 'activity': 'playing',
                                  'match_stats': {'kills': 0, 'mvps': 0}, 'state': {'round_killhs': 0}}}

    def test_bot_kills_and_duplicate_snapshots_across_restart(self):
        self.assertTrue(self.rewards.accept(self.packet))
        self.packet['player']['match_stats']['kills'] = 2
        self.packet['player']['state']['round_killhs'] = 1
        self.rewards.accept(self.packet)
        self.assertEqual(self.rewards.state['total'], 13)
        self.rewards.accept(self.packet)
        reloaded = gsi.Rewards(self.tmp.name)
        reloaded.accept(self.packet)
        self.assertEqual(reloaded.state['total'], 13)
        self.packet['player']['match_stats']['mvps'] = 1
        self.packet['map']['phase'] = 'gameover'
        reloaded.accept(self.packet)
        reloaded.accept(self.packet)
        self.assertEqual(reloaded.state['total'], 638)
        self.assertEqual((Path(self.tmp.name) / 'cs2_gc_rewards.txt').read_text().strip(), '638')

    def test_warmup_spectator_and_bot_possession_do_not_award(self):
        self.rewards.accept(self.packet)
        invalid = copy.deepcopy(self.packet)
        invalid['auth']['token'] = 'wrong'
        self.assertFalse(self.rewards.accept(invalid))
        self.packet['player']['steamid'] = 'a-bot'
        self.packet['player']['match_stats']['kills'] = 99
        self.rewards.accept(self.packet)
        self.assertEqual(self.rewards.state['total'], 0)
        self.packet['player']['steamid'] = 'local-test-player'
        self.packet['map']['phase'] = 'warmup'
        self.rewards.accept(self.packet)
        self.assertEqual(self.rewards.state['total'], 0)

    def test_match_reset_new_round_and_old_packets(self):
        self.rewards.accept(self.packet)
        self.packet['player']['state']['round_killhs'] = 1
        self.packet['player']['match_stats']['kills'] = 1
        self.rewards.accept(self.packet)
        old = copy.deepcopy(self.packet)
        self.packet['map']['round'] = 1
        self.packet['provider']['timestamp'] = 101
        self.packet['player']['match_stats']['kills'] = 2
        self.rewards.accept(self.packet)
        self.assertEqual(self.rewards.state['total'], 16)
        self.rewards.accept(old)
        self.assertEqual(self.rewards.state['total'], 16)
        self.packet['map']['round'] = 0
        self.packet['player']['match_stats']['kills'] = 0
        self.rewards.accept(self.packet)
        self.assertEqual(self.rewards.state['total'], 16)

    def test_bonus_premier_wins_apply_once_and_only_upward(self):
        (Path(self.tmp.name) / 'cs2_gc_gameplay.cfg').write_text('premier_bonus_wins = 8\n')
        granted = gsi.Rewards(self.tmp.name)
        self.assertEqual(granted.state['premier']['wins'], 8)
        self.assertEqual(granted.state['premier']['rating'], 1000 + 8 * 300)
        self.assertEqual(granted.state['premier_bonus_applied'], 8)
        self.assertEqual((Path(self.tmp.name) / 'cs2_gc_premier.txt').read_text(), '3400 8 10\n')
        again = gsi.Rewards(self.tmp.name)   # a restart must not grant them again
        self.assertEqual(again.state['premier']['wins'], 8)
        (Path(self.tmp.name) / 'cs2_gc_gameplay.cfg').write_text('premier_bonus_wins = 9\n')
        self.assertEqual(gsi.Rewards(self.tmp.name).state['premier']['wins'], 9)   # only the difference
        (Path(self.tmp.name) / 'cs2_gc_gameplay.cfg').write_text('premier_bonus_wins = 2\n')
        self.assertEqual(gsi.Rewards(self.tmp.name).state['premier']['wins'], 9)   # lowering removes nothing

    def test_bonus_premier_wins_are_ignored_when_premier_is_off(self):
        (Path(self.tmp.name) / 'cs2_gc_gameplay.cfg').write_text('premier_enabled = 0\npremier_bonus_wins = 8\n')
        self.assertEqual(gsi.Rewards(self.tmp.name).state['premier']['wins'], 0)

    def test_invalid_persisted_state_is_not_overwritten(self):
        state = Path(self.tmp.name) / 'cs2_gc_gsi_state.json'
        state.write_text('{broken')
        with self.assertRaises(ValueError):
            gsi.Rewards(self.tmp.name)
        self.assertEqual(state.read_text(), '{broken')

    def test_config_subscribes_local_player_stats(self):
        config = gsi.config_text('test-token', 31923)
        self.assertIn('http://127.0.0.1:31923/', config)
        self.assertIn('"player_match_stats" "1"', config)
        self.assertNotIn('allplayers', config)


if __name__ == '__main__':
    unittest.main()

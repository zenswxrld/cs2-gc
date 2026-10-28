import copy
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import gameplay_config as config
import gsi_rewards as gsi
import mixed_tradeup
import terminal_purchase
import rotate_armory
import premier_rating as premier


class GameplayOptions(unittest.TestCase):
    def test_example_and_validation(self):
        values = config.parse((ROOT / 'examples/cs2_gc_gameplay.cfg').read_text())
        self.assertEqual(values, config.balance(dict(config.DEFAULTS)))
        for line in ('unknown=1', 'match_drop_count=0', 'pity_soft_at=99\npity_hard_at=3',
                     'kill_xp=3\nkill_xp=4', 'match_skin_min_rarity=2', 'stars_enabled=2'):
            with self.assertRaises(ValueError): config.parse(line)

    def test_star_sale_balance_mirrors_the_gc(self):
        # Same golden values as StarEconomy() in tests/core_tests.cpp: the native Sell label equals the GC payout.
        keys = list(config.WEAPON_KEYS[1:]) + ['sell_knife_glove'] + list(config.STICKER_KEYS) + list(config.CHARM_KEYS) + \
            ['sell_agent_percent', 'sell_container_percent']
        defaults = config.balance(dict(config.DEFAULTS))
        self.assertEqual([defaults[k] for k in keys], [1, 1, 2, 4, 12, 24, 35, 0, 0, 0, 5, 1, 3, 9, 25, 50, 30])
        generous = config.parse('pity_soft_at = 2\narmory_pity_soft_at = 2\nsell_consumer = 2\nsell_industrial = 5\n'
                                'sell_mil_spec = 10\nsell_restricted = 15\nsell_classified = 25\nsell_covert = 50\n'
                                'sell_knife_glove = 150\nsell_sticker_percent = 90\nsell_music_kit = 90\n'
                                'sell_container_percent = 90\nsell_agent_percent = 85\n')
        self.assertEqual([generous[k] for k in keys], [1, 1, 2, 3, 6, 13, 25, 0, 0, 0, 5, 1, 3, 9, 25, 85, 90])
        self.assertEqual(config.balance(dict(generous)), generous)  # idempotent
        self.assertEqual(config.load(Path(tempfile.mkdtemp())), defaults)
        # Weapon routes priced by the model never return more than the configured share, even at the best wear.
        for values in (defaults, generous):
            enabled, high, _ = config.wear_model(values)
            weapons = [0] + [values[k] for k in config.WEAPON_KEYS[1:]]
            routes = config.sale_diagnostics(values, weapons, values['sell_knife_glove'], lambda v: config._share(v, high))
            self.assertLessEqual(max(routes.values()), values['sell_max_return_percent'] / 100 + 1e-9)
        with self.assertRaises(ValueError): config.parse('sell_max_return_percent = 100')

    def test_helper_requests_refuse_pending_and_invalid_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            token = 'a' * 32
            mixed_tradeup.submit(directory, list(range(1, 11)), token)
            path = directory / 'cs2_gc_tradeup_request.txt'
            self.assertEqual(path.read_text().split(), [token] + [str(10**12 + i) for i in range(1, 11)])
            with self.assertRaises(ValueError): mixed_tradeup.submit(directory, list(range(11, 21)))
            path.unlink()
            with self.assertRaises(ValueError): mixed_tradeup.submit(directory, [1] * 10)
            terminal_purchase.submit(directory, 382, token)
            self.assertEqual((directory / 'cs2_gc_terminal_request.txt').read_text().split(), [token] + [str(10**12 + 382)] * 5)
            with self.assertRaises(ValueError): terminal_purchase.submit(directory, 382)

    def test_configured_xp_completion_dedup_and_menu_gameover(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'cs2_gc_gameplay.cfg').write_text('kill_xp=10\nheadshot_xp=5\nmvp_xp=40\nmatch_complete_xp=1000\n')
            rewards = gsi.Rewards(path)
            packet = {'auth': {'token': rewards.state['token']},
                      'provider': {'appid': 730, 'steamid': 'test', 'timestamp': 100},
                      'map': {'name': 'de_test', 'phase': 'live', 'round': 0},
                      'player': {'steamid': 'test', 'team': 'T', 'activity': 'playing',
                                 'match_stats': {'kills': 0, 'mvps': 0}, 'state': {'round_killhs': 0}}}
            rewards.accept(packet)
            packet['player']['match_stats'] = {'kills': 1, 'mvps': 1}
            packet['player']['state']['round_killhs'] = 1
            packet['map']['phase'] = 'gameover'
            packet['player']['activity'] = 'menu'
            rewards.accept(packet)
            self.assertEqual(rewards.state['total'], 1055)
            self.assertEqual(rewards.state['matches'], 1)
            reloaded = gsi.Rewards(path)
            reloaded.accept(packet)
            self.assertEqual(reloaded.state['matches'], 1)
            self.assertEqual((path / 'cs2_gc_matches.txt').read_text().strip(), '1')
            # A first snapshot already at gameover must not award an unobserved match.
            reloaded.state['last'] = None
            reloaded.accept(packet)
            self.assertEqual(reloaded.state['matches'], 1)

    def test_local_premier_placements_bounds_and_bot_skill(self):
        state = premier.initial(config.DEFAULTS)
        for _ in range(9): state = premier.apply(state, 'wins', dict(config.DEFAULTS, premier_rating_variation=0))
        self.assertIsNone(premier.visible_rating(state, config.DEFAULTS))
        state = premier.apply(state, 'wins', dict(config.DEFAULTS, premier_rating_variation=0))
        self.assertEqual(premier.visible_rating(state, config.DEFAULTS), 4000)
        self.assertEqual(premier.apply(state, 'losses', dict(config.DEFAULTS, premier_rating_variation=0))['rating'], 3900)
        self.assertEqual(premier.apply(state, 'ties', dict(config.DEFAULTS, premier_rating_variation=0))['rating'], 4000)
        state['rating'] = 0
        self.assertEqual(premier.apply(state, 'losses', dict(config.DEFAULTS, premier_rating_variation=0))['rating'], 0)
        state['rating'] = 34999
        self.assertEqual(premier.apply(state, 'wins', dict(config.DEFAULTS, premier_rating_variation=0))['rating'], 35000)
        self.assertEqual(premier.bot_difficulty(state), 3)
        result = {'mode': 'competitive', 'team_t': {'score': 13}, 'team_ct': {'score': 0}}
        self.assertEqual(premier.outcome(result, 'T'), 'wins')
        self.assertEqual(premier.outcome(result, 'CT'), 'losses')
        result['mode'] = 'deathmatch'
        self.assertIsNone(premier.outcome(result, 'T'))

    def test_rotation_generator_checks_target_and_embeds_matching_settings(self):
        source = '''    const m_elContentPanel = root;
    function _UpdateShopGoods(m_nTrack) {
        aShopItemsData.forEach((element) => {
            _MakeShopTile(element);
            _MakeNavButton(element);
        });
    }
'''
        with self.assertRaises(ValueError): rotate_armory.patch(source, config.DEFAULTS)
        ui_config = dict(config.DEFAULTS, armory_howl_enabled=0)
        result = rotate_armory.patch(source, ui_config)
        self.assertIn('"seconds": 900', result)
        self.assertIn('Armory refresh: ', result)
        self.assertIn('m_localRotationItems = aShopItemsData', result)
        with self.assertRaises(ValueError): rotate_armory.patch(result, ui_config)
        with self.assertRaises(ValueError): rotate_armory.patch('different client', ui_config)


if __name__ == '__main__': unittest.main()

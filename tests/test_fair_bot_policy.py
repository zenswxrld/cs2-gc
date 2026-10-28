"""Human reactions, rating boundaries, and reversible owned plugin selection."""
import json,re,sys,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import fair_bot_policy as policy,premier_rating

class FairBots(unittest.TestCase):
    def setUp(self):
        guard=patch.object(policy,'require_game_closed')
        guard.start();self.addCleanup(guard.stop)

    def test_requested_rating_ladder_and_no_smoke_reveal_at_any_rank(self):
        for rating,difficulty in ((0,0),(9999,0),(10000,1),(19999,1),(20000,1),(24999,1),(25000,2),(29999,2),(30000,3),(40000,3)):
            self.assertEqual(premier_rating.bot_difficulty({'rating':rating}),difficulty)
            self.assertIn('bot_max_visible_smoke_length 0',policy.server_config(rating))
            self.assertIn('bot_max_vision_distance_override -1',policy.server_config(rating))
            self.assertIn('sv_compute_per_bot_difficulty false',policy.server_config(rating))
            self.assertIn('bot_defer_to_human_goals 1',policy.server_config(rating))
            self.assertIn('bot_auto_follow 1',policy.server_config(rating))
        self.assertEqual(policy.strength(9999),0)
        self.assertLess(policy.strength(15000),policy.strength(20000))
        self.assertLess(policy.strength(25000),policy.strength(30000))

    def test_profiles_cannot_override_reaction_floor_or_use_perfect_native_aim(self):
        text='Default\n Skill = 100\n ReactionTime = 0\n AttackDelay = 0\n AimFocusInitial = 0\n AimFocusDecay = 0.00001\n AimFocusOffsetScale = 0\n AimfocusInterval = 0\nEnd\nTemplate Pro\n ReactionTime = 0.0001\n WeaponPreference = ak47\nEnd\n'
        for rating in (0,9999,20000,25000,30000,40000):
            fixed=policy.humanize_profile(text,rating)
            reactions=[float(n) for n in re.findall(r'ReactionTime = ([0-9.]+)',fixed)]
            self.assertTrue(all(v>=.119 for v in reactions))
            self.assertIn('WeaponPreference = ak47',fixed)
            self.assertNotIn('AimFocusOffsetScale = 0\n',fixed)
        self.assertIn('Skill = 45',policy.humanize_profile(text,1000))

    def test_owned_plugins_stay_disabled_at_30k_and_restore_for_uninstall(self):
        with tempfile.TemporaryDirectory() as tmp:
            game=Path(tmp)/'game';proxy=game/'bin/win64';proxy.mkdir(parents=True)
            plugins,held=policy.paths(proxy);plugins.mkdir(parents=True)
            owned=[]
            for name in ('BotAimImprover','BotState','NadeSystem','BotRandomizer'):
                path=plugins/name/(name+'.dll');path.parent.mkdir();path.write_bytes(name.encode())
                owned.append(path.relative_to(game/'csgo').as_posix())
            (proxy/'cs2_gc_bot_skins.json').write_text(json.dumps({'files':owned}))
            (proxy/'cs2_gc_gsi_state.json').write_text(json.dumps({'premier':{'rating':1000}}))
            self.assertEqual(set(policy.apply(proxy)),{'BotAimImprover','BotState'})
            cfg=game/'csgo/cfg/cs2_gc_premier_bots.cfg'
            self.assertEqual(cfg.read_text(),policy.server_config(1000))
            self.assertEqual(policy.apply(proxy),[])
            self.assertTrue(all(policy.owned_exists(proxy,name) for name in owned))
            self.assertTrue((plugins/'BotRandomizer/BotRandomizer.dll').is_file())
            (proxy/'cs2_gc_gsi_state.json').write_text(json.dumps({'premier':{'rating':30000}}))
            self.assertEqual(policy.apply(proxy),[])
            self.assertFalse((plugins/'BotAimImprover/BotAimImprover.dll').exists())
            self.assertTrue((held/'BotState/BotState.dll').is_file(),'smoke reveal remains off at high rank')
            self.assertTrue((plugins/'NadeSystem/NadeSystem.dll').is_file(),'situational limited utility stays available')
            self.assertIn('bot_nades less',cfg.read_text())
            # Upgrade from the all-off patch: restore its held owned utility plugin.
            (plugins/'NadeSystem').rename(held/'NadeSystem')
            self.assertEqual(policy.apply(proxy),['NadeSystem'])
            policy.restore(proxy)
            self.assertTrue((plugins/'BotAimImprover/BotAimImprover.dll').is_file())
            self.assertTrue((plugins/'BotState/BotState.dll').is_file())
            self.assertFalse(held.exists())

    def test_unowned_plugin_never_moves(self):
        with tempfile.TemporaryDirectory() as tmp:
            proxy=Path(tmp)/'game/bin/win64';proxy.mkdir(parents=True)
            plugins,held=policy.paths(proxy);target=plugins/'BotAimImprover';target.mkdir(parents=True)
            (target/'BotAimImprover.dll').write_bytes(b'foreign')
            (proxy/'cs2_gc_bot_skins.json').write_text(json.dumps({'files':[]}))
            policy.apply(proxy)
            self.assertTrue((target/'BotAimImprover.dll').is_file())

class GameGuard(unittest.TestCase):
    def test_running_game_and_failed_process_check_refuse_changes(self):
        from types import SimpleNamespace
        for result in (SimpleNamespace(returncode=0,stdout='"cs2.exe","123"'),SimpleNamespace(returncode=1,stdout='')):
            with patch.object(policy.sys,'platform','win32'),patch.object(policy.subprocess,'run',return_value=result):
                with self.assertRaisesRegex(RuntimeError,'Close CS2'):policy.require_game_closed()
        with patch.object(policy.sys,'platform','win32'),patch.object(policy.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='INFO: No tasks are running')):
            policy.require_game_closed()

if __name__=='__main__':unittest.main()

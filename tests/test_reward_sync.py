import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from gsi_rewards import Rewards

class RewardSync(unittest.TestCase):
    def packet(self,rewards,stamp=100):
        return {'auth':{'token':rewards.state['token']},'provider':{'appid':730,'steamid':'local','timestamp':stamp},
            'player':{'steamid':'local','activity':'playing','team':'T','match_stats':{'kills':0,'mvps':0},'state':{'round_killhs':0}},
            'map':{'name':'de_cache','mode':'competitive','round':0,'phase':'live','team_t':{'score':0},'team_ct':{'score':0}}}

    def test_inventory_ahead_of_helper_allows_new_earnings_without_replaying_ambiguous_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'cs2_gc_inventory.txt').write_text('"inventory" { "items" {} "progression" { "reward_total" "13510" } "match_reward_total" "7" "mission_star_total" "3" }')
            (root/'cs2_gc_gsi_state.json').write_text(json.dumps({'token':'local','total':1167,'matches':1,'last':None}))
            rewards=Rewards(root);self.assertEqual((rewards.state['total'],rewards.state['matches']),(13510,7))
            self.assertEqual(rewards.state['reward_sync_review'][0]['total']['helper'],1167)
            first=self.packet(rewards);rewards.accept(first)
            end=copy.deepcopy(first);end['provider']['timestamp']+=1;end['player']['match_stats']['kills']=1;end['map']['phase']='gameover';end['map']['team_t']['score']=13
            rewards.accept(end);rewards.accept(end)
            self.assertEqual((rewards.state['total'],rewards.state['matches']),(14115,8))
            self.assertEqual(rewards.state['achievement_stars'],15) # first match + 10,000 earned XP
            self.assertEqual(rewards.state['mission_stars'],70) # paid floor 3 + kill 2 + completion 50 + achievements 15
            again=Rewards(root)
            self.assertEqual(len(again.state['reward_sync_review']),1)
            self.assertEqual(again.state['total'],14115)

    def test_configurable_kills_mvps_and_completed_objectives_pay_once_only_for_local_actor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'cs2_gc_gameplay.cfg').write_text('kill_stars=4\nheadshot_stars=3\nmvp_stars=9\nplant_stars=12\ndefuse_stars=15\nmatch_complete_stars=70\n')
            rewards=Rewards(root);p=self.packet(rewards);rewards.accept(p)
            p['provider']['timestamp']+=1;p['bomb']={'state':'planting','player':'local'};rewards.accept(p)
            p['provider']['timestamp']+=1;p['bomb']={'state':'planted'};p['player']['match_stats'].update(kills=1,mvps=1);p['player']['state']['round_killhs']=1
            rewards.accept(p);rewards.accept(p)
            self.assertEqual(rewards.state['mission_stars'],4+3+9+12)
            p['provider']['timestamp']+=1;p['bomb']={'state':'defusing','player':'bot'};rewards.accept(p)
            p['provider']['timestamp']+=1;p['bomb']={'state':'defused'};rewards.accept(p)
            self.assertEqual(rewards.state['mission_stars'],28)
            p['map']['round']=1;p['provider']['timestamp']+=1;p['bomb']={'state':'defusing','player':'local'};rewards.accept(p)
            p['provider']['timestamp']+=1;p['bomb']={'state':'defused'};rewards.accept(p)
            self.assertEqual(rewards.state['mission_stars'],43)
            self.assertEqual((root/'cs2_gc_mission_progress.txt').read_text(),'stars 43\n')
            self.assertEqual(Rewards(root).state['mission_stars'],43)

    def test_joining_a_planted_bomb_and_disabled_stars_do_not_pay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'cs2_gc_gameplay.cfg').write_text('stars_enabled=0\n')
            rewards=Rewards(root);p=self.packet(rewards);p['bomb']={'state':'planted','player':'local'};rewards.accept(p)
            p['provider']['timestamp']+=1;p['player']['match_stats']['kills']=2;rewards.accept(p)
            self.assertEqual(rewards.state.get('mission_stars',0),0)

    def test_dead_player_spectating_a_bot_still_gets_completion_but_never_the_bots_kills(self):
        with tempfile.TemporaryDirectory() as tmp:
            rewards=Rewards(tmp);p=self.packet(rewards);rewards.accept(p)
            bot=copy.deepcopy(p);bot['provider']['timestamp']+=1;bot['player']['steamid']='bot';bot['player']['team']='CT';bot['player']['match_stats']['kills']=99
            rewards.accept(bot);self.assertEqual(rewards.state['total'],0)
            bot['provider']['timestamp']+=1;bot['map']['phase']='gameover';bot['map']['team_t']['score']=13
            rewards.accept(bot);rewards.accept(bot)
            self.assertEqual(rewards.state['matches'],1)
            self.assertEqual(rewards.state['total'],600)
            self.assertEqual(rewards.state['mission_stars'],55) # completion 50 + first-match achievement 5
            self.assertEqual(rewards.state['achievement_stars'],5)
            self.assertEqual(rewards.state['premier']['wins'],1)

if __name__=='__main__':unittest.main()

import copy,hashlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from career_achievements import DEFINITIONS,award,unlocked,counts,recent_unlocks
from combat_events import CombatEvents,prepare,PLUGIN
from gsi_rewards import Rewards

class CareerRewards(unittest.TestCase):
    def test_rewards_are_one_time_and_award_stars_do_not_feed_star_milestones(self):
        state={'matches':1,'mission_stars':0,'gameplay_stars_earned':999}
        self.assertEqual(award(state),5)
        self.assertEqual(state['mission_stars'],5)
        self.assertEqual(award(state),0)
        self.assertNotIn('stars:1000',unlocked(state))
        state=json.loads(json.dumps(state));self.assertEqual(award(state),0)
        state['gameplay_stars_earned']=1000
        self.assertEqual(award(state),10);self.assertEqual(state['achievement_stars'],15)
        self.assertEqual(counts(state)['stars'],1000)

    def test_legacy_unlocks_get_one_payment_and_disabled_stars_never_retroactively_pay(self):
        state={'local_achievements':['rating:20000'],'premier':{'rating':0}}
        self.assertEqual(award(state),60);self.assertEqual(award(state),0)
        off={'matches':1};self.assertEqual(award(off,False),0)
        self.assertEqual(award(off,True),0)

    def test_recent_unlock_history_survives_restarts_without_duplicate_or_invented_entries(self):
        state={'matches':1}
        with patch('career_achievements.time.time',return_value=100):self.assertEqual(award(state),5)
        self.assertEqual(recent_unlocks(state),[dict(id='matches:1',stars=5,at=100)])
        state=json.loads(json.dumps(state));award(state)
        self.assertEqual(len(recent_unlocks(state)),1)
        state['combat_stats']={'blind_kills':5}
        with patch('career_achievements.time.time',return_value=200):award(state)
        self.assertEqual([r['id'] for r in recent_unlocks(state)],['blind_kills:5','matches:1'])
        self.assertEqual(recent_unlocks({'local_achievements':['matches:1']}),[])
        state['achievement_recent'].append(dict(id='invented:1',stars=999,at=300))
        self.assertEqual(len(recent_unlocks(state)),2)

    def test_finite_catalogue_has_unique_ids_and_modest_first_tier_rewards(self):
        self.assertEqual(len(DEFINITIONS),len({a['id'] for a in DEFINITIONS}))
        self.assertGreater(len(DEFINITIONS),70)
        self.assertTrue(all(0<a['stars']<=150 and a['description'] for a in DEFINITIONS))
        for a in DEFINITIONS:
            if a['key'] in ('kills','headshots'):
                self.assertLessEqual(a['stars'],a['target']*.2)

    def fixture(self,folder):
        r=Rewards(folder);r.state['local_player']='76561198000000000'
        bridge=CombatEvents(r,123)
        data=dict(version=1,pid=123,nonce=bridge.nonce,session='a'*32,sequence=1,
                  players={'76561198000000000':{'blind_kills':5,'enemies_flashed':10}})
        return r,bridge,data

    def test_plugin_install_checks_payload_api_and_ownership(self):
        with tempfile.TemporaryDirectory() as folder:
            proxy=Path(folder)/'game/bin/win64';payload=proxy/'cs2_gc_payload/career';payload.mkdir(parents=True)
            api=Path(folder)/'game/csgo/addons/counterstrikesharp/api/CounterStrikeSharp.API.dll'
            api.parent.mkdir(parents=True);api.write_bytes(b'api')
            binary=payload/(PLUGIN+'.dll');binary.write_bytes(b'owned plugin')
            sha=lambda b:hashlib.sha256(b).hexdigest()
            bundle=payload/'bundle.json';bundle.write_text(json.dumps(dict(sha256=sha(binary.read_bytes()),api_sha256=sha(api.read_bytes()))))
            target=api.parent.parent/'plugins'/PLUGIN;target.mkdir(parents=True)
            foreign=target/'foreign.txt';foreign.write_text('keep')
            with patch('fair_bot_policy.require_game_closed'):
                with self.assertRaisesRegex(ValueError,'Unowned'):prepare(proxy,{})
                self.assertEqual(foreign.read_text(),'keep');foreign.unlink()
                self.assertTrue(prepare(proxy,{}).startswith('installed'))
                self.assertEqual((target/binary.name).read_bytes(),b'owned plugin')
                (target/binary.name).write_bytes(b'externally edited')
                with self.assertRaisesRegex(ValueError,'externally'):prepare(proxy,{})
                api.write_bytes(b'new API')
                with self.assertRaisesRegex(ValueError,'mismatch'):prepare(proxy,{})
            (proxy/'cs2_gc_bot_plugins_disabled').touch()
            self.assertTrue(prepare(proxy,{}).startswith('unavailable'))

    def test_event_snapshots_are_bound_to_this_process_and_not_double_counted(self):
        with tempfile.TemporaryDirectory() as folder:
            r,b,data=self.fixture(folder)
            for field,value in (('pid',999),('nonce','wrong')):
                bad=copy.deepcopy(data);bad[field]=value;self.assertFalse(b.consume(bad))
            self.assertTrue(b.consume(data));r.save()
            self.assertEqual(r.state['combat_stats']['blind_kills'],5)
            self.assertEqual(r.state['achievement_stars'],10)
            self.assertFalse(b.consume(data))
            restarted=Rewards(folder);again=CombatEvents(restarted,123);data['nonce']=again.nonce
            self.assertFalse(again.consume(data));self.assertEqual(restarted.state['achievement_stars'],10)
            data['sequence']=2;data['players'][r.state['local_player']]['blind_kills']=6
            self.assertTrue(again.consume(data));restarted.save()
            self.assertEqual(restarted.state['combat_stats']['blind_kills'],6)
            self.assertEqual(restarted.state['achievement_stars'],10)

    def test_regressing_or_unsupported_events_do_not_mutate_progress(self):
        with tempfile.TemporaryDirectory() as folder:
            r,b,data=self.fixture(folder);self.assertTrue(b.consume(data));r.save();before=copy.deepcopy(r.state)
            data['sequence']=2;data['players'][r.state['local_player']]['blind_kills']=4
            self.assertFalse(b.consume(data));self.assertEqual(r.state,before)
            data['players'][r.state['local_player']]={'invented':1}
            self.assertFalse(b.consume(data));self.assertEqual(r.state,before)

    def test_failed_publish_is_retried_without_recounting(self):
        with tempfile.TemporaryDirectory() as folder:
            r,b,data=self.fixture(folder);path=Path(folder)/'cs2_gc_combat_events.json';path.write_text(json.dumps(data))
            original=r.save
            with patch.object(r,'save',side_effect=OSError('disk busy')):self.assertFalse(b.poll())
            self.assertTrue(b.pending);self.assertEqual(r.state['combat_stats']['blind_kills'],5)
            b.poll();self.assertFalse(b.pending);self.assertEqual(r.state['combat_stats']['blind_kills'],5)
            self.assertEqual(r.state['achievement_stars'],10)

if __name__=='__main__':unittest.main()

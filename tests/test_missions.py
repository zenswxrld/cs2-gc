import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import native_missions as nm
from mission_tracker import MissionTracker

BASE = 1791939600
KEY = '%d:1' % BASE


def template(mission, **fields):
    entries = [(k, nm.STRING, v) for k, v in fields.items()]
    entries.append(('xp_round_to', nm.BYTE, 25))
    entries.append(('gc', nm.SUBKEY, [('random', nm.SUBKEY, [('expression', nm.STRING, fields.get('expression', ''))])]))
    return (mission, nm.SUBKEY, entries)


def recorded():
    """Two recorded periods in the real layout: one blob holding several missions, one with a Premier-only one."""
    first = nm.write_kv([
        template('11003', gamemode='deathmatch', mapgroup='![mg_casualdelta|mg_casualalpha]', map='',
                 points='40, 80, 120', xp_expr='200, 200, 200',
                 expression='act_kill_human && !![weapon_ak47|weapon_awp]'),
        template('11004', gamemode='competitive', mapgroup='', map='de_vertigo', points='5,11,18',
                 xp_expr='300,350,400', expression='act_win_round'),
        template('11006', gamemode='competitive', mapgroup='', map='lobby_mapveto', points='5,11,18',
                 xp_expr='300,350,400', expression='act_win_round')])
    second = nm.write_kv([template('11017', gamemode='rush', mapgroup='mg_rush_001', map='rush_001',
                                   points='1,2,3', xp_expr='250,250,250', expression='act_win_match')])
    return (nm._field(1, nm._field(1, BASE) + nm._field(2, first)) +
            nm._field(1, nm._field(1, BASE + 604800) + nm._field(2, second)) + nm._field(1, nm._field(1, BASE + 9 * 604800)))


GAMEMODES = '"mapgroups" { "mg_casualdelta" { "name" "mg_casualdelta" "maps" { "de_train" "" "de_nuke" "" } } ' \
            '"mg_casualalpha" { "name" "mg_casualalpha" "maps" { "de_dust2" "" } } }'


class Schedule(unittest.TestCase):
    def test_templates_round_trip_and_unplayable_ones_are_dropped(self):
        found = nm.recorded_templates(recorded())
        self.assertEqual([m for _, m, _ in found], ['11003', '11004', '11006', '11017'])
        for _, mission, body in found:
            self.assertEqual(nm.read_kv(nm.write_kv([(mission, nm.SUBKEY, body)]))[0], [(mission, nm.SUBKEY, body)])
        self.assertEqual([m for _, m, b in found if nm.playable(b)], ['11003', '11004'])

    def test_pool_holds_every_combination_with_random_choices_fixed(self):
        body, plan = nm.build(recorded(), GAMEMODES)
        variants = plan['variants']
        # 11003: 2 map groups x 2 weapons, 11004: no choices; interleaved so consecutive missions differ
        self.assertEqual([v['mission'] for v in variants], [11003, 11004, 11003, 11003, 11003])
        kills = [(v['weapon'], v['mapgroup']) for v in variants if v['kind'] == 'kill']
        self.assertEqual(len(set(kills)), 4)
        served = nm.proto_fields(body)
        self.assertEqual(len(served), len(variants))
        for index, (number, value) in enumerate(served):
            fields = dict(nm.proto_fields(value))
            self.assertEqual(fields[1], index)
            entries, _ = nm.read_kv(fields[2])
            text = json.dumps(nm.as_dict(entries))
            self.assertNotIn('|', text)  # no random lists left for the client to roll differently
            mission = variants[index]
            self.assertEqual(entries[0][0], str(mission['mission']))
            if mission['kind'] == 'kill':
                self.assertIn('!![%s]' % mission['weapon'], text)
                self.assertEqual(mission['maps'], {'mg_casualdelta': ['de_nuke', 'de_train'],
                                                   'mg_casualalpha': ['de_dust2']}[mission['mapgroup']])
        self.assertEqual(nm.build(recorded(), GAMEMODES)[0], body)


def packet(kills=0, weapon='weapon_awp', mode='deathmatch', name='de_nuke', own=0, other=0, phase='live', team='CT'):
    player = {'team': team, 'weapons': {'weapon_0': {'name': 'weapon_knife', 'state': 'holstered'},
                                        'weapon_1': {'name': weapon, 'state': 'active'}}}
    game_map = {'name': name, 'mode': mode, 'phase': phase, 'team_ct': {'score': own}, 'team_t': {'score': other}}
    return {}, player, game_map, {'kills': kills}


class Tracking(unittest.TestCase):
    def tracker(self, mission):
        folder = Path(tempfile.mkdtemp())
        (folder / 'cs2_gc_missions.json').write_text(json.dumps({'variants': [{'mission': 1}, mission]}))
        (folder / 'cs2_gc_mission_current.txt').write_text('1 %d\n' % BASE)  # written by the DLL
        return folder, MissionTracker(folder, {}, now=lambda: BASE + 10)

    def test_kills_count_only_with_the_mission_weapon_in_its_mode_and_maps(self):
        folder, tracker = self.tracker({'mission': 11003, 'kind': 'kill', 'weapon': 'weapon_awp', 'mode': 'deathmatch',
                                        'maps': ['de_nuke'], 'points': [2, 4, 6], 'xp': [200, 200, 200]})
        self.assertEqual(tracker.observe(*packet(kills=5)), 0)  # first packet: baseline only
        self.assertEqual(tracker.observe(*packet(kills=6)), 0)
        self.assertEqual(tracker.observe(*packet(kills=7)), 200)  # second AWP kill reaches the first tier
        self.assertEqual(tracker.observe(*packet(kills=8, weapon='weapon_ak47')), 0)  # wrong weapon
        self.assertEqual(tracker.observe(*packet(kills=9, mode='competitive')), 0)  # wrong mode: no count
        self.assertEqual(tracker.state['missions'][KEY], 2)
        self.assertEqual((folder / 'cs2_gc_mission_progress.txt').read_text(), '11003 %d 2\nstars 2\n' % BASE)
        tracker.observe(*packet(kills=1, mode='deathmatch'))  # a new match restarts the baseline
        self.assertEqual(tracker.observe(*packet(kills=20)), 400)  # capped at the last tier, both tiers paid
        self.assertEqual(tracker.state['missions'][KEY], 6)
        self.assertEqual(tracker.observe(*packet(kills=21)), 0)
        self.assertEqual(tracker.state['mission_stars'], 6)  # 1 star per 100 XP of each step reached

    def test_a_new_armory_rotation_starts_a_new_mission(self):
        folder, tracker = self.tracker({'mission': 11003, 'kind': 'kill', 'weapon': 'weapon_awp', 'mode': 'deathmatch',
                                        'maps': [], 'points': [2, 4], 'xp': [200, 200]})
        tracker.observe(*packet(kills=0)); tracker.observe(*packet(kills=1))
        (folder / 'cs2_gc_mission_current.txt').write_text('0 %d\n' % (BASE + 900))  # rotated to a kind-less mission
        self.assertEqual(tracker.observe(*packet(kills=5)), 0)
        self.assertEqual(tracker.state['missions'], {KEY: 1})

    def test_rounds_and_matches(self):
        _, rounds = self.tracker({'mission': 11004, 'kind': 'round', 'mode': 'competitive', 'maps': ['de_vertigo'],
                                  'points': [5, 11, 18], 'xp': [300, 350, 400]})
        rounds.observe(*packet(mode='competitive', name='de_vertigo'))
        rounds.observe(*packet(mode='competitive', name='de_vertigo', own=1))
        rounds.observe(*packet(mode='competitive', name='de_vertigo', own=1, other=1))
        self.assertEqual(rounds.state['missions'][KEY], 1)
        _, matches = self.tracker({'mission': 11017, 'kind': 'match', 'mode': 'competitive', 'maps': [],
                                   'points': [1], 'xp': [250]})
        matches.observe(*packet(mode='competitive', own=12, other=3))
        self.assertEqual(matches.observe(*packet(mode='competitive', own=13, other=3, phase='gameover')), 250)


if __name__ == '__main__':
    unittest.main()

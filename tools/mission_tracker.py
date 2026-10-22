"""Count this week's mission from Game State Integration packets (bot matches never report quest progress).

Plan: cs2_gc_missions.json (native_missions.py). Progress: cs2_gc_mission_progress.txt, one "mission period progress"
line per period, read by the DLL (shown as the native CSOAccountRecurringMission progress). Reaching a points tier pays
that tier's XP through the helper's normal XP total.

Counting, local player only and only in the mission's mode on one of its maps:
  kill  - kills that rise while the mission weapon is the active weapon (bots count: offline there are no humans;
          grenade kills can not be attributed because the grenade has left the hand)
  round - own team's round score rising
  match - the match ending with the own team ahead
The first packet of a match only sets the baseline, so reconnecting never counts old kills or rounds.
"""
from pathlib import Path
import json
import time

PROGRESS_FILE = 'cs2_gc_mission_progress.txt'


class MissionTracker:
    def __init__(self, directory, state, now=time.time):
        self.directory, self.state, self.now = Path(directory), state, now
        self.state.setdefault('missions', {})
        self.last = None

    def plan(self):
        try:
            data = json.loads((self.directory / 'cs2_gc_missions.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None, None
        now, week = self.now(), data.get('week', 604800)
        for period, mission in data.get('periods', {}).items():
            if int(period) <= now < int(period) + week:
                return int(period), mission
        return None, None

    def observe(self, provider, player, game_map, stats):
        """XP earned by mission tiers for this packet (0 when nothing changed)."""
        period, mission = self.plan()
        if mission is None or not mission.get('kind'):
            self.last = None
            return 0
        name = str(game_map.get('name') or '').replace('\\', '/').rsplit('/', 1)[-1]
        team = player.get('team')
        own = (game_map.get('team_ct') if team == 'CT' else game_map.get('team_t')) or {}
        other = (game_map.get('team_t') if team == 'CT' else game_map.get('team_ct')) or {}
        weapons = player.get('weapons') or {}
        active = next((w.get('name') for w in weapons.values() if isinstance(w, dict) and w.get('state') == 'active'), None)
        current = {'period': period, 'map': name, 'mode': game_map.get('mode'), 'phase': game_map.get('phase'),
                   'kills': stats.get('kills', 0), 'own': own.get('score', 0), 'other': other.get('score', 0)}
        last, self.last = self.last, current
        if (not last or any(last[k] != current[k] for k in ('period', 'map', 'mode'))
                or current['kills'] < last['kills'] or current['own'] < last['own']):
            return 0  # new match, reconnect or another week: baseline only
        if current['mode'] != mission.get('mode') or (mission.get('maps') and name not in mission['maps']):
            return 0
        gained = 0
        if mission['kind'] == 'kill' and active == mission.get('weapon'):
            gained = current['kills'] - last['kills']
        elif mission['kind'] == 'round' and current['phase'] in ('live', 'gameover'):
            gained = current['own'] - last['own']
        elif (mission['kind'] == 'match' and current['phase'] == 'gameover' and last['phase'] != 'gameover'
              and current['own'] > current['other']):
            gained = 1
        return self.add(period, mission, gained) if gained > 0 else 0

    def add(self, period, mission, gained):
        key = str(period)
        goals, rewards = mission.get('points') or [0], mission.get('xp') or []
        before = self.state['missions'].get(key, 0)
        after = min(goals[-1], before + gained)
        self.state['missions'][key] = after
        xp = sum(reward for goal, reward in zip(goals, rewards) if before < goal <= after)
        self.publish()
        print('Mission %s: %d/%d%s' % (mission.get('mission'), after, goals[-1],
                                       ' (+%d XP)' % xp if xp else ''), flush=True)
        return xp

    def publish(self):
        from native_tradeups import atomic_write
        period, mission = self.plan()
        lines = []
        try:
            plan = json.loads((self.directory / 'cs2_gc_missions.json').read_text(encoding='utf-8'))['periods']
        except (OSError, ValueError, KeyError):
            plan = {}
        for key, progress in sorted(self.state['missions'].items()):
            if key in plan: lines.append('%d %s %d\n' % (plan[key]['mission'], key, progress))
        atomic_write(self.directory / PROGRESS_FILE, ''.join(lines))

"""Count the current mission from Game State Integration packets (bot matches never report quest progress).

User (28 Oct): "once the mission is complete it auto generates a new one, remove the link" (to the Armory). The
helper owns the choice: cs2_gc_mission_choice.txt holds the variant index (cs2_gc_missions.json, native_missions.py)
the DLL should serve; it changes only when the mission is completed, to the next variant. The DLL serves it with a
fresh period each launch and writes what it serves to cs2_gc_mission_current.txt ("variant period"). Progress belongs
to the mission (state key "gen<N>:<variant>"), not to a period, so it survives restarts; cs2_gc_mission_progress.txt
carries it as "mission period progress" for the served period, plus a cumulative "stars N" line. Reaching a points
tier pays that tier's XP through the helper's normal XP total and 1 star per 100 XP.

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
CURRENT_FILE = 'cs2_gc_mission_current.txt'  # "variant period", written by the DLL each rotation
SESSION_FILE = 'cs2_gc_mission_session.txt'  # retired match pin (missions no longer rotate); removed when seen
CHOICE_FILE = 'cs2_gc_mission_choice.txt'  # the variant the DLL should serve, written by this helper


class MissionTracker:
    def __init__(self, directory, state, now=time.time,defer_publish=False):
        self.directory, self.state, self.now = Path(directory), state, now
        self.state.setdefault('missions', {})
        self.last = None
        self.reason = None
        self.defer_publish=defer_publish
        self.published=None

    def suspend(self,clear=False):
        (self.directory/SESSION_FILE).unlink(missing_ok=True)
        if clear:self.state.pop('mission_session',None)

    def keep_alive(self,game_map):
        self.suspend(clear=True)

    def session_plan(self,game_map,stats,player):
        """Missions no longer rotate under a running match, so there is nothing to pin."""
        self.suspend(clear=True)
        return self.plan()

    def variants(self):
        try:
            return json.loads((self.directory / 'cs2_gc_missions.json').read_text(encoding='utf-8'))['variants']
        except (OSError, ValueError, KeyError):
            return []

    def served(self):
        try:
            index, period = (int(x) for x in (self.directory / CURRENT_FILE).read_text().split()[:2])
            return index, period
        except (OSError, ValueError):
            return None

    def choice(self, variants):
        """The mission the player is on: kept until completed, then the next variant."""
        choice = self.state.get('mission_choice')
        if not isinstance(choice, dict) or not 0 <= choice.get('index', -1) < len(variants):
            served = self.served()
            choice = {'index': served[0] if served and 0 <= served[0] < len(variants) else 0, 'gen': 0}
            self.state['mission_choice'] = choice
        path = self.directory / CHOICE_FILE
        text = '%d\n' % choice['index']
        try:
            current = path.read_text()
        except OSError:
            current = None
        if current != text:
            from native_tradeups import atomic_write
            atomic_write(path, text)
        return choice

    def plan(self):
        """(progress key, mission) of the current mission once the DLL serves it."""
        variants = self.variants()
        if not variants: return None, None
        choice = self.choice(variants)
        served = self.served()
        if served != self.published: self.publish()  # a new launch serves a new period: move the progress to it
        if not served or served[0] != choice['index']:
            return None, None  # the GC has not switched to the new mission yet
        return 'gen%d:%d' % (choice['gen'], choice['index']), variants[choice['index']]

    def observe(self, provider, player, game_map, stats):
        """XP earned by mission tiers for this packet (0 when nothing changed)."""
        period, mission = self.session_plan(game_map,stats,player)
        if mission is None or not mission.get('kind'):
            self.explain('no countable mission (waiting for the GC to serve the current mission in %s)' % CURRENT_FILE if mission is None
                         else 'mission %s is not a kill/round/match mission' % mission.get('mission'))
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
            self.explain('mission %s counts in %s on %s; this match is %s on %s' % (
                mission.get('mission'), mission.get('mode'), ', '.join(mission.get('maps') or ['any map']), current['mode'], name))
            return 0
        gained = 0
        if mission['kind'] == 'kill' and current['kills'] > last['kills'] and active != mission.get('weapon'):
            self.explain('kill not counted: mission weapon %s, active weapon %s%s' % (
                mission.get('weapon'), active, '' if weapons else ' (no weapon data: restart CS2 once so it reads the new game-state config)'))
        if mission['kind'] == 'kill' and active == mission.get('weapon') and current['phase'] in ('live','gameover'):
            gained = current['kills'] - last['kills']
        elif mission['kind'] == 'round' and current['phase'] in ('live', 'gameover'):
            gained = current['own'] - last['own']
        elif (mission['kind'] == 'match' and current['phase'] == 'gameover' and last['phase'] != 'gameover'
              and current['own'] > current['other']):
            gained = 1
        return self.add(period, mission, gained) if gained > 0 else 0

    def explain(self, text):
        if text != self.reason:  # once per reason, not every packet
            self.reason = text
            print('Mission: ' + text, flush=True)

    def add(self, key, mission, gained):
        goals, rewards = mission.get('points') or [0], mission.get('xp') or []
        before = self.state['missions'].get(key, 0)
        after = min(goals[-1], before + gained)
        self.state['missions'][key] = after
        if before < goals[-1] <= after:
            self.state['missions_completed']=self.state.get('missions_completed',0)+1
            # Completed: the next mission straight away (the DLL picks the choice file up on its next poll).
            variants = self.variants()
            choice = self.state.get('mission_choice') or {'index': 0, 'gen': 0}
            if variants:
                self.state['mission_choice'] = {'index': (choice['index'] + 1) % len(variants), 'gen': choice['gen'] + 1}
                self.choice(variants)
        xp = sum(reward for goal, reward in zip(goals, rewards) if before < goal <= after)
        # User: missions also pay stars, 1 per 100 XP of each step reached (rounded up).
        stars = sum(-(-reward // 100) for goal, reward in zip(goals, rewards) if before < goal <= after)
        self.state['mission_stars'] = self.state.get('mission_stars', 0) + stars
        if not self.defer_publish:self.publish()
        print('Mission %s: %d/%d%s' % (mission.get('mission'), after, goals[-1],
                                       ' (+%d XP, +%d stars)' % (xp, stars) if xp else ''), flush=True)
        return xp

    def publish(self):
        """The current mission's progress, for the period the DLL serves it with, and the cumulative stars."""
        from native_tradeups import atomic_write
        variants = self.variants()
        served = self.served()
        self.published = served
        lines = []
        choice = self.state.get('mission_choice')
        if variants and served and isinstance(choice, dict) and served[0] == choice.get('index') and served[0] < len(variants):
            progress = self.state['missions'].get('gen%d:%d' % (choice['gen'], choice['index']), 0)
            if progress: lines.append('%d %d %d\n' % (variants[served[0]]['mission'], served[1], progress))
        lines.append('stars %d\n' % self.state.get('mission_stars', 0))
        atomic_write(self.directory / PROGRESS_FILE, ''.join(lines))

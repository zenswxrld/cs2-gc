"""Count this week's mission from Game State Integration packets (bot matches never report quest progress).

Plan: cs2_gc_missions.json (native_missions.py) + cs2_gc_mission_current.txt (the DLL's current variant). Progress: cs2_gc_mission_progress.txt, one "mission period progress"
line per period plus a cumulative "stars N" line, read by the DLL (shown as the native CSOAccountRecurringMission
progress). Reaching a points tier pays that tier's XP through the helper's normal XP total and 1 star per 100 XP.

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
SESSION_FILE = 'cs2_gc_mission_session.txt'


class MissionTracker:
    def __init__(self, directory, state, now=time.time,defer_publish=False):
        self.directory, self.state, self.now = Path(directory), state, now
        self.state.setdefault('missions', {})
        self.last = None
        self.reason = None
        self.defer_publish=defer_publish

    def suspend(self,clear=False):
        (self.directory/SESSION_FILE).unlink(missing_ok=True)
        if clear:self.state.pop('mission_session',None)

    def keep_alive(self,game_map):
        session=self.state.get('mission_session')
        name=str(game_map.get('name') or '').replace('\\','/').rsplit('/',1)[-1]
        if session and session['map']==name and session['mode']==game_map.get('mode') and game_map.get('phase') in ('warmup','live'):
            from native_tradeups import atomic_write
            atomic_write(self.directory/SESSION_FILE,'%d %d %d\n'%(session['index'],session['period'],int(self.now())))
        else:self.suspend(clear=not name or game_map.get('phase')=='gameover')

    def session_plan(self,game_map,stats,player):
        """Keep one compatible mission for the full match; a short lease also pins the GC/UI schema."""
        name=str(game_map.get('name') or '').replace('\\','/').rsplit('/',1)[-1]
        mode,phase=game_map.get('mode'),game_map.get('phase')
        session=self.state.get('mission_session')
        score=(game_map.get('team_ct') or {}).get('score',0)+(game_map.get('team_t') or {}).get('score',0)
        kills=stats.get('kills',0)
        if session and (session['map']!=name or session['mode']!=mode or kills<session['kills'] or score<session['score']):
            session=None;self.state.pop('mission_session',None);self.last=None
        key,mission=self.plan()
        if session:
            try:
                variants=json.loads((self.directory/'cs2_gc_missions.json').read_text(encoding='utf-8'))['variants']
                mission=variants[session['index']];key='%d:%d'%(session['period'],session['index'])
            except (OSError,ValueError,KeyError,IndexError):session=None
        if not session and mission and mission.get('kind') and mission.get('mode')==mode and (not mission.get('maps') or name in mission['maps']) and phase in ('warmup','live'):
            period,index=(int(x) for x in key.split(':'))
            session={'period':period,'index':index,'map':name,'mode':mode,'kills':kills,'score':score}
        if session:
            session.update(kills=kills,score=score)
            self.state['mission_session']=session
            if phase in ('warmup','live'):
                from native_tradeups import atomic_write
                atomic_write(self.directory/SESSION_FILE,'%d %d %d\n'%(session['index'],session['period'],int(self.now())))
            else:self.suspend(clear=True)
        else:self.suspend(clear=True)
        return key,mission

    def plan(self):
        """(progress key, mission) of the current Armory rotation, from the DLL's cs2_gc_mission_current.txt."""
        try:
            variants = json.loads((self.directory / 'cs2_gc_missions.json').read_text(encoding='utf-8'))['variants']
            index, period = (int(x) for x in (self.directory / CURRENT_FILE).read_text().split()[:2])
        except (OSError, ValueError, KeyError):
            return None, None
        if not 0 <= index < len(variants): return None, None
        return '%d:%d' % (period, index), variants[index]

    def observe(self, provider, player, game_map, stats):
        """XP earned by mission tiers for this packet (0 when nothing changed)."""
        period, mission = self.session_plan(game_map,stats,player)
        if mission is None or not mission.get('kind'):
            self.explain('no countable mission (the DLL has not written %s yet)' % CURRENT_FILE if mission is None
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
        xp = sum(reward for goal, reward in zip(goals, rewards) if before < goal <= after)
        # User: missions also pay stars, 1 per 100 XP of each step reached (rounded up).
        stars = sum(-(-reward // 100) for goal, reward in zip(goals, rewards) if before < goal <= after)
        self.state['mission_stars'] = self.state.get('mission_stars', 0) + stars
        if not self.defer_publish:self.publish()
        print('Mission %s: %d/%d%s' % (mission.get('mission'), after, goals[-1],
                                       ' (+%d XP, +%d stars)' % (xp, stars) if xp else ''), flush=True)
        return xp

    def publish(self):
        from native_tradeups import atomic_write
        try:
            variants = json.loads((self.directory / 'cs2_gc_missions.json').read_text(encoding='utf-8'))['variants']
        except (OSError, ValueError, KeyError):
            variants = []
        lines = []
        for key, progress in sorted(self.state['missions'].items()):
            period, _, index = key.partition(':')
            if index.isdigit() and int(index) < len(variants):
                lines.append('%d %s %d\n' % (variants[int(index)]['mission'], period, progress))
        lines.append('stars %d\n' % self.state.get('mission_stars', 0))
        atomic_write(self.directory / PROGRESS_FILE, ''.join(lines))

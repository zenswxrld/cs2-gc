"""Read cumulative event counters from our owned local server plugin, never from GSI guesses."""
import hashlib,json,os,re,secrets
from pathlib import Path
from career_achievements import EVENT_KEYS
from local_stats import record

OWNER='cs2-gc-career-events-v1'
PLUGIN='CS2GCCareerBridge'

def prepare(directory,config):
    proxy=Path(directory).resolve();game=proxy.parents[1]
    payload=proxy/'cs2_gc_payload/career'
    if not (payload/'bundle.json').is_file():return 'unavailable: career event payload missing'
    api=game/'csgo/addons/counterstrikesharp/api/CounterStrikeSharp.API.dll'
    if (proxy/'cs2_gc_bot_plugins_disabled').exists() or not api.is_file():return 'unavailable: local server plugins are disabled or missing'
    spec=json.loads((payload/'bundle.json').read_text());binary=(payload/(PLUGIN+'.dll')).read_bytes()
    sha=lambda b:hashlib.sha256(b).hexdigest()
    if sha(binary)!=spec['sha256'] or sha(api.read_bytes())!=spec['api_sha256']:
        raise ValueError('Career event payload/API mismatch; no plugin was changed')
    target=game/'csgo/addons/counterstrikesharp/plugins'/PLUGIN
    marker=target/'cs2_gc_owner.json';dll=target/(PLUGIN+'.dll')
    prior=json.loads(marker.read_text()) if marker.exists() else {}
    if target.is_symlink() or (target.exists() and any(target.iterdir()) and prior.get('owner')!=OWNER):
        raise ValueError('Unowned career plugin folder; leaving it unchanged')
    if dll.exists() and sha(dll.read_bytes()) not in (prior.get('sha256'),spec['sha256']):
        raise ValueError('Career plugin was edited externally; leaving it unchanged')
    from fair_bot_policy import require_game_closed
    require_game_closed()
    from launch_setup import atomic_bytes
    target.mkdir(parents=True,exist_ok=True)
    if not dll.exists() or sha(dll.read_bytes())!=spec['sha256']:atomic_bytes(dll,binary)
    atomic_bytes(marker,(json.dumps(dict(owner=OWNER,sha256=spec['sha256']))+'\n').encode())
    return 'installed: server-confirmed flashes, smoke/blind kills, weapon classes and utility kills'

class CombatEvents:
    def __init__(self,rewards,pid):
        self.rewards=rewards;self.pid=pid;self.nonce=secrets.token_hex(16);self.pending=False
        self.published=None
        if pid:self.publish()

    def publish(self):
        state=self.rewards.state
        data=dict(pid=self.pid,nonce=self.nonce,owner=state.get('local_player',''))
        encoded=json.dumps(data)
        if encoded==self.published:return
        from gsi_rewards import atomic_text
        atomic_text(self.rewards.directory/'cs2_gc_combat_session.json',encoded);self.published=encoded

    def poll(self):
        if not self.pid:return False
        path=self.rewards.directory/'cs2_gc_combat_events.json'
        try:
            if self.pending:
                self.rewards.save();self.pending=False
            self.publish()
            if not path.is_file() or path.stat().st_size>1024*1024:return False
            data=json.loads(path.read_text(encoding='utf-8'))
            changed=self.consume(data)
            if changed:
                self.pending=True;self.rewards.save();self.pending=False
            return changed
        except (OSError,ValueError,TypeError,KeyError):return False

    def consume(self,data):
        if (not isinstance(data,dict) or data.get('version')!=1 or data.get('pid')!=self.pid
                or data.get('nonce')!=self.nonce):return False
        session=data.get('session');sequence=data.get('sequence');players=data.get('players')
        if (not isinstance(session,str) or not re.fullmatch('[0-9a-f]{32}',session)
                or type(sequence) is not int or sequence<0 or not isinstance(players,dict)):return False
        state=self.rewards.state;owner=state.get('local_player') or (state.get('last') or {}).get('player')
        if not isinstance(owner,str) or not owner.isdigit():return False
        totals=players.get(owner,{})
        if not isinstance(totals,dict) or any(k not in EVENT_KEYS or type(v) is not int or not 0<=v<=1000000000 for k,v in totals.items()):return False
        cursors=state.get('combat_event_cursors') or {}
        previous=cursors.get(session,{});old=previous.get('counts',{})
        if sequence<previous.get('sequence',-1) or any(totals.get(k,0)<v for k,v in old.items()):return False
        if sequence==previous.get('sequence') and totals!=old:return False
        if sequence==previous.get('sequence') and state.get('event_tracking_ready'):return False
        deltas={k:totals.get(k,0)-old.get(k,0) for k in EVENT_KEYS}
        record(state,**deltas)
        cursors=dict(cursors);cursors.pop(session,None)
        cursors[session]=dict(sequence=sequence,counts=dict(totals))
        state['combat_event_cursors']=dict(list(cursors.items())[-8:])
        state['event_tracking_ready']=True
        return True

"""Saved local combat totals from authenticated GSI deltas and owned server event counters."""
MAX=(1<<64)-1
from career_achievements import GOALS,EVENT_KEYS,unlocked,progress,recent_unlocks
KEYS=('kills','headshots','mvps','plants','defuses')+EVENT_KEYS

def achievements(state):
    return unlocked(state)

def record(state, **deltas):
    stats=state.setdefault('combat_stats',dict(version=1,**{k:0 for k in KEYS}))
    for key,delta in deltas.items():
        if key not in KEYS or type(delta) is not int or delta<0:raise ValueError('Invalid combat delta')
        prior=stats.get(key,0)
        if type(prior) is not int or not 0<=prior<=MAX:raise ValueError('Invalid saved combat total')
        stats[key]=min(MAX,prior+delta)

def snapshot(directory):
    import json
    from pathlib import Path
    from unboxing_stats import snapshot as openings
    from companions import snapshot as companions
    from collectible_rewards import snapshot as collectibles
    path=Path(directory)/'cs2_gc_gsi_state.json'
    state=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    def number(value):return value if type(value) is int and 0<=value<=MAX else 0
    combat=state.get('combat_stats') or {}
    return dict(matches=number(state.get('matches')),xp=number(state.get('total')),
                bonus_stars=number(state.get('mission_stars')),combat_available=bool(combat),
                combat={k:number(combat.get(k)) for k in KEYS},
                missions_completed=number(state.get('missions_completed')),unlocked=achievements(state),
                achievements=progress(state),achievement_stars=number(state.get('achievement_stars')),
                event_tracking_ready=bool(state.get('event_tracking_ready')),recent_unlocks=recent_unlocks(state),openings=openings(directory),companions=companions(directory),collectibles=collectibles(directory))

"""Align a restarted helper with paid inventory cursors without replaying old awards."""
import json
from pathlib import Path
from native_tradeups import parse

def paid(directory):
    path=Path(directory)/'cs2_gc_inventory.txt'
    if not path.is_file():return {'total':0,'matches':0,'mission_stars':0}
    root=parse(path.read_text(encoding='utf-8-sig')).one('inventory')
    def value(node,key):
        found=[n for n in node.children or [] if n.key==key]
        if len(found)>1 or (found and (found[0].children is not None or not str(found[0].value).isdigit())):
            raise ValueError('Invalid paid reward cursor: '+key)
        return int(found[0].value) if found else 0
    progress=[n for n in root.children if n.key=='progression']
    if len(progress)>1:raise ValueError('Duplicate progression block')
    return {'total':value(progress[0],'reward_total') if progress else 0,
            'matches':value(root,'match_reward_total'),'mission_stars':value(root,'mission_star_total')}

def reconcile(directory,state):
    floors=paid(directory)
    pending={}
    for key,floor in floors.items():
        current=state.get(key,0)
        if type(current) is not int or not 0<=current<(1<<64):raise ValueError('Invalid helper reward counter: '+key)
        if current<floor:
            # An older helper save cannot prove which old earnings are unpaid. Preserve its counters for recovery,
            # then start new earnings above the authoritative paid cursor. Never auto-grant ambiguous history twice.
            pending[key]={'helper':current,'paid':floor}
            state[key]=floor
    if pending:
        state.setdefault('reward_sync_review',[]).append(pending)
        print('Reward counters synchronized with the inventory. Earlier mismatched counters were preserved for review; new XP and match rewards can pay normally.',flush=True)
    return bool(pending)

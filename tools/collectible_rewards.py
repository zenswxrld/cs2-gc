"""Read authoritative native match milestones; never grant items from the UI."""
from pathlib import Path
from native_tradeups import parse

def snapshot(directory):
    result=dict(matches=0,paid=0)
    path=Path(directory)/'cs2_gc_inventory.txt'
    if not path.is_file():return result
    try:
        root=parse(path.read_text(encoding='utf-8-sig')).one('inventory')
        for key,name in [('match_reward_total','matches'),('career_collectible_mask','paid')]:
            nodes=[n for n in root.children if n.key==key]
            if nodes:
                if len(nodes)!=1 or not nodes[0].value.isdecimal():raise ValueError('Invalid milestone state')
                result[name]=int(nodes[0].value)
        if result['paid']>7 or result['matches']>2**64-1:raise ValueError('Invalid milestone state')
        return result
    except (ValueError,AttributeError,OSError):return dict(matches=0,paid=0)

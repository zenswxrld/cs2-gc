"""Whitelisted display snapshot of successful native openings, never inferred from inventory contents."""
import math
from pathlib import Path
from native_tradeups import parse
MAX=(1<<64)-1

def snapshot(directory):
    empty=dict(available=True,total=0,containers=0,armory=0,stattrak=0,rarities=[0]*9,recent=[],best=[])
    path=Path(directory)/'cs2_gc_inventory.txt'
    if not path.is_file():return empty
    try:
        root=parse(path.read_text(encoding='utf-8-sig')).one('inventory')
        nodes=[n for n in root.children if n.key=='unboxing']
        if not nodes:return empty
        if len(nodes)!=1:raise ValueError('Duplicate opening stats')
        node=nodes[0]
        def number(text,limit=MAX):
            if not isinstance(text,str) or not text.isdigit() or int(text)>limit:raise ValueError('Invalid opening counter')
            return int(text)
        if node.text('version')!='1':raise ValueError('Unsupported opening record')
        result=dict(available=True,**{k:number(node.text(k)) for k in ('total','containers','armory','stattrak')})
        if result['containers']+result['armory']!=result['total'] or result['stattrak']>result['total']:raise ValueError('Invalid totals')
        rarities=node.one('rarities')
        result['rarities']=[number(rarities.text(str(i))) for i in range(9)]
        if sum(result['rarities'])!=result['total']:raise ValueError('Invalid rarity totals')
        for name,limit in (('recent',8),('best',3)):
            entries=node.one(name).children
            if entries is None or len(entries)>limit:raise ValueError('Invalid opening history')
            rows=[];seen=set()
            for entry in entries:
                seq=number(entry.key,result['total']);words=(entry.value or '').split()
                if not seq or seq in seen or len(words)!=13:raise ValueError('Invalid opening record')
                seen.add(seq)
                stamp,source,item_id,definition,paint=map(number,words[:5]);wear=float(words[5])
                seed,rarity,st,gold,sticker,music,charm=map(number,words[6:])
                if not definition or source>1 or not math.isfinite(wear) or not 0<=wear<=1 or seed>1000 or rarity>7 or st>1 or gold>1:raise ValueError('Invalid opening item')
                rows.append(dict(sequence=seq,timestamp=stamp,source=source,id=str(1000000000000+item_id),definition=definition,
                    paint=paint,wear=wear,seed=seed,rarity=rarity,stattrak=bool(st),gold=bool(gold),sticker=sticker,music=music,charm=charm))
            result[name]=list(reversed(rows)) if name=='recent' else rows
        return result
    except (OSError,ValueError,TypeError,OverflowError):return dict(empty,available=False)

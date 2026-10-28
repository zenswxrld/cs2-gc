"""Safe view of permanent native egg/chicken items and their owned accessories."""
from pathlib import Path
from native_tradeups import parse
from chicken_cosmetics import ACCESSORIES
BREEDS={3:'Catalana',4:'Silkie',5:'Polish'}
STAGES=('Egg','Chick','Pullet','Hen')

def snapshot(directory):
    result=dict(selected='0',pets=[],accessories=[])
    path=Path(directory)/'cs2_gc_inventory.txt'
    if not path.is_file():return result
    try:
        root=parse(path.read_text(encoding='utf-8-sig')).one('inventory')
        active=[n.value for n in root.children if n.key=='pet_active']
        if active and int(active[0]):result['selected']=str(1000000000000+int(active[0]))
        for row in root.one('items').children:
            fields={n.key:n.value for n in row.children or [] if n.children is None}
            definition=int(fields.get('def_index',0))
            if 55000<=definition<=55009 and definition not in result['accessories']:result['accessories'].append(definition)
            if not fields.get('pet'):continue
            seed,breed,stage,age,hatch,accessory=map(int,fields['pet'].split())
            if definition not in (4948,4681) or breed not in BREEDS or not 0<=stage<=3 or hatch not in (1,2):continue
            result['pets'].append(dict(id=str(1000000000000+int(row.key)),seed=seed,breed=breed,name=BREEDS[breed],stage=stage,
                stage_name=STAGES[stage],age=age,hatch_at=hatch,accessory=accessory))
        result['catalogue']=[dict(definition=55000+i,id=key,name=name,rarity=rarity) for i,(key,name,rarity) in enumerate(ACCESSORIES)]
        return result
    except (ValueError,TypeError,OSError):return dict(result,available=False)

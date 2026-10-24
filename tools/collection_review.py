"""Small, idempotent target-client review fixes; preserve unrelated collections and owned kits."""
from copy import deepcopy
ORDER={'ancient':0,'legendary':1,'mythical':2,'rare':3,'uncommon':4}
EXPECTED=[1,2,3,4,6]

def counts(entries):
    return [sum(e['tier']==tier for e in entries) for tier in ORDER]

def material_entry(entry,donor,label,mode,themes):
    result=dict(entry)
    for field in ('effect_source','palette_source','pattern_source','signature_finish','random_on_pull'):
        result.pop(field,None)
    result.update(detail=1,donor=donor,label=label,mode=mode,themes=list(themes),review_revision=1)
    return result

def refine(lineup,rows,works,report):
    result=deepcopy(lineup);applied=[];unavailable=[]
    # Change the repeated AWP geometry, rather than cycling Man-o'-war through more hues.
    awps={
      'insignia':('cu_awp_hannya','Crown Regent','family',('Cobalt','Teal','Ash')),
      'ironclad':('cu_awp_asimov','Composite Armour','fixed',('Teal',)),
      'rampart':('cu_awp_cobra','Watchline','fixed',('Azure',)),
      'redoubt':('cu_awp_chroma_pink','Signal Breach','family',('Crimson','Amber','Ash')),
    }
    for icon,(donor,label,mode,themes) in awps.items():
        entries=result.get(icon,[])
        at=next((i for i,e in enumerate(entries) if e['weapon']=='weapon_awp' and
                 (e.get('donor')=='am_awp_glory' or e.get('donor')==donor)),None)
        if at is None:continue
        if donor not in rows or not works(donor,mode,themes):
            unavailable.append(icon+': AWP artwork unavailable');continue
        entries[at]=material_entry(entries[at],donor,label,mode,themes)
        applied.append(icon+': '+label)
    entries=result.get('insignia',[])
    by_weapon={e['weapon']:e for e in entries}
    if len(entries)==16 and all(w in by_weapon for w in ('weapon_famas','weapon_awp','weapon_hkp2000')):
        before=deepcopy(entries)
        famas,awp,p2000=(by_weapon[w] for w in ('weapon_famas','weapon_awp','weapon_hkp2000'))
        if awp.get('donor')=='cu_awp_hannya' and any(e.get('signature_finish') for e in entries):
            # A detailed AWP and the Foil AK earn the top tiers. The simple scale
            # FAMAS gets a lower rarity and a palette adjusted for its actual 5x gain.
            awp['tier']='ancient'
            famas.update(tier='mythical',mode='fixed',themes=['Cobalt'],label='Enamel Scale')
            p2000.update(tier='legendary',mode='fixed',themes=['Cobalt'])
            if counts(entries)!=EXPECTED or not works(famas['donor'],'fixed',['Cobalt']) or not works(p2000['donor'],'fixed',['Cobalt']):
                result['insignia']=before
                unavailable.append('insignia: premium tier migration retained until all materials work')
    # Keep the pictured Negev plate at Restricted. The M249 was already Mil-Spec.
    entries=result.get('juggernaut',[])
    heavy=next((e for e in entries if e.get('donor')=='am_diamond_plate' and e['tier']=='ancient'),None)
    rifle=next((e for e in entries if e['weapon']=='weapon_m4a1'),None)
    donor='cu_m4_asimov';themes=('Cobalt','Teal','Ash')
    if heavy and rifle:
        if donor in rows and works(donor,'family',themes) and works(heavy['donor'],'fixed',['Ash']):
            candidate=deepcopy(entries)
            for i,entry in enumerate(candidate):
                if entry['weapon']=='weapon_m4a1':
                    candidate[i]=material_entry(entry,donor,'Siege Protocol','family',themes)
                    candidate[i]['tier']='ancient'
                elif entry['weapon']==heavy['weapon']:
                    candidate[i].update(tier=rifle['tier'],mode='fixed',themes=['Ash'],label='Bastion Plate')
            if counts(candidate)==EXPECTED:
                result['juggernaut']=candidate
                applied.append('juggernaut: Iron Sovereign chase; plate Negev downgraded')
        else:unavailable.append('juggernaut: replacement chase unavailable')
    for entries in result.values():entries.sort(key=lambda e:ORDER[e['tier']])
    report['client_review']={'applied':applied,'unavailable':unavailable,
       'policy':'unique target artwork, reviewed channel palettes, original wear/masks, retained historical IDs'}
    return result

"""Recognisable chase artwork: one reviewed source per pool, native weapon layouts only."""
from copy import deepcopy
# Shortlist combines tracked player use and completed-sale activity, not a claim
# that a single universal popularity ranking exists. Sources documented alongside.
CHASES={
 'rampart':('gs_ak47_bloodsport','weapon_ak47','Oath Circuit','family',('Cobalt','Teal','Ash')),
 'warden':('gs_ak47_supercharged','weapon_ak47','Cold Ignition','family',('Cobalt','Teal','Ash')),
 'ashfall':('cu_ak47_rubber','weapon_ak47','Molten Guardian','family',('Crimson','Amber','Teal')),
 'nebula':('cu_m4a1_hyper_beast','weapon_m4a1_silencer','Voidborn','family',('Teal','Violet','Magenta')),
 'nightwatch':('cu_m4a1s_printstream','weapon_m4a1_silencer','Blackout Print','fixed',('Inverse',)),
 'redoubt':('cu_m4a4_neo_noir','weapon_m4a1','Gilded Sentinel','fixed',('Amber',)),
 'monsoon':('cu_m4a1s_cyrex','weapon_m4a1_silencer','Storm Circuit','family',('Emerald','Teal','Ash')),
 'talisman':('gs_ak47_empress','weapon_ak47','Jade Sovereign','family',('Emerald','Teal','Amber')),
 'zephyr':('cu_m4a4_temukau','weapon_m4a1','Jade Slipstream','fixed',('Emerald',)),
 'mosaic':('ak_porcelain','weapon_ak47','Prismatic Heirloom','family',('Magenta','Violet','Amber')),
}

def apply(lineup,rows,works,report):
    from collection_review import material_entry,counts,EXPECTED,ORDER
    result=deepcopy(lineup);applied=[];unavailable=[]
    for icon,(donor,weapon,label,mode,themes) in CHASES.items():
        entries=result.get(icon,[])
        chase=next((i for i,e in enumerate(entries) if e['tier']=='ancient'),None)
        if chase is None:continue
        # Explicit protection for the user's approved centrepiece and artwork.
        if entries[chase].get('label')=='Gold Brick':continue
        if donor not in rows or weapon not in rows[donor].get('guns',()) or not works(donor,mode,themes):
            unavailable.append(icon+': '+label+' artwork unavailable');continue
        occupied=next((i for i,e in enumerate(entries) if e['weapon']==weapon),None)
        at=chase if occupied is None else occupied
        candidate=deepcopy(entries)
        if at!=chase:
            displaced=deepcopy(entries[chase]);displaced['tier']=entries[at]['tier']
            if displaced['mode']=='family':
                choices=[t for t in displaced.get('themes',()) if works(displaced['donor'],'fixed',[t])]
                if not choices:
                    unavailable.append(icon+': former chase has no valid lower-tier colour');continue
                displaced.update(mode='fixed',themes=[choices[0]])
            candidate[chase]=displaced
        candidate[at]=material_entry(entries[at],donor,label,mode,themes)
        candidate[at].update(weapon=weapon,tier='ancient',popular_chase_revision=1)
        if counts(candidate)!=EXPECTED or len({e['weapon'] for e in candidate})!=16:
            unavailable.append(icon+': retained full pool pending valid chase layout');continue
        if sum(e['mode']=='family' for e in candidate)>2:
            unavailable.append(icon+': retained pool to avoid excess colour families');continue
        candidate.sort(key=lambda e:ORDER[e['tier']])
        result[icon]=candidate;applied.append(icon+': '+label)
    report['popular_chases']={'applied':applied,'unavailable':unavailable,
        'policy':'source-native artwork, protected neutral/portrait details, distinct non-stock variants'}
    return result

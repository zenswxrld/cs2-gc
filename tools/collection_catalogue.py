"""Install the reviewed 36-pool matrix atomically, keeping approved and owned skins."""
from copy import deepcopy
from collection_review import counts,EXPECTED

REVISION=2

def apply(lineup,rows,works,report):
    from collection_catalogue_designs import LINEUPS,PROFILES
    result=deepcopy(lineup);applied=[];unavailable=[];preserved=[]
    for icon,current in lineup.items():
        proposed=LINEUPS.get(icon)
        if proposed is None:continue
        if current==proposed:
            preserved.append(icon);continue
        # All entries are checked before publishing any part of a pool. A
        # mismatch retains the complete saved pool and reports the failed slot.
        reason=None
        if counts(proposed)!=EXPECTED or len({e['weapon'] for e in proposed})!=16:
            reason='invalid authored tier/weapon layout'
        elif not 1<=sum(e['mode']=='family' for e in proposed)<=2:
            reason='invalid authored family count'
        else:
            for entry in proposed:
                donor=entry.get('donor');row=rows.get(donor,{})
                # The retained Gold Brick/Berry/Spoon/Foil adapters are the only
                # explicit cross-layout exceptions; new artwork uses native UVs.
                adapted=(entry.get('pattern_source') or entry.get('palette_source') or entry.get('signature_finish')
                         or row.get('transfer'))
                if not row or (not adapted and entry['weapon'] not in row.get('guns',())):
                    reason=entry['label']+': native artwork unavailable';break
                if not works(donor,entry['mode'],entry.get('themes',()),entry.get('palette_source'),
                             entry.get('pattern_source'),entry.get('effect_source')):
                    reason=entry['label']+': distinct material/effect unavailable';break
        # Protect approved additions even if an older/newer saved pool differs
        # from the preflight baseline. Never silently replace a later revision.
        for entry in current:
            if entry.get('popular_chase_revision') or entry.get('signature_finish') or entry.get('pattern_source') or entry.get('palette_source'):
                comparable=lambda e:{k:v for k,v in e.items() if k!='all_collection_revision'}
                if not any(comparable(e)==comparable(entry) for e in proposed):
                    reason=entry.get('label','approved finish')+': retain newer approved entry';break
        if reason:
            unavailable.append({'collection':icon,'reason':reason});continue
        result[icon]=deepcopy(proposed);applied.append(icon)
    failed={item['collection'] for item in unavailable}
    active=[icon for icon,entries in result.items() if icon not in failed and len(entries)==16 and all(e.get('all_collection_revision')==REVISION for e in entries)]
    report['all_collection_rebuild']={'revision':REVISION,'applied':applied,'unchanged':preserved,
        'active':active,'unavailable':unavailable,'collections':len(active),'slots':sum(len(result[i]) for i in active),
        'profiles':{i:PROFILES[i] for i in active},
        'policy':'native artwork, narrow pool palette, retained approved additions/history, complete pools only',
        'visual_status':'material preflight passed; mounted client appearance needs review'}
    return result


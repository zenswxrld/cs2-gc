"""Targeted feedback changes and palette/effect coverage; retain good artwork."""
from collection_policies import coordinate

def install(entries,donor,weapon,label,themes,rows,works):
    if donor not in rows or not works(donor,'family',themes):return False
    target=next((i for i,e in enumerate(entries) if e['tier']=='legendary' and e['mode']=='family'),None)
    if target is None:target=next((i for i,e in enumerate(entries) if e['tier']=='legendary'),None)
    if target is None:return False
    occupied=next((i for i,e in enumerate(entries) if e['weapon']==weapon),None)
    if occupied is not None and entries[occupied]['tier']=='ancient':return False
    at=target if occupied is None else occupied
    displaced=dict(entries[target])
    if at!=target:
        displaced['tier']=entries[at]['tier']
        if displaced['tier'] not in ('ancient','legendary') and displaced['mode']=='family':
            choices=[t for t in displaced.get('themes',()) if works(displaced['donor'],'fixed',[t])]
            if not choices:return False
            displaced.update(mode='fixed',themes=[choices[0]])
        entries[target]=displaced
    entries[at]={'detail':1,'donor':donor,'weapon':weapon,'label':label,'tier':'legendary',
                 'mode':'family','themes':list(themes),'signature_finish':True,'random_on_pull':True}
    order={'ancient':0,'legendary':1,'mythical':2,'rare':3,'uncommon':4}
    entries.sort(key=lambda item:order[item['tier']])
    return True

def polish(lineup,rows,works,report):
    lineup=coordinate(lineup,rows,works,report)
    installed=[]
    recipes=(('phantom_blade','aq_deagle_case_hardened_2','weapon_deagle','Rainbow Spoon',
              ('Cobalt','Violet','Magenta','Midnight')),
             ('insignia','gsch_ak_djiin','weapon_ak47','Foil',('Cobalt','Teal','Ash')))
    for icon,donor,weapon,label,themes in recipes:
        entries=lineup.get(icon,[])
        if entries and not any(e.get('donor')==donor and e.get('signature_finish') for e in entries):
            if install(entries,donor,weapon,label,themes,rows,works):installed.append(icon+':'+label)
    for entry in lineup.get('ashfall',()):
        if entry.get('donor')=='aa_flames' and entry['weapon']=='weapon_deagle' and works('aa_flames','fixed',['Teal']):
            entry.update(mode='fixed',themes=['Teal'],label='Blaze')
    from collection_review import refine
    lineup=refine(lineup,rows,works,report)
    from popular_chases import apply as apply_popular
    lineup=apply_popular(lineup,rows,works,report)
    from collection_catalogue import apply as apply_catalogue
    lineup=apply_catalogue(lineup,rows,works,report)
    coverage={};missing=[]
    for icon,entries in lineup.items():
        found=[]
        for entry in entries:
            if (rows.get(entry.get('donor'),{}).get('effects') or entry.get('effect_source') or entry.get('signature_finish')):
                found.append(entry.get('label',entry.get('donor','')))
        if not found:
            candidates=sorted((e for e in entries if e.get('donor') in rows and e['mode'] in ('family','fixed')
                               and e.get('label')!='Gold Brick' and not e.get('pattern_source')),
                               key=lambda e:0 if e['tier']=='legendary' else 1 if e['tier']=='mythical' else 2)
            for entry in candidates:
                if works(entry['donor'],entry['mode'],entry.get('themes',()),entry.get('palette_source'),
                         entry.get('pattern_source'),'am_jorm_blue'):
                    entry['effect_source']='am_jorm_blue'
                    found.append(entry.get('label',entry['donor']))
                    break
        if not found:missing.append(icon)
        coverage[icon]=found
    report['signature_families']=installed
    report['signature_family_status']={icon:('available' if any(e.get('donor')==donor and e.get('signature_finish')
        and e.get('mode')=='family' for e in lineup.get(icon,())) else 'material unavailable; saved slot retained')
        for icon,donor,weapon,label,themes in recipes}
    report['special_finishes']={'coverage':coverage,'missing':missing,
      'policy':'active source effect or compatible shader with observed pearl scalar; client visual review required'}
    return lineup

"""Authored collection upgrades; keep old definitions, masks and effect layers intact."""
import colorsys
import re

DESIGNS = {
 'forged': {'revision':2,'weapon':'weapon_ak47','palette':('Crimson','Amber','Cobalt','Teal','Violet','Ember'),
  'motifs':('metal','steel','copper','brass','plate','forge','titanium','crystal'),
  'chase':{'donor':'am_gold_brick','weapon':'weapon_ak47','pattern_source':'am_doppler_phase2','label':'Gold Brick','themes':('Gold',)},
  'modes':{'ancient':('fixed',),'legendary':('family','family')},
  'names':('Gold Brick','Furnace Glass','Tempered Crown','Brassworks','Quenched Edge','Heat Bloom','Mill Scale',
           'Rivet Line','Oxide Vein','Sootfall','Foundry Dust','Cast Iron','Slag Trail','Heat Mark','Billet','Cold Press')},
 'phantom_blade': {'weapon':'weapon_m4a1_silencer','palette':('Violet','Cobalt','Teal','Rose','Midnight','Galaxy'),
  'motifs':('iridescent','pearl','glass','obsidian','shadow','night','shard','crystal'),
  'names':('Veil Piercer','Ghostglass','Wraith Edge','Silent Oath','Moonshard','Spectral Trace','Black Veil',
           'Afterimage','Night Etching','Cold Apparition','Hush','Shade Line','Mistfall','Dark Signal','Pale Echo','Vesper')},
 'harbor': {'weapon':'weapon_awp','palette':('Cobalt','Teal','Coral','Amber','Ocean','Glacier'),
  'motifs':('water','ocean','marine','storm','tide','ripple','wave','naut','blueprint'),
  'family':{'donor':'aa_fade_m4a1s','weapon':'weapon_m4a1_silencer','palette_source':'aa_fade_red_blue','label':'Berry Current'},
  'names':('Stormwatch','Stormglass','Breakwater','Tide Chart','Saltline','Deep Current','Bluewake','Docklight',
           'Sea Glass','Hull Mark','Mooring','Wake Line','Salt Spray','Low Tide','Patina','Sounding')},
 'mosaic': {'weapon':'weapon_deagle','palette':('Vapor','Lime','Sunrise','Royal','Candy','Teal'),
  'motifs':('mosaic','tile','diamond','geomet','prism','polygon','hex','triangle','stained'),
  'family':{'donor':'aa_awp_fade','weapon':'weapon_awp','palette_source':'aa_fade_red_blue','label':'Berry Duet'},
  'names':('Prismatic Reliquary','Prismglass','Jewelbox','Tessera','Broken Light','Inlay','Glazed Edge','Tilework',
           'Colour Study','Fracture Line','Grout','Ceramic Dust','Split Hue','Shardfall','Kiln Mark','Small Pieces')},
}

def recolour(colors,theme):
    if theme=='Gold':return [list(c) for c in colors]
    import native_finishes as f
    from collection_detail import recolour_details
    return recolour_details(colors,theme,f.THEMES,f.DUO_THEMES,f.GRADIENT_THEMES)

def visible_accent_change(original,changed):
    moves=[sum((x-y)**2 for x,y in zip(a[:3],b[:3]))**.5 for a,b in zip(original,changed)]
    # A protected ink/metal channel is allowed to remain byte-for-byte identical.
    painted=[m for m in moves if m>=.08]
    return bool(painted) and max(painted)>=.14 and sum(painted)/len(painted)>=.14

def donor_fit(name,row,design,tier):
    text=(name+' '+row.get('title','')).lower()
    motif=sum(word in text for word in design.get('motifs',()))
    # Preserve existing shader effects, do not invent effect settings or infer
    # glitter from the generic default glitter-normal texture binding.
    effects=row.get('effects',())
    premium=bool(effects) and tier in ('ancient','legendary')
    patterned=row.get('style') in (1,2,4,5)
    return motif*20 + premium*50 + patterned*3

def upgrade(lineup,rows,guns,icons,families,works,report):
    import gun_collections as gc
    selected=[icon for icon in icons if icon in DESIGNS and
              not all(e.get('detail')==DESIGNS[icon].get('revision',1) for e in lineup.get(icon,()))]
    if not selected:return lineup
    reserved={e['donor'] for icon,entries in lineup.items() if icon not in selected
              for e in entries if 'donor' in e}
    planned=gc.plan(rows,guns,selected,families,works,seed='cs2gc-authored-detail-v1',
                    designs=DESIGNS,reserved=reserved)
    result={icon:[dict(e) for e in entries] for icon,entries in lineup.items()}
    upgraded=[]
    for icon,entries in planned.items():
        counts=[sum(e['tier']==tier for e in entries) for tier,_ in gc.TIER_COUNTS]
        if counts != [count for _,count in gc.TIER_COUNTS]:
            report.setdefault('rebuild_unavailable',[]).append({'collection':icon,'counts':counts})
            continue # keep the complete previous pool, never sell a partial set
        result[icon]=entries
        upgraded.append(icon)
    report['rebuilt_collections']=upgraded
    return result

def audit(lineup,rows):
    """Review every visible slot, even collections outside the initial rebuild batch."""
    uses={}
    patterns={}
    for icon,entries in lineup.items():
        for e in entries:
            donor=e.get('donor')
            if donor:
                uses.setdefault(donor,[]).append(icon)
                row=rows.get(donor,{})
                key=(row.get('pattern'),e['weapon'],tuple(e.get('themes',())))
                patterns.setdefault(key,[]).append((icon,donor))
    result={}
    for icon,entries in lineup.items():
        issues=[]
        for index,e in enumerate(entries):
            donor=e.get('donor')
            row=rows.get(donor,{})
            if not donor:continue
            if not row:issues.append({'slot':index+1,'issue':'donor unavailable'});continue
            if e['mode'] in ('fixed','family') and not e.get('detail'):
                issues.append({'slot':index+1,'issue':'existing generation; inspect repaired trim/contrast and material fallback report'})
            if e['mode']=='transfer' and e['weapon'] in row.get('pattern_guns',()):
                issues.append({'slot':index+1,'issue':'official finish repeated on original weapon'})
            key=(row.get('pattern'),e['weapon'],tuple(e.get('themes',())))
            if row.get('pattern') and len(patterns.get(key,()))>1:
                issues.append({'slot':index+1,'issue':'shared pattern/weapon/colourway; inspect for duplicate look',
                               'collections':sorted({item[0] for item in patterns[key]})})
            if len(uses[donor])>1:
                issues.append({'slot':index+1,'issue':'reused donor; compare actual weapon/colourway','collections':sorted(set(uses[donor]))})
            if e['tier'] in ('ancient','legendary') and row.get('style') in (0,3):
                issues.append({'slot':index+1,'issue':'simple finish in premium slot; visual review'})
        result[icon]={'slots':len(entries),'detail_revision':all(e.get('detail') for e in entries),
                      'issues':issues,'visual_status':'requires target-client review'}
    return result

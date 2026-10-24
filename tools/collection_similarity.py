"""Conservative pattern/material + palette similarity checks, on the same weapon.

This is a material-level preflight, not a rendered-image approval. It catches
aliases, official palette copies and weak recolours. Layout/lighting still need
target-client review. Historical inventory definitions are never removed.
"""
import math

GEOMETRY_FAMILIES = (
 'am_jorm_', 'am_crystallized', 'am_ossify', 'am_carbon_fiber',
 'am_ddpatdense_', 'hy_ddpat', 'hy_varicamo', 'hy_geometric_steps_',
 'hy_kimono_diamonds', 'sp_zebracam', 'hy_webs', 'am_seastorm',
 'hy_ak47lam', 'am_knots_', 'am_tigers_', 'hy_veneto_',
)

def geometry(name,row):
    for prefix in GEOMETRY_FAMILIES:
        if name.startswith(prefix):return ('family',prefix)
    return ('texture',row.get('pattern') or name)

def near(first,second):
    if not first or not second or len(first)!=len(second):return False
    moves=[math.sqrt(sum((a-b)**2 for a,b in zip(x[:3],y[:3]))) for x,y in zip(first,second)]
    # A small trim-only shift must not turn a stock design into a custom premium.
    return max(moves)<.22 or sum(moves)/len(moves)<.075

def effective(palette,gain=1):
    return [[min(1,max(0,float(v)*gain)) for v in c[:3]] for c in palette]

class Guard:
    def __init__(self,rows,palette_for):
        self.rows,self.palette_for=rows,palette_for
        self.registry={}
        self.rejected=0
        self.unrated=set()
        for name,row in sorted(rows.items()):
            palette=row.get('colors') or []
            if not palette:continue
            for weapon in row.get('guns',()):
                self.record(name,weapon,palette,'official:'+name)

    def key(self,donor,weapon,entry=None):
        row=self.rows[donor]
        shape=('pattern_source',entry['pattern_source']) if entry and entry.get('pattern_source') else geometry(donor,row)
        return (weapon,row.get('style',0),shape)

    def record(self,donor,weapon,palette,label,entry=None):
        key=self.key(donor,weapon,entry)
        p=effective(palette,self.rows[donor].get('brightness',1))
        self.registry.setdefault(key,[]).append((p,label))

    def matches(self,donor,weapon,palette,entry=None):
        if not palette:return []
        p=effective(palette,self.rows[donor].get('brightness',1))
        return [label for other,label in self.registry.get(self.key(donor,weapon,entry),()) if near(p,other)]

    def allowed(self,donor,weapon,mode,themes,entry=None,commit=False):
        if mode=='knife_family':return list(themes)
        choices=themes if mode!='transfer' else [None]
        accepted=[];palettes=[]
        from collection_detail import palettes_distinct
        for theme in choices:
            palette=self.palette_for(donor,theme,entry or {})
            if not palette:
                # Texture-only designs have their own decoder change/stock-hue
                # gate. Do not invent a four-colour signature for their artwork.
                self.unrated.add(donor)
                accepted.append(theme);palettes.append(None)
                continue
            if self.matches(donor,weapon,palette,entry):
                if commit:self.rejected+=1
                continue
            if mode=='family' and any(p and not palettes_distinct(palette,p) for p in palettes):continue
            accepted.append(theme);palettes.append(palette)
        if len(accepted)<(3 if mode=='family' else 1):
            if commit:self.rejected+=1
            return None
        if commit:
            for theme,palette in zip(accepted,palettes):
                if palette:self.record(donor,weapon,palette,'custom:'+donor+':'+str(theme),entry)
        return [] if mode=='transfer' else accepted

    def reserve(self,lineup):
        for icon,entries in lineup.items():
            for entry in entries:
                donor=entry.get('donor')
                if donor not in self.rows:continue
                for theme in entry.get('themes',()) if entry['mode']!='transfer' else [None]:
                    palette=self.palette_for(donor,theme,entry)
                    if palette:self.record(donor,entry['weapon'],palette,icon+':'+str(theme),entry)

def audit(lineup,rows,palette_for):
    """Compare every visible outcome, across all 36 pools and the official catalogue."""
    guard=Guard(rows,palette_for)
    flags=[];slots=0;outcomes=0;unrated=[]
    for icon,entries in lineup.items():
        for index,entry in enumerate(entries):
            slots+=1
            donor=entry.get('donor')
            if donor not in rows:
                unrated.append({'collection':icon,'slot':index+1,'reason':'external family; target-client review'})
                continue
            themes=entry.get('themes',()) if entry['mode']!='transfer' else [None]
            for theme in themes:
                outcomes+=1
                palette=palette_for(donor,theme,entry)
                if not palette:
                    unrated.append({'collection':icon,'slot':index+1,'theme':theme,'reason':'texture-authored variant; decoder gate and visual review'})
                    continue
                matches=guard.matches(donor,entry['weapon'],palette,entry)
                if matches:flags.append({'collection':icon,'slot':index+1,'weapon':entry['weapon'],
                    'donor':donor,'theme':theme,'matches':matches,'issue':'same pattern family and near palette'})
                guard.record(donor,entry['weapon'],palette,icon+':'+str(index+1)+':'+str(theme),entry)
    return {'collections':len(lineup),'slots':slots,'outcomes':outcomes,'near_matches':flags,'unrated':unrated,
            'scope':'same weapon, actual shared pattern or known geometry family, brightness-adjusted palettes',
            'visual_status':'target-client review required; different patterns can still look similar'}

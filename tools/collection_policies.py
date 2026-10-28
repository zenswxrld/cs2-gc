"""Collection palettes: related hues plus neutral hardware, not a random wheel."""
PALETTES={
 'forged':('Amber','Cobalt','Teal','Ash'),
 'phantom_blade':('Cobalt','Violet','Magenta','Midnight'),
 'harbor':('Emerald','Teal','Azure','Cobalt','Ash'),
 'mosaic':('Magenta','Violet','Rose','Amber'),
 'kestrel':('Amber','Emerald','Teal','Ash'),
 'juggernaut':('Cobalt','Teal','Azure','Ash'),
 'lodestar':('Violet','Teal','Magenta','Midnight'),
 'fathom':('Emerald','Teal','Violet','Midnight'),
 'ashfall':('Teal','Ember','Amber','Ash'),
 'aurora':('Emerald','Teal','Azure','Violet'),
 'brimstone':('Crimson','Ember','Sunrise','Amber','Ash'),
 'cascade':('Emerald','Teal','Azure','Cobalt','Glacier'),
 'cinder':('Crimson','Ember','Sunrise','Amber','Ash'),
 'eclipse':('Cobalt','Violet','Magenta','Midnight'),
 'halcyon':('Emerald','Teal','Azure','Glacier','Ash'),
 'kaleido':('Magenta','Violet','Rose','Amber'),
 'monsoon':('Emerald','Teal','Azure','Cobalt','Ash'),
 'nebula':('Cobalt','Violet','Magenta','Midnight'),
 'solstice':('Crimson','Ember','Sunrise','Amber','Ash'),
 'zephyr':('Emerald','Teal','Azure','Glacier','Ash'),
 'tidewater':('Emerald','Teal','Azure','Cobalt','Ash'),
 'obelisk':('Cobalt','Violet','Magenta','Midnight','Ash'),
 'zenith':('Emerald','Teal','Azure','Cobalt','Ash'),
 'rampart':('Cobalt','Teal','Azure','Ash'),
 'ironclad':('Cobalt','Teal','Azure','Ash'),
 'marauder':('Crimson','Ember','Sunrise','Amber','Ash'),
 'nightwatch':('Cobalt','Violet','Magenta','Midnight','Ash'),
 'outrider':('Amber','Lime','Emerald','Teal','Ash'),
 'quarry':('Emerald','Teal','Cobalt','Glacier','Ash'),
 'redoubt':('Crimson','Ember','Sunrise','Amber','Ash'),
 'talisman':('Emerald','Teal','Amber','Ash'),
 'undertow':('Emerald','Teal','Azure','Cobalt','Ash'),
 'cipher':('Emerald','Teal','Azure','Ash'),
 'driftwood':('Amber','Lime','Emerald','Teal','Ash'),
 'insignia':('Cobalt','Teal','Ash'),
 'warden':('Cobalt','Teal','Azure','Ash'),
}

def apply_designs(designs):
    for icon,design in designs.items():
        if icon in PALETTES:
            design['palette']=PALETTES[icon]
            design['family_palette']=PALETTES[icon]
            design['full_family_palette']=True

def history_entry(history,name,entry):
    # A narrowed visible family must not erase older rolled inventory variants.
    saved=dict(entry)
    prior=history.get(name,{})
    if saved.get('mode')=='family' and prior.get('mode')=='family':
        saved['themes']=list(dict.fromkeys(list(prior.get('themes',()))+list(saved.get('themes',()))))
    history[name]=saved

def coordinate(lineup,rows,works,report):
    import colorsys
    import native_finishes as f
    from collection_rebuild import DESIGNS
    result={icon:[dict(e) for e in entries] for icon,entries in lineup.items()}
    changes=[];unresolved=[]
    def hue(theme):
        if theme in f.THEMES:return f.THEMES[theme][0]
        if theme in f.DUO_THEMES:return f.DUO_THEMES[theme][0]
        return f.GRADIENT_THEMES.get(theme,([0],0))[0][0]
    def distance(a,b):
        d=abs(hue(a)-hue(b))%360
        return min(d,360-d)
    for icon,entries in result.items():
        allowed=PALETTES.get(icon)
        if not allowed:continue
        for slot,entry in enumerate(entries):
            if entry.get('label')=='Gold Brick' or entry.get('pattern_source') or entry.get('signature_finish') or entry.get('review_revision') or entry.get('themes')==['Inverse']:
                continue
            donor=entry.get('donor')
            if donor not in rows:continue
            mode=entry['mode']
            if mode=='transfer':
                # Neutral stock metal remains useful hardware. Other transferable
                # patterns must also receive the collection's coordinated colours.
                if donor in ('am_carbon_fiber','am_oval_hex','an_silver','aq_blued','so_whiteout_riptide','so_night'):
                    continue
                if rows[donor].get('recolour'):mode='fixed'
                else:
                    unresolved.append({'collection':icon,'slot':slot+1,'reason':'uncoloured transfer requires visual palette review'})
                    continue
            if mode not in ('family','fixed'):continue
            existing=list(entry.get('themes',()))
            candidates=list(dict.fromkeys([t for t in existing if t in allowed]+list(allowed)))
            if mode=='fixed':
                anchor=existing[0] if existing else allowed[0]
                candidates.sort(key=lambda t:(t!=anchor,distance(t,anchor)))
                chosen=next(([t] for t in candidates if works(donor,'fixed',[t],entry.get('palette_source'),entry.get('pattern_source'))),None)
            else:
                chosen=[t for t in candidates if works(donor,'fixed',[t],entry.get('palette_source'),entry.get('pattern_source'))]
                if not works(donor,'family',chosen,entry.get('palette_source'),entry.get('pattern_source')):chosen=None
            if chosen is None:
                unresolved.append({'collection':icon,'slot':slot+1,'reason':'no visible coordinated colourway; retained for explicit review'})
                continue
            if chosen!=existing:
                entry['themes']=chosen
                entry['mode']=mode
                changes.append({'collection':icon,'slot':slot+1,'from':existing,'to':chosen})
    report['palette_review']={'changes':changes,'unresolved':unresolved,'collections':len(result)}
    return result

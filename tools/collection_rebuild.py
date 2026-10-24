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

# Batch two uses explicit semantic pools. Effects cannot admit unrelated art.
DESIGNS.update({
 'kestrel': {'weapon':'weapon_aug','palette':('Cobalt','Amber','Forest','Glacier','Teal','Midnight'),
  'motifs':('wing','feather','bird','usaf','tact','camo','air'),
  'allow':('hy_feathers_aug','hy_p250_crackshot','hy_usaf_round','hye_yellow_usaf','hye_geobirds',
           'hye_geobirds_sunrise','spe_missile','am_black_panther','hy_arctic','hy_arctic_contrast',
           'hy_varicamo','hy_varicamo_blue','hy_varicamo_desert','hy_varicamo_night','hy_varicamo_red',
           'hy_varicamo_urban','sp_camo_wood_blue','sp_khaki_camo','ht_simple_camo','so_space_marine',
           'soe_blue_and_chrome','soe_blue_famas','so_aqua','so_stormfront','an_titanium30v'),
  'chase':{'donor':'hy_feathers_aug','weapon':'weapon_aug','label':'Apex Flight','required':True},
  'family':{'donor':'hy_p250_crackshot','weapon':'weapon_p250','label':'Talon Trace','required':True},
  'names':('Apex Flight','Talon Trace','Air Command','Wingtip','Strike Vector','Flightline','Raptor Grid',
           'Crosswind','Airframe','Cloudbreak','Field Wing','Wind Shear','Scout Pattern','Flight Dust','High Ground','Patrol')},
 'juggernaut': {'weapon':'weapon_negev','palette':('Crimson','Amber','Cobalt','Ember','Midnight','Violet'),
  'motifs':('steel','metal','plate','carbon','gunmetal','armor','titanium'),
  'allow':('am_diamond_plate','am_carbon_fiber','am_carbon_fiber_cz75','am_ddpatdense_silver','am_urban',
           'am_oval_hex','am_metal_inlay','am_metals','ht_metal_edges','hye_chrome_ripple','an_gunmetal_bravo',
           'an_titanium30v','aq_blued','aq_steel','aq_steel_bravo','aq_steel_inferno','hy_blueprint_aqua',
           'hy_blueprint_red','so_night','so_stormfront','so_space_marine','sp_overpass_paint_pen_metal',
           'am_fluted_tec9','hy_red_hex','hy_redhex','hy_bluehex','ht_white_edges'),
  'chase':{'donor':'am_diamond_plate','weapon':'weapon_negev','label':'Siegebreaker','required':True},
  'family':{'donor':'ht_white_edges','weapon':'weapon_glock','label':'Reactive Armour','required':True},
  'names':('Siegebreaker','Reactive Armour','Iron Dominion','Ablative','Rivet Guard','Bastion Plate','Steel Tread',
           'Carbon Lock','Hardpoint','Armourline','Reinforced','Mill Finish','Boltwork','Chassis','Heavy Gauge','Workshop')},
 'lodestar': {'weapon':'weapon_awp','palette':('Violet','Teal','Emerald','Magenta','Galaxy','Midnight'),
  'motifs':('star','space','moon','galaxy','meteor','crystal','quartz','irides','pearl'),
  'allow':('am_aqua_flecks','am_copper_flecks','aa_spacerace_orange','sp_spacerace_blue','sp_star_bravo',
           'hy_zodiac1','aa_glock_18_urban_moon_fever','aa_ump45_moonrise_sunset','am_crystallized',
           'am_crystallized_blue','am_crystallized_dark','am_crystallized_silver','am_crystallized_green',
           'am_crystallized_dark_green','soe_pink_pearl','soe_purple','hy_geometric_steps_pearl',
           'soe_blue_and_chrome','hy_cloud_camo','so_night','an_silver','so_whiteout_riptide'),
  'chase':{'donor':'am_aqua_flecks','weapon':'weapon_awp','label':'Northstar','required':True},
  'family':{'donor':'soe_pink_pearl','weapon':'weapon_cz75a','label':'Stardust','required':True},
  'names':('Northstar','Stardust','Astral Meridian','Moonfall','Orbit Glass','Meteor Trace','Celestial Map',
           'Star Metal','Night Compass','Lunar Phase','Orbital Dust','Far Signal','Cold Vacuum','Silver Transit','Sky Chart','Distant Light')},
 'fathom': {'weapon':'weapon_mp9','palette':('Violet','Emerald','Coral','Teal','Ocean','Midnight'),
  'motifs':('water','ocean','sea','wave','coral','tide','ripple','topo','jorm'),
  'allow':('am_jorm_blue','am_ossify_blue','am_ossify_blue_p2000_bravo','am_seastorm','am_seastorm_blood',
           'am_seastorm_shojo','am_zebra_dark','am_mac10_oceani','am_mag7_caustic','am_tec_9_sea_salt',
           'hy_ocean_bravo','hy_seaside_bravo','hy_water_crest','hy_p2000_oceani','hye_topo','hye_coral',
           'hye_pink_coral','sp_galil_wave','sp_spray_water','sp_spray_waves_bravo','sp_tape_dots_waves',
           'am_p250_sputnik','am_ump45_electrowave','soe_teal_glitter','cu_famas_holo_ocean'),
  'chase':{'donor':'am_jorm_blue','weapon':'weapon_mp9','label':'Leviathan','required':True},
  'family':{'donor':'cu_famas_holo_ocean','weapon':'weapon_famas','label':'Abyssal Nephthys',
            'themes':('Violet','Emerald','Coral','Amber'),'required':True},
  'slots':{('legendary',1):{'donor':'soe_teal_glitter','weapon':'weapon_hkp2000','label':'Bioluminescence',
                          'themes':('Violet',),'required':True}},
  'names':('Leviathan','Abyssal Nephthys','Bioluminescence','Pressure Glass','Black Current','Deepwater',
           'Trenchline','Reef Shadow','Drowned Signal','Tidal Mark','Salt Deposit','Ocean Floor','Dark Shoal','Depth Gauge','Silt Line','Undertow')},
})

from remaining_collection_designs import designs as remaining_designs
DESIGNS.update(remaining_designs())

def eligible(name,row,design,tier):
    allowed=design.get('allow')
    if allowed is None:return True
    if name not in allowed:return False
    if tier in ('ancient','legendary'):
        if design.get('premium') and name not in design['premium']:return False
        return bool(row.get('effects')) or row.get('style') in (1,4,5)
    return True

def feedback(lineup,rows,works,report):
    """Repair reviewed slots without reshuffling the approved chases."""
    current=lineup.get('phantom_blade',[])
    if len(current)!=16 or not all(e.get('detail') for e in current):return lineup
    if all(e.get('feedback_revision')==1 for e in current):return lineup
    if 'cu_usp_printstream' not in rows or 'hy_geometric_steps_pearl' not in rows:return lineup
    if not works('cu_usp_printstream','fixed',['Inverse']):return lineup
    if not works('hy_geometric_steps_pearl','family',['Violet','Cobalt','Teal','Rose']):return lineup
    result={icon:[dict(e) for e in entries] for icon,entries in lineup.items()}
    entries=result['phantom_blade']
    nova=next((dict(e) for e in entries if e.get('label')=='Wraith Edge'),None)
    if nova:
        nova.update(tier='mythical',mode='fixed')
        entries[3]=nova
    entries[1]={'detail':1,'tier':'legendary','weapon':'weapon_usp_silencer','mode':'fixed',
                'donor':'cu_usp_printstream','themes':['Inverse'],'label':'Ghostglass Inverse'}
    entries[2]={'detail':1,'tier':'legendary','weapon':'weapon_sg556','mode':'family',
                'donor':'hy_geometric_steps_pearl','themes':['Violet','Cobalt','Teal','Rose'],'label':'Spectral Glass'}
    for entry in entries:entry['feedback_revision']=1
    report['feedback_repairs']=['phantom_blade: Restricted Wraith Edge; inverse Ghostglass; pearlescent Spectral Glass']
    return result

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

def upgrade(lineup,rows,guns,icons,families,works,report,accept=None):
    import gun_collections as gc
    selected=[icon for icon in icons if icon in DESIGNS and
              not all(e.get('detail')==DESIGNS[icon].get('revision',1) for e in lineup.get(icon,()))]
    if not selected:return feedback(lineup,rows,works,report)
    reserved={e['donor'] for icon,entries in lineup.items() if icon not in selected
              for e in entries if 'donor' in e}
    planned=gc.plan(rows,guns,selected,families,works,seed='cs2gc-authored-detail-v1',
                    designs=DESIGNS,reserved=reserved,accept=accept)
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
    return feedback(result,rows,works,report)

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

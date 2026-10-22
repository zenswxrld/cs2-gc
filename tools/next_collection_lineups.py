"""Weekly/Armory collection upgrades. Retained definitions live in a separate module."""
from dataclasses import replace
import re
from retained_collection_lineups import DESIGNS as ORIGINAL_DESIGNS, Design, TIERS, RARITIES, WEAPON_ORDER
from collection_donors import REQUIRED, catalog, candidates, previous_materials
from collection_detail import rolled_name, palettes_distinct

DESIGNS = dict(ORIGINAL_DESIGNS)
OLDER_NAMES = {
    "ashfall": "Cinder Crown|Ember Vein|Burnished Edge|Volcanic Glass|Char Line|Ashen Circuit|Scoria|Coal Seam|Hot Stencil|Dark Furnace|Dust Coat|Grey Rake|Basalt|Falling Ash|Pumice|Soot Grain",
    "aurora": "Polar Halo|Ion Stream|Winter Flare|Boreal Current|Northern Prism|Sky Ribbon|Ice Signal|Charged Mist|Night Flight|Glacial Trace|Snowline|Pale Drift|Cold Echo|Blue Static|Thin Air|Frost Mark",
    "brimstone": "Sulfur Crown|Hellfire Alloy|Burning Sigil|Smelter Glass|Fume Coil|Firebrand|Charcoal Grid|Sulfur Trace|Rift Metal|Burn Line|Dark Deposit|Ash Chip|Lime Scale|Yellow Dust|Coal Print|Furnace Sand",
    "cascade": "Whitewater|River Prism|Spillway|Rapid Glass|Mist Current|Waterline|Foam Runner|Lock Gate|Blue Drop|River Mesh|Silt Print|Pebble|Spray Mark|Shallow Run|Wet Slate|Streambed",
    "cinder": "Fireheart|Cinder Veil|Bronze Flare|Spark Glass|Coal Bloom|Red Kiln|Blazing Mesh|Warm Rivet|Fire Trail|Black Hearth|Clay Dust|Ember Fleck|Kiln Coat|Coal Trace|Potter Mark|Baked Earth",
    "eclipse": "Totality|Umbra Glass|Solar Rim|Shadow Flare|Black Meridian|Dark Corona|Night Matrix|Lunar Path|Obscured Sun|Orbital Trace|Moon Ash|Dusk Dust|Pale Halo|Night Haze|Orbit Line|Grey Shadow",
    "halcyon": "Stillwater|Azure Reverie|Calm Horizon|Summer Prism|Ocean Hush|Cloud Glass|Blue Interval|Light Current|Clear Skies|Reefline|Soft Tide|Pale Coast|Sea Mist|Quiet Wake|Air Blue|Calm Wash",
    "kaleido": "Prismatic Crown|Spectrum Glass|Shifting Jewel|Mirror Bloom|Colour Spiral|Fractured Light|Facet Grid|Glass Circuit|Angle Shift|Jewel Cut|Prism Dust|Small Mirror|Tile Glint|Colour Chip|Fine Mosaic|Light Fragment",
    "monsoon": "Stormfront|Rain Current|Thunderhead|Violet Squall|Downpour|Cloudburst|Rain Gauge|Storm Lattice|Wet Signal|Flood Mark|Water Bead|Grey Rain|Wind Trace|Slick Stone|Low Cloud|Puddle",
    "nebula": "Star Nursery|Cosmic Veil|Ion Halo|Astral Glass|Deep Orbit|Distant Sun|Stellar Grid|Gas Cloud|Solar Thread|Night Signal|Void Dust|Comet Trail|Space Grain|Redshift|Star Chart|Cold Orbit",
    "solstice": "High Sun|Solar Alloy|Golden Hour|Dawn Glass|Summer Zenith|Daybreak|Sun Dial|Copper Ray|Heat Ribbon|Long Light|Sun Bleach|Warm Sand|Day Mark|Pale Gold|Season Line|Bright Dust",
    "zephyr": "Skyborne|Wind Prism|Swift Current|Airglow|Feather Glass|Blue Draft|Wind Mesh|Open Sky|Thin Cloud|Gale Trace|Air Print|Pale Feather|Light Breeze|Wind Mark|Sky Dust|Soft Gust",
    "tidewater": "Tidal Crown|Estuary Glass|Copper Buoy|Flood Prism|Reef Current|Sea Etching|Channel Grid|Brackish Coil|Dune Metal|Salt Line|Mudflat|Ebb Mark|Marsh Grain|Silt Wash|Green Berth|Shore Signal",
    "obelisk": "Black Monolith|Royal Inlay|Stone Halo|Ancient Glass|Rune Matrix|Night Granite|Carved Grid|Dark Facet|Old Sigil|Stone Rake|Mica Dust|Quarry Line|Basalt Cut|Fine Rune|Deep Stone|Grey Pillar",
    "zenith": "High Meridian|Sky Jewel|Cobalt Crown|Peak Glass|Summit Coil|Blue Altitude|Airborne Grid|Thin Light|Peak Line|Far Horizon|Pale Apex|Height Mark|Cold Summit|Cloud Grain|Fine Compass|Sky Gauge",
    "rampart": "Iron Bastion|Fortress Alloy|Guardian Glass|Reinforced Crest|Wall Current|Armour Etch|Defense Grid|Red Masonry|Guard Line|Steel Ribbon|Wall Chip|Field Coat|Gate Mark|Rough Mortar|Stone Guard|Iron Chalk",
    "ironclad": "Dreadnought|Rivet Alloy|Armour Crest|Deep Steel|Hull Prism|Heavy Etch|Plate Circuit|Pressure Hull|Anchor Grid|Brass Rivet|Iron Scale|Rusted Seam|Grey Bolt|Lower Deck|Mill Dust|Cold Weld",
    "marauder": "Raid Leader|Tiger Flare|Copper Fang|Wild Prism|Ambush Glass|Red Banner|Predator Mesh|Raid Signal|Sharp Stripe|Outlaw Mark|Dust Trail|Field Streak|Wild Grain|Red Clay|Hidden Track|Dry Camp",
    "nightwatch": "Night Sentinel|Midnight Signal|Violet Guard|Watch Glass|Dark Relay|Moonlit Trace|Quiet Circuit|Night Shift|Dim Beacon|Black Register|Late Patrol|Shadow Print|Low Signal|Steel Dusk|Watch Mark|Night Dust",
    "outrider": "Trailbreaker|Hunting Stripe|Copper Horizon|Scout Glass|Frontier Coil|Open Range|Field Matrix|Long Patrol|Sand Runner|Riding Line|Trail Mark|Dry Grass|Fine Spur|Dust Scout|Wind Print|Road Grain",
    "quarry": "Bedrock|Mineral Glass|Copper Vein|Stone Prism|Jade Seam|Granite Cut|Drill Grid|Rock Circuit|Slate Ribbon|Crystal Line|Mica Fleck|Stone Dust|Grey Seam|Rough Cut|Pit Mark|Gravel",
    "redoubt": "Last Bastion|Scarlet Alloy|Cobalt Shield|Guard Prism|Fortress Glass|Iron Relay|Defense Matrix|Steel Trace|Red Wire|Barrel Mark|Grey Guard|Field Stone|Wall Grain|Steel Chip|Watch Coat|Gate Dust",
    "talisman": "Lucky Star|Jade Sigil|Royal Charm|Rune Glass|Copper Omen|Sacred Coil|Charm Matrix|Woven Sign|Hidden Glyph|Bright Thread|Old Charm|Fine Script|Pale Rune|Worn Token|Jade Dust|Faded Sign",
    "undertow": "Deep Pull|Abyssal Glass|Cobalt Current|Trench Prism|Violet Tide|Sea Coil|Sonar Matrix|Cold Channel|Depth Trace|Kelp Thread|Brine Dust|Sea Print|Dark Shale|Lower Tide|Silt Grain|Deep Mark"
}
# These source finishes are weapon-specific. Keep their intended masks/UVs.
FAMILY_BINDINGS = {
    'forged': ('Crimson Foil','gsch_sport_ump45','weapon_ump45'),
    'juggernaut': ('Crimson Foil','gsch_sport_ump45','weapon_ump45'),
    'insignia': ('Crimson Foil','gsch_sport_ump45','weapon_ump45'),
    'phantom_blade': ('Rainbow Spoon','aq_titanium_rainbow_galilar','weapon_galilar'),
    'mosaic': ('Rainbow Spoon','aq_titanium_rainbow_galilar','weapon_galilar'),
    'lodestar': ('Rainbow Spoon','aq_titanium_rainbow_galilar','weapon_galilar'),
}
# Compatibility exports for callers that previously read the authored donor lists.
FALLBACKS = ()
SLOT_DONORS = ()

def all_designs():
    from native_skins import REFINED_DESIGNS, ADDITIONAL_DESIGNS
    result = dict(DESIGNS)
    for icon,names in OLDER_NAMES.items():
        chase,donor,themes = (REFINED_DESIGNS if icon in REFINED_DESIGNS else ADDITIONAL_DESIGNS)[icon]
        result[icon] = Design(chase,(donor,),themes,tuple(names.split('|')),family_slots=(0,1))
    return result


def rename_retained(definitions, kits):
    """Apply readable names to owned historical variants without changing any kit/ID."""
    designs = all_designs()
    output = []
    bases = sorted(kits,key=lambda n:(-len(n),n))
    for name,title,values in definitions:
        if name.startswith('nc32_'):
            output.append((name,title,values));continue
        if name.startswith('nc31_'):
            base = next((n for n in bases if '_'+n+'_' in '_'+name+'_'),None)
            if base and ('Foil' in title or 'Rainbow Spoon' in title):
                # Correct the old misleading aliases; retain the actual material.
                from native_finishes import source_title
                theme = next((t for d in designs.values() for t in d.themes
                              if name.endswith('_'+t.lower())),None)
                root = source_title(base,{})
                title = rolled_name(root,theme) if theme else root
        elif name.startswith(('cwf_','cw2f_','cw2v_','ccf_','ccv_')):
            for icon,design in designs.items():
                prefix = name.split('_',1)[0]+'_'+icon+'_'
                if not name.startswith(prefix):
                    continue
                tail = name[len(prefix):]
                slot = 0 if tail.startswith('chase_') else None
                for tier,start,count in (('legendary',1,2),('mythical',3,3),('rare',6,4),('uncommon',10,6)):
                    for index in range(count):
                        if tail.startswith(tier+str(index)+'_'):
                            slot=start+index
                if slot is not None:
                    title = design.names[slot]
                    if name.startswith(('cw2v_','ccv_')):
                        import native_finishes as finishes
                        palette_names=tuple(finishes.THEMES)+tuple(finishes.DUO_THEMES)+tuple(finishes.GRADIENT_THEMES)
                        theme=next((t for t in palette_names if re.search(
                            '_'+t.lower()+r'(?:_inverted)?_(?:ancient|legendary|mythical|rare|uncommon)$',tail)),None)
                        if theme:
                            title=rolled_name(title,theme)+(' Inverted' if '_inverted_' in name else '')
                break
        output.append((name,title,values))
    return output


def build(source_text, kits, titles, kit_path, source, families, made_kits, report, previous_entries=()):
    import native_finishes as finishes
    from native_skins import _collection_lists, weapon_rarity_tags, paint_rarity_for_weapon
    available=set(re.findall(r'"name"\s+"(weapon_[a-z0-9_]+)"',source_text))
    rarities=weapon_rarity_tags(source_text)
    donors=catalog(source_text,kits,kit_path)
    previously_used=previous_materials(previous_entries,kits,kit_path)
    from collection_material import pattern_from_source
    previous_patterns={pattern_from_source(source,path) for path in previously_used}
    previous_patterns.discard(None)
    result,files,lists,names,items,icons=[],{},[],[],[],{}
    counts={}
    publication=report.setdefault('collection_upgrade',{})
    report['next_12']={}
    for icon,design in all_designs().items():
        collection='set_cs2gc_case_'+icon
        binding=FAMILY_BINDINGS.get(icon)
        names_for=list(design.names)
        first_wave=binding[2] if binding else None
        guns=[design.chase]
        if first_wave:
            guns.append(first_wave)
            names_for[1]=binding[0]
        guns += [w for w in WEAPON_ORDER if w not in guns]
        guns=guns[:16]
        row={'status':'unavailable','skins':[],'reason':''}
        publication[icon]=row
        if icon in DESIGNS:
            report['next_12'][icon]=row
        if len(guns)!=16 or any(w not in available for w in guns):
            row['reason']='required weapon missing from installed schema';continue
        tiers={t:[] for t in RARITIES}
        pending=[];pending_files={};pending_families={}
        seen=set();local_counts=dict(counts)
        for slot,(weapon,tier,title) in enumerate(zip(guns,TIERS,names_for)):
            variable=slot in design.family_slots
            if slot==1 and binding:
                source_name=binding[1]
                # Do not silently substitute a different finish under a real name.
                choices=[donors[source_name]] if source_name in donors else []
            else:
                choices=candidates(donors,icon,weapon,previously_used if icon in DESIGNS else set(),
                    local_counts,seen,limit=2 if icon in DESIGNS else 4)
            selected=None
            for donor in choices:
                if donor.material in seen:
                    continue
                if not donor.generic and weapon not in donor.weapons:
                    continue
                stem='nc32_%s_%02d_%s'%(icon,slot,donor.name)
                shift=slot%len(design.themes)
                themes=design.themes[shift:]+design.themes[:shift]
                entries=[];assets={};variants=[];colors=[];signatures=set()
                actual_material=None;accepted_palettes=[]
                for theme in themes:
                    name=stem+'_'+theme.lower()
                    palette_report={}
                    try:
                        made=finishes.make_finish(source,donor.name,donor.material,name,theme,
                            report=palette_report,weapon_palette=tier,weapon_tone=3,detail_policy=True)
                    except ValueError as error:
                        if str(error).startswith(('Unsupported KV3','KV3 dictionaries and binary blobs')):
                            continue
                        raise
                    if not made:
                        continue
                    evidence=palette_report.get(donor.name+':'+tier,{})
                    palette=evidence.get('themes',{}).get(theme)
                    # A reported palette is required: prove distinct colours, not just different names.
                    if not palette:
                        continue
                    signature=tuple(round(v,4) for c in palette for v in c)
                    if signature in signatures or (variable and any(not palettes_distinct(palette,other) for other in accepted_palettes)):
                        continue
                    signatures.add(signature);accepted_palettes.append(palette)
                    actual_material=evidence.get('pattern_identity',evidence.get('source_material',donor.material))
                    if actual_material in seen or (icon in DESIGNS and not (slot==1 and binding) and actual_material in previous_patterns):
                        break
                    values={k:v for k,v in kits[donor.name][1].items()
                        if isinstance(v,str) and k not in ('name','description_string','description_tag')}
                    path=finishes.COMPMAT_DIR+name+'.vcompmat'
                    values.update(composite_material_path=path,
                        _rarity=paint_rarity_for_weapon(tier,weapon,rarities))
                    entries.append((name,rolled_name(title,theme) if variable else title,values))
                    assets[path+'_c'],assets[finishes.VMAT_DIR+name+'.vmat_c']=made
                    assets.update(palette_report.get('_files',{}))
                    variants.append(name);colors.append(theme)
                    if not variable:
                        break
                if ((actual_material in seen) or (not (slot==1 and binding) and
                        local_counts.get(actual_material,0)>=(2 if icon in DESIGNS else 4))
                        or len(variants)<(2 if variable else 1)):
                    continue
                active=variants[0]
                if variable:
                    active=stem+'_family'
                    entries.append((active,title,dict(entries[0][2])))
                selected=(donor,active,entries,assets,variants,colors,actual_material)
                break
            if selected is None:
                row['reason']=('required family donor unavailable or not safely recolourable: '+binding[1]
                    if slot==1 and binding else
                    'no unused compatible Weekly/Armory donor for slot %d (%s)'%(slot,title))
                break
            donor,active,entries,assets,variants,colors,actual_material=selected
            pending.extend(entries);pending_files.update(assets)
            seen.update((donor.material,actual_material))
            for identity in {donor.material,actual_material}:
                local_counts[identity]=local_counts.get(identity,0)+1
            if variable:
                pending_families[active]=variants
            tiers[tier].append('[%s]%s'%(active,weapon))
            row['skins'].append(dict(slot=slot,weapon=weapon,rarity=tier,title=title,kit=active,
                donor=donor.name,source_material=donor.material,material_template=actual_material,
                source_collections=list(donor.collections),source_weapons=list(donor.weapons),
                family=variable,themes=colors,variants=variants if variable else [],
                previously_used=donor.material in previously_used,detail_policy='source-detail-v1',
                required_family=bool(slot==1 and binding)))
        if [len(tiers[t]) for t in RARITIES]!=[1,2,3,4,6]:
            row['skins']=[];continue
        result.extend(e for e in pending if e[0] not in made_kits)
        files.update(pending_files);families.update(pending_families);counts=local_counts
        lists.append(_collection_lists(collection,tiers,RARITIES));names.append(collection)
        items.extend(e for t in RARITIES for e in tiers[t]);icons[collection]=icon
        row.update(status='ready',reason='',fixed_skins=14,family_skins=2)
    return result,files,'\n'.join(lists),names,items,icons


def replace_pools(baseline, upgraded):
    """Replace active loot only for complete upgrades. Keep all owned definitions/assets."""
    definitions,files,lists,names,items,icons=baseline
    old_items=set()
    for name in upgraded[3]:
        for suffix in ('',)+tuple('_'+t for t in RARITIES):
            pattern=r'(?m)^\s*"'+re.escape(name+suffix)+r'"\s*\{[^}]*\}'
            for block in re.findall(pattern,lists):
                old_items.update(re.findall(r'"(\[[^\]]+\]weapon_[a-z0-9_]+)"',block))
            lists=re.sub(pattern,'',lists)
    return (definitions+upgraded[0],dict(files,**upgraded[1]),lists+'\n'+upgraded[2],
        [n for n in names if n not in upgraded[3]]+upgraded[3],
        [e for e in items if e not in old_items]+upgraded[4],dict(icons,**upgraded[5]))

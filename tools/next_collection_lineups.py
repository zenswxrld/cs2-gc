"""Authored third-batch collections, using the existing native material generator.

Only the 12 Build 30 draft pools are replaced. Existing kit definitions and IDs
remain with native_skins; every new finish has its own stable nc31_ identity.
"""
from dataclasses import dataclass
import re

TIERS = ('ancient', 'legendary', 'legendary', 'mythical', 'mythical', 'mythical',
         'rare', 'rare', 'rare', 'rare', 'uncommon', 'uncommon', 'uncommon',
         'uncommon', 'uncommon', 'uncommon')
RARITIES = ('ancient', 'legendary', 'mythical', 'rare', 'uncommon')


@dataclass(frozen=True)
class Design:
    chase: str
    chase_donors: tuple
    themes: tuple
    names: tuple
    family_slots: tuple = (1, 3)
    wave: tuple = ()


def words(text):
    return tuple(text.split('|'))


DESIGNS = {
    'forged': Design('weapon_ak47', ('am_metal_inlay', 'am_gold_brick'),
        ('Inferno', 'Ember', 'Crimson', 'Amber'),
        words('Crucible|Crimson Foil|Tempered Crown|Furnace Bloom|Quenched Edge|Brassworks|Hot Rivet|Slag Line|Foundry Mesh|Blacksmith|Scale Break|Iron Filing|Sootfall|Mill Finish|Heat Mark|Castoff'),
        wave=('am_electric_red', 'am_crystallized')),
    'phantom_blade': Design('weapon_m4a1_silencer', ('am_doppler_phase2', 'am_navy_shine'),
        ('Violet', 'Midnight', 'Galaxy', 'Glacier'),
        words('Spectral Edge|Rainbow Spoon|Veil Piercer|Cold Apparition|Afterimage|Wraithglass|Vanish Point|Night Shard|Silent Cut|Ghostwire|Pale Trace|Shadow Grain|Low Profile|Mistline|Blue Silence|Faded Signal'),
        family_slots=(0, 1), wave=('am_marble_fade', 'aa_fade')),
    'harbor': Design('weapon_awp', ('am_seastorm', 'am_seastorm_blood'),
        ('Ocean', 'Teal', 'Glacier', 'Cobalt'),
        words('Storm Anchorage|Phosphor Beacon|Breakwater|Tidal Coil|Blue Pilot|Saltwake|Dry Dock|Mooring Line|Sea Gauge|Blue Berth|Hull Plate|Buoy Mark|Ropewalk|Jetty Paint|Sounding Line|Dockside'),
        wave=('am_m4a1s_bluesmoke', 'am_aqua_flecks')),
    'mosaic': Design('weapon_deagle', ('cg_pattern_prismatic_facets', 'am_ddpatdense_peacock'),
        ('Candy', 'Rainbow', 'Vapor', 'Royal'),
        words('Tessellated Crown|Rainbow Spoon|Prism Pavilion|Jewelwork|Glass Garden|Colour Theory|Tile Runner|Broken Symmetry|Inlay Grid|Lapis Circuit|Grout Line|Ceramic Shift|Small Tessera|Colour Block|Stone Cut|Glaze Test'),
        wave=('am_marble_fade', 'aa_fade')),
    'kestrel': Design('weapon_sg556', ('am_m4a1s_bluesmoke', 'am_gyrate'),
        ('Azure', 'Glacier', 'Teal', 'Amber'),
        words('Sky Talon|Phosphor Flight|Strike Feather|Raptor Current|High Pursuit|Crosswind|Featherline|Flight Deck|Wing Cut|Airframe|Perch Mark|Wind Gauge|Light Spar|Glide Path|Field Wing|Scout Plume'),
        wave=('am_aqua_flecks', 'am_navy_shine')),
    'juggernaut': Design('weapon_negev', ('am_diamond_plate', 'am_metal_inlay'),
        ('Crimson', 'Inferno', 'Amber', 'Ash'),
        words('Siegebreaker|Crimson Foil Plating|Brass Colossus|War Machine|Heavy Alloy|Impact Layer|Armour Belt|Pressure Plate|Red Reinforcement|Rivet Row|Ballast|Billet|Workshop Red|Load Bearing|Plate Offcut|Steel Dust'),
        wave=('am_electric_red', 'am_jorm_orange')),
    'lodestar': Design('weapon_awp', ('am_aqua_flecks', 'am_heist_plans_purple'),
        ('Galaxy', 'Violet', 'Midnight', 'Cobalt'),
        words('Astral Meridian|Rainbow Spoon Navigation|Northlight|Celestial Bearing|Star Compass|Orbit Glass|Azimuth|Blue Sextant|Polar Map|Moon Dial|Transit Line|Survey Mark|Night Bearing|Far Point|Chart Grain|Wayfinder'),
        family_slots=(0, 1), wave=('aa_fade', 'am_marble_fade')),
    'fathom': Design('weapon_mp9', ('am_jorm_blue', 'am_seastorm'),
        ('Ocean', 'Teal', 'Glacier', 'Violet'),
        words('Abyssal Coil|Phosphor Depth|Pressure Bloom|Pelagic Veil|Trenchlight|Deep Current|Kelp Circuit|Dive Marker|Sonar Wash|Underswell|Sea Glass|Depth Gauge|Siltline|Cold Brine|Marine Layer|Sounding Weight'),
        wave=('am_m4a1s_bluesmoke', 'am_aqua_flecks')),
    'cipher': Design('weapon_glock', ('aa_wiring', 'aa_vertigogeo_neon'),
        ('Emerald', 'Toxin', 'Teal', 'Galaxy'),
        words('Zero Knowledge|Quantum Key|Encrypted Trace|Ghost Protocol|Key Exchange|Green Circuit|Hash Grid|Packet Shift|Signal Mask|Private Channel|Checksum|Bit Plane|Wire Frame|Null Route|Access Bit|Terminal Green'),
        wave=('am_aqua_flecks', 'am_heist_plans_purple')),
    'driftwood': Design('weapon_ak47', ('am_knots_brown', 'am_bamboo_jungle'),
        ('Amber', 'Coral', 'Teal', 'Forest'),
        words('Saltworn Borre|Emerald Grain|Lacquer Tide|Weathered Coil|Seafoam Heart|Shoreline Burl|Beach Grain|Brine Knot|Tide Lacquer|Worn Compass|Pale Timber|Splinter Map|Sandwash|Shingle|Coastal Patina|Flotsam'),
        wave=('am_jorm_green', 'am_jorm_orange')),
    'insignia': Design('weapon_m4a1', ('am_gold_brick', 'am_metal_inlay'),
        ('Royal', 'Amber', 'Crimson', 'Sunrise'),
        words('Sovereign Brick|Crimson Foil Standard|Honour Guard|Ceremonial Coil|Laurel Glass|Parade Alloy|Gold Chevron|Service Ribbon|Unit Mark|Dress Plate|Braided Trim|Field Citation|Brass Button|Uniform Grain|Rank File|Service Stripe'),
        wave=('am_electric_red', 'am_jorm_orange')),
    'warden': Design('weapon_xm1014', ('am_chainmail', 'am_diamond_plate'),
        ('Cobalt', 'Ash', 'Amber', 'Midnight'),
        words('High Security|Restricted Spectrum|Lockdown Plate|Night Custody|Access Lattice|Watch Command|Barred Entry|Keyway|Warning Band|Secure Perimeter|Cell Block|Grey Register|Gate Mesh|Shift Change|Steel Notice|Visitor Pass'),
        wave=('am_navy_shine', 'am_aqua_flecks')),
}

# A deliberate rank-by-rank mix: premium rifles and pistols at the top, then
# SMGs, shotguns and utility weapons. The chase is removed before taking 15.
WEAPON_ORDER = ('weapon_m4a1_silencer', 'weapon_deagle', 'weapon_usp_silencer',
                'weapon_m4a1', 'weapon_fiveseven', 'weapon_p250', 'weapon_ump45',
                'weapon_ssg08', 'weapon_mac10', 'weapon_nova', 'weapon_mp7',
                'weapon_tec9', 'weapon_galilar', 'weapon_mag7', 'weapon_bizon',
                'weapon_hkp2000', 'weapon_famas')

# Distinct generic, recolourable patterns per collection. Each slot tries its
# preferred donor first; alternatives are ordered and the actual selection is
# reported. Unsupported materials never become renamed stock skins.
SLOT_DONORS = (
    ('am_chainmail', 'am_diamond_plate'),
    ('am_gold_brick', 'am_metal_inlay'),
    ('am_crystallized_silver', 'am_crystallized'),
    ('am_jorm_green', 'am_jorm_blue', 'am_jorm_orange'),
    ('am_carbon_fiber', 'am_navy_shine'),
    ('am_geometric_steps', 'cg_pattern_vector_lattice'),
    ('am_heist_plans_purple', 'am_heist_plans_green'),
    ('aa_vertigogeo_neon', 'aa_wiring'),
    ('am_gyrate', 'am_czv2_mf'),
    ('am_zebra_dark', 'am_ossify_blue'),
    ('am_bamboo_jungle', 'am_knots_brown'),
    ('am_turqoise_halftone', 'am_ddpatdense_peacock'),
    ('am_moro_textile_bright', 'am_mirage_flowers_metalic'),
    ('am_ossify', 'cg_pattern_obsidian_fault'),
    ('am_kimono_sunrise', 'am_seastorm_blood'),
)
FALLBACKS = tuple(dict.fromkeys(n for candidates in SLOT_DONORS for n in candidates))


def build(source_text, kits, titles, kit_path, source, families, made_kits, report):
    """Same six-value result as native_skins.custom_cases; commit complete pools only."""
    import native_finishes as finishes
    from native_skins import _collection_lists, weapon_rarity_tags, paint_rarity_for_weapon
    available = set(re.findall(r'"name"\s+"(weapon_[a-z0-9_]+)"', source_text))
    base_rarities = weapon_rarity_tags(source_text)
    result, files, lists, names, items, icons = [], {}, [], [], [], {}
    publication = report.setdefault('next_12', {})
    used_rolls = set()
    for icon, design in DESIGNS.items():
        collection = 'set_cs2gc_case_' + icon
        guns = [design.chase] + [w for w in WEAPON_ORDER if w != design.chase][:15]
        row = {'status': 'unavailable', 'skins': [], 'reason': ''}
        publication[icon] = row
        if len(guns) != 16 or any(w not in available for w in guns):
            row['reason'] = 'required weapon missing from installed schema'
            continue
        pending, pending_files, pending_families, tiers = [], {}, {}, {t: [] for t in RARITIES}
        seen_materials, seen_titles = set(), set()
        pending_rolls = set()
        for slot, (weapon, tier, title) in enumerate(zip(guns, TIERS, design.names)):
            variable = slot in design.family_slots
            preferred = (design.chase_donors if slot == 0 else design.wave if slot == 1
                         else SLOT_DONORS[slot - 1])
            candidates = tuple(dict.fromkeys(preferred + FALLBACKS))
            selected = None
            for donor in candidates:
                if donor not in kits:
                    continue
                original_path = kit_path(donor, kits[donor][1])
                identity = original_path.replace('\\', '/').lower()
                if identity in seen_materials:
                    continue
                paint_tier = paint_rarity_for_weapon(tier, weapon, base_rarities)
                stem = 'nc31_%s_%02d_%s' % (icon, slot, donor)
                local_entries, local_files, variants, palettes, chosen_themes = [], {}, [], set(), []
                # Fixed chase uses its authored first theme; other fixed skins
                # try the chosen colour first, then compatible collection colours.
                shift = 0 if slot == 0 else slot % len(design.themes)
                themes = design.themes[shift:] + design.themes[:shift]
                for theme in themes:
                    roll = (identity, weapon, tier, theme)
                    if roll in used_rolls:
                        continue
                    material = stem + '_' + theme.lower()
                    palette_report = {}
                    try:
                        made = finishes.make_finish(source, donor, original_path, material, theme,
                            report=palette_report, weapon_palette=tier, weapon_inverse=False, weapon_tone=3)
                    except ValueError as error:
                        if str(error).startswith(('Unsupported KV3', 'KV3 dictionaries and binary blobs')):
                            continue
                        raise
                    if made is None:
                        continue
                    palette = palette_report.get(donor + ':' + tier, {}).get('themes', {}).get(theme)
                    if palette:
                        signature = tuple(round(v, 4) for colour in palette for v in colour)
                        if signature in palettes:
                            continue
                        palettes.add(signature)
                    values = {k: v for k, v in kits[donor][1].items() if isinstance(v, str)
                              and k not in ('name', 'description_string', 'description_tag')}
                    path = finishes.COMPMAT_DIR + material + '.vcompmat'
                    values.update(composite_material_path=path, _rarity=paint_tier)
                    kit = material
                    rolled_title = theme + ' ' + title if variable else title
                    local_entries.append((kit, rolled_title, values))
                    local_files[path + '_c'], local_files[finishes.VMAT_DIR + material + '.vmat_c'] = made
                    variants.append(kit)
                    chosen_themes.append(theme)
                    if not variable:
                        break
                if len(variants) < (2 if variable else 1):
                    continue
                active = variants[0]
                if variable:
                    active = stem + '_family'
                    local_entries.append((active, title, dict(local_entries[0][2])))
                selected = (active, donor, identity, original_path, local_entries, local_files,
                            variants, chosen_themes)
                break
            if selected is None:
                row['reason'] = 'no distinct compatible recolour donor for slot %d (%s)' % (slot, title)
                break
            active, donor, identity, original_path, local_entries, local_files, variants, chosen_themes = selected
            if title in seen_titles:
                raise ValueError('Duplicate authored skin title: ' + title)
            seen_materials.add(identity)
            seen_titles.add(title)
            pending.extend(local_entries)
            pending_files.update(local_files)
            pending_rolls.update((identity, weapon, tier, theme) for theme in chosen_themes)
            if variable:
                pending_families[active] = variants
            tiers[tier].append('[%s]%s' % (active, weapon))
            row['skins'].append({'slot': slot, 'weapon': weapon, 'rarity': tier,
                'title': title, 'kit': active, 'donor': donor, 'source_material': original_path,
                'family': variable, 'themes': chosen_themes, 'variants': variants if variable else [],
                'fallback': donor not in preferred})
        if [len(tiers[t]) for t in RARITIES] != [1, 2, 3, 4, 6]:
            # No orphan definitions, families or material files escape a failed pool.
            row['skins'] = []
            continue
        if len(pending_families) != 2:
            raise ValueError('Expected two family skins in ' + icon)
        result.extend(entry for entry in pending if entry[0] not in made_kits)
        files.update(pending_files)
        used_rolls.update(pending_rolls)
        families.update(pending_families)
        lists.append(_collection_lists(collection, tiers, RARITIES))
        names.append(collection)
        items.extend(entry for t in RARITIES for entry in tiers[t])
        icons[collection] = icon
        row.update(status='ready', reason='', fixed_skins=14, family_skins=2)
    return result, files, '\n'.join(lists), names, items, icons

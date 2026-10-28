"""Explicit art-preserving colour pairs, separate from shared knife themes."""

# Main ink / secondary ink. The decoder retains value detail, neutral trim and
# material alpha. These two reviewed sources need distinct colour roles rather
# than a single compressed hue; unrelated artwork keeps its existing treatment.
PAIRS = {
    ('cu_overpass_monster_ak47', 'Azure'): (208, 338, .78),
    ('cu_overpass_monster_ak47', 'Teal'): (178, 38, .78),
    ('cu_overpass_monster_ak47', 'Rose'): (338, 38, .78),
    ('cu_awp_hannya', 'Violet'): (272, 40, .76),
    ('cu_awp_hannya', 'Cobalt'): (226, 338, .76),
    ('cu_awp_hannya', 'Magenta'): (316, 40, .76),
    ('gs_ak47_bloodsport', 'Crimson'): (355, 42, .80),
    ('gs_ak47_bloodsport', 'Amber'): (40, 355, .80),
    ('gs_ak47_bloodsport', 'Cobalt'): (226, 40, .80),
    ('cu_ak_neon_rider', 'Ember'): (24, 276, .82),
    ('cu_ak_neon_rider', 'Violet'): (276, 38, .72),
    ('cu_ak_neon_rider', 'Crimson'): (355, 42, .78),
    ('cu_ak_neon_rider', 'Emerald'): (148, 316, .68),
    ('soe_tropical', 'Rose'): (338, 42, .68),
    ('cu_p2000_fire_elemental', 'Rose'): (338, 42, .72),
    ('cu_usp_black_lotus', 'Ember'): (22, 42, .72),
    ('soe_pink_cranes', 'Amber'): (38, 18, .58),
}

def recipe(kit, theme):
    from colour_families import split
    theme=split(theme)[0]
    return PAIRS.get((kit, theme))

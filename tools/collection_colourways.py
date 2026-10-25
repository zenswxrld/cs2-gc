"""Explicit art-preserving colour pairs, separate from shared knife themes."""

# Main ink / secondary ink. The decoder retains value detail, neutral trim and
# material alpha. These two reviewed sources need distinct colour roles rather
# than a single compressed hue; unrelated artwork keeps its existing treatment.
PAIRS = {
    ('cu_ak_neon_rider', 'Ember'): (24, 276, .82),
    ('cu_ak_neon_rider', 'Violet'): (276, 38, .72),
    ('cu_ak_neon_rider', 'Crimson'): (355, 42, .78),
    ('cu_ak_neon_rider', 'Emerald'): (148, 316, .68),
    ('soe_tropical', 'Rose'): (338, 42, .68),
}

def recipe(kit, theme):
    return PAIRS.get((kit, theme))

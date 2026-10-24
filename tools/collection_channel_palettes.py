"""Reviewed four-channel palettes; retain the original pattern, mask and wear bindings."""

def channels(kit,theme):
    if kit=='hye_ak47_nouveau' and theme=='Royal':
        # Body, scrollwork, coloured enamel and dark hardware, respectively.
        # The original ivory/red pairing became muddy brown under a hue-only shift.
        return [[.08,.10,.14,1],[.60,.67,.74,1],[.12,.28,.52,1],[.06,.09,.15,1]]
    if kit=='am_scales_bravo' and theme=='Cobalt':
        # This material has brightness=5. Keep authored linear inputs below .15
        # so the scale pattern retains contrast instead of clipping to white.
        return [[.035,.045,.065,1],[.020,.070,.140,1],[.120,.130,.150,1],[.045,.055,.080,1]]
    return None

"""Collection recolours preserve the donor's contrast, trim and hue relationships."""
import colorsys


def recolour_details(colors, theme, themes, duos, gradients):
    hsv = [colorsys.rgb_to_hsv(*c[:3]) for c in colors]
    # Dark ink, silver foil, white lettering and neutral hardware are protected.
    accents = [i for i, (_,s,v) in enumerate(hsv) if s >= .16 and v >= .16]
    if not accents:
        # A neutral engraved finish gets one painted accent, never an all-over wash.
        eligible = [i for i, (_,s,v) in enumerate(hsv) if .25 <= v <= .88]
        if not eligible:
            return [list(c) for c in colors]
        accents = [max(eligible, key=lambda i:hsv[i][2])]
    anchor = max(accents, key=lambda i:hsv[i][1]*hsv[i][2])
    if theme in themes:
        target, saturation, _ = themes[theme]
    elif theme in duos:
        target, _, saturation = duos[theme]
    else:
        hues, saturation = gradients[theme]
        target = hues[0]
    offset = target / 360 - hsv[anchor][0]
    result = [list(c) for c in colors]
    for i in accents:
        h,s,v = hsv[i]
        # One shared hue rotation retains the original pattern's relationships.
        # Never flatten highlights/shadows or raise muted ink to neon saturation.
        result[i] = [*colorsys.hsv_to_rgb((h+offset)%1, min(s,saturation), v), colors[i][3]]
    return result


def rolled_name(title, theme):
    # A blue outcome must not still describe itself as crimson or gold.
    roots = {'Crimson Foil':'Foil', 'Blue Phosphor':'Phosphor',
             'Gold Brick':'Brick', 'Rainbow Spoon':'Rainbow Spoon'}
    return theme + ' ' + roots.get(title,title)

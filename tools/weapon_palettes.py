"""Collection-only paint palettes. Change four colour vectors, never textures or shader settings."""
import colorsys
import math


def is_new_colourway(original, changed):
    """Reject originals, near copies and nearly identical colour permutations.

    Neutral trim may stay original; it is the painted accents that must change.
    """
    if len(original) != len(changed) or not original:
        return False
    delta = sum(sum((a-b)**2 for a,b in zip(x[:3],y[:3])) for x,y in zip(original,changed))
    if math.sqrt(delta / (3*len(original))) < .085:
        return False
    accents = [i for i,c in enumerate(original) if colorsys.rgb_to_hsv(*c[:3])[1] >= .12 and max(c[:3]) >= .14]
    if not accents:
        return True  # coloured variants of an originally neutral metal
    distances = []
    for i in accents:
        old_h,old_s,old_v = colorsys.rgb_to_hsv(*original[i][:3])
        new_h,new_s,new_v = colorsys.rgb_to_hsv(*changed[i][:3])
        distances.append(min(abs(new_h-old_h),1-abs(new_h-old_h)))
    return sum(distances)/len(distances) >= 22/360


def recolour(colors, theme, tier, themes, duos, gradients, tone=2):
    """Colour channels form gradients only where the donor's original pattern blends them.

    Retain neutral metal/trim and relative light/dark structure. All-neutral patterns
    get their two lighter channels coloured, keeping their dark engraved detail.
    """
    hsv = [colorsys.rgb_to_hsv(*c[:3]) for c in colors]
    accents = {i for i,(h,s,v) in enumerate(hsv) if s >= .12 and v >= .14}
    if not accents:
        accents = set(sorted(range(len(colors)),key=lambda i:hsv[i][2])[-2:])
    if theme in gradients:
        hues,saturation = gradients[theme]
    elif theme in duos:
        first,last,saturation = duos[theme]
        difference=(last-first+180)%360-180
        hues=tuple((first+difference*i/3)%360 for i in range(4))
    else:
        hue,saturation,spread=themes[theme]
        hues=tuple((hue+max(spread,26)*(i/3-.5))%360 for i in range(4))
    strength={'uncommon':.48,'rare':.66,'mythical':.84,'legendary':.94,'ancient':1.0}[tier]
    output=[list(c) for c in colors]
    ranked=sorted(accents,key=lambda i:hsv[i][2])
    for rank,i in enumerate(ranked):
        old_h,old_s,old_v=hsv[i]
        hue=hues[round(rank*3/max(1,len(ranked)-1))]/360
        sat=min(.82,saturation*strength)
        # A darker, slightly muted under-colour makes the brighter gradient visible.
        sat*=.88 if rank==0 and len(ranked)>1 else 1
        value=min(.96,max(.14,old_v))
        if tone>=2 and value>.72:value=.72+(value-.72)*.28
        output[i]=[*colorsys.hsv_to_rgb(hue,sat,value),colors[i][3]]
    from colour_families import tone
    return tone(output,theme,colors)


def invert_panels(original, changed, tone=2):
    """Swap painted neutral panels between charcoal and off-white; preserve alpha.

    On fully coloured patterns invert the tonal hierarchy rather than RGB-negating
    the colours. The pattern, masks and unpainted weapon hardware are untouched.
    """
    output=[list(c) for c in changed]
    neutrals={i for i,c in enumerate(original) if colorsys.rgb_to_hsv(*c[:3])[1]<.12}
    indices=neutrals or set(range(len(changed)))
    values=[max(c[:3]) for c in changed]
    pivot=1.02 if neutrals else min(values)+max(values)
    for i in indices:
        h,s,v=colorsys.rgb_to_hsv(*changed[i][:3])
        value=max(.14,min(.96,pivot-v))
        if tone>=2 and neutrals:value=min(.82,value)
        output[i]=[*colorsys.hsv_to_rgb(h,min(s,.06) if neutrals else s,value),changed[i][3]]
    return output

"""Named tonal choices; preserve source detail and existing theme identities."""
import colorsys
SHADES=('Light','Muted','Deep','Vivid')

def split(theme):
    base,sep,shade=theme.rpartition('_')
    return (base,shade) if sep and shade in SHADES else (theme,None)

def expand(themes):
    return list(dict.fromkeys(t for theme in themes for t in
        ([theme]+[theme+'_'+shade for shade in SHADES] if not split(theme)[1] and theme not in ('Inverse','Gold') else [theme])))

def register(themes,duos,gradients):
    for table in (themes,duos,gradients):
        for name,values in list(table.items()):
            if split(name)[1]:continue
            for shade in SHADES:
                # Brightness is applied after hue transformation, retaining
                # each source mask's relative highlight/shadow differences.
                palette=(226,226,.65) if table is duos and name=='Midnight' else (18,350,.70) if table is duos and name=='Sunset' else values
                table.setdefault(name+'_'+shade,palette)

def tone(colors,theme,original=None):
    base,shade=split(theme)
    if not shade:return colors
    result=[list(c) for c in colors]
    for i,color in enumerate(colors):
        if original is not None and list(color)==list(original[i]):continue
        h,s,v=colorsys.rgb_to_hsv(*color[:3])
        if s<.10 and (original is None or base!='Ash'):continue # lettering, metal, unpainted trim and ink
        if shade=='Light':s*=.48;v=v+.25*v*(1-v)
        elif shade=='Muted':s*=.60;v*=.85
        elif shade=='Deep':s=min(.86,s*1.05);v*=.50
        else:s=min(.94,max(.80,s+.24))
        if base=='Ash':
            s=min(.10,s)
            if shade=='Vivid':v=v+.10*v*(1-v)
        result[i]=[*colorsys.hsv_to_rgb(h,s,v),color[3]]
    return result

def title(theme):return theme.replace('_',' ')

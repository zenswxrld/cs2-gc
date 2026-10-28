"""Source-weapon artwork variants; preserve neutral trim, alpha and material masks."""
import json
import os
from pathlib import Path
import subprocess
import kv3
from collection_material import texture_payload, owned_texture, exposed

DONORS = {'cu_famas_holo_ocean':'hue', 'cu_usp_printstream':'invert',
          'gsch_sport_ump45':'foil', 'aq_titanium_rainbow_galilar':'ramp',
          'aq_deagle_case_hardened_2':'spoon_target','gsch_ak_djiin':'foil_target',
          'awp_queens_gambit':'hue','cu_awp_asimov':'hue','cu_awp_cobra':'hue',
          'cu_awp_chroma_pink':'hue','cu_m4_asimov':'hue','cu_negev_impact':'hue',
          'gs_ak47_bloodsport':'foil','gs_ak47_supercharged':'hue','cu_ak47_rubber':'hue',
          'cu_m4a1s_cyrex':'hue','cu_m4a1_hyper_beast':'hue','cu_m4a1s_printstream':'invert',
          'cu_m4a4_neo_noir':'hue','gs_ak47_empress':'portrait','cu_m4a4_temukau':'portrait',
          'ak_porcelain':'blue_ink'}

# Explicit reviewed native artwork sources for the complete collection matrix.
from collection_art_sources import SOURCES
DONORS.update(SOURCES)
DONORS['soe_tropical']='overlay'

def make(source,kit,path,new_name,theme):
    import native_finishes as f
    from gun_collections import inspect
    found=inspect(source,path)
    if not found:return None
    kind=DONORS[kit]
    adapted=kind in ('spoon_target','foil_target')
    binding_name=('g_tOverlay' if kind=='overlay' else
                  'g_tCaseHardeningColorRamp' if kind in ('ramp','spoon_target','foil_target') else 'g_tPattern')
    params=found['params']
    if adapted:
        family='aq_titanium_rainbow_galilar' if kind=='spoon_target' else 'gsch_sport_ump45'
        donor=inspect(source,'weapons/paints/set_realism_camo/'+family+'.vcompmat')
        if not donor or params.get('F_CASE_HARDENING')!=1:return None
        params=donor['params']
        if kind=='foil_target':
            target_shader=found['material'][2].get('m_shaderName')
            source_shader=donor['material'][2].get('m_shaderName')
            if not target_shader or not source_shader or target_shader.value!=source_shader.value:return None
    family_params=params
    pattern=params.get(binding_name)
    if not isinstance(pattern,str):return None
    decoder=Path(os.environ.get('CS2_GC_TEXTURE_DECODER',str(Path(__file__).with_name('cs2_gc_texture_decode.exe'))))
    if not decoder.is_file():decoder=Path(__file__).with_name('cs2_gc_texture_decode')
    if not decoder.is_file():return None
    mode='ramp' if adapted else kind
    from collection_feedback import MODES, bindings
    numeric_mode=MODES.get(kit,{'invert':3,'hue':2,'overlay':2,'foil':0,'ramp':1,'portrait':6,'blue_ink':7}[mode])
    if mode=='invert':
        if theme!='Inverse':return None
        hue,cap=0,1
    elif theme in f.THEMES:hue,cap,_=f.THEMES[theme]
    elif theme in f.DUO_THEMES:hue,_,cap=f.DUO_THEMES[theme]
    else:
        hues,cap=f.GRADIENT_THEMES[theme];hue=hues[0]
    from collection_colourways import recipe
    paired=recipe(kit,theme)
    if paired:hue,accent,cap=paired;numeric_mode=10
    data,guid,root=found['compmat'];mdata,mguid,mroot=found['material']
    from artwork_cache import current
    cache=current();inputs=[]
    for binding_name in bindings(kit,binding_name):
        pattern=params.get(binding_name)
        original=source.read(pattern+'_c') if isinstance(pattern,str) and pattern else None
        if original is None:return None
        inputs.append((binding_name,original))
    key=cache.key({'kit':kit,'theme':theme,'mode':numeric_mode,'hue':hue,'cap':cap,
                   'paired':paired},inputs) if cache else None
    records=cache.load(key) if cache else None
    if records and any(r['binding'] not in dict(inputs) for r in records):records=None
    if records is None:
        records=[]
        for binding_name,original in inputs:
            try:_,_,_,width,height,payload=texture_payload(original)
            except ValueError:return None
            command=[str(decoder),str(width),str(height),str(hue),str(cap),str(numeric_mode)]
            if paired:command.append(str(accent))
            child=subprocess.run(command,
                input=payload,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if child.returncode==7:return None
            if child.returncode:raise ValueError('Artwork decoder failed: '+str(child.returncode))
            stats=json.loads(child.stderr)
            if not records and (not stats['changed_pixels'] or not stats['palette']):return None
            # Keep a neutral secondary overlay/ramp, with its original masks.
            if not stats['changed_pixels']:continue
            content=owned_texture(original,child.stdout)
            records.append({'binding':binding_name,'stats':stats,'file':cache.blob(content) if cache else content})
        if cache:cache.save(key,records)
    owned_textures={};primary_stats=records[0]['stats']
    for record in records:
        binding_name=record['binding']
        suffix='' if binding_name=='g_tPattern' else '_'+binding_name[3:].lower()
        texture='materials/cs2_gc/collection_artwork/'+kit+'_'+theme.lower()+suffix+'.vtex'
        changed=False
        for item in exposed(root).get(binding_name,()):
            binding=item.get('m_strTextureRuntimeResourcePath')
            if binding is None:return None
            binding.value=texture;changed=True
        textures=mroot.get('m_textureParams')
        for item in textures.value if textures else ():
            key,value=item.get('m_name'),item.get('m_pValue')
            if key and key.value==binding_name and value:value.value=texture;changed=True
        if not changed:return None
        owned_textures[texture+'_c']=record['file']
    if kind=='foil_target':
        from collection_effects import set_scalar
        for key in ('g_flPearlescentScale','g_flIridescentStrength'):
            value=family_params.get(key)
            if value and not set_scalar(root,mroot,key,value):return None
    if kind=='overlay':
        from collection_channel_palettes import channels
        colours=channels(kit,theme)
        if colours:
            from gun_collections import _colour_bindings
            vectors=_colour_bindings(root);template=f._vector_params(mroot,allow_partial=True) or {}
            for index,colour in enumerate(colours):
                key='g_vColor%d'%index
                for value in vectors.get(key,()):
                    for channel,number in zip(value.value,colour[:3]):channel.value=round(number*255)
                if key in template:
                    for channel,number in zip(template[key].value,colour[:3]):channel.value=number
    owned=f.VMAT_DIR+new_name+'.vmat'
    f._specific_material(root).value=owned
    label=mroot.get('m_materialName')
    if label:label.value=owned
    return (f._with_block(data,'DATA',kv3.write_kv3(guid,root)),
            f._with_block(mdata,'DATA',kv3.write_kv3(mguid,mroot)),
            [],primary_stats['palette'],owned_textures)

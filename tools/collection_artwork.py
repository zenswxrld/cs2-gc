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
          'cu_awp_chroma_pink':'hue','cu_m4_asimov':'hue'}

def make(source,kit,path,new_name,theme):
    import native_finishes as f
    from gun_collections import inspect
    found=inspect(source,path)
    if not found:return None
    kind=DONORS[kit]
    adapted=kind in ('spoon_target','foil_target')
    binding_name='g_tCaseHardeningColorRamp' if kind in ('ramp','spoon_target','foil_target') else 'g_tPattern'
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
    original=source.read(pattern+'_c') if pattern else None
    if original is None:return None
    try:_,_,_,width,height,payload=texture_payload(original)
    except ValueError:return None
    decoder=Path(os.environ.get('CS2_GC_TEXTURE_DECODER',str(Path(__file__).with_name('cs2_gc_texture_decode.exe'))))
    if not decoder.is_file():decoder=Path(__file__).with_name('cs2_gc_texture_decode')
    if not decoder.is_file():return None
    mode='ramp' if adapted else kind
    if mode=='invert':
        if theme!='Inverse':return None
        hue,cap=0,1
    elif theme in f.THEMES:hue,cap,_=f.THEMES[theme]
    elif theme in f.DUO_THEMES:hue,_,cap=f.DUO_THEMES[theme]
    else:
        hues,cap=f.GRADIENT_THEMES[theme];hue=hues[0]
    child=subprocess.run([str(decoder),str(width),str(height),str(hue),str(cap),str({'invert':3,'hue':2,'foil':0,'ramp':1}[mode])],
        input=payload,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if child.returncode==7:return None
    if child.returncode:raise ValueError('Artwork decoder failed: '+str(child.returncode))
    stats=json.loads(child.stderr)
    if not stats['changed_pixels'] or not stats['palette']:return None
    texture='materials/cs2_gc/collection_artwork/'+kit+'_'+theme.lower()+'.vtex'
    data,guid,root=found['compmat'];mdata,mguid,mroot=found['material']
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
    if kind=='foil_target':
        from collection_effects import set_scalar
        for key in ('g_flPearlescentScale','g_flIridescentStrength'):
            value=family_params.get(key)
            if value and not set_scalar(root,mroot,key,value):return None
    owned=f.VMAT_DIR+new_name+'.vmat'
    f._specific_material(root).value=owned
    label=mroot.get('m_materialName')
    if label:label.value=owned
    return (f._with_block(data,'DATA',kv3.write_kv3(guid,root)),
            f._with_block(mdata,'DATA',kv3.write_kv3(mguid,mroot)),
            [],stats['palette'],{texture+'_c':owned_texture(original,child.stdout)})

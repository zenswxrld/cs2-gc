"""Source-weapon artwork variants; preserve neutral trim, alpha and material masks."""
import json
import os
from pathlib import Path
import subprocess
import kv3
from collection_material import texture_payload, owned_texture, exposed

DONORS = {'cu_famas_holo_ocean':'hue', 'cu_usp_printstream':'invert'}

def make(source,kit,path,new_name,theme):
    import native_finishes as f
    from gun_collections import inspect
    found=inspect(source,path)
    if not found:return None
    pattern=found['params'].get('g_tPattern')
    if not isinstance(pattern,str):return None
    original=source.read(pattern+'_c') if pattern else None
    if original is None:return None
    try:_,_,_,width,height,payload=texture_payload(original)
    except ValueError:return None
    decoder=Path(os.environ.get('CS2_GC_TEXTURE_DECODER',str(Path(__file__).with_name('cs2_gc_texture_decode.exe'))))
    if not decoder.is_file():decoder=Path(__file__).with_name('cs2_gc_texture_decode')
    if not decoder.is_file():return None
    mode=DONORS[kit]
    if mode=='invert':
        if theme!='Inverse':return None
        hue,cap=0,1
    elif theme in f.THEMES:hue,cap,_=f.THEMES[theme]
    elif theme in f.DUO_THEMES:hue,_,cap=f.DUO_THEMES[theme]
    else:
        hues,cap=f.GRADIENT_THEMES[theme];hue=hues[0]
    child=subprocess.run([str(decoder),str(width),str(height),str(hue),str(cap),'3' if mode=='invert' else '2'],
        input=payload,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if child.returncode==7:return None
    if child.returncode:raise ValueError('Artwork decoder failed: '+str(child.returncode))
    stats=json.loads(child.stderr)
    if not stats['changed_pixels'] or not stats['palette']:return None
    texture='materials/cs2_gc/collection_artwork/'+kit+'_'+theme.lower()+'.vtex'
    data,guid,root=found['compmat'];mdata,mguid,mroot=found['material']
    changed=False
    for item in exposed(root).get('g_tPattern',()):
        binding=item.get('m_strTextureRuntimeResourcePath')
        if binding is None:return None
        binding.value=texture;changed=True
    params=mroot.get('m_textureParams')
    for item in params.value if params else ():
        key,value=item.get('m_name'),item.get('m_pValue')
        if key and key.value=='g_tPattern' and value:value.value=texture;changed=True
    if not changed:return None
    owned=f.VMAT_DIR+new_name+'.vmat'
    f._specific_material(root).value=owned
    label=mroot.get('m_materialName')
    if label:label.value=owned
    return (f._with_block(data,'DATA',kv3.write_kv3(guid,root)),
            f._with_block(mdata,'DATA',kv3.write_kv3(mguid,mroot)),
            [],stats['palette'],{texture+'_c':owned_texture(original,child.stdout)})

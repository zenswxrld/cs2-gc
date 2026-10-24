"""Use an observed pearl value on a compatible shader; retain target masks/art."""
import kv3
from collection_material import exposed

def set_scalar(root,material,key,value):
    changed=False
    for item in exposed(root).get(key,()):
        field=item.get('m_flValueFloatX')
        if field is not None:field.value=float(value);changed=True
    floats=material.get('m_floatParams')
    for item in floats.value if floats else ():
        name,field=item.get('m_name'),item.get('m_flValue')
        if name and name.value==key and field is not None:field.value=float(value);changed=True
    return changed

def apply(source,path,made,effect_source):
    import native_finishes as f
    from gun_collections import inspect
    donor=inspect(source,'weapons/paints/legacy/'+effect_source+'.vcompmat')
    if not donor:return None
    _,blocks=kv3.read_resource(made[0]);guid,root=kv3.read_kv3(dict(blocks)['DATA'])
    _,blocks=kv3.read_resource(made[1]);mguid,material=kv3.read_kv3(dict(blocks)['DATA'])
    shader=material.get('m_shaderName');source_shader=donor['material'][2].get('m_shaderName')
    if not shader or not source_shader or shader.value!=source_shader.value:return None
    value=donor['params'].get('g_flPearlescentScale',0)
    if not value or not set_scalar(root,material,'g_flPearlescentScale',value):return None
    result=list(made)
    result[0]=f._with_block(made[0],'DATA',kv3.write_kv3(guid,root))
    result[1]=f._with_block(made[1],'DATA',kv3.write_kv3(mguid,material))
    return tuple(result)

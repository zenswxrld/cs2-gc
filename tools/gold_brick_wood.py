"""Private Gold Brick base-albedo override: dark wood grain, original gold/normal/wear."""
from copy import deepcopy
import os
from pathlib import Path
import subprocess
import kv3
from collection_material import texture_payload,owned_texture
_CACHE={}
SHARED='weapons/paints/legacy/_shared_paint_generic.vcompmat'
OWNED='weapons/paints/cs2_gc/goldbrick_black_wood_shared.vcompmat'
BASES=(
 ('legacy','materials/models/weapons/customization/rif_ak47/rif_ak47_composite_inputs.vmat'),
 ('modern','weapons/models/ak47/materials/composite_inputs/weapon_rif_ak47_composite_inputs.vmat'),
)

def blacken(rgba,width,height,modern=False):
    """Retain per-pixel grain/alpha. Restrict warm wood to verified AK UV islands."""
    if len(rgba)!=width*height*4:raise ValueError('AK base texture size mismatch')
    out=bytearray(rgba);seen=bytearray(width*height);changed=0
    regions=((0,.19,.13,.41),(.71,.29,.86,.52),(.16,.31,.45,.39),
             (.45,.40,.81,.61),(0,.63,.36,1),(.57,.71,.81,.87)) if modern else ((.25,.46,.94,.94),)
    for left,top,right,bottom in regions:
        for y in range(int(top*height),min(height,int(bottom*height)+1)):
            for x in range(int(left*width),min(width,int(right*width)+1)):
                index=y*width+x
                if seen[index]:continue
                seen[index]=1;p=index*4
                r,g,b,a=rgba[p:p+4]
                # Base albedo alpha is material data, not opacity: wood can have
                # alpha=0. Preserve it while excluding neutral metal and brass.
                if r<g*1.18 or g<b*.90 or r<b*1.32:continue
                luminance=.2126*r+.7152*g+.0722*b
                shade=min(255,round(24+.28*luminance))
                out[p:p+3]=bytes((shade,shade,shade));changed+=1
    return bytes(out),changed

def node(**values):
    return kv3.Node(kv3.OBJECT,[(key,kv3.Node(kv3.STRING,value)) for key,value in values.items()])

def copy_color(alias,conditions=None):
    result=node(m_nMutatorCommandType='COMP_MAT_PROPERTY_MUTATOR_COPY_PROPERTY',
       m_strCopyProperty_InputContainerSrc=alias,m_strCopyProperty_InputContainerProperty='g_tColor',
       m_strCopyProperty_TargetProperty='g_tColor')
    if conditions is not None:result.value.append(('m_vecConditions',deepcopy(conditions)))
    return result

def prepare(source):
    import native_finishes as f
    from gun_collections import _read
    if source in _CACHE:return _CACHE[source]
    shared=_read(source,SHARED)
    if not shared:return None
    data,guid,root=shared
    points=root.get('m_Points')
    procedures=points.value[0].get('m_vecCompositeMaterialAssemblyProcedures') if points and points.value else None
    if not procedures or len(procedures.value)!=1:return None
    procedure=procedures.value[0]
    containers=procedure.get('m_vecCompositeInputContainers');mutators=procedure.get('m_vecPropertyMutators')
    if not containers or not mutators:return None
    generation=next((m for m in mutators.value if m.get('m_strGenerateTexture_TargetParam') and
                     m.get('m_strGenerateTexture_TargetParam').value=='g_tColor'),None)
    instructions=generation.get('m_vecTexGenInstructions') if generation else None
    if not instructions:return None
    modern=next((m.get('m_vecConditions') for m in instructions.value if m.get('m_nSetValue_Value') and
                 m.get('m_nSetValue_Value').get('m_strName').value=='F_SEPARATE_CHANNEL_INPUTS'),None)
    if modern is None:return None
    decoder=Path(os.environ.get('CS2_GC_TEXTURE_DECODER',str(Path(__file__).with_name('cs2_gc_texture_decode.exe'))))
    if not decoder.is_file():decoder=Path(__file__).with_name('cs2_gc_texture_decode')
    if not decoder.is_file():return None
    files={};evidence={}
    for label,path in BASES:
        found=_read(source,path)
        if not found:return None
        material,mguid,mroot=found
        textures=mroot.get('m_textureParams')
        color=next((p.get('m_pValue') for p in textures.value if p.get('m_name').value=='g_tColor'),None) if textures else None
        if color is None:return None
        original=source.read(color.value+'_c')
        if not original:return None
        try:_,_,_,w,h,payload=texture_payload(original)
        except ValueError:return None
        child=subprocess.run([str(decoder),str(w),str(h)],input=payload,capture_output=True,
             creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if child.returncode:return None
        rgba,count=blacken(child.stdout,w,h,label=='modern')
        if not count:return None
        owned_texture_path='materials/cs2_gc/goldbrick_wood/'+label+'.vtex'
        files[owned_texture_path+'_c']=owned_texture(original,rgba)
        color.value=owned_texture_path
        owned_material=f.VMAT_DIR+'goldbrick_wood_'+label+'.vmat'
        mroot.get('m_materialName').value=owned_material
        files[owned_material+'_c']=f._with_block(material,'DATA',kv3.write_kv3(mguid,mroot))
        alias='goldbrick_wood_'+label
        containers.value.append(node(m_nCompositeMaterialInputContainerSourceType='CONTAINER_SOURCE_TYPE_SPECIFIC_MATERIAL',
                                     m_strSpecificContainerMaterial=owned_material,m_strAlias=alias))
        evidence[label]={'changed_wood_pixels':count,'alpha_preserved':True,'normal_roughness_wear':'original'}
    # Copy only albedo after the game's own composite inputs. Metalness generation
    # still reads the untouched inputs. Modern AK layouts use the native existing flag.
    anchor=next((i for i,m in enumerate(instructions.value) if m.get('m_strCopyMatchingKeys_InputContainerSrc') and
                  m.get('m_strCopyMatchingKeys_InputContainerSrc').value=='composite_inputs'),None)
    if anchor is None:return None
    instructions.value[anchor+1:anchor+1]=[copy_color('goldbrick_wood_legacy'),copy_color('goldbrick_wood_modern',modern)]
    files[OWNED+'_c']=f._with_block(data,'DATA',kv3.write_kv3(guid,root))
    _CACHE[source]=(files,evidence)
    return _CACHE[source]

def attach(source,root):
    made=prepare(source)
    if made is None:return {},{'status':'unavailable; gold finish retained'}
    changed=False
    def visit(n):
        nonlocal changed
        if n.type==kv3.OBJECT:
            includes=n.get('m_vecCompMatIncludes')
            if includes:
                for value in includes.value:
                    if value.value==SHARED:value.value=OWNED;changed=True
            for _,child in n.value:visit(child)
        elif isinstance(n.value,list):
            for child in n.value:visit(child)
    visit(root)
    if not changed:return {},{'status':'unavailable; no supported shared paint include'}
    return made[0],dict(status='black wood attached',textures=made[1])

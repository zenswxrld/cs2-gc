"""Original four-channel pattern masks on verified installed paint materials.

Keep the donor's weapon masks, gloss, wear, shader and effect setup. Only replace
its existing pattern texture binding and owned material paths. No guessed slots.
"""
from pathlib import Path
import struct

import kv3
import native_finishes as finishes

PATTERNS = {
    'tidal_contour': 'Tidal Contour',
    'obsidian_fault': 'Obsidian Fault',
    'prismatic_facets': 'Prismatic Facets',
    'vector_lattice': 'Vector Lattice',
}
EFFECT_DONORS = ('soe_teal_glitter','soe_pink_pearl','soe_iridescent_purple','soe_metallic_green_2')


class GeneratedSource:
    def __init__(self, original, files):
        self.original,self.files=original,files

    def read(self,path):
        return self.files[path] if path in self.files else self.original.read(path)


def material_document(source, path):
    try:
        return _material_document(source,path)
    except ValueError as error:
        # Optional donors can use a newer KV3 codec/layout. Corruption and other
        # unexpected errors still stop preparation, rather than publishing half a pack.
        if str(error).startswith(('KV3 dictionaries and binary blobs','Unsupported KV3 compression method','Unsupported KV3 node type')):
            return None
        raise


def _material_document(source, path):
    comp=source.read(path+'_c')
    if comp is None:return None
    _,blocks=kv3.read_resource(comp);data=dict(blocks).get('DATA',b'')
    if len(data)<4 or struct.unpack_from('<I',data)[0]!=kv3.MAGIC5:return None
    guid,root=kv3.read_kv3(data);specific=finishes._specific_material(root)
    if specific is None:return None
    mat=source.read(specific.value+'_c')
    if mat is None:return None
    _,blocks=kv3.read_resource(mat);data=dict(blocks).get('DATA',b'')
    if len(data)<4 or struct.unpack_from('<I',data)[0]!=kv3.MAGIC5:return None
    mat_guid,mat_root=kv3.read_kv3(data)
    return comp,guid,root,specific,mat,mat_guid,mat_root


def inspect_effects(source,kits):
    report={}
    for name in EFFECT_DONORS:
        if name not in kits:continue
        path=finishes.kit_path(name,kits[name][1])
        document=material_document(source,path)
        row={'source_compmat':path,'status':'unsupported or missing material layout'}
        if document:
            root=document[-1];shader=root.get('m_shaderName')
            row['shader']=shader.value if shader else ''
            row['vectors']={}
            params=root.get('m_vectorParams')
            for entry in params.value if params else []:
                key,value=entry.get('m_name'),entry.get('m_value')
                if key and value and isinstance(value.value,list):
                    row['vectors'][key.value]=[component.value for component in value.value]
            colors=finishes._vector_params(root,allow_partial=True)
            if colors:row['status']='colour template ready; native effect appearance needs testing'
        report[name]=row
    return report


def plan(source,kits,titles,assets=None):
    assets=Path(assets) if assets is not None else Path(__file__).parent/'weapon_patterns'
    added={};names={};files={};report={}
    # These are installed generic four-colour pattern materials, not artwork UVs.
    donor=None
    for candidate in ('am_geometric_steps','am_ossify','am_crystallized'):
        if candidate not in kits:continue
        document=material_document(source,finishes.kit_path(candidate,kits[candidate][1]))
        if not document or finishes._vector_params(document[-1]) is None:continue
        binding=pattern_binding(document[-1])
        if binding is not None and source.read(binding.value+'_c') is not None:
            donor=candidate;break
    for pattern,title in PATTERNS.items():
        row={'title':title,'status':'pattern asset or compatible source unavailable'}
        image=assets/(pattern+'.png')
        if not donor or not image.is_file():report[pattern]=row;continue
        path=finishes.kit_path(donor,kits[donor][1])
        comp,guid,root,specific,mat,mat_guid,mat_root=material_document(source,path)
        if finishes._vector_params(mat_root) is None:report[pattern]=row;continue
        binding=pattern_binding(mat_root)
        template=source.read(binding.value+'_c') if binding else None
        if template is None:report[pattern]=row;continue
        texture='materials/cs2_gc/patterns/'+pattern+'.vtex'
        binding.value=texture
        name='cg_pattern_'+pattern
        material=finishes.VMAT_DIR+name+'.vmat'
        composite=finishes.COMPMAT_DIR+name+'.vcompmat'
        label=mat_root.get('m_materialName')
        if label:label.value=material
        specific.value=material
        files[texture+'_c']=finishes.make_vtex(template,image.read_bytes())
        files[material+'_c']=finishes._with_block(mat,'DATA',kv3.write_kv3(mat_guid,mat_root))
        files[composite+'_c']=finishes._with_block(comp,'DATA',kv3.write_kv3(guid,root))
        values=dict(kits[donor][1]);values['composite_material_path']=composite
        added[name]=('0',values);names[name]=title
        report[pattern]={'title':title,'status':'generated; native pattern appearance needs testing','donor':donor}
    return added,names,files,report


def pattern_binding(root):
    params=root.get('m_textureParams')
    for entry in params.value if params else []:
        key,value=entry.get('m_name'),entry.get('m_pValue')
        if key and key.value=='g_tPattern' and value and value.type==kv3.STRING:
            return value
    return None

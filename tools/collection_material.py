"""Respect composite input overrides; preserve authored texture, masks, wear and effects."""
import colorsys
import json
import os
from pathlib import Path
import struct
import subprocess
import kv3
from collection_detail import recolour_details

TEXTURE_FAMILIES = {
    'gsch_sport_ump45': ('g_tPattern',False),
    'aq_titanium_rainbow_galilar': ('g_tCaseHardeningColorRamp',True),
}
_TEXTURES={}

def exposed(root):
    result={}
    def visit(node):
        if node.type==kv3.OBJECT:
            alias=node.get('m_strAlias');variables=node.get('m_vecLooseVariables')
            if alias and alias.value=='exposed_params' and variables:
                for item in variables.value:
                    name=item.get('m_strName')
                    if name:
                        result.setdefault(name.value,[]).append(item)
            for _,child in node.value:visit(child)
        elif isinstance(node.value,list):
            for child in node.value:visit(child)
    visit(root)
    return result

def pattern_identity(root,specific):
    variables=exposed(root)
    for item in variables.get('g_tPattern',[]):
        path=item.get('m_strTextureRuntimeResourcePath')
        if path:return path.value
    return specific.value

def pattern_from_source(source,path):
    if source is None:return None
    try:
        data=source.read(path+'_c')
        if not data:return None
        _,blocks=kv3.read_resource(data);_,root=kv3.read_kv3(dict(blocks)['DATA'])
        import native_finishes as finishes
        specific=finishes._specific_material(root)
        return pattern_identity(root,specific) if specific else None
    except (ValueError,KeyError):
        return None

def texture_payload(data,decode_payload=True):
    size=struct.unpack_from('<I',data)[0]
    version,blocks=kv3.read_resource(data[:size]);header=dict(blocks)['DATA']
    v,flags,*_=struct.unpack_from('<HH4fHHHBBIII',header)
    width,height,depth,fmt,mips=struct.unpack_from('<HHHBB',header,20)
    extra_offset,count=struct.unpack_from('<II',header,32)
    if v!=1 or depth!=1 or fmt!=20 or not mips:
        raise ValueError('Unsupported recolour texture layout')
    compression=0;sizes=None;table=32+extra_offset
    for index in range(count):
        kind,offset,length=struct.unpack_from('<III',header,table+12*index)
        if kind==4:
            start=table+12*index+4+offset
            compression,mip_offset,mip_count=struct.unpack_from('<III',header,start)
            sizes=list(struct.unpack_from('<%di'%mip_count,header,start+4+mip_offset))
    if compression not in (0,1):
        raise ValueError('Unsupported recolour texture compression')
    position=size
    for level in range(mips-1,-1,-1):
        raw=((max(1,width>>level)+3)//4)*((max(1,height>>level)+3)//4)*16
        stored=sizes[level] if sizes and compression else raw
        block=data[position:position+stored];position+=stored
        if level==0:
            if len(block)!=stored:raise ValueError('Truncated recolour texture')
            if not decode_payload:return version,blocks,flags,width,height,None
            if compression==1 and stored<raw:block=kv3.lz4_block_decompress(block,raw)
            if len(block)!=raw:raise ValueError('Wrong recolour texture payload size')
            return version,blocks,flags,width,height,block
    raise ValueError('Missing recolour texture mip')

def owned_texture(data,rgba):
    version,blocks,flags,width,height,_=texture_payload(data,decode_payload=False)
    if len(rgba)!=width*height*4:raise ValueError('Decoded texture length mismatch')
    pixels=bytearray(rgba)
    pixels[0::4],pixels[2::4]=rgba[2::4],rgba[0::4]
    reflect=[sum(rgba[i::4])/(width*height*255) for i in range(4)]
    # User (28 Oct): BC7, the format of the finish being recoloured and of CS2's own skins: 1 byte per pixel instead
    # of 4, so the generated packs are several times smaller and much quicker to write and pack.
    decoder=Path(os.environ.get('CS2_GC_TEXTURE_DECODER',str(Path(__file__).with_name('cs2_gc_texture_decode.exe'))))
    if not decoder.is_file():decoder=Path(__file__).with_name('cs2_gc_texture_decode')
    source_format=struct.unpack_from('<HH4fHHHBBIII',dict((name,value) for name,value in blocks)['DATA'],0)[9]
    if decoder.is_file():
        encoded=subprocess.run([str(decoder),'--bc7',str(width),str(height)],input=bytes(rgba),stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if encoded.returncode==0 and len(encoded.stdout)==((width+3)//4)*((height+3)//4)*16:
            header=struct.pack('<HH4fHHHBBIII',1,flags,*reflect,width,height,1,source_format,1,0,8,0)
            return kv3.write_resource(version,[[name,header if name=='DATA' else value] for name,value in blocks])+encoded.stdout
    header=struct.pack('<HH4fHHHBBIII',1,flags,*reflect,width,height,1,28,1,0,8,0)
    # The supported client already reads LZ4 mip blocks. Keep every pixel and
    # all detail; compact generated BGRA textures rather than downsampling them.
    decoder=Path(os.environ.get('CS2_GC_TEXTURE_DECODER',str(Path(__file__).with_name('cs2_gc_texture_decode.exe'))))
    if not decoder.is_file():decoder=Path(__file__).with_name('cs2_gc_texture_decode')
    if decoder.is_file():
        compressed=subprocess.run([str(decoder),'--lz4'],input=bytes(pixels),stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if compressed.returncode==0 and len(compressed.stdout)<len(pixels):
            # Verify lossless output before using the native compressed mip format.
            from native_codec import pipeline
            if not pipeline() and kv3.lz4_block_decompress(compressed.stdout,len(pixels))!=pixels:
                raise ValueError('Owned artwork lossless-compression mismatch')
            header+=struct.pack('<III',4,8,16)+struct.pack('<IIII',1,8,1,len(compressed.stdout))
            header=bytearray(header);struct.pack_into('<I',header,36,1)
            pixels=compressed.stdout
    # Extra mip/metadata tables describe the original BC7 stream; replace DATA.
    return kv3.write_resource(version,[[name,header if name=='DATA' else value] for name,value in blocks])+pixels

def make_texture(source,path,theme,ramps,finishes):
    key=(source,path,theme,ramps)
    if key in _TEXTURES:return _TEXTURES[key]
    import os
    decoder=Path(os.environ.get('CS2_GC_TEXTURE_DECODER',str(Path(__file__).with_name('cs2_gc_texture_decode.exe'))))
    if not decoder.is_file():
        decoder=Path(__file__).with_name('cs2_gc_texture_decode')
    if not decoder.is_file():return None
    original=source.read(path+'_c')
    if original is None:return None
    try: _,_,_,width,height,payload=texture_payload(original)
    except ValueError:return None
    if theme in finishes.THEMES:
        hue,saturation,_=finishes.THEMES[theme]
    elif theme in finishes.DUO_THEMES:
        hue,_,saturation=finishes.DUO_THEMES[theme]
    else:
        hues,saturation=finishes.GRADIENT_THEMES[theme];hue=hues[0]
    child=subprocess.run([str(decoder),str(width),str(height),str(hue),str(saturation),'1' if ramps else '0'],
        input=payload,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    stats=json.loads(child.stderr)
    if stats['changed_pixels']==0:return None
    made=owned_texture(original,child.stdout)
    # An input/colour pair is generated once even if featured in several collections.
    _TEXTURES[key]=(made,stats)
    return made,stats

def make(source,kit,new_name,theme,compmat,guid,root,specific,material,m_guid,m_root,report,tier):
    import native_finishes as finishes
    variables=exposed(root)
    if not variables:return False,None
    identity=pattern_identity(root,specific)
    original_specific=specific.value
    entry={'source_material':original_specific,'pattern_identity':identity,
        'shader':m_root.get('m_shaderName').value if m_root.get('m_shaderName') else '',
        'policy':'composite-detail-v1','themes':{}}
    texture_files={}
    if kit in TEXTURE_FAMILIES:
        binding,ramps=TEXTURE_FAMILIES[kit]
        rows=variables.get(binding,[])
        if not rows:return True,None
        paths=[row.get('m_strTextureRuntimeResourcePath') for row in rows]
        if any(path is None for path in paths) or len({path.value for path in paths})!=1:
            return True,None
        made=make_texture(source,paths[0].value,theme,ramps,finishes)
        if not made:return True,None
        texture,stats=made
        owned='materials/cs2_gc/colour_families/'+kit+'_'+theme.lower()+'.vtex'
        texture_files[owned+'_c']=texture
        for path in paths:path.value=owned
        # Evidence identifies the real texture transformation, not neutral template colours.
        entry.update(texture_binding=binding,texture_stats=stats,owned_texture=owned,
                     policy='masked-source-texture-v1')
        entry['themes'][theme]=stats['palette']
    else:
        template=finishes._vector_params(m_root)
        if template is None:return True,None
        keys=sorted(template);colors=[]
        for key in keys:
            values=[item.get('m_cValueColor4') for item in variables.get(key,[])]
            if any(v is None or len(v.value) not in (3,4) for v in values):return True,None
            if values:
                all_colors=[[c.value/255 for c in value.value] for value in values]
                if any(c!=all_colors[0] for c in all_colors):return True,None
                color=all_colors[0][:3]+[all_colors[0][3] if len(all_colors[0])==4 else 1]
            else:color=[v.value for v in template[key].value]
            colors.append(color)
        changed=recolour_details(colors,theme,finishes.THEMES,finishes.DUO_THEMES,finishes.GRADIENT_THEMES)
        from weapon_palettes import is_new_colourway
        if not is_new_colourway(colors,changed):return True,None
        for key,color in zip(keys,changed):
            bindings=variables.get(key,[])
            if bindings:
                for item in bindings:
                    for channel,value in zip(item.get('m_cValueColor4').value,color):
                        channel.value=round(value*255)
            else:
                for channel,value in zip(template[key].value,color):channel.value=value
        entry.update(original_colors=colors)
        entry['themes'][theme]=changed
    owned=finishes.VMAT_DIR+new_name+'.vmat'
    specific.value=owned
    label=m_root.get('m_materialName')
    if label:label.value=owned
    # Report extra owned texture files explicitly for the pool's atomic publication.
    if report is not None:
        report[kit+':'+tier]=entry
        report['_files']=texture_files
    return True,(finishes._with_block(compmat,'DATA',kv3.write_kv3(guid,root)),
        finishes._with_block(material,'DATA',kv3.write_kv3(m_guid,m_root)))



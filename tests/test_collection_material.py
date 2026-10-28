import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import collection_material as cm
import native_finishes as finishes
import kv3
from kv3 import Node
from test_native_finishes import material,compmat,obj,string,GUID

def fixture_v4(root,compressed=False):
    strings={};lanes={1:bytearray(),2:bytearray(),4:bytearray(),8:bytearray()};types=bytearray()
    def sid(s):
        if s not in strings:strings[s]=len(strings)
        return strings[s]
    def put(w,f,v):lanes[w].extend(struct.pack(f,v))
    def typ(n):
        types.append(n.type|(0x80 if n.flag else 0))
        if n.flag:types.append(n.flag)
    def val(n):
        k=n.type
        if k in kv3.CONSTANTS:return
        if k in kv3.LANES:
            w,f=kv3.LANES[k];put(w,f,n.value);return
        if k==kv3.STRING:put(4,'<i',sid(n.value));return
        if k==kv3.OBJECT:
            put(4,'<i',len(n.value))
            for name,item in n.value:typ(item);put(4,'<i',sid(name));val(item)
        elif k==kv3.ARRAY:
            put(4,'<i',len(n.value))
            for item in n.value:typ(item);val(item)
        elif k==kv3.ARRAY_TYPE_BYTE_LENGTH:
            put(1,'<B',len(n.value));types.append(n.subtype)
            for item in n.value:val(item)
        else:raise ValueError(k)
    typ(root);val(root);data=bytearray()
    lanes[4]=bytearray(struct.pack('<i',len(strings)))+lanes[4]
    for w in (1,2,4,8):
        if lanes[w]:
            data.extend(b'\0'*((-len(data))%w));data.extend(lanes[w])
    data.extend(b'\0'*((-len(data))%8))
    text=b''.join(s.encode()+b'\0' for s in strings)
    data.extend(text);data.extend(types);data.extend(struct.pack('<I',kv3.TRAILER))
    raw=bytes(data)
    if compressed:
        count=max(0,len(raw)-15);extra=bytearray()
        while count>=255:extra.append(255);count-=255
        extra.append(count);payload=bytes([min(15,len(raw))<<4])+extra+raw
    else:payload=raw
    return struct.pack('<I',kv3.MAGIC4)+GUID+struct.pack('<IHHiiiiHHiiiiii',
        int(compressed),0,16384 if compressed else 0,
        len(lanes[1]),len(lanes[4])//4,len(lanes[8])//8,len(text)+len(types),0,0,
        len(raw),len(payload),0,0,len(lanes[2])//2,0)+payload

def loose(name,values):
    return obj(('m_strName',string(name)),('m_cValueColor4',
        Node(kv3.ARRAY_TYPE_BYTE_LENGTH,[Node(kv3.UINT8,v) for v in values],0,kv3.UINT8)))

def composite():
    root=kv3.read_kv3(dict(kv3.read_resource(compmat('materials/template.vmat'))[1])['DATA'])[1]
    root.get('m_Points').value[0].get('m_vecCompositeInputContainers').value.append(obj(
        ('m_strAlias',string('exposed_params')),('m_vecLooseVariables',Node(kv3.ARRAY,[
            loose('g_vColor0',[10,10,10]),loose('g_vColor1',[220,30,20]),
            loose('g_vColor2',[240,240,240]),loose('g_vColor3',[100,18,12])]))))
    return root

def bc7_solid(r,g,b,a=255):
    value=1<<6;offset=7
    for c in (r,g,b,a):
        for _ in range(2):value|=(c>>1)<<offset;offset+=7
    value|=(r&1)<<offset;offset+=1;value|=(r&1)<<offset
    return value.to_bytes(16,'little')

def texture():
    header=struct.pack('<HH4fHHHBBIII',1,0,0,0,0,1,4,8,1,20,1,0,8,0)
    return kv3.write_resource(1,[['DATA',header]])+bc7_solid(255,1,1)+bc7_solid(127,127,127)

class CompositeDetails(unittest.TestCase):
    def test_v4_uncompressed_and_lz4_roundtrip_preserves_types_and_flags(self):
        root=composite();root.value.append(('protected',Node(kv3.STRING,'texture.vtex',1)))
        for compression in (False,True):
            guid,decoded=kv3.read_kv3(fixture_v4(root,compression))
            self.assertEqual((guid,decoded),(GUID,root))
            self.assertEqual(kv3.read_kv3(kv3.write_kv3(guid,decoded)),(guid,decoded))

    def test_exposed_colours_are_edited_instead_of_ignored_template_defaults(self):
        root=composite();comp=kv3.write_resource(0,[['DATA',fixture_v4(root,True)]])
        files={'paint.vcompmat_c':comp,'materials/template.vmat_c':material('materials/template.vmat',[[1,1,1,1]]*4)}
        class Source:
            def read(self,path):return files.get(path)
        report={}
        made=finishes.make_finish(Source(),'hy_test','paint.vcompmat','new','Teal',
            report=report,weapon_palette='ancient',detail_policy=True)
        self.assertIsNotNone(made)
        _,newroot=kv3.read_kv3(dict(kv3.read_resource(made[0])[1])['DATA'])
        before=cm.exposed(root);after=cm.exposed(newroot)
        self.assertEqual(after['g_vColor0'],before['g_vColor0'])
        self.assertEqual(after['g_vColor2'],before['g_vColor2'])
        self.assertNotEqual(after['g_vColor1'],before['g_vColor1'])
        self.assertEqual(report['hy_test:ancient']['policy'],'composite-detail-v1')
        for key in ('g_vColor1','g_vColor3'):
            after[key][0].get('m_cValueColor4').value=before[key][0].get('m_cValueColor4').value
        finishes._specific_material(newroot).value=finishes._specific_material(root).value
        self.assertEqual(newroot,root)

    @unittest.skipUnless(os.environ.get('CS2_GC_TEXTURE_DECODER'),'decoder executable required')
    def test_official_families_change_only_their_real_lacquer_or_ramp_binding(self):
        for kit,binding in (('gsch_sport_ump45','g_tPattern'),
                            ('aq_titanium_rainbow_galilar','g_tCaseHardeningColorRamp')):
            root=composite()
            variables=root.get('m_Points').value[0].get('m_vecCompositeInputContainers').value[-1].get('m_vecLooseVariables')
            for key in ('g_tPattern','g_tCaseHardeningColorRamp'):
                variables.value.append(obj(('m_strName',string(key)),
                    ('m_strTextureRuntimeResourcePath',string(key+'.vtex'))))
            comp=kv3.write_resource(0,[['DATA',fixture_v4(root,True)]])
            files={'paint.vcompmat_c':comp,
                'materials/template.vmat_c':material('materials/template.vmat',[[1,1,1,1]]*4),
                'g_tPattern.vtex_c':texture(),'g_tCaseHardeningColorRamp.vtex_c':texture()}
            class Source:
                def read(self,path):return files.get(path)
            report={}
            made=finishes.make_finish(Source(),kit,'paint.vcompmat','owned_family','Teal',
                report=report,weapon_palette='legendary',detail_policy=True)
            self.assertIsNotNone(made)
            evidence=report[kit+':legendary']
            self.assertEqual(evidence['texture_binding'],binding)
            self.assertTrue(evidence['themes']['Teal'])
            self.assertEqual(len(report['_files']),1)
            _,changed=kv3.read_kv3(dict(kv3.read_resource(made[0])[1])['DATA'])
            changed_vars=cm.exposed(changed);original_vars=cm.exposed(root)
            changed_vars[binding][0].get('m_strTextureRuntimeResourcePath').value=original_vars[binding][0].get('m_strTextureRuntimeResourcePath').value
            finishes._specific_material(changed).value=finishes._specific_material(root).value
            self.assertEqual(changed,root,'all masks, wear, effects, colour/metal trim and other bindings remain intact')

    @unittest.skipUnless(os.environ.get('CS2_GC_TEXTURE_DECODER'),'decoder executable required')
    def test_bc7_foil_recolour_preserves_silver_geometry_and_alpha(self):
        path=os.environ['CS2_GC_TEXTURE_DECODER']
        _,_,_,width,height,payload=cm.texture_payload(texture())
        decoded=subprocess.run([path,str(width),str(height)],input=payload,capture_output=True,check=True)
        self.assertEqual(decoded.stdout[:4],bytes([255,1,1,255]))
        self.assertEqual(decoded.stdout[64:68],bytes([127,127,127,255]))
        recolored=subprocess.run([path,str(width),str(height),'178','.7','0'],
            input=payload,capture_output=True,check=True)
        self.assertNotEqual(recolored.stdout[:3],decoded.stdout[:3])
        self.assertEqual(recolored.stdout[64:],decoded.stdout[64:])
        self.assertEqual(recolored.stdout[3::4],decoded.stdout[3::4])
        self.assertEqual(json.loads(recolored.stderr)['changed_pixels'],16)
        rebuilt=cm.owned_texture(texture(),recolored.stdout)
        _,_,_,w,h,packed=cm.texture_payload(rebuilt)
        self.assertEqual((w,h),(4,8));self.assertEqual(len(packed),2*16)
        again=subprocess.run([path,str(w),str(h)],input=packed,capture_output=True,check=True).stdout
        self.assertLessEqual(max(abs(a-b) for a,b in zip(again,recolored.stdout)),8)

    @unittest.skipUnless(os.environ.get('CS2_GC_TEXTURE_DECODER'),'decoder executable required')
    def test_artwork_rotation_preserves_neutrals_alpha_and_rejects_original_hue(self):
        path=os.environ['CS2_GC_TEXTURE_DECODER']
        _,_,_,w,h,payload=cm.texture_payload(texture())
        original=subprocess.run([path,str(w),str(h)],input=payload,capture_output=True,check=True).stdout
        rotated=subprocess.run([path,str(w),str(h),'270','.8','2'],input=payload,capture_output=True,check=True)
        self.assertNotEqual(rotated.stdout[:3],original[:3])
        self.assertEqual(rotated.stdout[64:],original[64:])
        self.assertEqual(rotated.stdout[3::4],original[3::4])
        self.assertEqual(subprocess.run([path,str(w),str(h),'0','.8','2'],input=payload,capture_output=True).returncode,7)
        inverse=subprocess.run([path,str(w),str(h),'0','1','3'],input=payload,capture_output=True,check=True)
        self.assertEqual(inverse.stdout[:64],original[:64])
        self.assertEqual(inverse.stdout[64:67],bytes([128,128,128]))
        self.assertEqual(inverse.stdout[3::4],original[3::4])

    @unittest.skipUnless(os.environ.get('CS2_GC_TEXTURE_DECODER'),'decoder executable required')
    def test_artwork_changes_only_pattern_binding_retaining_effect_and_wear_masks(self):
        import collection_artwork as ca
        root=composite()
        variables=root.get('m_Points').value[0].get('m_vecCompositeInputContainers').value[-1].get('m_vecLooseVariables')
        variables.value.append(obj(('m_strName',string('g_tPattern')),
            ('m_nVariableType',string('LOOSE_VARIABLE_TYPE_RESOURCE_TEXTURE')),('m_strTextureRuntimeResourcePath',string('art.vtex'))))
        comp=kv3.write_resource(0,[['DATA',fixture_v4(root,True)]])
        files={'paint.vcompmat_c':comp,'materials/template.vmat_c':material('materials/template.vmat',[[1,1,1,1]]*4),'art.vtex_c':texture()}
        class Source:
            def read(self,path):return files.get(path)
        made=ca.make(Source(),'cu_famas_holo_ocean','paint.vcompmat','owned','Violet')
        self.assertIsNotNone(made)
        _,newroot=kv3.read_kv3(dict(kv3.read_resource(made[0])[1])['DATA'])
        cm.exposed(newroot)['g_tPattern'][0].get('m_strTextureRuntimeResourcePath').value='art.vtex'
        finishes._specific_material(newroot).value=finishes._specific_material(root).value
        self.assertEqual(newroot,root)
        self.assertEqual(len(made[4]),1)


class AdaptedSignatureMaterials(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('CS2_GC_TEXTURE_DECODER'),'decoder executable required')
    def test_signature_adaptations_keep_target_pattern_and_masks(self):
        import copy
        from unittest.mock import patch
        import collection_artwork as ca
        from test_gun_collections import patterned
        for kit,family in (('aq_deagle_case_hardened_2','aq_titanium_rainbow_galilar'),
                           ('gsch_ak_djiin','gsch_sport_ump45')):
            root=composite()
            variables=root.get('m_Points').value[0].get('m_vecCompositeInputContainers').value[-1].get('m_vecLooseVariables')
            variables.value.append(obj(('m_strName',string('g_tCaseHardeningColorRamp')),
                ('m_strTextureRuntimeResourcePath',string('target-ramp.vtex'))))
            for key,value in (('g_flPearlescentScale',0.),('g_flIridescentStrength',0.)):
                variables.value.append(obj(('m_strName',string(key)),('m_flValueFloatX',Node(kv3.FLOAT,value))))
            mdata=patterned('target.vmat',[[1,1,1,1]]*4,'target-own-uv-artwork.vtex')
            _,material_root=kv3.read_kv3(dict(kv3.read_resource(mdata)[1])['DATA'])
            compdata=kv3.write_resource(0,[['DATA',kv3.write_kv3(GUID,root)]])
            def inspect(source,path):
                own=path=='target.vcompmat'
                return {'params':{'F_CASE_HARDENING':1,'g_tCaseHardeningColorRamp':'target-ramp.vtex' if own else 'family-ramp.vtex',
                        'g_flPearlescentScale':0 if own else .5,'g_flIridescentStrength':0 if own else .1},
                        'compmat':(compdata,GUID,copy.deepcopy(root)),
                        'material':(mdata,GUID,copy.deepcopy(material_root))}
            class Source:
                def read(self,path):return texture() if path=='family-ramp.vtex_c' else None
            with patch('gun_collections.inspect',side_effect=inspect):
                made=ca.make(Source(),kit,'target.vcompmat','owned_signature','Teal')
            self.assertIsNotNone(made)
            _,changed=kv3.read_kv3(dict(kv3.read_resource(made[0])[1])['DATA'])
            _,changed_material=kv3.read_kv3(dict(kv3.read_resource(made[1])[1])['DATA'])
            values=cm.exposed(changed)
            values['g_tCaseHardeningColorRamp'][0].get('m_strTextureRuntimeResourcePath').value='target-ramp.vtex'
            if kit=='gsch_ak_djiin':
                self.assertAlmostEqual(values['g_flPearlescentScale'][0].get('m_flValueFloatX').value,.5)
                self.assertAlmostEqual(values['g_flIridescentStrength'][0].get('m_flValueFloatX').value,.1)
                for key in ('g_flPearlescentScale','g_flIridescentStrength'):
                    values[key][0].get('m_flValueFloatX').value=0.
            finishes._specific_material(changed).value=finishes._specific_material(root).value
            self.assertEqual(changed,root)
            changed_material.get('m_materialName').value='target.vmat'
            self.assertEqual(changed_material,material_root,'target UV artwork and masks must remain untouched')
            self.assertEqual(len(made[4]),1)


class GoldBrickWood(unittest.TestCase):
    def test_black_stain_keeps_grain_alpha_and_metal_pixels(self):
        from gold_brick_wood import blacken
        w=h=100;original=bytearray(bytes([100,100,100,255])*(w*h))
        def put(x,y,value):original[(y*w+x)*4:(y*w+x)*4+4]=bytes(value)
        put(50,60,[160,70,30,117]);put(51,60,[90,35,15,222])
        put(52,60,[200,185,60,255]);put(50,10,[160,70,30,255])
        put(53,60,[160,70,30,0])
        out,count=blacken(original,w,h)
        at=lambda data,x,y:data[(y*w+x)*4:(y*w+x)*4+4]
        self.assertEqual(count,3)
        self.assertEqual(at(out,53,60)[3],0,'base-albedo alpha is retained material data')
        self.assertNotEqual(at(out,53,60)[:3],at(original,53,60)[:3])
        self.assertGreater(at(out,50,60)[0],at(out,51,60)[0],'grain contrast must remain')
        self.assertEqual(at(out,50,60)[0],at(out,50,60)[1])
        for x,y in ((52,60),(50,10)):self.assertEqual(at(out,x,y),at(original,x,y))
        self.assertEqual(out[3::4],original[3::4])

    def test_owned_shared_input_is_attached_to_gold_only(self):
        from unittest.mock import patch
        import gold_brick_wood as wood
        root=obj(('m_vecCompMatIncludes',Node(kv3.ARRAY,[string(wood.SHARED),string('other.vcompmat')])))
        with patch.object(wood,'prepare',return_value=({'private.vtex_c':b'owned'}, {'legacy':{'changed_wood_pixels':10}})):
            files,status=wood.attach(object(),root)
        self.assertEqual([x.value for x in root.get('m_vecCompMatIncludes').value],[wood.OWNED,'other.vcompmat'])
        self.assertEqual(status['status'],'black wood attached')
        self.assertIn('private.vtex_c',files)
        # The scope is a private includes reference, never an edit to shared stock materials.
        self.assertNotIn(wood.SHARED+'_c',files)

    @unittest.skipUnless(os.environ.get('CS2_GC_TEXTURE_DECODER'),'decoder executable required')
    def test_selective_modes_keep_portrait_tones_and_gold_porcelain_frame(self):
        path=os.environ['CS2_GC_TEXTURE_DECODER']
        for mode,first,protected in ((6,(255,1,1),(181,121,91)),(7,(1,81,255),(201,141,21))):
            data=texture()
            # The fixture has two 4x4 BC7 blocks.
            size=struct.unpack_from('<I',data)[0]
            data=data[:size]+bc7_solid(*first)+bc7_solid(*protected)
            _,_,_,w,h,payload=cm.texture_payload(data)
            original=subprocess.run([path,str(w),str(h)],input=payload,capture_output=True,check=True).stdout
            changed=subprocess.run([path,str(w),str(h),'148','.8',str(mode)],input=payload,capture_output=True,check=True)
            self.assertNotEqual(changed.stdout[:64],original[:64])
            self.assertEqual(changed.stdout[64:],original[64:])
            self.assertEqual(changed.stdout[3::4],original[3::4])

if __name__=='__main__':unittest.main()



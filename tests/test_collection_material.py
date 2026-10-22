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
        w,h,bgra=finishes.read_vtex(rebuilt)
        self.assertEqual((w,h),(4,8));self.assertEqual(bgra[:4],recolored.stdout[:4][2::-1]+b'\xff')

if __name__=='__main__':unittest.main()

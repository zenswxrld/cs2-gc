"""Generated artwork keeps exact full-resolution pixels in native LZ4 mip blocks."""
import os,random,struct,subprocess,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import kv3
import collection_material as cm
import native_finishes as f

class LosslessArtwork(unittest.TestCase):
    def test_native_lz4_block_roundtrip_and_bounds(self):
        decoder=os.environ.get('CS2_GC_TEXTURE_DECODER')
        if not decoder:self.skipTest('CI-built decoder required')
        rng=random.Random(9183)
        cases=[b'',b'a',b'a'*270,b'rgba'*65536,bytes(range(256))*600,
               bytes(rng.getrandbits(8) for _ in range(70001)),
               b'ABCD'*17000+b'last few literal pixels']
        for data in cases:
            with self.subTest(size=len(data)):
                result=subprocess.run([decoder,'--lz4'],input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(kv3.lz4_block_decompress(result.stdout,len(data)),data)
        compressed=subprocess.run([decoder,'--lz4'],input=b'rgba'*65536,stdout=subprocess.PIPE,check=True).stdout
        self.assertLess(len(compressed),65536)

    def test_compiled_owned_texture_uses_native_mip_table_and_exact_pixels(self):
        if not os.environ.get('CS2_GC_TEXTURE_DECODER'):self.skipTest('CI-built decoder required')
        width=height=128
        header=struct.pack('<HH4fHHHBBIII',1,0,0,0,0,1,width,height,1,20,1,0,8,0)
        original=kv3.write_resource(1,[['DATA',header]])+bytes(16)*(width*height//16)
        rgba=bytes((12,42,87,0,240,239,200,255))*(width*height//2)
        result=cm.owned_texture(original,rgba)
        w,h,bgra=f.read_vtex(result)
        self.assertEqual((w,h),(width,height))
        expected=bytearray(rgba);expected[0::4],expected[2::4]=rgba[2::4],rgba[0::4]
        self.assertEqual(bgra,expected)
        self.assertLess(len(result),len(rgba)//4)

if __name__=='__main__':unittest.main()


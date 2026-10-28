"""Native codec equivalence, per-art invalidation and file-backed publication."""
import hashlib,json,os,random,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import artwork_cache as cache
import collection_artwork as art
import kv3
from resource_files import publish

class ArtworkCaching(unittest.TestCase):
    def test_clean_seed_skips_obsolete_planner_and_existing_ids_preserve_history(self):
        import gun_collections as gc,native_finishes as f,collection_catalogue_designs as designs
        from test_gun_collections import compmat,patterned,Recolour,GUNS
        files={};kits={};loot=[]
        for i in range(40):
            name='hy_cache_%02d'%i;path='materials/'+name+'.vmat'
            files['weapons/paints/legacy/'+name+'.vcompmat_c']=compmat(path)
            files[path+'_c']=patterned(path,[[.8,.2,.1,1],[.2,.6,.9,1],[.9,.9,.3,1],[.4,.1,.5,1]],'pattern/'+name+'.vtex')
            kits[name]=(str(100+i),{'name':name})
            loot.append('"[%s]%s" "1"'%(name,GUNS[i%len(GUNS)]))
        text='"items_game" { "items" { %s } "client_loot_lists" { "set_x_rare" { %s } } }'%(
            ' '.join('"%d" { "name" "%s" }'%(i+1,g) for i,g in enumerate(GUNS)),' '.join(loot))
        source=Recolour().source(files);titles={k:k for k in kits}
        authored={'ashfall':[dict(donor=name,label=name) for name in list(kits)[:16]]}
        tiers=['ancient']+['legendary']*2+['mythical']*3+['rare']*4+['uncommon']*6
        for i,entry in enumerate(authored['ashfall']):
            entry.update(detail=1,review_revision=1,all_collection_revision=2,weapon=GUNS[i],tier=tiers[i],
                         mode='family' if i in (1,2) else 'fixed',themes=['Emerald','Violet','Ash'] if i in (1,2) else ['Violet'])
        with tempfile.TemporaryDirectory() as tmp,patch.object(designs,'LINEUPS',authored):
            root=Path(tmp);report={};path=root/gc.LINEUP_FILE
            with patch.object(gc,'plan',side_effect=lambda *a,**k:self.fail('clean seed called old planner: '+str(report.get('all_collection_rebuild')))):
                clean=gc.build(text,kits,titles,f.kit_path,source,{},lineup_path=path,icons=['ashfall'],report=report)
            self.assertEqual(len(clean[4]),16)
            self.assertIn('skipped obsolete',report['catalogue_seed'])
            path.unlink();(root/'cs2_gc_finish_ids.json').write_text('{}')
            with patch.object(gc,'plan',wraps=gc.plan) as legacy:
                retained=gc.build(text,kits,titles,f.kit_path,source,{},lineup_path=path,icons=['ashfall'])
            self.assertTrue(legacy.called)
            self.assertTrue(any(name.startswith('gc3') for name,_,_ in retained[0]),'existing IDs keep legacy kit definitions')

    def test_cache_invalidates_source_theme_policy_and_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(cache,'pipeline',return_value='fixture-v1'):
                store=cache.ArtworkCache(Path(tmp)/'cache')
            recipe={'kit':'native-art','theme':'Teal','mode':2}
            key=store.key(recipe,[('g_tPattern',b'original')])
            blob=store.blob(b'owned texture')
            records=[dict(binding='g_tPattern',stats={'changed_pixels':16,'palette':[[0,.7,.7,1]]},file=blob)]
            store.save(key,records)
            self.assertEqual(store.load(key),records)
            for other,inputs in ((dict(recipe,theme='Violet'),b'original'),(dict(recipe,mode=5),b'original'),(recipe,b'updated source')):
                changed=store.key(other,[('g_tPattern',inputs)])
                self.assertNotEqual(changed,key);self.assertIsNone(store.load(changed))
            store.version=('fixture-v2',store.version[1])
            self.assertIsNone(store.load(store.key(recipe,[('g_tPattern',b'original')])))

    def test_damaged_missing_or_partial_cache_regenerates(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(cache,'pipeline',return_value='fixture'):
                store=cache.ArtworkCache(tmp)
            key=store.key({},[]);blob=store.blob(b'abcdef')
            records=[dict(binding='g_tPattern',stats={'changed_pixels':16,'palette':[[0,1,1,1]]},file=blob)]
            store.save(key,records)
            self.assertIsNotNone(store.load(key))
            blob.write_bytes(b'broken')
            self.assertIsNone(store.load(key),'same-size damaged texture cannot pass cache')
            store.blob(b'abcdef');self.assertIsNotNone(store.load(key))
            blob.unlink();self.assertIsNone(store.load(key))
            (Path(tmp)/(key+'.json')).write_text('{incomplete')
            self.assertIsNone(store.load(key))
            self.assertFalse(list(Path(tmp).glob('*.tmp')))

    def test_file_payload_publishes_atomically_and_does_not_modify_shared_inode(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source.blob';source.write_bytes(b'art')
            target=root/'mod/art.vtex_c'
            self.assertTrue(publish(target,source));self.assertEqual(target.read_bytes(),b'art')
            self.assertFalse(publish(target,source))
            self.assertTrue(publish(target,b'new art'))
            self.assertEqual(source.read_bytes(),b'art','replacement cannot overwrite cache hardlink')
            with patch('resource_files.os.link',side_effect=OSError('unsupported filesystem')):
                publish(target,source)
            self.assertEqual(target.read_bytes(),b'art')
            self.assertFalse(list(target.parent.glob('*.tmp')))

    @unittest.skipUnless(os.environ.get('CS2_GC_TEXTURE_DECODER'),'native decoder required')
    def test_warm_artwork_avoids_decoder_and_retains_every_output_byte(self):
        from test_collection_material import composite,fixture_v4,texture,obj,string
        from test_native_finishes import material
        root=composite();variables=root.get('m_Points').value[0].get('m_vecCompositeInputContainers').value[-1].get('m_vecLooseVariables')
        variables.value.append(obj(('m_strName',string('g_tPattern')),('m_nVariableType',string('LOOSE_VARIABLE_TYPE_RESOURCE_TEXTURE')),
                                  ('m_strTextureRuntimeResourcePath',string('pattern.vtex'))))
        files={'paint.vcompmat_c':kv3.write_resource(0,[['DATA',fixture_v4(root,True)]]),
               'materials/template.vmat_c':material('materials/template.vmat',[[1,1,1,1]]*4),'pattern.vtex_c':texture()}
        class Source:
            def read(self,path):return files.get(path)
        source=Source()
        baseline=art.make(source,'cu_famas_holo_ocean','paint.vcompmat','owned','Violet')
        with tempfile.TemporaryDirectory() as tmp:
            with cache.activate(tmp) as store:
                cold=art.make(source,'cu_famas_holo_ocean','paint.vcompmat','owned','Violet')
                self.assertEqual(cold[:4],baseline[:4])
                self.assertEqual({k:v.read_bytes() for k,v in cold[4].items()},baseline[4])
                # The material name is deliberately not part of texture identity.
                with patch.object(art.subprocess,'run',side_effect=AssertionError('warm cache decoded again')):
                    warm=art.make(source,'cu_famas_holo_ocean','paint.vcompmat','owned','Violet')
                    other_name=art.make(source,'cu_famas_holo_ocean','paint.vcompmat','historical_owned','Violet')
                self.assertEqual(warm,cold)
                self.assertEqual(warm[4],other_name[4])
                self.assertEqual((store.hits,store.misses),(2,1))
                # Duplicate required entries schedule one render; these calls
                # must still use the existing cache, including across threads.
                entries=[dict(donor='cu_famas_holo_ocean',mode='fixed',themes=['Violet'])]*2
                with patch.object(art.subprocess,'run',side_effect=AssertionError('prewarm decoded cached art')):
                    cache.prewarm(source,{'cu_famas_holo_ocean':('1',{})},lambda *a:'paint.vcompmat',entries)
                self.assertEqual((store.hits,store.misses),(3,1))

class NativeLz4(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('CS2_GC_TEXTURE_DECODER'),'native decoder required')
    def test_native_decoder_matches_python_and_rejects_truncation_and_declared_overruns(self):
        path=os.environ['CS2_GC_TEXTURE_DECODER'];rng=random.Random(7481)
        for data in (b'',b'a',b'A'*400000,b'rgba'*200000,bytes(range(256))*4000,
                     bytes(rng.getrandbits(8) for _ in range(300000))):
            encoded=subprocess.run([path,'--lz4'],input=data,capture_output=True,check=True).stdout
            decoded=subprocess.run([path,'--unlz4',str(len(data))],input=encoded,capture_output=True,check=True)
            self.assertEqual(decoded.stdout,data)
            with patch('native_codec.pipeline',return_value=None):self.assertEqual(kv3.lz4_block_decompress(encoded,len(data)),data)
            bad=subprocess.run([path,'--unlz4',str(len(data)+1)],input=encoded,capture_output=True)
            self.assertNotEqual(bad.returncode,0)
        for encoded,size in ((b'\xff',100),(b'\x00\x00\x00',4),(b'\x00\x01\x00',4),(b'\x10',1),(b'\xf0\xff',32)):
            self.assertNotEqual(subprocess.run([path,'--unlz4',str(size)],input=encoded,capture_output=True).returncode,0)

if __name__=='__main__':unittest.main()

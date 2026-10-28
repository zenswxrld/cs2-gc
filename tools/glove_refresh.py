"""Small owned glove override, independent of the expensive weapon artwork build."""
import hashlib,json,zlib
from pathlib import Path
import native_gloves as gloves
import native_finishes as finishes
from native_tradeups import parse,read_text,atomic_write,mount_gameinfo
from preparation_cache import digest

FOLDER='cs2_gc_glove_palettes'
OWNER='cs2-gc-glove-refresh-v1'

def patch_schema(source,entries,case):
    root=parse(source).one('items_game');sections={}
    for n in root.children:sections.setdefault(n.key,[]).append(n)
    kits={n.key:n for block in sections.get('paint_kits',[]) for n in block.children or []}
    edits=[];extra=[];rarities=[]
    for kit,name,title,values in entries:
        if kit in kits:
            node=kits[kit]
            if node.text('name')!=name:raise ValueError('Owned glove paint ID conflict')
            for field in ('description_string','description_tag'):
                n=node.one(field)
                if n.value!=title:edits.append((n.start,n.end,finishes._quote(title)))
        else:
            extra.append(finishes._block(kit,[('name',name),('description_string',title),('description_tag',title),
                ('composite_material_path',values.get('composite_material_path') or gloves.COMPMAT_DIR+name+'.vcompmat')],2))
            rarities.append(finishes._quote(name)+' "ancient"')
    if extra:
        at=sections['paint_kits'][-1].end-1;edits.append((at,at,'\n'+'\n'.join(extra)+'\n'))
        at=sections['paint_kits_rarity'][-1].end-1;edits.append((at,at,'\n'+'\n'.join(rarities)+'\n'))
    pools=[n for block in sections.get('client_loot_lists',[]) for n in block.children or [] if n.key==gloves.CASE_NAME+'_ancient']
    if len(pools)!=1:raise ValueError('Expected one owned Gauntlet pool')
    pool=pools[0];edits.append((pool.opening,pool.end-1,'\n'+'\n'.join(finishes._quote(n)+' "1"' for n in case)+'\n'))
    for start,end,text in sorted(edits,reverse=True):source=source[:start]+text+source[end:]
    return source

def prepare(directory,config):
    if not config.get('knife_finishes',1) or not config.get('glove_finishes',1):return 'disabled'
    proxy=Path(directory).resolve();game=proxy.parents[1];mod=game/FOLDER
    schema=game/'cs2_gc_native/scripts/items/items_game.txt';native_manifest=game/'cs2_gc_native/cs2_gc_native_manifest.json'
    marker=mod/'cs2_gc_gloves_manifest.json';prior=json.loads(marker.read_text()) if marker.exists() else {}
    if mod.exists() and any(mod.iterdir()) and prior.get('owner')!=OWNER:raise ValueError('Unowned glove override folder')
    for name,sha in prior.get('files',{}).items():
        p=mod/name
        if not p.is_file() or digest(p)!=sha:raise ValueError('Edited glove override; leaving it unchanged')
    ids_path=proxy/'cs2_gc_finish_ids.json'
    def fingerprint():
        from colour_families import __file__ as shades_file
        return hashlib.sha256(json.dumps([digest(Path(gloves.__file__)),digest(Path(finishes.__file__)),digest(Path(shades_file)),digest(schema),digest(ids_path),
            digest(proxy/'gold_pools.txt'),config.get('glove_panel_variants',1)],sort_keys=True).encode()).hexdigest()
    if prior.get('input')==fingerprint():return 'cached: glove palettes unchanged'
    source=read_text(schema);manifest=json.loads(read_text(native_manifest))
    if manifest.get('owner')!='cs2-gc-native-mixed-v1' or manifest.get('output_sha256')!=digest(schema):raise ValueError('Native schema is not an unchanged owned override')
    original=read_text(proxy/'items_game.txt');gold=read_text(proxy/'gold_pools.txt');known=json.loads(read_text(ids_path))
    installed=finishes.Source(vpk=game/'csgo/pak01_dir.vpk');_,_,kits,_=finishes.schema_info(original,gold)
    english=installed.read('resource/csgo_english.txt').decode('utf-8-sig');report={}
    files,entries,case,_=gloves.plan(original,gold,finishes.titles_from(english,kits),installed,known,[],
        panel_variants=bool(config.get('glove_panel_variants',1)),report=report)
    updated=patch_schema(source,entries,case)
    mod.mkdir(parents=True,exist_ok=True)
    for name,data in files.items():
        p=mod/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    from vpk_pack import pack
    pack(mod)
    known.update({name:int(kit) for kit,name,_,_ in entries});atomic_write(ids_path,json.dumps(known,sort_keys=True,indent=1)+'\n')
    if updated!=source:
        atomic_write(schema,updated);manifest['output_sha256']=digest(schema);atomic_write(native_manifest,json.dumps(manifest,indent=2)+'\n')
        atomic_write(schema.parents[2]/'cs2_gc_schema_stamp.txt','CS2_GC_NATIVE_V1 %d %d\n'%(zlib.crc32(original.encode()),zlib.crc32(updated.encode())))
        pack(schema.parents[2])
    info=game/'csgo/gameinfo.gi';current=read_text(info);mounted=mount_gameinfo(current,True,FOLDER,'cs2_gc glove palette refresh')
    if current!=mounted:atomic_write(info,mounted)
    atomic_write(proxy/gloves.PALETTE_REPORT,json.dumps(report,sort_keys=True,indent=1)+'\n')
    atomic_write(marker,json.dumps(dict(owner=OWNER,input=fingerprint(),files={name:hashlib.sha256(data).hexdigest() for name,data in files.items()}),sort_keys=True,indent=1)+'\n')
    return 'rebuilt glove palettes only; weapon materials reused'

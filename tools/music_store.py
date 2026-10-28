"""Complete native music-kit Store selection, built from this installation's schema."""
import json,re,zlib
from pathlib import Path
import price_sheet as sheet
from native_tradeups import parse,read_text,atomic_write,digest

MARKER='cs2gc_music_store_v1'

def catalogue(source):
    sections=sheet.items_game.collect(sheet.items_game.parse(source))
    lists=sections.get('client_loot_lists',{})
    kits={d['name']:(str(index),d) for index,node in sections.get('music_definitions',{}).items()
          if isinstance(node,list) and (d:=sheet.items_game.as_dict(node)).get('name')}
    supported_st=set()
    def list_kits(name,seen=()):
        if name in seen or len(seen)>16:return set()
        result=set()
        for key,value in lists.get(name,[]):
            if key.startswith('[') and key.endswith(']musickit'):result.add(key[1:-9])
            elif key in lists:result.update(list_kits(key,seen+(name,)))
        return result
    for name,node in lists.items():
        if not isinstance(node,list):continue
        values=sheet.items_game.as_dict(node)
        if values.get('will_produce_stattrak')=='1':
            supported_st.update(list_kits(name))
    offers={}
    capsules=[]
    for index,node in sections.get('items',{}).items():
        if not isinstance(node,list):continue
        d=sheet.items_game.as_dict(node);name=d.get('name','')
        entries=[k for k,_ in lists.get(d.get('loot_list_name',''),[]) if k!='public_list_contents']
        if len(entries)==1 and entries[0].startswith('[') and entries[0].endswith(']musickit'):
            kit=entries[0][1:-9]
            if kit in kits:
                st=d.get('will_produce_stattrak')=='1'
                offers.setdefault((kit,st),(str(index),name))
                if st:supported_st.add(kit)
        if name.startswith('coupon - ') and 'musickit_capsule' in name:
            capsules.append((str(index),name,'stattrak' in name))
    return kits,offers,supported_st,capsules

def patch_schema(source):
    if MARKER in source:return source
    kits,offers,supported_st,_=catalogue(source)
    if not kits:return source
    root=parse(source).one('items_game')
    items=[n for n in root.children if n.key=='items'];lists=[n for n in root.children if n.key=='client_loot_lists']
    if not items or not lists:raise ValueError('Music store needs item and loot-list sections')
    used={n.key for block in items for n in block.children or []};rows=[];loot=[]
    for kit,(index,d) in kits.items():
        if not re.fullmatch('[a-zA-Z0-9_]+',kit) or not index.isdigit():raise ValueError('Unexpected music kit identifier')
        for st in (False,True):
            if (kit,st) in offers or (st and kit not in supported_st):continue
            definition=str(56000+int(index)*2+int(st))
            if definition in used:raise ValueError('Reserved music store definition occupied: '+definition)
            name='cs2gc_music_'+kit+('_stattrak' if st else '')
            title=d.get('loc_name',kit);image=d.get('image_inventory','')
            if any('"' in v or '\n' in v for v in (title,image)):raise ValueError('Unexpected music kit metadata')
            rows.append('"%s" { "name" "%s" "prefab" "coupon_prefab" "item_name" "%s" "item_description" "#coupon_desc" "image_inventory" "%s" "loot_list_name" "coupon loot list - %s" "will_produce_stattrak" "%d" }'%(definition,name,title,image,name,st))
            loot.append('"coupon loot list - %s" { "public_list_contents" "1" "[%s]musickit" "1" }'%(name,kit))
    for at,text in sorted([(items[0].end-1,'\n// '+MARKER+'\n'+'\n'.join(rows)+'\n'),(lists[0].end-1,'\n'+'\n'.join(loot)+'\n')],reverse=True):
        source=source[:at]+text+source[at:]
    return source

def add_store(tree,source):
    kits,offers,_,capsules=catalogue(source)
    if not kits:return 0
    entries=sheet.section(tree,'store','entries')
    templates={}
    for _,values in entries:
        if not isinstance(values,list):continue
        d=dict(values);name=d.get('item_link','')
        if 'musickit_capsule' in name and d.get('prices'):
            templates.setdefault('stattrak' in name,values)
    if False not in templates or True not in templates:raise ValueError('Missing native music-kit price templates')
    existing={dict(v).get('item_link') for _,v in entries if isinstance(v,list)};added=0
    rows=[(idx,name,st) for (kit,st),(idx,name) in offers.items()]+capsules
    for idx,name,st in rows:
        if name not in existing:
            prices=[tuple(p) for p in dict(templates[st])['prices']]
            entries.append((name,[('item_link',name),('category_tags','Misc'),('prices',prices)]))
            existing.add(name);added+=1
    sheet.add_banner_entries(tree,[idx for idx,_,_ in rows])
    return added

def prepare(directory,config):
    proxy=Path(directory).resolve();mod=proxy.parents[1]/'cs2_gc_native'
    target=mod/'scripts/items/items_game.txt';manifest_path=mod/'cs2_gc_native_manifest.json'
    if not target.is_file():return 'unavailable: native schema missing'
    source=read_text(target);manifest=json.loads(read_text(manifest_path))
    if manifest.get('owner')!='cs2-gc-native-mixed-v1' or digest(source)!=manifest.get('output_sha256'):
        raise ValueError('Music store requires an unchanged owned schema override')
    changed=patch_schema(source)
    if changed!=source:
        atomic_write(target,changed);manifest['output_sha256']=digest(changed)
        atomic_write(manifest_path,json.dumps(manifest,indent=2)+'\n')
        original=read_text(proxy/'items_game.txt')
        atomic_write(mod/'cs2_gc_schema_stamp.txt','CS2_GC_NATIVE_V1 %d %d\n'%(zlib.crc32(original.encode()),zlib.crc32(changed.encode())))
        from vpk_pack import pack
        pack(mod)
    kits,offers,_,_=catalogue(changed)
    return 'ready: %d kits, %d direct regular/StatTrak selections'%(len(kits),len(offers))

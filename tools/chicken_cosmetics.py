"""Local native inventory accessories referencing the installed photo-booth models; no Valve assets ship."""
import hashlib,json,math,struct,zlib
from pathlib import Path
from native_tradeups import parse,atomic_write,digest,read_text
COLLECTION='cs2gc_chicken_cosmetics'
ACCESSORIES=(('helmet','Combat Helmet','rare'),('armor','Armoured Helmet','rare'),('glasses','Glasses','rare'),
    ('nose_glasses','Disguise','rare'),('banana','Banana Hat','mythical'),('party','Party Hat','mythical'),
    ('sprout','Sprout','mythical'),('alien','Alien','legendary'),('top_hat','Top Hat','legendary'),('wizard_hat','Wizard Hat','ancient'))

def icon(index):
    """Authored simple silhouettes, rendered locally. Actual inspect/follower models remain the native models."""
    pixels=[];kind=ACCESSORIES[index][0]
    for y in range(128):
        row=bytearray()
        for x in range(128):
            xx=(x-64)/48;yy=(y-64)/48
            if kind in ('helmet','armor'):on=(xx*xx+yy*yy<1 and yy<.2) or (-1.1<xx<1.1 and .15<yy<.33) or (kind=='armor' and .55<abs(xx)<.85 and .2<yy<.7)
            elif kind in ('glasses','nose_glasses'):on=(.33<((abs(xx)-.48)**2+yy*yy)**.5<.48) or (abs(xx)<.15 and abs(yy)<.07) or (kind=='nose_glasses' and abs(xx)<.22 and 0<yy<.6)
            elif kind in ('top_hat','wizard_hat','party'):on=(-1<xx<1 and .5<yy<.65) or (kind=='top_hat' and abs(xx)<.6 and -.8<yy<.55) or (kind!='top_hat' and -.9<yy<.55 and abs(xx)<(yy+.9)*.55)
            elif kind=='banana':on=.7<((xx+.3)**2+(yy-.3)**2)**.5<1.05 and yy>-.5 and xx>-.6
            elif kind=='sprout':on=(abs(xx)<.07 and -.1<yy<.9) or ((abs(xx)-.4)**2/.28+(yy+.3)**2/.18<1)
            else:on=xx*xx/.7+yy*yy<1 and not ((abs(xx)-.36)**2+(yy+.15)**2<.05)
            row.extend((221,229,233,255 if on else 0))
        pixels.append(b'\0'+row)
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',128,128,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(pixels)))+chunk(b'IEND',b'')

REDEEM='\n"operational_point_redeemable" { "item_name" "lootlist:%s" "points" "3" "local_rotation_slot" "collection" "ui_order" "2" }\n'%COLLECTION

def patch(source,armory=False):
    """Add the accessories (kept so owned ones work); sell them in the Armory only when armory is set.
    User (29 Oct): "lets remove the chicken accecories for now from the armory as they still need work"."""
    if 'cs2gc_chicken_cosmetics_v1' in source:
        if not armory:return source.replace(REDEEM,'')
        if REDEEM in source:return source
        root=parse(source).one('items_game')
        campaign=[n for sec in root.children if sec.key=='seasonaloperations' for n in sec.children or [] if n.key=='11'][0]
        return source[:campaign.end-1]+REDEEM+source[campaign.end-1:]
    root=parse(source).one('items_game');items=[n for n in root.children if n.key=='items']
    used={n.key for block in items for n in block.children or []}
    if any(str(55000+i) in used for i in range(10)):raise ValueError('Reserved chicken accessory definition is occupied')
    campaigns=[n for sec in root.children if sec.key=='seasonaloperations' for n in sec.children or [] if n.key=='11']
    if len(campaigns)!=1:raise ValueError('Expected one native Armory campaign')
    campaign=campaigns[0]
    item_rows=[];tiers={key:[] for key in ('rare','mythical','legendary','ancient')}
    for i,(key,title,rarity) in enumerate(ACCESSORIES):
        model='armor_helmet' if key=='armor' else key
        item_rows.append('"%d" { "name" "cs2gc_chicken_%s" "item_class" "tool" "item_name" "Chicken | %s" "item_type_name" "Chicken Accessory" "item_description" "Equip this permanent accessory from Stats > Companions in a local match." "item_rarity" "%s" "image_inventory" "econ/cs2gc_chicken/%s" "attributes" { "pedestal display model" "models/photobooth/silly_hats/%s.vmdl" } }'%(55000+i,key,title,rarity,key,model))
        tiers[rarity].append('"cs2gc_chicken_%s" "1"'%key)
    lists='"%s" { %s }\n'%(COLLECTION,' '.join('"%s_%s" "1"'%(COLLECTION,t) for t in tiers))
    lists+='\n'.join('"%s_%s" { %s }'%(COLLECTION,t,' '.join(rows)) for t,rows in tiers.items())
    loot=[n for n in root.children if n.key=='client_loot_lists']
    if not items or not loot:raise ValueError('Expected item and loot-list sections')
    edits=[(items[0].end-1,'\n// cs2gc_chicken_cosmetics_v1\n'+'\n'.join(item_rows)+'\n'),
           (loot[0].end-1,'\n'+lists+'\n')]+([(campaign.end-1,REDEEM)] if armory else [])
    for at,text in sorted(edits,reverse=True):source=source[:at]+text+source[at:]
    return source

def prepare(directory,config):
    proxy=Path(directory).resolve();game=proxy.parents[1];mod=game/'cs2_gc_native';target=mod/'scripts/items/items_game.txt';manifest_path=mod/'cs2_gc_native_manifest.json'
    if not target.is_file():return 'unavailable: native schema override missing'
    source=read_text(target);manifest=json.loads(manifest_path.read_text())
    if manifest.get('owner')!='cs2-gc-native-mixed-v1' or digest(source)!=manifest.get('output_sha256'):raise ValueError('Native schema is not an unchanged owned override')
    armory=bool(config.get('armory_chicken_cosmetics',0))
    changed=patch(source,armory)
    catalogue=manifest.setdefault('armory_catalogue',{});listed=('lootlist:'+COLLECTION) in catalogue
    where='in the Armory' if armory else 'not sold in the Armory'
    if changed==source and listed==armory:return 'installed: Chicken Cosmetics, 10 native-model accessories, '+where
    from native_finishes import Source,make_vtex
    template=Source(vpk=game/'csgo/pak01_dir.vpk').read('panorama/images/econ/pets/chicken_egg_png.vtex_c')
    folder=mod/'panorama/images/econ/cs2gc_chicken';folder.mkdir(parents=True,exist_ok=True)
    for i,(key,_,_) in enumerate(ACCESSORIES):(folder/(key+'_png.vtex_c')).write_bytes(make_vtex(template,icon(i)))
    if armory:catalogue['lootlist:'+COLLECTION]='collection'
    else:catalogue.pop('lootlist:'+COLLECTION,None)
    atomic_write(target,changed);manifest['output_sha256']=digest(changed);manifest['chicken_cosmetics']=1;atomic_write(manifest_path,json.dumps(manifest,indent=2)+'\n')
    original=read_text(proxy/'items_game.txt')
    atomic_write(mod/'cs2_gc_schema_stamp.txt','CS2_GC_NATIVE_V1 %d %d\n'%(zlib.crc32(original.encode()),zlib.crc32(changed.encode())))
    from vpk_pack import pack
    pack(mod);return 'prepared: Chicken Cosmetics, 10 accessories, '+where+'; restart required'

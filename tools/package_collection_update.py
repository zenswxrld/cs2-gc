"""Package the reviewed helper update on GitHub Actions; no game assets or binaries."""
import hashlib
import json
from pathlib import Path
import zipfile

FILES = (
    'kv3.py','native_skins.py','native_finishes.py','weapon_palettes.py',
    'native_patterns.py','next_collection_lineups.py','retained_collection_lineups.py',
    'collection_detail.py','collection_donors.py','collection_material.py','prepare_native.py',
    'preparation_cache.py','rotate_armory.py',
)

def main():
    root=Path(__file__).resolve().parent
    out=root.parent/'dist';out.mkdir(exist_ok=True)
    manifest={}
    with zipfile.ZipFile(out/'CS2GC-Collection-Update-Test.zip','w',zipfile.ZIP_DEFLATED) as archive:
        decoder=root.parent/'build/Release/cs2_gc_texture_decode.exe'
        data=decoder.read_bytes()
        archive.writestr('cs2_gc_texture_decode.exe',data)
        manifest['cs2_gc_texture_decode.exe']=hashlib.sha256(data).hexdigest()
        archive.writestr('BCDEC-LICENSE.txt',(root.parent/'third_party/bcdec.h').read_text(encoding='utf-8').split('/* LICENSE:')[1])
        for name in FILES:
            data=(root/name).read_bytes()
            archive.writestr(name,data)
            manifest[name]=hashlib.sha256(data).hexdigest()
        archive.writestr('COLLECTION-UPDATE-README.txt',
            'Collection helper test update; keep your existing launcher and DLL.\n'
            'Close CS2 and its helper. Back up the matching helper Python files, then\n'
            'copy these files beside the existing launcher in game/bin/win64.\n'
            'Keep inventory, config and cs2_gc_finish_ids.json. No game assets are included.\n'
            'First launch regenerates the owned material pack. Subsequent unchanged launches use cache.\n'
            'New donors require compatible installed material layouts. Unsupported complete\n'
            'pools are not published; the weapon palette report records the exact reason.\n'
            'Actions checks do not establish in-game appearance. Inspect and report the\n'
            'collection_upgrade section in cs2_gc_weapon_palettes.json if a pool is absent.\n'
            'Original-weapon artwork is retained for Rainbow Spoon and Crimson Foil.\n')
        archive.writestr('COLLECTION-UPDATE-SHA256.json',json.dumps(manifest,indent=2))
    print(out/'CS2GC-Collection-Update-Test.zip')

if __name__=='__main__':
    main()

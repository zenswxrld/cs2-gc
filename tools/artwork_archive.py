"""Stream owned collection assets into standard numbered VPK archives."""
import hashlib,json,shutil,struct,tempfile,zlib
from pathlib import Path

ARCHIVE_LIMIT=1<<30
CHUNK=1<<20
CACHE='cs2_gc_pack_cache.json'
OWNER='cs2gc-stream-pack-cache-v1'

def _stamp(path):
    stat=path.stat();return [stat.st_size,stat.st_mtime_ns,stat.st_ino]

def _outputs(folder):
    return {p.name:_stamp(p) for p in owned_archives(folder)+[folder/'pak01_dir.vpk'] if p.is_file()}

def _cached(folder,state):
    try:
        saved=json.loads((folder/CACHE).read_text(encoding='utf-8'))
        if saved.get('owner')!=OWNER:return False
        return saved.get('inputs')==state and saved.get('outputs')==_outputs(folder) and (folder/'pak01_dir.vpk').is_file()
    except (OSError,ValueError,TypeError,AttributeError):return False

def _remember(folder,state):
    target=folder/CACHE;temporary=target.with_suffix('.json.tmp')
    temporary.write_text(json.dumps({'owner':OWNER,'inputs':state,'outputs':_outputs(folder)},sort_keys=True),encoding='utf-8')
    temporary.replace(target)

def owned_archives(folder):
    return sorted(p for p in Path(folder).glob('pak01_*.vpk')
                  if p.stem.removeprefix('pak01_').isdigit())

def _same(a,b):
    if not a.is_file() or a.stat().st_size!=b.stat().st_size:return False
    with a.open('rb') as first,b.open('rb') as second:
        while True:
            x,y=first.read(CHUNK),second.read(CHUNK)
            if x!=y:return False
            if not x:return True

def pack(folder,extra=()):
    folder=Path(folder)
    if not folder.is_dir():return False
    extra=tuple(extra);inputs=[];archives=set(owned_archives(folder))
    for path in sorted(folder.rglob('*')):
        if (not path.is_file() or path.name=='pak01_dir.vpk' or path in archives
                or path.suffix in ('.json','.tmp') or path.name=='cs2_gc_schema_stamp.txt'):continue
        inputs.append((path.relative_to(folder).as_posix(),path))
    state={'format':1,'archive_limit':ARCHIVE_LIMIT,'files':[[name,_stamp(path)] for name,path in inputs],
           'extra':sorted([[name,hashlib.sha256(data).hexdigest()] for name,data in extra])}
    if _cached(folder,state):return False
    # Internal staging is outside the input walk and removed on any failure.
    with tempfile.TemporaryDirectory(prefix='cs2gc-pack-',dir=folder.parent) as stage:
        stage=Path(stage)
        for i,(name,data) in enumerate(extra):
            path=stage/('extra-'+str(i));path.write_bytes(data);inputs.append((name,path))
        if not inputs:return False
        tree={};stored={};parts=[];archive=None;position=0;index=-1
        try:
            for name,path in sorted(inputs):
                digest=hashlib.sha256();crc=0;length=0
                with path.open('rb') as source:
                    while True:
                        block=source.read(CHUNK)
                        if not block:break
                        digest.update(block);crc=zlib.crc32(block,crc);length+=len(block)
                key=digest.digest()
                if key not in stored:
                    if archive is None or position+length>ARCHIVE_LIMIT:
                        if archive:archive.close()
                        index+=1
                        if index>=1000:raise ValueError('Too many owned VPK archives')
                        part=stage/('pak01_%03d.vpk'%index);parts.append(part)
                        archive=part.open('wb');position=0
                    if length>0xffffffff:raise ValueError('Owned VPK member exceeds native length field')
                    stored[key]=(index,position)
                    with path.open('rb') as source:shutil.copyfileobj(source,archive,CHUNK)
                    position+=length
                member_index,offset=stored[key]
                directory,_,filename=name.rpartition('/');stem,dot,extension=filename.rpartition('.')
                if not dot:stem,extension=filename,''
                tree.setdefault(extension or ' ',{}).setdefault(directory or ' ',[]).append(
                    (stem,crc&0xffffffff,member_index,offset,length))
        finally:
            if archive:archive.close()
        tree_data=bytearray()
        for extension in sorted(tree):
            tree_data+=extension.encode()+b'\0'
            for directory in sorted(tree[extension]):
                tree_data+=directory.encode()+b'\0'
                for stem,crc,member_index,offset,length in sorted(tree[extension][directory]):
                    tree_data+=stem.encode()+b'\0'+struct.pack('<IHHIIH',crc,0,member_index,offset,length,0xffff)
                tree_data+=b'\0'
            tree_data+=b'\0'
        tree_data+=b'\0';checks=bytearray()
        for member_index,part in enumerate(parts):
            with part.open('rb') as source:
                start=0
                while True:
                    block=source.read(CHUNK)
                    if not block:break
                    checks+=struct.pack('<III',member_index,start,len(block))+hashlib.md5(block).digest()
                    start+=len(block)
        header=struct.pack('<IIIIIII',0x55aa1234,2,len(tree_data),0,len(checks),48,0)
        body=header+tree_data+checks+hashlib.md5(tree_data).digest()+hashlib.md5(checks).digest()
        directory=body+hashlib.md5(body).digest()
        target=folder/'pak01_dir.vpk'
        if target.is_file() and target.read_bytes()==directory and all(_same(folder/p.name,p) for p in parts):
            _remember(folder,state);return False
        # Native directory is published last, after all referenced archive data.
        for part in parts:
            part.replace(folder/part.name)
        temp=folder/'pak01_dir.vpk.tmp';temp.write_bytes(directory);temp.replace(target)
        wanted={p.name for p in parts}
        for stale in owned_archives(folder):
            if stale.name not in wanted:stale.unlink()
        _remember(folder,state)
        return True



"""Content-addressed local artwork cache. No downloaded or shipped game assets."""
from contextlib import contextmanager
import hashlib,json,os,tempfile
from pathlib import Path
from native_codec import pipeline

OWNER='cs2gc-artwork-cache-v1'
_ACTIVE=None

def current():return _ACTIVE

def prewarm(source,kits,kit_path,entries):
    """Render independent required textures on a bounded number of native workers."""
    cache=current()
    if cache is None:return
    from concurrent.futures import ThreadPoolExecutor,as_completed
    from collection_artwork import DONORS,make
    jobs=sorted({(e['donor'],theme) for e in entries if e.get('donor') in DONORS and e['donor'] in kits
                 and e.get('mode') in ('fixed','family') for theme in e.get('themes',())})
    if not jobs:return
    workers=min(4,max(1,(os.cpu_count() or 2)//2),len(jobs))
    print('Artwork preflight: %d required variants; %d native workers.' % (len(jobs),workers),flush=True)
    def render(job):
        donor,theme=job
        try:return make(source,donor,kit_path(donor,kits[donor][1]),'cache_preflight',theme) is not None
        except (OSError,ValueError,KeyError):return False  # normal main validation still decides pool availability
    failed=0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for count,future in enumerate(as_completed([pool.submit(render,job) for job in jobs]),1):
            if not future.result():failed+=1
            if count%25==0 or count==len(jobs):
                print('Artwork preflight: %d/%d checked (%d pending main validation).' % (count,len(jobs),failed),flush=True)

@contextmanager
def activate(root):
    global _ACTIVE
    previous=_ACTIVE
    cache=ArtworkCache(root) if pipeline() else None
    _ACTIVE=cache
    try:yield cache
    finally:
        _ACTIVE=previous
        if cache:print('Artwork cache: %d reused, %d generated; texture payloads stored on disk.' % (cache.hits,cache.misses),flush=True)

class ArtworkCache:
    def __init__(self,root):
        self.root=Path(root);self.hits=self.misses=0;self.checked={}
        marker=self.root/'owner.json'
        if marker.is_file():
            if json.loads(marker.read_text(encoding='utf-8')).get('owner')!=OWNER:raise ValueError('Unowned artwork cache')
        elif self.root.exists() and any(self.root.iterdir()):raise ValueError('Artwork cache contains unowned files')
        self.root.mkdir(parents=True,exist_ok=True)
        if not marker.exists():self.atomic(marker,json.dumps({'owner':OWNER}).encode())
        code=hashlib.sha256()
        for name in ('collection_artwork.py','collection_material.py','kv3.py','native_codec.py'):
            code.update(Path(__file__).with_name(name).read_bytes())
        self.version=(pipeline(),code.hexdigest())

    def atomic(self,path,data):
        with tempfile.NamedTemporaryFile(dir=self.root,prefix='write-',suffix='.tmp',delete=False) as temp:
            temporary=Path(temp.name)
            try:temp.write(data)
            except BaseException:
                temp.close();temporary.unlink(missing_ok=True);raise
        try:temporary.replace(path)
        finally:temporary.unlink(missing_ok=True)

    def key(self,recipe,inputs):
        value={'format':1,'pipeline':self.version,'recipe':recipe,
               'inputs':[(name,hashlib.sha256(data).hexdigest()) for name,data in inputs]}
        return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()

    def valid(self,path,digest,size):
        try:
            stat=path.stat();stamp=(stat.st_size,stat.st_mtime_ns,stat.st_ino)
            if stat.st_size!=size:return False
            if self.checked.get(str(path))==stamp:return True
            check=hashlib.sha256()
            with path.open('rb') as source:
                for block in iter(lambda:source.read(1<<20),b''):check.update(block)
            if check.hexdigest()!=digest:return False
            self.checked[str(path)]=stamp;return True
        except OSError:return False

    def blob(self,data):
        digest=hashlib.sha256(data).hexdigest();path=self.root/(digest+'.blob')
        if not self.valid(path,digest,len(data)):self.atomic(path,data)
        return path

    def load(self,key):
        try:
            rows=json.loads((self.root/(key+'.json')).read_text(encoding='utf-8'))
            if not isinstance(rows,list) or not rows:return None
            for row in rows:
                stats=row['stats']
                if (not isinstance(row['binding'],str) or not row['binding'].startswith('g_t')
                    or not isinstance(stats,dict) or not stats.get('changed_pixels') or not stats.get('palette')):return None
                digest=row['digest']
                if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):return None
                path=self.root/(digest+'.blob')
                if not self.valid(path,digest,row['size']):return None
                row.pop('digest');row.pop('size')
                row['file']=path
            self.hits+=1;return rows
        except (OSError,ValueError,KeyError,TypeError):return None

    def save(self,key,rows):
        records=[]
        for row in rows:
            path=row['file']
            records.append({**{k:v for k,v in row.items() if k!='file'},'digest':path.stem,'size':path.stat().st_size})
        self.atomic(self.root/(key+'.json'),json.dumps(records,sort_keys=True).encode())
        self.misses+=1

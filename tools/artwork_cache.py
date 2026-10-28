"""Content-addressed local artwork cache. No downloaded or shipped game assets."""
from contextlib import contextmanager
import hashlib,json,os,tempfile,time
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
    completed=False
    try:
        yield cache
        completed=True
    finally:
        _ACTIVE=previous
        if cache:
            # Only after a complete generation: every texture the current skins use was touched this run.
            freed=cache.prune() if completed else 0
            print('Artwork cache: %d reused, %d generated; %.1f GB of unused older textures removed.' % (
                cache.hits,cache.misses,freed/2**30),flush=True)

class ArtworkCache:
    def __init__(self,root):
        self.root=Path(root);self.hits=self.misses=0;self.checked={};self.used=set();self._index=None
        # The finish pack beside the cache holds every texture of the last complete generation (artwork_archive).
        self.archive=self.root.parent/'cs2_gc_finishes'
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

    def index(self):
        if self._index is None:
            from finish_storage import read_index  # textures released to the pack by finish_storage.compact
            self._index=read_index(self.archive)
        return self._index

    def restore(self,path,digest,size):
        """Copy a texture this cache released back out of the packed archive, verified by its sha256."""
        found=self.index().get(digest)
        if not found or found[2]!=size:return False
        archive,offset,length=found
        try:
            with archive.open('rb') as source:
                source.seek(offset);data=source.read(length)
        except OSError:return False
        if len(data)!=size or hashlib.sha256(data).hexdigest()!=digest:return False
        self.atomic(path,data);return True

    def valid(self,path,digest,size):
        try:
            if not path.exists() and not self.restore(path,digest,size):return False
            stat=path.stat();stamp=(stat.st_size,stat.st_mtime_ns,stat.st_ino)
            if stat.st_size!=size:return False
            if self.checked.get(str(path))==stamp:return True
            check=hashlib.sha256()
            with path.open('rb') as source:
                for block in iter(lambda:source.read(1<<20),b''):check.update(block)
            if check.hexdigest()!=digest:return False
            # Windows updates modification times coarsely (~15 ms): a same-size rewrite right after a check can keep
            # the same stamp, so only files that have been unchanged for a while may skip the next hash.
            if time.time_ns()-stat.st_mtime_ns>2_000_000_000:self.checked[str(path)]=stamp
            return True
        except OSError:return False

    def blob(self,data):
        digest=hashlib.sha256(data).hexdigest();path=self.root/(digest+'.blob')
        if not self.valid(path,digest,len(data)):self.atomic(path,data)
        self.used.add(path.name)
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
            self.used.add(key+'.json');self.used.update(row['file'].name for row in rows)
            self.hits+=1;return rows
        except (OSError,ValueError,KeyError,TypeError):return None

    def save(self,key,rows):
        records=[]
        for row in rows:
            path=row['file']
            records.append({**{k:v for k,v in row.items() if k!='file'},'digest':path.stem,'size':path.stat().st_size})
        self.atomic(self.root/(key+'.json'),json.dumps(records,sort_keys=True).encode())
        self.used.add(key+'.json');self.used.update(row['file'].name for row in rows)
        self.misses+=1

    def prune(self):
        """Remove cached records and textures this (complete) generation did not use. Returns bytes freed."""
        freed=0
        for path in self.root.iterdir():
            if path.suffix not in ('.blob','.json') or path.name=='owner.json' or path.name in self.used:continue
            try:
                info=path.stat()
                if info.st_nlink<=1:freed+=info.st_size
                path.unlink()
            except OSError:pass
        return freed

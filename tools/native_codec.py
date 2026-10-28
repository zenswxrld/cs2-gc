"""Optional bounded native LZ4 path; small blocks and older tools use Python."""
import os,subprocess
from functools import lru_cache
from pathlib import Path

def executable():
    path=Path(os.environ.get('CS2_GC_TEXTURE_DECODER',str(Path(__file__).with_name('cs2_gc_texture_decode.exe'))))
    if not path.is_file():path=Path(__file__).with_name('cs2_gc_texture_decode')
    return path

@lru_cache(maxsize=4)
def version(path,stamp):
    try:
        result=subprocess.run([path,'--cache-version'],capture_output=True,timeout=10,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        text=result.stdout.decode('ascii').strip()
        return text if result.returncode==0 and text.startswith('cs2gc-artwork-v2:') else None
    except (OSError,ValueError,subprocess.TimeoutExpired):return None

def pipeline():
    path=executable()
    try:stamp=(path.stat().st_size,path.stat().st_mtime_ns)
    except OSError:return None
    return version(str(path),stamp)

def decompress(data,size):
    if size<1<<18 or size>1<<27 or not pipeline():return None
    result=subprocess.run([str(executable()),'--unlz4',str(size)],input=data,capture_output=True,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode or len(result.stdout)!=size:raise ValueError('Invalid native LZ4 block or declared size')
    return result.stdout

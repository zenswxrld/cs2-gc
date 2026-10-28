"""Complete, checked local progress snapshots. Never copy executables or generated game assets."""
import argparse,contextlib,datetime,hashlib,json,os,sys,uuid,zipfile
from pathlib import Path
from rewards_runtime import InstanceLock

FILES=('cs2_gc_inventory.txt','cs2_gc_gsi_state.json','cs2_gc_rewards.txt','cs2_gc_matches.txt',
       'cs2_gc_premier.txt','cs2_gc_finish_ids.json','cs2_gc_gun_collections.json',
       'cs2_gc_mission_progress.txt','cs2_gc_missions.json','cs2_gc_skin_families.txt',
       'cs2_gc_console.txt','cs2_gc_console_boot.txt','cs2_gc_gameplay.cfg','cs2_gc.cfg')
MAX_FILE=64*1024*1024

def digest(data):return hashlib.sha256(data).hexdigest()

def save_folder(proxy):return Path(proxy).resolve().parents[2]/'CS2 GC Saves'

@contextlib.contextmanager
def closed(proxy):
    from fair_bot_policy import require_game_closed
    require_game_closed()
    with InstanceLock(proxy) as acquired:
        if not acquired:raise ValueError('Close the rewards helper before backing up or restoring progress.')
        yield

def read_files(proxy,strict=True):
    result={}
    for name in FILES:
        path=Path(proxy)/name
        if path.is_file():
            if path.is_symlink() or path.stat().st_size>MAX_FILE:raise ValueError('Invalid save file: '+name)
            result[name]=path.read_bytes()
    if strict:
        if 'cs2_gc_inventory.txt' not in result:raise ValueError('No inventory found in this game copy.')
        validate(result)
    return result

def validate(files):
    from native_tradeups import parse
    root=parse(files['cs2_gc_inventory.txt'].decode('utf-8-sig')).one('inventory')
    root.one('items')
    for name,data in files.items():
        if name.endswith('.json'):json.loads(data.decode('utf-8-sig'))
    if 'cs2_gc_gsi_state.json' in files:
        state=json.loads(files['cs2_gc_gsi_state.json'])
        for key,name in (('total','cs2_gc_rewards.txt'),('matches','cs2_gc_matches.txt')):
            if name in files and int(files[name])!=state.get(key,0):
                raise ValueError('Save counters disagree: '+name+'. Close the game and retry.')

def snapshot(proxy,folder=None,label='Progress',strict=True):
    """Caller holds the helper lock and has checked that CS2 is closed."""
    files=read_files(proxy,strict)
    folder=Path(folder) if folder else save_folder(proxy);folder.mkdir(parents=True,exist_ok=True)
    stamp=datetime.datetime.now().astimezone().isoformat(timespec='seconds')
    manifest={'format':1,'created':stamp,'present':list(files),'sha256':{n:digest(d) for n,d in files.items()}}
    if not strict:manifest['raw_recovery']=True
    release=Path(proxy)/'cs2_gc_release.json'
    if release.is_file():manifest['source_build']=json.loads(release.read_text()).get('commit','unknown')
    name=label+'-'+datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')+'-'+uuid.uuid4().hex[:6]+'.zip'
    target=folder/name;temporary=target.with_suffix('.tmp')
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
        for path,data in files.items():archive.writestr(path,data)
        archive.writestr('save.json',json.dumps(manifest,indent=2))
    temporary.replace(target)
    return target

def load_snapshot(path):
    with zipfile.ZipFile(path) as archive:
        infos=archive.infolist();names=[i.filename for i in infos]
        if len(names)!=len(set(names)) or any(n not in FILES+('save.json',) for n in names):
            raise ValueError('Unknown or duplicate file in progress backup.')
        if any(i.file_size>MAX_FILE for i in infos):raise ValueError('Backup file too large.')
        manifest=json.loads(archive.read('save.json'))
        present=manifest.get('present',[])
        if manifest.get('format')!=1 or not isinstance(present,list) or set(present)!=set(names)-{'save.json'}:
            raise ValueError('Unsupported or incomplete progress backup.')
        files={n:archive.read(n) for n in present}
        if 'cs2_gc_inventory.txt' not in files or any(digest(d)!=manifest.get('sha256',{}).get(n) for n,d in files.items()):
            raise ValueError('Backup checksum mismatch; no progress changed.')
    validate(files)
    return files

def atomic(path,data):
    temporary=path.with_name(path.name+'.restore-tmp')
    with temporary.open('wb') as output:output.write(data);output.flush();os.fsync(output.fileno())
    temporary.replace(path)

def restore(proxy,path,folder=None):
    """Preflight all files, keep a rollback snapshot, and roll back a failed multi-file restore."""
    proxy=Path(proxy);incoming=load_snapshot(path)
    if 'cs2_gc_gsi_state.json' in incoming:
        state=json.loads(incoming['cs2_gc_gsi_state.json'])
        state.pop('mission_session',None)
        if 'last' in state:state['last']=None
        incoming['cs2_gc_gsi_state.json']=(json.dumps(state,separators=(',',':'))+'\n').encode()
    before={n:(proxy/n).read_bytes() for n in FILES if (proxy/n).is_file()}
    rollback=snapshot(proxy,folder,'Before-Restore',strict=False)
    changed=[]
    try:
        for name in FILES:
            dest=proxy/name
            if dest.exists() and dest.is_symlink():raise ValueError('Refusing a linked save file: '+name)
            changed.append(name)
            if name in incoming:atomic(dest,incoming[name])
            elif dest.exists():dest.unlink()
        # Old map/mission/cache/console sessions must never be replayed after restore.
        for name in ('cs2_gc_mission_session.txt','cs2_gc_mission_current.txt','cs2_gc_prepare_cache.json',
                     'cs2_gc_combat_session.json','cs2_gc_combat_events.json','cs2_gc_pet_request.txt','cs2_gc_pets.json'):
            (proxy/name).unlink(missing_ok=True)
    except Exception:
        for name in reversed(changed):
            if name in before:atomic(proxy/name,before[name])
            else:(proxy/name).unlink(missing_ok=True)
        raise
    return rollback

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('backup','restore'));parser.add_argument('--proxy-dir',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--file',type=Path);args=parser.parse_args()
    try:
        with closed(args.proxy_dir):
            if args.action=='backup':print('Progress saved to:\n'+str(snapshot(args.proxy_dir)))
            else:
                chosen=args.file
                if chosen is None:
                    folder=save_folder(args.proxy_dir);saves=sorted(folder.glob('*.zip'),key=lambda p:p.stat().st_mtime,reverse=True)
                    if not saves:raise ValueError('No backups in '+str(folder)+'. Copy a complete progress backup here first.')
                    for i,path in enumerate(saves,1):print('%d. %s'%(i,path.name))
                    answer=input('Backup number to restore (Enter cancels): ').strip()
                    if not answer:return 0
                    if not answer.isdigit() or not 1<=int(answer)<=len(saves):raise ValueError('Invalid backup number.')
                    chosen=saves[int(answer)-1]
                rollback=restore(args.proxy_dir,chosen)
                print('Progress restored. Your previous progress is saved in:\n'+str(rollback))
        return 0
    except (OSError,ValueError,KeyError,zipfile.BadZipFile) as error:
        print('Progress operation stopped: '+str(error));return 1

if __name__=='__main__':raise SystemExit(main())

"""Build the complete drag-and-drop ZIP on Actions. No Valve files or player data."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.request
import zipfile
from make_proxy_def import export_names, OVERRIDDEN

PYTHON_URL = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip'
BIN = 'game/bin/win64/'
EXCLUDED_NAMES = {'items_game.txt','steam_api64_real.dll','steam_api64.dll',
                  'cs2_gc_inventory.txt','cs2_gc_finish_ids.json','cs2_gc.cfg','cs2_gc_gameplay.cfg'}


def project_files(root):
    tools = root/'tools'
    result = []
    for path in sorted(tools.rglob('*')):
        relative = path.relative_to(tools)
        if not path.is_file() or '__pycache__' in relative.parts:
            continue
        if path.suffix.lower() not in ('.py','.png','.cmd'):
            continue
        if path.name in EXCLUDED_NAMES or 'cs2_gc_replay' in relative.parts:
            raise ValueError('Player or game data must never enter the release ZIP')
        result.append((path,BIN+relative.as_posix()))
    return result


def expected_exports(root):
    return sorted(line.strip().split('=')[0].strip() for line in
                  (root/'data/steam_api64_exports.def').read_text().splitlines()
                  if line.startswith('    '))


def build_archive(root, runtime_data, bot_files):
    root = Path(root)
    build = root/'build/Release'
    proxy = build/'steam_api64.dll'
    names = export_names(proxy.read_bytes(),'steam_api64_real')
    if sorted(names) != expected_exports(root) or not set(OVERRIDDEN).issubset(names):
        raise ValueError('Proxy export validation failed')
    files = project_files(root)
    for name in ('cs2_gc_debug.exe','cs2_gc_profile.exe','cs2_gc_texture_decode.exe'):
        files.append((build/name,BIN+name))
    files += [(build/'cs2_gc_debug.exe','Launch CS2 GC.exe'),
              (proxy,BIN+'cs2_gc_payload/steam_api64.dll'),
              (root/'data/gold_pools.txt',BIN+'gold_pools.txt'),
              (root/'LICENSE','licenses/CS2-GC-LICENSE.txt'),
              (root/'data/CSGO-API-LICENSE','licenses/CSGO-API-LICENSE.txt'),
              (root/'README.md','README.md'),
              (root/'docs/DOWNGRADE.md','README-DOWNGRADE.md'),
              (root/'docs/INSTALL.md','README-INSTALL.md'),
              (root/'docs/FEATURES.md','FEATURES.md')]
    for name in ('INSTALL.md','DOWNGRADE.md','FEATURES.md','FEATURE-ROADMAP.md'):
        files.append((root/'docs'/name,'docs/'+name))
    manifest = {'format':1,'commit':os.environ.get('GITHUB_SHA',''),
                'supported_build':json.loads((root/'data/supported_build.json').read_text()),
                'python_source':PYTHON_URL,'python_archive_sha256':hashlib.sha256(runtime_data).hexdigest(),
                'files':{}}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
        seen = set()
        def add(name,data):
            if name in seen:
                raise ValueError('Duplicate release path: '+name)
            seen.add(name)
            archive.writestr(name,data)
            manifest['files'][name] = hashlib.sha256(data).hexdigest()
        for path,name in files:
            data = path.read_bytes()
            if name in ('README-INSTALL.md','FEATURES.md'):
                data = data.replace(b'(DOWNGRADE.md)',b'(README-DOWNGRADE.md)').replace(b'(INSTALL.md)',b'(README-INSTALL.md)')
            add(name,data)
        for name,data in bot_files.items():
            add(name,data)
        with zipfile.ZipFile(io.BytesIO(runtime_data)) as runtime:
            for info in runtime.infolist():
                if info.is_dir():
                    continue
                if '/' in info.filename or '\\' in info.filename or info.filename.startswith('.'):
                    raise ValueError('Unexpected Python runtime archive path')
                if info.filename.endswith('._pth'):
                    continue
                add(BIN+'cs2_gc_python/'+info.filename,runtime.read(info))
        add(BIN+'cs2_gc_python/python312._pth',b'python312.zip\n.\n..\n')
        add('licenses/BCDEC-LICENSE.txt',(root/'third_party/bcdec.h').read_text().split('/* LICENSE:')[1].encode())
        # User settings are deliberately not archive entries. Runtime defaults are
        # built into gameplay_config.py and the proxy, so upgrades preserve settings.
        archive.writestr(BIN+'cs2_gc_release.json',json.dumps(manifest,indent=2))
    return buffer.getvalue()


def smoke_test(archive_data):
    with tempfile.TemporaryDirectory(prefix='cs2gc-release-') as directory:
        root = Path(directory)
        with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
            archive.extractall(root)
        bin_dir = root/BIN
        manifest = json.loads((bin_dir/'cs2_gc_release.json').read_text())
        for name,wanted in manifest['files'].items():
            if hashlib.sha256((root/name).read_bytes()).hexdigest() != wanted:
                raise ValueError('ZIP hash mismatch: '+name)
        # The embedded runtime must work without any system Python or compiler DLLs.
        env = dict(os.environ)
        env.pop('PYTHONHOME',None)
        env.pop('PYTHONPATH',None)
        env['PATH'] = str(Path(os.environ['SystemRoot'])/'System32')
        subprocess.run([str(bin_dir/'cs2_gc_python/python.exe'),'-B','-c',
            'import launch_setup,prepare_native,gsi_rewards,bundled_bots,ctypes,lzma,ssl; print("Bundled runtime imports OK")'],
            cwd=bin_dir,env=env,check=True)
        profile = subprocess.run([str(bin_dir/'cs2_gc_profile.exe')],cwd=bin_dir,env=env)
        if profile.returncode != 1:
            raise ValueError('Profile helper did not start without compiler/runtime dependencies')
        subprocess.run([str(bin_dir/'cs2_gc_python/python.exe'),'-B','-c',
            'import compileall; assert compileall.compile_dir(".",quiet=1,force=True)'],
            cwd=bin_dir,env=env,check=True)



def fetch_bytes(url, limit=128*1024*1024):
    request = urllib.request.Request(url,headers={'User-Agent':'cs2-gc-release'})
    with urllib.request.urlopen(request,timeout=120) as response:
        data = response.read(limit+1)
    if len(data)>limit:
        raise ValueError('Release dependency exceeds limit: '+url)
    return data


def bot_payload(root, fetch=fetch_bytes):
    from bundled_bots import bundle_names
    metadata = json.loads((root/'data/bot_bundle.json').read_text())
    data = fetch(metadata['url'])
    if hashlib.sha256(data).hexdigest() != metadata['sha256']:
        raise ValueError('Upstream bot archive checksum mismatch')
    names = bundle_names(data)
    forbidden = ('engine2.dll','client.dll','steam_api64.dll','steam_api64_real.dll')
    if any(Path(n).name in forbidden or n.endswith('.vpk') for n in names):
        raise ValueError('Bot archive must not distribute Valve binaries or VPKs')
    base = BIN+'cs2_gc_payload/bots/'
    files = {base+'bot_improver.zip':data,
             base+'bundle.json':json.dumps(metadata,indent=2).encode()}
    raw = 'https://raw.githubusercontent.com/'+metadata['source_repo']+'/'+metadata['source_commit']+'/'
    resources = ['overrides/%s/botprofile.db'%tier for tier in ('Low','Medium','High')]
    resources += ['cfg/my_bot_%s_config_rules_unchanged.cfg'%mode for mode in ('normal','ffa')]
    for name in resources:
        files[base+'resources/'+name] = fetch(raw+name)
    files['licenses/CS2-Bot-Improver-LICENSE.txt'] = fetch(raw+'LICENSE')
    # Keep the unmodified upstream archive and exact plugin source snapshots
    # alongside notices; third-party plugins retain their own licences.
    sources = [{'repo':metadata['source_repo'],'commit':metadata['source_commit']}]+metadata['plugin_sources']
    notices = ['Bundled bot components: unmodified CS2-Bot-Improver '+metadata['version'],
               'Windows release: '+metadata['url'],
               'Framework/plugin licences inside cs2_gc_payload/bots/bot_improver.zip are retained.',
               'Exact source snapshots for the bot project and its pinned plugin submodules:','']
    for source in sources:
        repo,commit = source['repo'],source['commit']
        name = 'licenses/bot-sources/'+repo.replace('/','-')+'-'+commit+'.tar.gz'
        files[name] = fetch('https://api.github.com/repos/'+repo+'/tarball/'+commit)
        notices.append('https://github.com/'+repo+'/tree/'+commit+' -> '+name)
    files['licenses/BOT-SOURCES.txt'] = ('\n'.join(notices)+'\n').encode()
    print('Validated bundled bot frameworks, plugins, presets and source notices.')
    return files


def main():
    root = Path(__file__).resolve().parents[1]
    print('Fetching the private Python runtime from '+PYTHON_URL)
    with urllib.request.urlopen(PYTHON_URL,timeout=60) as response:
        runtime = response.read(32*1024*1024)
    data = build_archive(root,runtime,bot_payload(root))
    smoke_test(data)
    out = root/'dist'
    out.mkdir(exist_ok=True)
    target = out/'CS2GC-Portable-25966348.zip'
    target.write_bytes(data)
    (out/(target.name+'.sha256')).write_text(hashlib.sha256(data).hexdigest()+'  '+target.name+'\n')
    print(target)


if __name__ == '__main__':
    main()

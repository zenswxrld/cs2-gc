"""Install the pinned local bot payload; never download plugins on a player's PC."""
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import zipfile
import bot_skins as bots


def bundle_names(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = [n.replace('\\','/') for n in archive.namelist()]
        for name in names:
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or ':' in name:
                raise ValueError('Unsafe bot bundle path: '+name)
    prefix = bots._bundle_prefix(names)
    if prefix is None:
        raise ValueError('Bot bundle has no addons')
    base = prefix+'/' if prefix else ''
    relative = [n[len(base):] for n in names if n.startswith(base)]
    for required in ('addons/metamod/bin/','addons/counterstrikesharp/api/',
                     'addons/counterstrikesharp/dotnet/'):
        if not any(n.startswith(required) for n in relative):
            raise ValueError('Incomplete bot frameworks: '+required)
    for plugin in ('BotRandomizer','BotAI','BotAimImprover','BotBuy','BotState','NadeSystem'):
        if not any(n.endswith('/'+plugin+'.dll') for n in relative):
            raise ValueError('Missing bot plugin: '+plugin)
    return relative


def ensure(proxy):
    proxy = Path(proxy)
    from fair_bot_policy import owned_exists,apply as fair_bots
    if (proxy/'cs2_gc_bot_plugins_disabled').exists():
        print('Bot plugins disabled by your saved preference.',flush=True)
        return False
    payload = proxy/'cs2_gc_payload/bots'
    metadata = json.loads((payload/'bundle.json').read_text(encoding='utf-8'))
    game = bots._games(proxy)
    manifest = proxy/bots.MANIFEST
    previous = json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else {}
    installed = previous.get('files',[])
    # Reuse owned installs and curated loadouts, including the existing v1.4.6 copy.
    valid_paths = all(not PurePosixPath(p).is_absolute() and '..' not in PurePosixPath(p).parts
                      and ':' not in p and '\\' not in p for p in installed)
    matching = previous.get('botimprover',[None])[0] == metadata['version']
    ready = not previous.get('bundle_sha256') or previous.get('setup_complete') is True
    if ready and matching and installed and valid_paths and all(owned_exists(proxy,p) for p in installed):
        if all((proxy/'cs2_gc_bot_presets'/tier/'botprofile.db').is_file() for tier in bots.PRESET_TIERS):
            fair_bots(proxy)
            bots._mount(game,True,proxy)
            return False
    owned = {p.split('/')[1] for p in installed if valid_paths and p.startswith('addons/') and p.count('/')>=2}
    if not previous and any((game/'csgo/addons'/name).exists() for name in ('metamod','counterstrikesharp')):
        raise ValueError('Existing bot frameworks have no CS2 GC ownership record. Keep that copy backed up; use a separate clean supported game folder for this ZIP.')
    data = (payload/'bot_improver.zip').read_bytes()
    if hashlib.sha256(data).hexdigest() != metadata['sha256']:
        raise ValueError('Bot bundle checksum mismatch. Re-extract the complete ZIP.')
    bundle_names(data)
    def resource(name):
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or ':' in name or '\\' in name:
            raise ValueError('Unsafe bot resource path')
        return (payload/'resources'/name).read_bytes()
    # Preflight every resource before installing any addon.
    for tier in bots.PRESET_TIERS:
        resource('overrides/%s/botprofile.db'%tier)
    for mode in ('normal','ffa'):
        resource('cfg/my_bot_%s_config_rules_unchanged.cfg'%mode)
    print('Installing bundled bot skins and Bot Improver '+metadata['version']+'...',flush=True)
    # A repair reinstalls the whole payload. Put held owned plugins back first so
    # the installer can replace them rather than creating active/held duplicates.
    from fair_bot_policy import restore
    restore(proxy)
    written = bots._install_improver(proxy,game,data,owned,resource_reader=resource)
    bots._core_config(game)
    # Keep the ownership record even if catalogue curation is interrupted.
    record = {'metamod':'bundled with Bot Improver','counterstrikesharp':'bundled with Bot Improver',
              'botimprover':[metadata['version'],metadata['asset']],
              'bundle_sha256':metadata['sha256'],'files':sorted(set(installed+written))}
    from launch_setup import atomic_bytes
    atomic_bytes(manifest,(json.dumps(record,indent=1)+'\n').encode())
    bots.recurate(proxy)
    bots._mount(game,True,proxy)
    record['setup_complete'] = True
    atomic_bytes(manifest,(json.dumps(record,indent=1)+'\n').encode())
    fair_bots(proxy)
    return True

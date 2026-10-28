"""Rating-scaled human reaction/aim and reversible control of owned combat plugins."""
import json,re,subprocess,sys
from pathlib import Path

OWNER='cs2gc-fair-bots-v1'
COMBAT=('BotAimImprover','BotState','NadeSystem')

def require_game_closed():
    if sys.platform!='win32':return
    result=subprocess.run(['tasklist','/FI','IMAGENAME eq cs2.exe','/FO','CSV','/NH'],capture_output=True,text=True,check=False)
    if result.returncode or '"cs2.exe"' in result.stdout.lower():
        raise RuntimeError('Close CS2 before preparing or changing the bot policy.')

def rating(proxy):
    try:return max(0,int(json.loads((Path(proxy)/'cs2_gc_gsi_state.json').read_text(encoding='utf-8')).get('premier',{}).get('rating',0)))
    except (OSError,ValueError,TypeError):return 0

def strength(value):
    # Low below 10k; approach medium at 20k, hard at 25k; extreme only above 30k.
    for low,high,a,b in ((0,10000,0,0),(10000,20000,0,.45),(20000,25000,.45,.75),(25000,30000,.75,.85),(30000,40000,.85,1)):
        if value<high:return a+(b-a)*max(0,value-low)/(high-low)
    return 1

def humanize_profile(text,value):
    weight=strength(value)
    floors={'ReactionTime':.32-.20*weight,'AttackDelay':.12-.08*weight,
            'AimFocusInitial':2.8-2.0*weight,'AimFocusDecay':.25,
            'AimFocusOffsetScale':.50-.30*weight,'AimfocusInterval':.30-.16*weight}
    lookup={key.lower():number for key,number in floors.items()}
    def update(match):
        key=match[2].lower();old=float(match[4])
        number=min(old,45+53*weight) if key=='skill' else max(old,lookup[key])
        return match[1]+match[2]+match[3]+format(number,'.6g')
    return re.sub(r'(?mi)^([ \t]*)(Skill|ReactionTime|AttackDelay|AimFocusInitial|AimFocusDecay|AimFocusOffsetScale|AimfocusInterval)([ \t]*=[ \t]*)([0-9.eE+-]+)',update,text)

def server_config(value):
    difficulty=0 if value<10000 else 1 if value<25000 else 2 if value<30000 else 3
    return ('// Local Premier bots: human reactions; no smoke reveal at any rating.\n'
            'bot_difficulty %d\nbot_prefix ""\nbot_max_visible_smoke_length 0\n'
            'bot_max_vision_distance_override -1\nsv_compute_per_bot_difficulty false\nbot_allow_grenades 0\nbot_nades less\n'
            'bot_defer_to_human_goals 1\nbot_auto_follow 1\n'%difficulty)

def paths(proxy):
    game=Path(proxy).resolve().parents[1]
    return game/'csgo/addons/counterstrikesharp/plugins',game/'cs2_gc_bot_policy'

def owned_exists(proxy,relative):
    game=Path(proxy).resolve().parents[1];active=game/'csgo'/relative
    if active.is_file():return True
    plugins,held=paths(proxy)
    try:part=active.relative_to(plugins)
    except ValueError:return False
    if not part.parts or part.parts[0] not in COMBAT:return False
    try:owned=json.loads((held/'owner.json').read_text(encoding='utf-8')).get('owner')==OWNER
    except (OSError,ValueError):return False
    return owned and (held/part).is_file()

def apply(proxy):
    """Launcher only, before CS2 starts. Touch only payload-owned combat plugins."""
    require_game_closed()
    proxy=Path(proxy);plugins,held=paths(proxy)
    try:manifest=json.loads((proxy/'cs2_gc_bot_skins.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):return []
    owned=set(manifest.get('files',[]));value=rating(proxy)
    if held.exists():
        marker=held/'owner.json'
        if not marker.is_file() or json.loads(marker.read_text(encoding='utf-8')).get('owner')!=OWNER:
            raise ValueError('Unowned bot-policy folder; leaving plugins unchanged')
    else:
        held.mkdir(parents=True);(held/'owner.json').write_text(json.dumps({'owner':OWNER}),encoding='utf-8')
    changed=[]
    for name in COMBAT:
        prefix='addons/counterstrikesharp/plugins/'+name+'/'
        if not any(path.startswith(prefix) for path in owned):continue
        source,target=(held/name,plugins/name) if name=='NadeSystem' else (plugins/name,held/name)
        if source.exists():
            # Resolve both final paths before moving a directory; no foreign plugin or merge.
            root=plugins if source.parent==plugins else held
            if source.resolve().parent!=root.resolve() or target.resolve().parent not in (plugins.resolve(),held.resolve()):
                raise ValueError('Invalid owned bot-policy path')
            if target.exists():raise ValueError('Both active and held combat plugin exist: '+name)
            source.rename(target);changed.append(name)
    cfg=proxy.resolve().parents[1]/'csgo/cfg/cs2_gc_premier_bots.cfg'
    cfg.parent.mkdir(parents=True,exist_ok=True)
    from launch_setup import atomic_bytes
    atomic_bytes(cfg,server_config(value).encode('utf-8'))
    return changed

def restore(proxy):
    """Return owned held plugins before the existing uninstaller removes its files."""
    require_game_closed()
    plugins,held=paths(proxy)
    if not held.exists():return
    if json.loads((held/'owner.json').read_text(encoding='utf-8')).get('owner')!=OWNER:
        raise ValueError('Unowned bot-policy folder; leaving plugins unchanged')
    moves=[]
    for name in COMBAT:
        source,target=held/name,plugins/name
        if not source.exists():continue
        if source.resolve().parent!=held.resolve() or target.resolve().parent!=plugins.resolve() or target.exists():
            raise ValueError('Cannot safely restore held combat plugin: '+name)
        moves.append((source,target))
    for source,target in moves:source.rename(target)
    if list(held.iterdir())==[held/'owner.json']:
        (held/'owner.json').unlink()
        held.rmdir()

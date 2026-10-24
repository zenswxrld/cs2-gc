"""Bot skins (user: "bot skin loadouts ... popular loadouts with popular sticker combos", "there is a way").

CS2's server never asks a game coordinator for bot items (bots have no Steam account), so the GC cannot give
them skins. The community route is a server plugin: Metamod:Source loads CounterStrikeSharp into the listen
server, and ed0ard's BotRandomizer (AGPL-3.0, https://github.com/ed0ard/CS2-Bot-Randomizer) hooks
GiveNamedItem to hand each bot a skinned weapon, knife, gloves, stickers and charms. Their signatures are
maintained by those projects for each CS2 update; nothing here touches game memory itself.

This tool downloads the three on the user's PC from their official release pages, installs them under
game/csgo/addons, mounts Metamod in gameinfo.gi (backed up first, other addons preserved) and replaces the
plugin's cosmetic catalogue with a curated one: popular skins per gun, popular sticker capsules (the plugin
already rolls crafts such as 4x the same sticker), popular knife finishes and gloves. Bots only; the player's
own inventory still comes from the local GC. Uninstall removes exactly what was installed.

    python bot_skins.py install | uninstall | status | recurate
"""
from pathlib import Path
import io
import json
import re
import shutil
import sys
import urllib.request
import zipfile

MANIFEST = 'cs2_gc_bot_skins.json'
METAMOD_PATH = 'csgo/addons/metamod'
COMMENT = 'cs2_gc bot skins (Metamod)'
METAMOD_LATEST = 'https://mms.alliedmods.net/mmsdrop/2.0/mmsource-latest-windows'
METAMOD_DROP = 'https://mms.alliedmods.net/mmsdrop/2.0/'
CSS_RELEASE = 'https://api.github.com/repos/roflmuffin/CounterStrikeSharp/releases/latest'
RANDOMIZER_RELEASE = 'https://api.github.com/repos/ed0ard/CS2-Bot-Randomizer/releases/latest'
PLUGIN_DIR = 'csgo/addons/counterstrikesharp/plugins/BotRandomizer'
CATALOG = 'cosmetic_catalog.json'

# Popular skins per gun, by their English finish names (resolved against the installed schema at install time;
# a gun with no match keeps the plugin's full list).
POPULAR_SKINS = {
    'weapon_ak47': ['Redline', 'Vulcan', 'Asiimov', 'Fire Serpent', 'Neon Rider', 'Bloodsport', 'Case Hardened',
                    'The Empress', 'Fuel Injector', 'Wild Lotus', 'Gold Arabesque', 'Head Shot', 'Nightwish',
                    'Ice Coaled', 'Slate', 'Neon Revolution', 'Hydroponic', 'Aquamarine Revenge', 'Frontside Misty'],
    'weapon_awp': ['Asiimov', 'Dragon Lore', 'Hyper Beast', 'Lightning Strike', 'Neo-Noir', 'Wildfire', 'Fade',
                   'Gungnir', 'Containment Breach', 'Chromatic Aberration', 'Printstream', 'Atheris', 'Duality',
                   'Medusa', 'Graphite', 'Redline', 'The Prince', 'Desert Hydra'],
    'weapon_m4a1': ['Howl', 'Asiimov', 'Neo-Noir', 'The Emperor', 'Desolate Space', 'Buzz Kill', 'In Living Color',
                    'Temukau', 'Royal Paladin', 'Hellfire', 'The Coalition', 'Poseidon', 'Spider Lily'],
    'weapon_m4a1_silencer': ['Hyper Beast', 'Printstream', 'Golden Coil', "Chantico's Fire", 'Player Two',
                             'Decimator', 'Mecha Industries', 'Hot Rod', 'Knight', 'Icarus Fell', 'Nightmare',
                             'Black Lotus', 'Welcome to the Jungle', 'Cyrex', 'Master Piece', 'Blue Phosphor'],
    'weapon_usp_silencer': ['Kill Confirmed', 'Neo-Noir', 'Printstream', 'Orion', 'Cortex', 'The Traitor',
                            'Monster Mashup', 'Jawbreaker', 'Caiman', 'Whiteout', 'Blueprint', 'Overgrowth'],
    'weapon_glock': ['Fade', 'Water Elemental', 'Gamma Doppler', 'Vogue', 'Neo-Noir', 'Wasteland Rebel',
                     'Bullet Queen', 'Dragon Tattoo', 'Twilight Galaxy', 'Snack Attack'],
    'weapon_deagle': ['Blaze', 'Printstream', 'Code Red', 'Kumicho Dragon', 'Golden Koi', 'Ocean Drive',
                      'Mecha Industries', 'Hypnotic', 'Conspiracy', 'Fennec Fox'],
    'weapon_p250': ['Asiimov', 'See Ya Later', 'Mehndi', 'Visions', 'Undertow', 'Muertos'],
    'weapon_fiveseven': ['Hyper Beast', 'Angry Mob', 'Case Hardened', 'Monkey Business', 'Fairy Tale'],
    'weapon_tec9': ['Fuel Injector', 'Decimator', 'Nuclear Threat', 'Remote Control'],
    'weapon_cz75a': ['Victoria', 'Xiangliu', 'Yellow Jacket', 'The Fuschia Is Now'],
    'weapon_hkp2000': ['Fire Elemental', 'Imperial Dragon', 'Ocean Foam', 'Wicked Sick'],
    'weapon_elite': ['Twin Turbo', 'Cobra Strike', 'Melondrama', 'Royal Consorts'],
    'weapon_revolver': ['Fade', 'Amber Fade', 'Crimson Web', 'Llama Cannon'],
    'weapon_mp9': ['Starlight Protector', 'Mount Fuji', 'Hydra', 'Food Chain', 'Wild Lily'],
    'weapon_mac10': ['Neon Rider', 'Disco Tech', 'Stalker', 'Case Hardened', 'Fade'],
    'weapon_mp7': ['Bloodsport', 'Nemesis', 'Abyssal Apparition', 'Fade'],
    'weapon_ump45': ['Primal Saber', 'Blaze', 'Momentum', 'Wild Child'],
    'weapon_p90': ['Asiimov', 'Death by Kitty', 'Emerald Dragon', 'Trigon', 'Nostalgia'],
    'weapon_mp5sd': ['Phosphor', 'Lab Rats', 'Liquidation'],
    'weapon_bizon': ['Judgement of Anubis', 'High Roller', 'Blue Streak'],
    'weapon_galilar': ['Chatterbox', 'Cerberus', 'Eco', 'Sugar Rush', 'Phoenix Blacklight'],
    'weapon_famas': ['Roll Cage', 'Commemoration', 'Mecha Industries', 'Afterimage', 'Eye of Athena'],
    'weapon_sg556': ['Integrale', 'Cyrex', 'Pulse', 'Hazard Pay'],
    'weapon_aug': ['Akihabara Accept', 'Chameleon', 'Momentum', 'Hot Rod', 'Flame Jörmungandr'],
    'weapon_ssg08': ['Dragonfire', 'Blood in the Water', 'Death Strike', 'Big Iron'],
    'weapon_scar20': ['Cyrex', 'Emerald', 'Splash Jam', 'Bloodsport'],
    'weapon_g3sg1': ['The Executioner', 'Flux', 'Chronos'],
    'weapon_nova': ['Antique', 'Hyper Beast', 'Bloomstick', 'Wild Six'],
    'weapon_xm1014': ['Tranquility', 'Incinegator', 'Seasons', 'Entombed'],
    'weapon_mag7': ['Justice', 'Bulldozer', 'Heat', 'Cinquedea'],
    'weapon_sawedoff': ['The Kraken', 'Wasteland Princess', 'Kiss♥Love', 'Devourer'],
    'weapon_negev': ['Mjölnir', 'Power Loader', 'Lionfish'],
    'weapon_m249': ['Emerald Poison Dart', 'Nebula Crusader', 'Aztec'],
}
# Sticker capsules people actually put on guns (old Katowice/Cologne holos, Crown, community classics, majors).
POPULAR_CAPSULES = ['2014 EMS One Katowice', '2014 ESL One Cologne', '2015 ESL One Katowice', '2015 ESL One Cologne',
                    'Community Sticker Capsule 1', '#CSGO_sticker_crate_key_community', '2014 DreamHack Winter',
                    'Community Capsule 2018', '2019 IEM Katowice', '2021 PGL Stockholm', '2022 PGL Antwerp',
                    'BLAST.tv Paris 2023', 'PGL Copenhagen 2024', 'Perfect World Shanghai 2024', 'BLAST.tv Austin 2025',
                    'StarLadder Budapest 2025', 'IEM Cologne 2026', 'Espionage Sticker Capsule',
                    'Elemental Craft Sticker Pack', 'Sugarface Capsule', 'Slid3 Capsule', 'Enfu Sticker Capsule']
POPULAR_KNIFE_FINISHES = {'Fade': 14, 'Doppler': 14, 'Gamma Doppler': 12, 'Marble Fade': 12, 'Tiger Tooth': 10,
                          'Crimson Web': 10, 'Slaughter': 9, 'Case Hardened': 9, 'Lore': 8, 'Autotronic': 8,
                          'Freehand': 6, 'Bright Water': 5, 'Damascus Steel': 5, 'Ultraviolet': 5, 'Black Laminate': 5}
POPULAR_GLOVES = ["Pandora's Box", 'Vice', 'Fade', 'Crimson Kimono', 'Emerald Web', 'Hedge Maze', 'Superconductor',
                  'King Snake', 'Slaughter', 'Crimson Weave', 'Amphibious', 'Omega', 'Spearmint', 'Marble Fade',
                  'Cool Mint', 'Nocts', 'Polygon', 'Imperial Plaid', 'Lt. Commander', 'Vice']


def finish_titles(items_game_text, english_text):
    """{paint kit index: English finish name} from the installed schema and language file."""
    from inventory_item import as_dict, collect, parse
    language = as_dict(as_dict(parse(english_text)).get('lang', []))
    tokens = {k.lower(): v for k, v in language.get('Tokens', []) if isinstance(v, str)}
    titles = {}
    for key, node in collect(parse(items_game_text)).get('paint_kits', {}).items():
        if not str(key).isdigit() or not isinstance(node, list): continue
        tag = as_dict(node).get('description_tag', '')
        titles[int(key)] = tokens.get(tag.lstrip('#').lower(), tag if not tag.startswith('#') else '')
    return titles


def curate(catalog, titles):
    """The plugin's catalogue limited to popular cosmetics. Returns (catalogue, report)."""
    def norm(text): return re.sub(r'[^a-z0-9]', '', text.lower())
    report = {'guns': {}, 'missing': {}}
    weapons = []
    for weapon in catalog['weapons']:
        wanted = {norm(name) for name in POPULAR_SKINS.get(weapon['designerName'], ())}
        found = [p for p in weapon['paints'] if norm(titles.get(p['paintKit'], '')) in wanted]
        names = {norm(titles.get(p['paintKit'], '')) for p in found}
        missing = [n for n in POPULAR_SKINS.get(weapon['designerName'], ()) if norm(n) not in names]
        if missing: report['missing'][weapon['designerName']] = missing
        weapons.append(dict(weapon, paints=found or weapon['paints']))
        report['guns'][weapon['designerName']] = len(found or weapon['paints'])
    gloves = [g for g in catalog['gloves'] if norm(titles.get(g['paintKit'], '')) in {norm(n) for n in POPULAR_GLOVES}]
    names = catalog['stickerCategories']
    populated = {s['category'] for s in catalog['stickerKits']}
    keep = [name for old, name in enumerate(names) if name in POPULAR_CAPSULES and old in populated]
    index = {names.index(name): new for new, name in enumerate(keep)}
    stickers = [dict(s, category=index[s['category']]) for s in catalog['stickerKits'] if s['category'] in index]
    knives = {p['finish'] for k in catalog['knives'] for p in k['paints']}
    preferences = [p for p in catalog['knifeFinishPreferences'] if p['finish'] not in POPULAR_KNIFE_FINISHES]
    preferences = [dict(p, weight=1) for p in preferences] + [
        {'finish': f, 'weight': w} for f, w in POPULAR_KNIFE_FINISHES.items() if f in knives]
    result = dict(catalog, weapons=weapons, gloves=gloves or catalog['gloves'],
                  stickerCategories=keep or catalog['stickerCategories'],
                  stickerKits=stickers if keep else catalog['stickerKits'], knifeFinishPreferences=preferences)
    report.update(gloves=len(result['gloves']), capsules=keep, stickers=len(result['stickerKits']))
    return result, report


def _get(url, accept=None):
    request = urllib.request.Request(url, headers={'User-Agent': 'cs2-gc-bot-skins', **({'Accept': accept} if accept else {})})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def _release_zip(api_url, *words):
    release = json.loads(_get(api_url, 'application/vnd.github+json'))
    for asset in release.get('assets', []):
        name = asset['name'].lower()
        if name.endswith('.zip') and all(word in name for word in words):
            return release.get('tag_name', '?'), asset['name'], _get(asset['browser_download_url'])
    raise RuntimeError('No %s release asset matching %s' % (api_url, words))


def _extract(data, target, strip=None):
    """Extract a zip into target, refusing paths outside it. strip: archive folder whose contents go to target."""
    written = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for member in archive.infolist():
            name = member.filename.replace('\\', '/')
            if strip is not None:
                if not name.startswith(strip): continue
                name = name[len(strip):]
            if not name or name.endswith('/'): continue
            path = (target / name).resolve()
            if target.resolve() not in path.parents: raise RuntimeError('Unsafe path in archive: ' + member.filename)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(member))
            written.append(str(path.relative_to(target.resolve())).replace('\\', '/'))
    return written


def _plugin_root(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name in archive.namelist():
            if name.replace('\\', '/').endswith('BotRandomizer.dll'):
                return name.replace('\\', '/').rsplit('BotRandomizer.dll', 1)[0]
    raise RuntimeError('BotRandomizer.dll not found in the plugin release')


def _games(proxy):
    game = proxy.parent.parent
    if not (game / 'csgo' / 'gameinfo.gi').is_file(): raise RuntimeError('Run this from game\\bin\\win64')
    return game


def _mount(game, enabled, proxy=None):
    from native_tradeups import mount_gameinfo, read_text, atomic_write
    info = game / 'csgo/gameinfo.gi'
    current = read_text(info)
    mounted = mount_gameinfo(current, enabled, METAMOD_PATH, COMMENT)
    if mounted != current:
        backup = info.with_name('gameinfo.gi.cs2_gc_bot_skins_backup')
        if not backup.exists(): backup.write_text(current, encoding='utf-8', newline='')
        atomic_write(info, mounted)
    if enabled and proxy is not None:
        # Our empty write folder must stay the first Game path (a VPK there stops CS2); Metamod goes after it,
        # still ahead of csgo.
        from native_resources import ensure_first_game_path
        ensure_first_game_path(proxy)


def _core_config(game):
    configs = game / 'csgo/addons/counterstrikesharp/configs'
    core = configs / 'core.json'
    if not core.exists() and (configs / 'core.example.json').exists():
        shutil.copyfile(configs / 'core.example.json', core)
    data = json.loads(core.read_text(encoding='utf-8-sig')) if core.exists() else {}
    data['FollowCS2ServerGuidelines'] = False  # the plugin's attribute writes need this (its README)
    core.parent.mkdir(parents=True, exist_ok=True)
    core.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def recurate(proxy):
    game = _games(proxy)
    plugin = game / PLUGIN_DIR
    original = plugin / (CATALOG + '.original')
    if not original.exists(): shutil.copyfile(plugin / CATALOG, original)
    from native_finishes import Source
    english = Source(vpk=game / 'csgo/pak01_dir.vpk').read('resource/csgo_english.txt').decode('utf-8-sig')
    titles = finish_titles((proxy / 'items_game.txt').read_text(encoding='utf-8-sig'), english)
    catalog, report = curate(json.loads(original.read_text(encoding='utf-8')), titles)
    (plugin / CATALOG).write_text(json.dumps(catalog), encoding='utf-8')
    return report


# --- CS2-Bot-Improver gameplay plugins (aim, grenades, movement, AI, buying) and its skill presets -------------
IMPROVER_RELEASE = 'https://api.github.com/repos/ed0ard/CS2-Bot-Improver/releases/latest'
IMPROVER_RAW = 'https://raw.githubusercontent.com/ed0ard/CS2-Bot-Improver/main/'
PRESET_TIERS = ('Low', 'Medium', 'High')
CFG_MARKER = '// cs2_gc bot improver (owned by bot_skins.py; delete this file to stop it)'
# Their settings, run after each mode's stock config from gamemode_<mode>_server.cfg (only files we create). Their
# own package replaces the stock gamemode configs and binds keys; we do neither.
SERVER_CFGS = {'competitive': 'cs2_gc_bot_improver', 'competitive2v2': 'cs2_gc_bot_improver',
               'casual': 'cs2_gc_bot_improver', 'deathmatch': 'cs2_gc_bot_improver_ffa'}
# Lines of their config left out: key binds, and difficulty (ours follows the local Premier rating).
SKIPPED = re.compile(r'^\s*(bind|bot_difficulty|custom_bot_difficulty|sv_auto_adjust_bot_difficulty|'
                     r'bot_autodifficulty_threshold_\w+)\b', re.I)


def bot_config(text):
    """Their bot config without key binds or difficulty settings."""
    return CFG_MARKER + '\n' + ''.join(line for line in text.splitlines(keepends=True) if not SKIPPED.match(line))


def _bundle_prefix(names):
    """The archive folder that holds addons/ (their zip may have a top folder), or None."""
    for name in names:
        name = name.replace('\\', '/')
        if '/addons/counterstrikesharp/' in '/' + name:
            return ('/' + name).split('/addons/counterstrikesharp/', 1)[0].lstrip('/')
    return None


def _install_improver(proxy, game, data, owned=(), resource_reader=None):
    """Copy their addons (plugins, plugin data, Metamod plugins) and write configs; returns the files written."""
    csgo = game / 'csgo'
    resource_reader = resource_reader or (lambda name: _get(IMPROVER_RAW + name))
    written = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = [n.replace('\\', '/') for n in archive.namelist()]
        prefix = _bundle_prefix(names)
        if prefix is None: raise RuntimeError('Bot Improver release has no addons folder')
        base = (prefix + '/') if prefix else ''
        tops = {n[len(base):].split('/')[1] for n in names if n.startswith(base + 'addons/') and n.count('/') > len(base.split('/'))}
        foreign = [t for t in tops if t not in owned and (csgo / 'addons' / t).exists()]
        if foreign: raise RuntimeError('Not overwriting your existing addons: ' + ', '.join(sorted(foreign)))
        for name in names:
            if not name.startswith(base + 'addons/') or name.endswith('/'): continue
            relative = name[len(base):]
            if '/plugins/disabled/' in relative: continue
            path = (csgo / relative).resolve()
            if csgo.resolve() not in path.parents: raise RuntimeError('Unsafe path in archive: ' + name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.read(name))
            written.append(relative)
        def member(*candidates):
            for candidate in candidates:
                if base + candidate in names: return archive.read(base + candidate).decode('utf-8-sig')
            return None
        normal = member('cfg/my_bot_normal_config_rules_unchanged.cfg', 'cfg/my_bot_normal_config.cfg')
        ffa = member('cfg/my_bot_ffa_config_rules_unchanged.cfg', 'cfg/my_bot_ffa_config.cfg')
    normal = normal or resource_reader('cfg/my_bot_normal_config_rules_unchanged.cfg').decode('utf-8-sig')
    ffa = ffa or resource_reader('cfg/my_bot_ffa_config_rules_unchanged.cfg').decode('utf-8-sig')
    cfg = csgo / 'cfg'
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / 'cs2_gc_bot_improver.cfg').write_text(bot_config(normal), encoding='utf-8')
    (cfg / 'cs2_gc_bot_improver_ffa.cfg').write_text(bot_config(ffa), encoding='utf-8')
    for mode, name in SERVER_CFGS.items():
        path = cfg / ('gamemode_%s_server.cfg' % mode)
        if path.exists() and not path.read_text(encoding='utf-8', errors='replace').startswith(CFG_MARKER):
            print('Kept your own %s; add "exec %s" to it for the bot plugins in that mode.' % (path.name, name))
            continue
        path.write_text('%s\nexec %s\nexec cs2_gc_premier_bots\n' % (CFG_MARKER, name), encoding='utf-8')
    # Skill presets (their botprofile.db per tier); native_bot_names picks one by the local Premier rating.
    for tier in PRESET_TIERS:
        target = proxy / 'cs2_gc_bot_presets' / tier / 'botprofile.db'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(resource_reader('overrides/%s/botprofile.db' % tier))
    return written


def _remove_improver(proxy, game):
    cfg = game / 'csgo/cfg'
    for mode in SERVER_CFGS:
        path = cfg / ('gamemode_%s_server.cfg' % mode)
        if path.is_file() and path.read_text(encoding='utf-8', errors='replace').startswith(CFG_MARKER): path.unlink()
    for name in ('cs2_gc_bot_improver.cfg', 'cs2_gc_bot_improver_ffa.cfg'):
        if (cfg / name).is_file(): (cfg / name).unlink()
    shutil.rmtree(proxy / 'cs2_gc_bot_presets', ignore_errors=True)


def install(proxy):
    game = _games(proxy)
    csgo = game / 'csgo'
    manifest = proxy / MANIFEST
    previous = json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else {}
    if not previous and any((csgo / 'addons' / d).exists() for d in ('metamod', 'counterstrikesharp')):
        raise RuntimeError('Metamod or CounterStrikeSharp is already installed by something else; not touching it')
    installed = list(previous.get('files', []))
    print('Downloading CS2-Bot-Improver (bot aim, grenades, movement, AI, buying, skins) ...', flush=True)
    release = json.loads(_get(IMPROVER_RELEASE, 'application/vnd.github+json'))
    assets = [a for a in release.get('assets', []) if a['name'].lower().endswith('.zip')
              and 'cs2botimprover' in a['name'].lower() and 'linux' not in a['name'].lower()]
    assets.sort(key=lambda a: 'rules_unchanged' not in a['name'].lower())
    if not assets: raise RuntimeError('No Windows CS2-Bot-Improver release found')
    improver = _get(assets[0]['browser_download_url'])
    with zipfile.ZipFile(io.BytesIO(improver)) as archive:
        names = [n.replace('\\', '/') for n in archive.namelist()]
    bundled = any('addons/metamod/bin/' in n for n in names) and any('addons/counterstrikesharp/api/' in n for n in names)
    name = tag = 'bundled with Bot Improver'
    if not bundled:  # their zip carries only plugins: get the frameworks from their official pages
        print('Downloading Metamod:Source 2.0 ...', flush=True)
        name = _get(METAMOD_LATEST).decode('ascii').strip()
        if not re.fullmatch(r'mmsource-[\w.\-]+-windows\.zip', name): raise RuntimeError('Unexpected Metamod name ' + name)
        installed += _extract(_get(METAMOD_DROP + name), csgo)
        print('Downloading CounterStrikeSharp (with runtime) ...', flush=True)
        tag, _, data = _release_zip(CSS_RELEASE, 'with-runtime', 'windows')
        installed += _extract(data, csgo)
    owned = {f.split('/')[1] for f in installed if f.startswith('addons/') and f.count('/') >= 2} | {'metamod', 'counterstrikesharp'}
    installed += _install_improver(proxy, game, improver, owned)
    if not (game / PLUGIN_DIR / 'BotRandomizer.dll').is_file():
        print('Downloading BotRandomizer ...', flush=True)
        _, _, data = _release_zip(RANDOMIZER_RELEASE)
        installed += ['addons/counterstrikesharp/plugins/BotRandomizer/' + p
                      for p in _extract(data, game / PLUGIN_DIR, _plugin_root(data))]
    _core_config(game)
    _mount(game, True, proxy)
    manifest.write_text(json.dumps({'metamod': name, 'counterstrikesharp': tag,
                                    'botimprover': [release.get('tag_name'), assets[0]['name']],
                                    'files': sorted(set(installed))}, indent=1) + '\n', encoding='utf-8')
    report = recurate(proxy)
    (proxy / 'cs2_gc_bot_plugins_disabled').unlink(missing_ok=True)
    print('Installed Bot Improver %s (Metamod/CounterStrikeSharp: %s).' % (release.get('tag_name'), name))
    print('Popular loadouts: %d gloves, %d sticker capsules (%d stickers).' % (report['gloves'], len(report['capsules']), report['stickers']))
    if report['missing']: print('Finish names not in this CS2 build (skipped): ' + json.dumps(report['missing']))
    print('Bot skill follows your local Premier rating: Low preset below 10,000, Medium to 29,999, High from 30,000.')
    print('Start CS2 with cs2_gc_debug.exe (it uses -insecure) and play a bot match.')


def uninstall(proxy):
    game = _games(proxy)
    (proxy / 'cs2_gc_bot_plugins_disabled').touch()
    _mount(game, False)
    _remove_improver(proxy, game)
    manifest = proxy / MANIFEST
    if manifest.exists():
        files = json.loads(manifest.read_text(encoding='utf-8')).get('files', [])
        tops = {'/'.join(f.split('/')[:2]) for f in files if f.startswith('addons/') and f.count('/') >= 2}
        for relative in files:
            path = game / 'csgo' / relative
            if path.is_file(): path.unlink()
        for folder in sorted(tops | {'addons/counterstrikesharp', 'addons/metamod'}):
            if (game / 'csgo' / folder).is_dir(): shutil.rmtree(game / 'csgo' / folder, ignore_errors=True)
        manifest.unlink()
    print('Bot plugins removed (Metamod unmounted, presets and configs removed; your other addons untouched).')
    print('Start CS2 with cs2_gc_debug.exe once so the normal bot profile comes back.')


def status(proxy):
    game = _games(proxy)
    text = (game / 'csgo/gameinfo.gi').read_text(encoding='utf-8', errors='replace')
    print('Metamod mounted: %s' % (METAMOD_PATH in text))
    print('Plugin present: %s' % (game / PLUGIN_DIR / 'BotRandomizer.dll').is_file())
    print('Skill presets: %s' % (proxy / 'cs2_gc_bot_presets').is_dir())
    if (proxy / MANIFEST).exists(): print((proxy / MANIFEST).read_text(encoding='utf-8')[:400])


if __name__ == '__main__':
    proxy = Path(__file__).resolve().parent
    action = (sys.argv[1:] or ['status'])[0]
    {'install': install, 'uninstall': uninstall, 'status': status,
     'recurate': lambda p: print(json.dumps(recurate(p), indent=1))}[action](proxy)

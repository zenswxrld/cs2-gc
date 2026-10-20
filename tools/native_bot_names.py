"""Give local bots random player-style names (like OfflineCS) through a dedicated botprofile.db override.

Only the name on each bot profile line ("Template[+Template] Name") is changed; skills, weapons and
templates stay exactly as the installed file defines them. The override lives in its own cs2_gc_bots
folder like the other native overrides and is removed again with bot_random_names = 0.
"""
from pathlib import Path
import random
import re

FOLDER = 'cs2_gc_bots'
COMMENT = 'cs2_gc random bot names'
OWNER = 'cs2-gc-bot-names-v1'
ASSET = 'botprofile.db'
SEED_FILE = 'cs2_gc_bot_names_seed.txt'

HANDLES = '''
kyro zenix frostbyte vortexx n0va slyde ghostie kaiz3n blitzer remy jinx0 orbit drift voidy tempo
sh4dow pyro kenji maverik lux3 hollow skye razr nimbus quill echo7 vexa colt ronin tundra
zeph flick spade raven juno dusty bolt cypher m1lo trix nyx atlas ember wraith kobi halo
saber fizz rook vapor mako jett onyx slick kairo bash nomad lynx crisp glint dex ace
boomer zappy toxic panda mochi tofu biscuit noodle waffle pickles muffin taco nacho sushi
yuki hiro sora ryu kenta daiki akira bjorn sven lars olek dima vlad tomasz kuba matti
luca enzo matteo diego pablo rafa nico theo felix hugo otto karl emil anton ivan
lowkey nofear deadeye oneTap headhuntr flashbang smokey molly clutchy aimbotnt eco_king
wallbang spraygod pistolpete awper entryfrag lurker igl_dad baiter ninjadefuse thrifty
xXslayerXx hypebeast sk8r gr1nd tilted calmdown gg_ez noscope quickscope eagle_eye
'''.split()


def _names(count, seed):
    rng = random.Random(seed)
    names = HANDLES[:]
    rng.shuffle(names)
    used, result = set(), []
    for name in names:
        if len(result) == count: break
        used.add(name.lower()); result.append(name)
    while len(result) < count:
        name = rng.choice(HANDLES) + str(rng.randint(2, 999))
        if name.lower() not in used:
            used.add(name.lower()); result.append(name)
    return result


PROFILE = re.compile(r'^([A-Za-z0-9_]+(?:\+[A-Za-z0-9_]+)*)([ \t]+)([^\s/]+)([ \t]*(?://.*)?)$')


def patch(text, seed):
    lines = text.splitlines(keepends=True)
    headers, depth = [], False
    for index, raw in enumerate(lines):
        line = raw.rstrip('\r\n')
        stripped = line.strip()
        if not stripped or stripped.startswith('//'): continue
        if depth:
            if stripped == 'End': depth = False
            elif line[0] not in ' \t': raise ValueError('botprofile.db layout changed: missing End before ' + stripped[:40])
            continue
        if line[0] in ' \t': raise ValueError('botprofile.db layout changed: attribute outside a block')
        if stripped == 'Default' or stripped.startswith('Template '):
            depth = True; continue
        match = PROFILE.match(line)
        if not match: raise ValueError('botprofile.db layout changed: ' + stripped[:40])
        headers.append((index, match)); depth = True
    if depth: raise ValueError('botprofile.db layout changed: missing End')
    if len(headers) < 10: raise ValueError('botprofile.db has too few bot profiles to rename')
    originals = [match.group(3) for _, match in headers]
    if len({name.lower() for name in originals}) != len(originals):
        raise ValueError('botprofile.db has duplicate bot names')
    for (index, match), name in zip(headers, _names(len(headers), seed)):
        ending = lines[index][len(lines[index].rstrip('\r\n')):]
        lines[index] = match.group(1) + match.group(2) + name + match.group(4) + ending
    return ''.join(lines)


def _seed(proxy_directory, reshuffle):
    path = Path(proxy_directory) / SEED_FILE
    if not reshuffle and path.is_file():
        try: return int(path.read_text(encoding='utf-8').strip())
        except ValueError: pass
    seed = random.SystemRandom().randrange(1, 2 ** 31)
    path.write_text(str(seed) + '\n', encoding='utf-8')
    return seed


def prepare(proxy_directory, config, reshuffle=False):
    """reshuffle: new names (the launcher, before CS2 starts); the helper keeps the launcher's names."""
    from native_resources import install_override
    enabled = bool(config.get('bot_random_names', 1))
    seed = _seed(proxy_directory, reshuffle) if enabled else 0
    return install_override(proxy_directory, enabled=enabled, folder=FOLDER, comment=COMMENT, owner=OWNER,
                            asset=ASSET, patch=lambda source: patch(source, seed))

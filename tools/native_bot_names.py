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
Kaizen_ zyrex frosty jxnny Snoopz w1nterz dxrk_ Vexoo fl1ckz Kiwi_ trxpz zeno kxsh
NightOwl_ sleepy_k shxdow xLuna Rexy2k toxicpanda Mochi_ blxze Ravenzz zKai noodlez
eth4n_ tylerr07 jakey_ mattyB Liamxo noahh_ Oskarr kubaz Mikk0 d1ma_ vlad1k Artemka
Lukas_ jonas_cs Felixx n1ko_ theoo_ maxi_ Bruno Diegoo rafitaa Tomi_ Sebaa santi_
ColdCoffee GhostFace_ silentstep DeadAim_ HeadHunter7 lowkeygod notaim clutchm0de
pistolprince ecoround_ forcebuy flashme_ smokecrime tapz onetap_ sprayNpray awpaholic
entryguy lurkmaster rushB_ ctside_ midcontrol bananaking_ ramp_ apartment_ connector
drop_ sitecheck tradeplease juiced_ peeky eco_merchant halfbuy savegod_ nadeking
hazy_ sunny bluee_ redd1t_ grayfox_ jadee lime violetz cherryy_ peachy_ minty_
Zyn_ Ari_ Kye_ Juno Nova_ Ezra_ Rhys_ Milo Arlo_ Ivo_ Kenzo_ Taro_ Yuki Hiro_ Ren_
xyz_ qwerty_ asdf zxc 1337_ n00b l0l_ gg_wp ez4me_ ggwp noscope_ lag_ fps 144hz_
cs2enjoyer goldnova_ silverlife faceitlvl3 premierpls dmonly retakeking aimlabsrat
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
        name = rng.choice(HANDLES).rstrip('_-') + rng.choice(('', '_', '.')) + str(rng.randint(1, 99))
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
    # CS2's own file repeats some names across difficulty tiers; every header gets a fresh unique name anyway.
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


def patch_labels(text):
    """Keep the full installed localization and its positional name placeholders."""
    for key, replacement in (('SFUI_bot_decorated_name', '%s1'),
                             ('SFUI_bot_decorated_name_controlled', '%s1 (%s2)')):
        pattern = re.compile(r'("' + key + r'"\s*)"([^"\r\n]*)"', re.I)
        matches = list(pattern.finditer(text))
        if len(matches) != 1 or '%s1' not in matches[0][2]:
            raise ValueError('Changed bot localization format: ' + key)
        text = pattern.sub(lambda match: match[1] + '"' + replacement + '"', text)
    return text


def prepare(proxy_directory, config, reshuffle=False):
    """reshuffle: new names (the launcher, before CS2 starts); the helper keeps the launcher's names."""
    from native_resources import install_override
    enabled = bool(config.get('bot_random_names', 1))
    seed = _seed(proxy_directory, reshuffle) if enabled else 0
    names = install_override(proxy_directory, enabled=enabled, folder=FOLDER, comment=COMMENT, owner=OWNER,
                             asset=ASSET, patch=lambda source: patch(source, seed))
    labels = install_override(proxy_directory, enabled=bool(config.get('bot_hide_tag', 1)),
        folder='cs2_gc_bot_labels', comment='cs2_gc native bot labels', owner='cs2-gc-bot-labels-v1',
        asset='resource/csgo_english.txt', patch=patch_labels)
    return names + '; bot labels: ' + labels

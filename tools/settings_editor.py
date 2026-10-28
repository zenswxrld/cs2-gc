"""Open the local reward settings without replacing existing preferences."""
from pathlib import Path
import re,subprocess,sys
from gameplay_config import DEFAULTS

REWARD_KEYS=('stars_enabled','kill_stars','headshot_stars','mvp_stars','plant_stars','defuse_stars','match_complete_stars',
             'profile_xp_percent','armory_xp_per_star','kill_xp','headshot_xp','mvp_xp','plant_xp','defuse_xp','match_complete_xp')

REFERENCE='cs2_gc_gameplay_reference.cfg'  # the annotated examples/cs2_gc_gameplay.cfg, shipped in the ZIP

def create_settings(directory):
    """First launch: write cs2_gc_gameplay.cfg listing every setting, all commented out, so the settings can be found
    and edited without changing anything until a line is uncommented. An existing file is never touched."""
    directory=Path(directory);path=directory/'cs2_gc_gameplay.cfg';reference=directory/REFERENCE
    if path.exists() or not reference.is_file():return path
    lines=['# CS2 GC settings. Every setting is listed with its default value, switched off by the "#" in front.',
           '# To change one: delete the "# " before it, edit the number, save, then restart the launcher.',
           '# Settings left with "#" keep their default.','']
    for line in reference.read_text(encoding='utf-8-sig').splitlines():
        if line.startswith('# Copy beside'):continue
        lines.append('# '+line if re.match(r'\s*[a-z_0-9]+\s*=',line) else line)
    with path.open('x',encoding='utf-8',newline='\r\n') as output:output.write('\n'.join(lines)+'\n')
    return path

def keep_custom_collections(directory):
    """custom_cases became 0 by default (user, 29 Oct: "lets make custom collections OFF by default"). An install
    that has already built the collections keeps them on, so custom skins it owns keep rendering: custom_cases = 1
    is written unless the file already sets it."""
    directory=Path(directory);path=directory/'cs2_gc_gameplay.cfg'
    if not (directory/'cs2_gc_gun_collections.json').is_file():return False
    text=path.read_text(encoding='utf-8-sig') if path.exists() else ''
    if re.search(r'(?m)^\s*custom_cases\s*=',text):return False
    with path.open('a',encoding='utf-8',newline='\r\n') as output:
        output.write(('' if not text or text.endswith('\n') else '\n')+
                     '\n# Kept on: this install already had the custom collections (skins you own need them).\ncustom_cases = 1\n')
    return True

def ensure(directory):
    path=Path(directory)/'cs2_gc_gameplay.cfg'
    if not path.exists():
        with path.open('x',encoding='utf-8') as output:
            output.write('# Local rewards. Restart CS2 and its helper after changes.\n# Headshot stars are an EXTRA bonus on top of kill stars.\n# Pass-derived stars are additional; a lower armory_xp_per_star earns them faster.\n')
            for key in REWARD_KEYS:output.write('%s = %d\n'%(key,DEFAULTS[key]))
    else:
        original=path.read_text(encoding='utf-8-sig')
        existing=set(re.findall(r'(?m)^\s*([a-z_]+)\s*=',original))
        missing=[key for key in REWARD_KEYS if key not in existing]
        if missing:
            with path.open('a',encoding='utf-8') as output:
                output.write('\n# Additional reward controls (restart CS2 after editing).\n# Headshot stars are an extra kill bonus.\n')
                for key in missing:output.write('%s = %d\n'%(key,DEFAULTS[key]))
    return path

if __name__=='__main__':
    here=Path(__file__).resolve().parent
    path=create_settings(here) if '--all' in sys.argv[1:] else here/'cs2_gc_gameplay.cfg'
    if '--all' not in sys.argv[1:] or not path.exists():path=ensure(here)
    subprocess.run(['notepad.exe',str(path)],check=True)

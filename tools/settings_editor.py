"""Open the local reward settings without replacing existing preferences."""
from pathlib import Path
import re,subprocess
from gameplay_config import DEFAULTS

REWARD_KEYS=('stars_enabled','kill_stars','headshot_stars','mvp_stars','plant_stars','defuse_stars','match_complete_stars',
             'profile_xp_percent','armory_xp_per_star','kill_xp','headshot_xp','mvp_xp','plant_xp','defuse_xp','match_complete_xp')

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
    path=ensure(Path(__file__).resolve().parent)
    subprocess.run(['notepad.exe',str(path)],check=True)

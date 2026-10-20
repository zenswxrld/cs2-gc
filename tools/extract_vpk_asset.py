"""Copy named assets out of the installed csgo/pak01_dir.vpk for inspection. Read-only: the game files are not modified.

Usage (from game\\bin\\win64):  python extract_vpk_asset.py panorama/scripts/crafting.vts_c panorama/scripts/scoreboard.vts_c
Writes each asset into a cs2_gc_extracted folder next to this script.
"""
from pathlib import Path
import sys
from native_resources import vpk_file


def main(names):
    game = Path(__file__).resolve().parent.parent.parent
    directory = game / 'csgo' / 'pak01_dir.vpk'
    out = Path(__file__).resolve().parent / 'cs2_gc_extracted'
    if not directory.is_file():
        print('Installed csgo/pak01_dir.vpk not found at', directory); return 1
    status = 0
    for name in names:
        try:
            data, actual = vpk_file(directory, name, aliases=True, with_path=True)
        except ValueError as error:
            print(name, '->', error); status = 1; continue
        target = out / actual
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        print('wrote', target, len(data), 'bytes')
    return status


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:] or ['panorama/scripts/crafting.vts_c', 'panorama/scripts/scoreboard.vts_c']))

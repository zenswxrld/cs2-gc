"""Package project binaries and helpers in Actions, without game or profile data."""
import hashlib
import json
import os
from pathlib import Path
import zipfile


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / 'dist'
    output.mkdir(exist_ok=True)
    # Validate every forwarded export against the inspected ABI metadata before packaging.
    from make_proxy_def import export_names, OVERRIDDEN
    proxy = root / 'build' / 'Release' / 'steam_api64.dll'
    names = export_names(proxy.read_bytes(), 'steam_api64_real')
    expected = [line.strip().split('=')[0].strip() for line in
                (root / 'data' / 'steam_api64_exports.def').read_text().splitlines()
                if line.startswith('    ')]
    if sorted(names) != sorted(expected) or not set(OVERRIDDEN).issubset(names):
        raise ValueError('Proxy exports do not match the inspected original library')
    manifest = {'commit': os.environ.get('GITHUB_SHA', ''), 'files': {}}
    files = [(p, p.name) for p in sorted((root / 'tools').glob('*.py'))]
    for name in ('steam_api64.dll', 'cs2_gc_debug.exe', 'cs2_gc_texture_decode.exe'):
        files.append((root / 'build' / 'Release' / name, name))
    files.append((root / 'data' / 'gold_pools.txt', 'gold_pools.txt'))
    with zipfile.ZipFile(output / 'CS2GC-Care-Package-Test.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for path, name in files:
            data = path.read_bytes()
            archive.writestr(name, data)
            manifest['files'][name] = hashlib.sha256(data).hexdigest()
        archive.writestr('BCDEC-LICENSE.txt',(root/'third_party/bcdec.h').read_text(encoding='utf-8').split('/* LICENSE:')[1])
        archive.writestr('CARE-PACKAGE-README.txt',
            'Care-package claim test update\n\n'
            'Close CS2 and its helper. Back up the current steam_api64.dll, launcher,\n'
            'and matching helper scripts. Extract this update beside cs2_gc_debug.exe\n'
            'in game/bin/win64, replacing those project files.\n'
            'Keep steam_api64_real.dll, inventory, settings, replay files and finish-ID maps.\n'
            'Launch through the NEW cs2_gc_debug.exe so the local session code is set.\n\n'
            'Choose any three of four pending rewards, then claim. The three selected\n'
            'items should enter inventory; the fourth is discarded. Restart and check\n'
            'that claimed items remain and cannot be claimed twice.\n'
            'If the claim times out, send cs2_gc_log.txt and cs2_gc_rewards.log diagnostics.\n'
            'Actions verifies offline behavior; live-client confirmation is still required.\n')
        archive.writestr('CARE-PACKAGE-SHA256.json',json.dumps(manifest,indent=2))
    print(output / 'CS2GC-Care-Package-Test.zip')


if __name__ == '__main__':
    main()

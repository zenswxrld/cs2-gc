"""Prepare the complete ZIP in place. Never ship or reset a player's saved state."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import struct
import sys
import tempfile
import traceback
from make_proxy_def import export_names


class SetupError(ValueError):
    pass


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024*1024),b''):
            result.update(block)
    return result.hexdigest()


def atomic_bytes(path, data):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def verify_build(root, supported):
    for name, expected in supported['files'].items():
        path = root / name
        if not path.is_file():
            raise SetupError('Incomplete CS2 installation: '+name+'. Finish BOTH depot downloads before launching.')
        if digest(path) != expected:
            raise SetupError('Unsupported CS2 files: '+name+'. This ZIP supports Steam build '+
                             supported['steam_build']+'. See README-DOWNGRADE.md in the game folder.')


def verify_package(root, manifest):
    for name, expected in manifest['files'].items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise SetupError('Invalid ZIP manifest path')
        path = root / relative
        if not path.is_file() or digest(path) != expected:
            raise SetupError('Missing or changed mod file: '+name+'. Extract the COMPLETE ZIP again, replacing its mod files.')


def original_exports(path):
    try:
        return set(export_names(Path(path).read_bytes()))
    except (ValueError,OSError,struct.error):
        return None


def install_proxy(directory):
    payload = directory / 'cs2_gc_payload' / 'steam_api64.dll'
    original = directory / 'steam_api64_real.dll'
    active = directory / 'steam_api64.dll'
    try:
        expected = set(export_names(payload.read_bytes(),'steam_api64_real'))
    except (OSError,ValueError) as error:
        raise SetupError('The ZIP proxy DLL is missing or invalid. Re-extract the complete ZIP.') from error
    if original.exists():
        if original_exports(original) != expected:
            raise SetupError('steam_api64_real.dll is not the matching original Steam library. Restore it from the supported Windows depot.')
    else:
        if not active.is_file() or original_exports(active) != expected:
            raise SetupError('The original steam_api64.dll is missing. Restore it from the Windows depot; the ZIP keeps the mod DLL in cs2_gc_payload.')
        # Exclusive creation: never replace an original saved by an earlier setup.
        with original.open('xb') as output:
            output.write(active.read_bytes())
            output.flush()
            os.fsync(output.fileno())
    if not active.exists() or digest(active) != digest(payload):
        if active.exists():
            try:
                if set(export_names(active.read_bytes(),'steam_api64_real')) != expected:
                    raise ValueError('Unexpected exports')
            except ValueError as error:
                raise SetupError('Unrecognised steam_api64.dll. Back it up and restore the supported original library before launching.') from error
        atomic_bytes(active,payload.read_bytes())


def ensure_schema(directory, vpk_reader=None):
    import native_resources
    if vpk_reader is None:
        # The schema is larger than the Panorama reader's default 8 MiB limit.
        old_limit = native_resources.MAX_ASSET
        try:
            native_resources.MAX_ASSET = 32*1024*1024
            data = native_resources.vpk_file(directory.parent.parent/'csgo/pak01_dir.vpk',
                                             'scripts/items/items_game.txt')
        finally:
            native_resources.MAX_ASSET = old_limit
    else:
        data = vpk_reader()
    if not 0 < len(data) <= 32*1024*1024 or b'items_game' not in data[:256]:
        raise SetupError('The installed VPK did not contain a valid items_game schema.')
    path = directory/'items_game.txt'
    if not path.is_file() or path.read_bytes() != data:
        if path.is_file():
            backup = directory/'items_game.txt.before-launcher'
            if not backup.exists():
                with backup.open('xb') as output:
                    output.write(path.read_bytes())
        atomic_bytes(path,data)


def ensure_profile(directory, client_version, runner=subprocess.run):
    replay = directory/'cs2_gc_replay'
    required = [replay/'4004.bin',replay/'2501.bin']
    if all(path.is_file() and 0 < path.stat().st_size <= 1024*1024 for path in required):
        return False
    print('First launch: requesting your own profile and Store data from Steam.\n'
          'Keep Steam open and signed in. No purchases or inventory actions are sent.',flush=True)
    helper = directory/'cs2_gc_profile.exe'
    log_path = directory/'cs2_gc_profile.log'
    with log_path.open('w',encoding='utf-8') as output:
        result = runner([str(helper),str(directory),str(client_version)],cwd=directory,
                        stdout=output,stderr=subprocess.STDOUT,timeout=105,
                        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode or not all(p.is_file() and p.stat().st_size for p in required):
        raise SetupError('Steam profile initialization failed. Make sure Steam is online and signed into the account that owns CS2. See cs2_gc_profile.log beside the mod DLL.')
    return True


def run(directory):
    directory = Path(directory).resolve()
    root = directory.parents[2]
    manifest_path = directory/'cs2_gc_release.json'
    if not manifest_path.is_file():
        raise SetupError('Missing cs2_gc_release.json. Extract the complete release ZIP over the CS2 root folder.')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    print('CS2 GC: checking the game version and complete ZIP...',flush=True)
    verify_build(root,manifest['supported_build'])
    verify_package(root,manifest)
    print('Preserving the original Steam library and installing the local GC...',flush=True)
    install_proxy(directory)
    app_id = directory/'steam_appid.txt'
    if not app_id.exists() or app_id.read_text(encoding='ascii').strip() != '730':
        atomic_bytes(app_id,b'730\n')
    ensure_schema(directory)
    import bundled_bots
    bundled_bots.ensure(directory)
    ensure_profile(directory,manifest['supported_build']['client_version'])
    print('Preparing native resources. The first launch can take several minutes.\n'
          'Progress and diagnostics: '+str(directory/'cs2_gc_prepare.log'),flush=True)
    import prepare_native
    with (directory/'cs2_gc_prepare.log').open('w',encoding='utf-8',buffering=1) as output:
        with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):
            prepare_native.prepare(directory)
    print('Preparation complete. Starting this copy of CS2...',flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proxy-dir',type=Path,required=True)
    args = parser.parse_args()
    failure = args.proxy_dir/'cs2_gc_launch_error.txt'
    try:
        failure.unlink(missing_ok=True)
        run(args.proxy_dir)
        failure.unlink(missing_ok=True)
        return 0
    except Exception as error:
        message = str(error)
        if isinstance(error,subprocess.TimeoutExpired):
            message = 'Steam profile initialization timed out. Open Steam, sign in, and retry.'
        failure.write_text(message+'\n',encoding='utf-8')
        with (args.proxy_dir/'cs2_gc_launcher.log').open('a',encoding='utf-8') as output:
            traceback.print_exc(file=output)
        print('CS2 GC could not start: '+message,flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

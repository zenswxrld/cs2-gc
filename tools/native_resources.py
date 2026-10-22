"""Read installed VPK assets and rewrite plaintext Panorama script DATA blocks.

Format references: ValveResourceFormat/ValvePak Package.Read.cs and
ValveResourceFormat Resource.cs / ResourceTypes/Panorama.cs. No game assets ship
with this helper; original archives are opened read-only. Unknown formats reject.
"""
from pathlib import Path
import struct
import hashlib
import json
from native_tradeups import atomic_write, read_text, mount_gameinfo
import zlib

MAX_ASSET = 8 * 1024 * 1024


def vpk_file(directory, wanted, *, aliases=False, with_path=False):
    directory = Path(directory)
    with directory.open('rb') as source:
        header = source.read(12)
        if len(header) != 12: raise ValueError('Truncated VPK header')
        magic, version, tree_size = struct.unpack('<III', header)
        if magic != 0x55aa1234 or version not in (1, 2): raise ValueError('Unsupported VPK header')
        header_size = 12 if version == 1 else 28
        if not 0 < tree_size <= 64 * 1024 * 1024: raise ValueError('Invalid VPK directory size')
        source.seek(header_size)
        tree = source.read(tree_size)
        if len(tree) != tree_size: raise ValueError('Truncated VPK directory')
        position = 0

        def string():
            nonlocal position
            end = tree.find(b'\0', position)
            if end < 0: raise ValueError('Truncated VPK path')
            value = tree[position:end].decode('utf-8'); position = end + 1
            return value

        found = None
        nearby = []
        while True:
            extension = string()
            if not extension: break
            while True:
                folder = string()
                if not folder: break
                while True:
                    name = string()
                    if not name: break
                    if position + 18 > len(tree): raise ValueError('Truncated VPK entry')
                    crc, preload, archive, offset, length, end = struct.unpack_from('<IHHIIH', tree, position)
                    position += 18
                    if end != 0xffff or position + preload > len(tree): raise ValueError('Invalid VPK entry')
                    small = tree[position:position + preload]; position += preload
                    path = ('' if folder == ' ' else folder + '/') + name + ('' if extension == ' ' else '.' + extension)
                    path = path.replace('\\', '/')
                    if name.lower() == Path(wanted).stem.lower(): nearby.append(path)
                    match = path.lower() == wanted.lower()
                    alias = (aliases and path.rsplit('.', 1)[0].lower() == wanted.rsplit('.', 1)[0].lower()
                             and extension.lower() in ('js', 'vjs', 'vjs_c', 'js_c', 'vts_c'))
                    if match or alias:
                        if found is not None: raise ValueError('Ambiguous VPK script assets: ' + found[5] + ', ' + path)
                        if length + preload > MAX_ASSET: raise ValueError('VPK asset too large')
                        found = (crc, small, archive, offset, length, path)
        if found is None: raise ValueError('Installed VPK asset not found: ' + wanted + '; matching basenames: ' + ', '.join(nearby[:8]))
        crc, small, archive, offset, length, actual = found
        if archive == 0x7fff:
            source.seek(header_size + tree_size + offset)
            result = small + source.read(length)
        else:
            if not directory.name.endswith('_dir.vpk'): raise ValueError('Expected a directory VPK filename')
            chunk = directory.with_name(directory.name[:-8] + f'_{archive:03d}.vpk')
            with chunk.open('rb') as data:
                data.seek(offset); result = small + data.read(length)
        if len(result) != len(small) + length or zlib.crc32(result) != crc:
            raise ValueError('Installed VPK asset checksum/length mismatch')
        return (result, actual) if with_path else result


def script_blocks(resource):
    if len(resource) < 16 or len(resource) > MAX_ASSET: raise ValueError('Invalid Panorama resource size')
    size, header, version, offset, count = struct.unpack_from('<IHHII', resource)
    # The installed game's compiled scripts (.vts_c) are header 12 / version 2: a RED2 block, the plaintext
    # DATA block and a STAT block. Version 4 is accepted too (what the older notes assumed).
    if size != len(resource) or header != 12 or version not in (2, 4) or not 1 <= count <= 32:
        raise ValueError('Unsupported Panorama script resource; expected plaintext header12/version2 or 4')
    table = 8 + offset
    if table < 16 or table + 12 * count > size: raise ValueError('Invalid Panorama block table')
    blocks, spans = [], []
    for i in range(count):
        entry = table + i * 12
        kind, relative, length = struct.unpack_from('<4sII', resource, entry)
        start = entry + 4 + relative
        if start < table + count * 12 or start + length > size: raise ValueError('Invalid Panorama block span')
        if any(start < end and start + length > other for other, end in spans):
            raise ValueError('Overlapping Panorama blocks')
        spans.append((start, start + length)); blocks.append((kind, resource[start:start + length]))
    if sum(kind == b'DATA' for kind, _ in blocks) != 1: raise ValueError('Ambiguous Panorama DATA block')
    return blocks


def rewrite_script(resource, patch):
    blocks = script_blocks(resource)
    version = struct.unpack_from('<H', resource, 6)[0]
    original = next(data for kind, data in blocks if kind == b'DATA')
    source = original.rstrip(b'\0').decode('utf-8')
    changed = patch(source).encode('utf-8') + (b'\0' if original.endswith(b'\0') else b'')
    # Debug source maps refer to the original line/column positions. Preserve other metadata.
    blocks = [(kind, changed if kind == b'DATA' else data) for kind, data in blocks if kind != b'SrMa']
    result = bytearray(struct.pack('<IHHII', 0, 12, version, 8, len(blocks)) + b'\0' * (len(blocks) * 12))
    for i, (kind, data) in enumerate(blocks):
        result.extend(b'\0' * (-len(result) % 16))
        entry = 16 + i * 12
        struct.pack_into('<4sII', result, entry, kind, len(result) - entry - 4, len(data))
        result.extend(data)
    struct.pack_into('<I', result, 0, len(result))
    if len(result) > MAX_ASSET: raise ValueError('Patched Panorama resource too large')
    script_blocks(result)
    return bytes(result)


def patch_installed_script(resource, actual_path, patch):
    # CS2 can store ordinary Panorama .js assets rather than a compiled .vjs_c.
    # Match the installed filename and representation; never wrap raw JS as a resource.
    if actual_path.endswith(('.js', '.vjs', '.db', '.txt')):
        encoding = 'utf-16' if resource.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8'
        return patch(resource.decode(encoding)).encode(encoding)
    return rewrite_script(resource, patch)


def install_override(proxy_directory, *, enabled, folder, comment, owner, asset, patch, source=None):
    """source: (bytes, path) to patch instead of the installed VPK asset (e.g. a bot difficulty preset)."""
    proxy = Path(proxy_directory).resolve()
    game = proxy.parent.parent
    info = game / 'csgo/gameinfo.gi'
    mod = game / folder
    manifest_path = mod / 'cs2_gc_ui_manifest.json'
    if not info.is_file(): return 'unavailable: installed gameinfo.gi not found'
    current = read_text(info)
    previous = None
    if manifest_path.exists():
        previous = json.loads(read_text(manifest_path))
        if previous.get('owner') != owner: raise ValueError('Native UI folder is not owned by this feature')
    elif mod.exists() and any(mod.iterdir()): raise ValueError('Native UI folder contains unowned files')
    mounted = mount_gameinfo(current, bool(enabled), folder, comment)
    if not enabled:
        if previous and mounted != current:
            atomic_write(info, mounted)
            return 'disabled; restart CS2 once to unload the UI override'
        return 'disabled'
    directory = game / 'csgo/pak01_dir.vpk'
    if not directory.is_file(): return 'unavailable: installed csgo/pak01_dir.vpk not found'
    original, actual = source if source is not None else vpk_file(directory, asset, aliases=True, with_path=True)
    target = mod / actual
    result = patch_installed_script(original, actual, patch)
    output_hash = hashlib.sha256(result).hexdigest()
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() not in (
            output_hash, (previous or {}).get('output_sha256')):
        raise ValueError('Native UI override was edited externally; leaving it unchanged')
    manifest = dict(owner=owner, asset_path=actual, source_sha256=hashlib.sha256(original).hexdigest(), output_sha256=output_hash)
    atomic_write(manifest_path, json.dumps(manifest, indent=2) + '\n')
    changed = not target.exists() or target.read_bytes() != result or mounted != current
    if not target.exists() or target.read_bytes() != result:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(target.name + '.tmp')
        temp.write_bytes(result); temp.replace(target)
    from vpk_pack import pack
    changed = pack(mod) or changed  # loose files lose to pak01 VPKs; a VPK in our own folder wins
    if mounted != current:
        backup = info.with_name(info.name + '.' + folder + '_backup')
        if not backup.exists():
            with backup.open('x', encoding='utf-8', newline='') as output: output.write(current)
        atomic_write(info, mounted)
    return (f'prepared from {actual}; RESTART CS2 ONCE to load native UI override' if changed else
            f'installed: {actual}; live verification needed')


WRITE_FOLDER = 'cs2_gc_first'
WRITE_COMMENT = 'cs2_gc empty write-path placeholder'
WRITE_OWNER = 'cs2-gc-write-path-v1'


def ensure_first_game_path(proxy_directory):
    """Keep an empty folder as the first Game search path.

    The first Game path is the engine's DEFAULT_WRITE_PATH. A pak01 VPK in that folder made CS2 stop with
    'Failed to load file (unexpected)', so the folders that hold VPKs must not be first.
    """
    from native_tradeups import parse
    proxy = Path(proxy_directory).resolve()
    game = proxy.parent.parent
    info = game / 'csgo/gameinfo.gi'
    mod = game / WRITE_FOLDER
    manifest_path = mod / 'cs2_gc_write_manifest.json'
    if not info.is_file(): return 'unavailable: installed gameinfo.gi not found'
    if manifest_path.exists():
        if json.loads(read_text(manifest_path)).get('owner') != WRITE_OWNER:
            raise ValueError('Write-path folder is not owned by this feature')
    elif mod.exists() and any(mod.iterdir()):
        raise ValueError('Write-path folder contains unowned files')
    current = read_text(info)
    search = parse(current).one('GameInfo').one('FileSystem').one('SearchPaths')
    first = next((node for node in search.children or [] if node.key == 'Game'), None)
    if first is not None and first.value == WRITE_FOLDER:
        return 'installed: ' + WRITE_FOLDER + ' is the first Game path'
    atomic_write(manifest_path, json.dumps(dict(owner=WRITE_OWNER), indent=2) + '\n')
    updated = mount_gameinfo(current, False, WRITE_FOLDER, WRITE_COMMENT)
    updated = mount_gameinfo(updated, True, WRITE_FOLDER, WRITE_COMMENT)
    backup = info.with_name(info.name + '.' + WRITE_FOLDER + '_backup')
    if not backup.exists():
        with backup.open('x', encoding='utf-8', newline='') as output: output.write(current)
    atomic_write(info, updated)
    return 'prepared; RESTART CS2 ONCE so the placeholder becomes the first Game path'

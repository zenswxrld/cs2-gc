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


def vpk_file(directory, wanted):
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
                    if path == wanted:
                        if found is not None: raise ValueError('Duplicate VPK asset')
                        if length + preload > MAX_ASSET: raise ValueError('VPK asset too large')
                        found = (crc, small, archive, offset, length)
        if found is None: raise ValueError('Installed VPK asset not found: ' + wanted)
        crc, small, archive, offset, length = found
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
        return result


def script_blocks(resource):
    if len(resource) < 16 or len(resource) > MAX_ASSET: raise ValueError('Invalid Panorama resource size')
    size, header, version, offset, count = struct.unpack_from('<IHHII', resource)
    if size != len(resource) or header != 12 or version != 4 or not 1 <= count <= 32:
        raise ValueError('Unsupported Panorama script resource; expected plaintext header12/version4')
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
    original = next(data for kind, data in blocks if kind == b'DATA')
    source = original.rstrip(b'\0').decode('utf-8')
    changed = patch(source).encode('utf-8') + (b'\0' if original.endswith(b'\0') else b'')
    # Debug source maps refer to the original line/column positions. Preserve other metadata.
    blocks = [(kind, changed if kind == b'DATA' else data) for kind, data in blocks if kind != b'SrMa']
    result = bytearray(struct.pack('<IHHII', 0, 12, 4, 8, len(blocks)) + b'\0' * (len(blocks) * 12))
    for i, (kind, data) in enumerate(blocks):
        result.extend(b'\0' * (-len(result) % 16))
        entry = 16 + i * 12
        struct.pack_into('<4sII', result, entry, kind, len(result) - entry - 4, len(data))
        result.extend(data)
    struct.pack_into('<I', result, 0, len(result))
    if len(result) > MAX_ASSET: raise ValueError('Patched Panorama resource too large')
    script_blocks(result)
    return bytes(result)


def install_override(proxy_directory, *, enabled, folder, comment, owner, asset, patch):
    proxy = Path(proxy_directory).resolve()
    game = proxy.parent.parent
    info = game / 'csgo/gameinfo.gi'
    mod = game / folder
    manifest_path = mod / 'cs2_gc_ui_manifest.json'
    target = mod / asset
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
    original = vpk_file(directory, asset)
    result = rewrite_script(original, patch)
    output_hash = hashlib.sha256(result).hexdigest()
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() not in (
            output_hash, (previous or {}).get('output_sha256')):
        raise ValueError('Native UI override was edited externally; leaving it unchanged')
    manifest = dict(owner=owner, source_sha256=hashlib.sha256(original).hexdigest(), output_sha256=output_hash)
    atomic_write(manifest_path, json.dumps(manifest, indent=2) + '\n')
    changed = not target.exists() or target.read_bytes() != result or mounted != current
    if not target.exists() or target.read_bytes() != result:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(target.name + '.tmp')
        temp.write_bytes(result); temp.replace(target)
    if mounted != current:
        backup = info.with_name(info.name + '.' + folder + '_backup')
        if not backup.exists():
            with backup.open('x', encoding='utf-8', newline='') as output: output.write(current)
        atomic_write(info, mounted)
    return ('prepared; RESTART CS2 ONCE to load native UI override' if changed else
            'installed: native UI override; live verification needed')

"""Keep the generated finish pack to about one copy on disk.

User (28 Oct): "the artwork cache needs to be compressed once done, not everyone will have 170gb spare".

native_finishes writes every generated texture loose into game/cs2_gc_finishes (as hard links to the artwork cache's
texture files where it can), then artwork_archive packs them into the numbered pak01 archives CS2 reads. That left
the same bytes on disk two or three times: the archives, the loose files and the cache (twice more after a move to
another drive, which breaks the links). The cached textures are already losslessly compressed texture data, so
compressing them again saves little. Instead, after a complete preparation:

  1. index which archive entry holds each cached texture (a loose file is a hard link to its cache file, so this
     needs no re-reading), in cs2_gc_pack_index.json beside the archives;
  2. delete the loose copies (CS2 only reads the VPK) once the pack is known to hold exactly them;
  3. drop the cache's own copy of every indexed texture. ArtworkCache.restore copies one back out of the archive,
     checked against its sha256, when a later generation needs it.

Only owned folders are touched, and nothing is deleted unless the archive provably holds the bytes.
"""
from pathlib import Path
import json
import os
import struct

FINISHES = 'cs2_gc_finishes'
ARTWORK = 'cs2_gc_artwork_cache'
INDEX = 'cs2_gc_pack_index.json'
OWNER = 'cs2gc-pack-index-v1'
SKIP_SUFFIXES = ('.json', '.tmp')


def vpk_entries(directory_path):
    """{relative path: (archive number, offset, length)} from a VPK v2 directory written by artwork_archive."""
    data = Path(directory_path).read_bytes()
    magic, version, tree_size = struct.unpack_from('<III', data, 0)
    if magic != 0x55aa1234 or version != 2: raise ValueError('Not a VPK v2 directory')
    tree, position, entries = data[28:28 + tree_size], 0, {}

    def string():
        nonlocal position
        end = tree.index(b'\0', position); value = tree[position:end].decode('utf-8'); position = end + 1
        return value
    while True:
        extension = string()
        if not extension: break
        while True:
            folder = string()
            if not folder: break
            while True:
                name = string()
                if not name: break
                _, preload, archive, offset, length, _ = struct.unpack_from('<IHHIIH', tree, position)
                position += 18 + preload
                path = ('' if folder == ' ' else folder + '/') + name + ('' if extension == ' ' else '.' + extension)
                entries[path] = (archive, offset, length)
    return entries


def _stamp(path):
    info = path.stat()
    return [info.st_size, info.st_mtime_ns]


def _archive(folder, number):
    return Path(folder) / ('pak01_%03d.vpk' % number)


def read_index(folder):
    """{sha256: (archive path, offset, length)} for archives unchanged since they were indexed."""
    folder = Path(folder)
    try:
        saved = json.loads((folder / INDEX).read_text(encoding='utf-8'))
        if saved.get('owner') != OWNER: return {}
        current = {name: stamp for name, stamp in saved['archives'].items()
                   if (folder / name).is_file() and _stamp(folder / name) == stamp}
        return {digest: (folder / name, offset, length) for digest, (name, offset, length) in saved['textures'].items()
                if name in current}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {}


def _loose(folder):
    return [p for p in sorted(folder.rglob('*')) if p.is_file() and not p.name.startswith('pak01_')
            and p.suffix not in SKIP_SUFFIXES and p.name != 'cs2_gc_schema_stamp.txt']


def _pack_is_current(folder, loose):
    """True when artwork_archive's own record says the archives were built from exactly these loose files."""
    try:
        from artwork_archive import CACHE, OWNER as PACK_OWNER, _outputs, _stamp as pack_stamp
        saved = json.loads((folder / CACHE).read_text(encoding='utf-8'))
        if saved.get('owner') != PACK_OWNER or saved.get('outputs') != _outputs(folder): return False
        files = [[p.relative_to(folder).as_posix(), pack_stamp(p)] for p in loose]
        return saved['inputs']['files'] == files
    except (OSError, ValueError, KeyError, TypeError, ImportError):
        return False


def compact(proxy_directory):
    """Index, then remove the loose copies and the cache's packed textures. Returns a one-line summary."""
    game = Path(proxy_directory).resolve().parent.parent
    folder, cache = game / FINISHES, game / ARTWORK
    if not (folder / 'pak01_dir.vpk').is_file(): return 'no finish pack yet'
    loose = _loose(folder)
    current = _pack_is_current(folder, loose) if loose else True
    textures = {digest: [path.name, offset, length] for digest, (path, offset, length) in read_index(folder).items()}
    if loose and current and cache.is_dir():
        blobs = {}
        for blob in cache.glob('*.blob'):
            try:
                info = blob.stat(); blobs[(info.st_dev, info.st_ino)] = (blob.stem, info.st_size)
            except OSError: pass
        entries = vpk_entries(folder / 'pak01_dir.vpk')
        for path in loose:
            info = path.stat()
            found = blobs.get((info.st_dev, info.st_ino))
            entry = entries.get(path.relative_to(folder).as_posix())
            if found and entry and entry[2] == found[1] == info.st_size:
                textures[found[0]] = ['pak01_%03d.vpk' % entry[0], entry[1], entry[2]]
    names = sorted({name for name, _, _ in textures.values()})
    temporary = folder / (INDEX + '.tmp')
    temporary.write_text(json.dumps({'owner': OWNER, 'archives': {n: _stamp(folder / n) for n in names},
                                     'textures': textures}, sort_keys=True), encoding='utf-8')
    temporary.replace(folder / INDEX)
    freed = 0
    if loose and current:
        for path in loose:
            try:
                info = path.stat()
                if info.st_nlink <= 1: freed += info.st_size
                path.unlink()
            except OSError: pass
        for path in sorted((p for p in folder.rglob('*') if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            if not any(path.iterdir()): path.rmdir()
    if cache.is_dir():
        for blob in cache.glob('*.blob'):
            if blob.stem not in textures or not (folder / textures[blob.stem][0]).is_file(): continue
            try:
                info = blob.stat()
                if info.st_size != textures[blob.stem][2]: continue
                if info.st_nlink <= 1: freed += info.st_size
                blob.unlink()
            except OSError: pass
    kept = 'kept (pack is older than them)' if loose and not current else 'removed'
    return '%.1f GB freed; loose copies %s; %d textures restorable from the pack' % (freed / 2**30, kept, len(textures))

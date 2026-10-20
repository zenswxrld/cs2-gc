"""Pack a native override folder into pak01_dir.vpk + pak01_000.vpk (Valve VPK v2, unsigned).

CS2 searches every installed pak01 VPK before loose files, so a loose override never wins. A VPK inside the
override folder is listed in search-path order (our folders come before csgo), which lets the override win.
Layout copied from the installed game's own pak01_dir.vpk: data lives in numbered archives, the directory file holds
the tree, an archive MD5 section (one entry per 1 MiB chunk) and a 48-byte "other" MD5 section.

CS2 only mounts a pak01 VPK from a folder listed in game/bin/win64/vpk.signatures (see vpk_signatures.py), which the
helper updates after packing. Kill switch: cs2_gc_no_vpk.txt beside the DLL removes our VPKs and writes none.
"""
from pathlib import Path
import hashlib
import struct
import zlib

SKIP = {'pak01_dir.vpk', 'pak01_dir.vpk.tmp', 'pak01_000.vpk', 'pak01_000.vpk.tmp'}
SKIP_SUFFIXES = ('.json', '.tmp')
SKIP_NAMES = {'cs2_gc_schema_stamp.txt'}
CHUNK = 1 << 20
KILL_SWITCH = 'cs2_gc_no_vpk.txt'


def _files(folder):
    folder = Path(folder)
    found = []
    for path in sorted(folder.rglob('*')):
        if not path.is_file() or path.name in SKIP or path.name in SKIP_NAMES or path.suffix in SKIP_SUFFIXES:
            continue
        found.append((path.relative_to(folder).as_posix(), path.read_bytes()))
    return found


def build(files):
    """files: [(relative/posix/path, bytes)] -> (directory VPK bytes, archive 000 bytes)."""
    tree = {}
    archive = bytearray()
    for path, content in files:
        directory, _, name = path.rpartition('/')
        stem, dot, extension = name.rpartition('.')
        if not dot: stem, extension = name, ''
        tree.setdefault(extension or ' ', {}).setdefault(directory or ' ', []).append(
            (stem, zlib.crc32(content) & 0xffffffff, len(archive), len(content)))
        archive.extend(content)
    tree_bytes = bytearray()
    for extension in sorted(tree):
        tree_bytes += extension.encode() + b'\0'
        for folder in sorted(tree[extension]):
            tree_bytes += folder.encode() + b'\0'
            for stem, crc, offset, length in sorted(tree[extension][folder]):
                tree_bytes += stem.encode() + b'\0'
                tree_bytes += struct.pack('<IHHIIH', crc, 0, 0, offset, length, 0xffff)  # archive index 0
            tree_bytes += b'\0'
        tree_bytes += b'\0'
    tree_bytes += b'\0'
    tree_bytes = bytes(tree_bytes)
    archive = bytes(archive)
    archive_md5 = bytearray()
    for start in range(0, len(archive), CHUNK):
        chunk = archive[start:start + CHUNK]
        archive_md5 += struct.pack('<III', 0, start, len(chunk)) + hashlib.md5(chunk).digest()
    archive_md5 = bytes(archive_md5)
    header = struct.pack('<IIIIIII', 0x55aa1234, 2, len(tree_bytes), 0, len(archive_md5), 48, 0)
    tree_md5 = hashlib.md5(tree_bytes).digest()
    section_md5 = hashlib.md5(archive_md5).digest()
    body = header + tree_bytes + archive_md5 + tree_md5 + section_md5
    return body + hashlib.md5(body).digest(), archive


def _write(path, content):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_bytes(content)
    temporary.replace(path)


def pack(folder):
    """Write folder/pak01_dir.vpk and pak01_000.vpk from the folder's files. Returns True when they changed."""
    folder = Path(folder)
    directory_path, archive_path = folder / 'pak01_dir.vpk', folder / 'pak01_000.vpk'
    proxy = folder.parent / 'bin' / 'win64'
    if (proxy / KILL_SWITCH).exists():
        removed = False
        for path in (directory_path, archive_path):
            if path.exists():
                path.unlink(); removed = True
        return removed
    files = _files(folder)
    if not files:
        return False
    directory, archive = build(files)
    if (directory_path.exists() and archive_path.exists() and directory_path.read_bytes() == directory
            and archive_path.read_bytes() == archive):
        return False
    _write(archive_path, archive)
    _write(directory_path, directory)
    return True


def status(proxy_directory):
    """One line for the rewards log: kill switch state and which override folders hold a VPK."""
    proxy = Path(proxy_directory).resolve()
    game = proxy.parent.parent
    if (proxy / KILL_SWITCH).exists():
        return 'OFF (' + KILL_SWITCH + ' exists beside the DLL)'
    folders = sorted(path.name for path in game.glob('cs2_gc_*') if (path / 'pak01_dir.vpk').is_file())
    return ('on; VPKs present in ' + ', '.join(folders)) if folders else 'on; no override VPKs written yet'

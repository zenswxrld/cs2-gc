"""Pack a native override folder into pak01_dir.vpk (Valve VPK v2, data stored inside the directory file).

CS2 searches every installed pak01 VPK before loose files, so a loose override never wins. A VPK inside the
override folder is listed in search-path order (our folders come before csgo), which lets the override win.
"""
from pathlib import Path
import struct
import zlib

SKIP = {'pak01_dir.vpk', 'pak01_dir.vpk.tmp'}
SKIP_SUFFIXES = ('.json', '.tmp')
SKIP_NAMES = {'cs2_gc_schema_stamp.txt'}


def _files(folder):
    folder = Path(folder)
    found = []
    for path in sorted(folder.rglob('*')):
        if not path.is_file() or path.name in SKIP or path.name in SKIP_NAMES or path.suffix in SKIP_SUFFIXES:
            continue
        found.append((path.relative_to(folder).as_posix(), path.read_bytes()))
    return found


def build(files):
    """files: [(relative/posix/path, bytes)] -> VPK v2 bytes."""
    tree = {}
    data = bytearray()
    for path, content in files:
        directory, _, name = path.rpartition('/')
        stem, dot, extension = name.rpartition('.')
        if not dot: stem, extension = name, ''
        tree.setdefault(extension or ' ', {}).setdefault(directory or ' ', []).append(
            (stem, zlib.crc32(content) & 0xffffffff, len(data), len(content)))
        data.extend(content)
    directory = bytearray()
    for extension in sorted(tree):
        directory += extension.encode() + b'\0'
        for folder in sorted(tree[extension]):
            directory += folder.encode() + b'\0'
            for stem, crc, offset, length in sorted(tree[extension][folder]):
                directory += stem.encode() + b'\0'
                directory += struct.pack('<IHHIIH', crc, 0, 0x7fff, offset, length, 0xffff)
            directory += b'\0'
        directory += b'\0'
    directory += b'\0'
    header = struct.pack('<IIIIIII', 0x55aa1234, 2, len(directory), len(data), 0, 0, 0)
    return header + bytes(directory) + bytes(data)


def pack(folder):
    """Write folder/pak01_dir.vpk from the folder's files. Returns True when the VPK changed."""
    folder = Path(folder)
    files = _files(folder)
    target = folder / 'pak01_dir.vpk'
    if not files:
        return False
    content = build(files)
    if target.exists() and target.read_bytes() == content:
        return False
    temporary = target.with_name(target.name + '.tmp')
    temporary.write_bytes(content)
    temporary.replace(target)
    return True

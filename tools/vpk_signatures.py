"""List our override VPKs in game/bin/win64/vpk.signatures so CS2 mounts them.

From the installed filesystem_stdio.dll (CS2 build 25966348): only pakNN_dir.vpk files are mounted from a search path,
and with "pakxx" "off" every pakNN VPK must be listed as  "pak01" { "<folder>" "MD5:<hex>" }. A pak01 VPK in a folder
that is not listed stops the game with "Failed to load file (unexpected)!", a wrong hash with "(invalid)". The hash is
the last MD5 of the VPK directory file's "other MD5" section (Valve's own pak01/csgo entry matches that value).
The file is plain KeyValues and is not itself signature-checked. We back it up once, only add/replace a pak01 block
whose children are all cs2_gc_* folders, and leave every Valve entry untouched. Steam verify/update restores the
original; the helper adds the block again on the next start.
"""
from pathlib import Path
import re
import struct

BACKUP_SUFFIX = '.cs2_gc_backup'
OWNED = re.compile(r'\r?\n"pak01"\r?\n\{\r?\n(?:[ \t]*"cs2_gc_[A-Za-z0-9_]+"[ \t]+"MD5:[0-9a-f]{32}"\r?\n)+\}')


def directory_checksum(directory_vpk):
    """The 16-byte checksum CS2 compares: the last MD5 of the 48-byte other-MD5 section, as hex."""
    data = Path(directory_vpk).read_bytes()
    magic, version, tree, file_data, archive_md5, other_md5, _ = struct.unpack_from('<IIIIIII', data)
    if magic != 0x55aa1234 or version != 2 or other_md5 != 48:
        raise ValueError('Not a VPK v2 directory with an other-MD5 section: ' + str(directory_vpk))
    end = 28 + tree + file_data + archive_md5
    return data[end + 32:end + 48].hex()


def update(proxy_directory):
    proxy = Path(proxy_directory).resolve()
    game = proxy.parent.parent
    path = proxy / 'vpk.signatures'
    if not path.is_file():
        return 'unavailable: vpk.signatures not found beside the DLL'
    with path.open('r', encoding='utf-8', newline='') as source:
        current = source.read()
    if not current.lstrip('﻿').startswith('"vpk.signatures"'):
        raise ValueError('vpk.signatures has an unexpected layout; leaving it unchanged')
    entries = []
    for folder in sorted(game.glob('cs2_gc_*')):
        if (folder / 'pak01_dir.vpk').is_file():
            entries.append((folder.name, directory_checksum(folder / 'pak01_dir.vpk')))
    base = OWNED.sub('', current)
    if entries:
        newline = '\r\n' if '\r\n' in current else '\n'
        closing = base.rstrip().rfind('}')
        if closing < 0:
            raise ValueError('vpk.signatures has no closing brace; leaving it unchanged')
        block = newline + '"pak01"' + newline + '{' + newline + ''.join(
            '\t"' + name + '" "MD5:' + digest + '"' + newline for name, digest in entries) + '}'
        updated = base[:closing].rstrip('\r\n') + block + newline + base[closing:]
    else:
        updated = base
    if updated == current:
        return ('installed: ' + ', '.join(name for name, _ in entries)) if entries else 'no override VPKs to list'
    backup = path.with_name(path.name + BACKUP_SUFFIX)
    if not backup.exists():
        with backup.open('x', encoding='utf-8', newline='') as output: output.write(current)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w', encoding='utf-8', newline='') as output: output.write(updated)
    temporary.replace(path)
    return ('prepared: ' + ', '.join(name for name, _ in entries) + '; RESTART CS2 ONCE') if entries else 'removed our entries'

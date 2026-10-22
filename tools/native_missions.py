"""Missions that rotate with the Armory (user: "make the missions rotate with the armory").

The recorded RecurringMissionSchema (cs2_gc_replay/9226.bin, the answer to 9225) has templates only for two weeks of
October 2026. This builds a pool of mission variants from the playable templates: every combination of each template's
random choices ("![a|b]" / "!![a|b]" resolved to one option, keeping the syntax), interleaved by template. The DLL
serves variant (cycle % pool size) for the current Armory rotation, so the game shows exactly what the rewards helper
counts, and switches when the Armory rotates or is refreshed.

Outputs (next to the proxy): cs2_gc_missions.bin (pool: repeated {1: index, 2: template blob}) and
cs2_gc_missions.json (what each variant counts). Template format: binary KeyValues, objects end with 0x0b.
"""
from pathlib import Path
import json
import random
import re
import struct
import time

RECORDED = 'cs2_gc_replay/9226.bin'
SCHEMA_FILE = 'cs2_gc_missions.bin'
PLAN_FILE = 'cs2_gc_missions.json'
# lobby_mapveto is Premier's map veto and rush_001 the Rush mode: neither launches as a local bot match.
UNPLAYABLE = ('lobby_mapveto', 'rush')
END, SUBKEY, STRING, INT32, FLOAT, UINT64, BYTE, ZERO = 0x0b, 0, 1, 2, 3, 7, 9, 10


def _varint(data, i):
    value = shift = 0
    while True:
        byte = data[i]; i += 1
        value |= (byte & 127) << shift; shift += 7
        if byte < 128: return value, i


def proto_fields(data):
    i, out = 0, []
    while i < len(data):
        key, i = _varint(data, i)
        number, wire = key >> 3, key & 7
        if wire == 0: value, i = _varint(data, i)
        elif wire == 2:
            length, i = _varint(data, i); value = data[i:i + length]; i += length
        elif wire == 5: value = data[i:i + 4]; i += 4
        elif wire == 1: value = data[i:i + 8]; i += 8
        else: raise ValueError('unsupported wire type %d' % wire)
        out.append((number, value))
    return out


def _put_varint(value):
    out = bytearray()
    while True:
        byte = value & 127; value >>= 7
        out.append(byte | (128 if value else 0))
        if not value: return bytes(out)


def _field(number, value):
    if isinstance(value, int): return _put_varint(number << 3) + _put_varint(value)
    return _put_varint(number << 3 | 2) + _put_varint(len(value)) + value


def read_kv(data, i=0):
    """Binary KeyValues -> [(key, type, value)], value a nested list for subkeys. Keeps types for a faithful rewrite."""
    entries = []
    while i < len(data):
        kind = data[i]; i += 1
        if kind in (END, 8): return entries, i
        end = data.index(0, i); key = data[i:end].decode('utf-8'); i = end + 1
        if kind == SUBKEY: value, i = read_kv(data, i)
        elif kind == STRING: end = data.index(0, i); value = data[i:end].decode('utf-8'); i = end + 1
        elif kind == INT32: value = struct.unpack_from('<i', data, i)[0]; i += 4
        elif kind == FLOAT: value = struct.unpack_from('<f', data, i)[0]; i += 4
        elif kind == UINT64: value = struct.unpack_from('<Q', data, i)[0]; i += 8
        elif kind == BYTE: value = data[i]; i += 1
        elif kind == ZERO: value = 0
        else: raise ValueError('unsupported KeyValues type %d' % kind)
        entries.append((key, kind, value))
    return entries, i


def write_kv(entries):
    out = bytearray()
    for key, kind, value in entries:
        out += bytes((kind,)) + key.encode('utf-8') + b'\0'
        if kind == SUBKEY: out += write_kv(value)
        elif kind == STRING: out += value.encode('utf-8') + b'\0'
        elif kind == INT32: out += struct.pack('<i', value)
        elif kind == FLOAT: out += struct.pack('<f', value)
        elif kind == UINT64: out += struct.pack('<Q', value)
        elif kind == BYTE: out += bytes((value,))
    return bytes(out) + bytes((END,))


def as_dict(entries):
    return {key: (as_dict(value) if kind == SUBKEY else value) for key, kind, value in entries}


def recorded_templates(schema):
    """[(period, mission id, entries)] from a recorded 9226 body, later periods replacing earlier ones per id."""
    found = {}
    for number, value in proto_fields(schema):
        if number != 1 or isinstance(value, int): continue
        period, blobs = 0, []
        for inner, item in proto_fields(value):
            if inner == 1: period = item
            elif inner == 2: blobs.append(item)
        for blob in blobs:
            entries, _ = read_kv(blob)
            for mission, kind, body in entries:
                if kind == SUBKEY and mission.isdigit(): found[mission] = (period, mission, body)
    return [found[key] for key in sorted(found, key=int)]


def playable(body):
    fields = as_dict(body)
    text = ' '.join(str(fields.get(k, '')) for k in ('gamemode', 'map', 'mapgroup'))
    return not any(word in text for word in UNPLAYABLE) and fields.get('expression')


def resolve(entries, rng_for):
    """Each "![a|b]" / "!![a|b]" becomes a one-option list. The same original text resolves the same way everywhere
    in the template (so gc.random matches the visible fields)."""
    def choose(match):
        options = [o for o in match.group(2).split('|') if o]
        return '%s[%s]' % (match.group(1), rng_for(match.group(0)).choice(options))
    out = []
    for key, kind, value in entries:
        if kind == SUBKEY: value = resolve(value, rng_for)
        elif kind == STRING: value = re.sub(r'(!!?)\[([^\]]*)\]', choose, value)
        out.append((key, kind, value))
    return out


def _choice(text):
    found = re.search(r'!!?\[([^\]|]*)\]', text or '')
    return found.group(1) if found else (text or '')


def describe(mission, body, mapgroups):
    fields = as_dict(body)
    expression = fields.get('expression', '')
    weapon = re.search(r'weapon_[a-z0-9_]+', expression)
    kind = ('kill' if 'act_kill' in expression else 'round' if 'act_win_round' in expression else
            'match' if 'act_win_match' in expression else None)
    group = _choice(fields.get('mapgroup'))
    the_map = _choice(fields.get('map'))
    numbers = lambda text: [int(x) for x in re.findall(r'\d+', str(text))]
    return {'mission': int(mission), 'kind': kind, 'weapon': weapon.group(0) if weapon else None,
            'mode': fields.get('gamemode', ''), 'map': the_map, 'mapgroup': group,
            'maps': sorted(set(mapgroups.get(group, ())) | ({the_map} if the_map else set())),
            'points': numbers(fields.get('points')), 'xp': numbers(fields.get('xp_expr'))}


def mapgroups_from(gamemodes_text):
    groups = {}
    for name, maps in re.findall(r'"name"\s+"(mg_[^"]+)".*?"maps"\s*\{([^}]*)\}', gamemodes_text, re.S):
        groups.setdefault(name, re.findall(r'"([^"]+)"\s+""', maps))
    return groups


def variants(entries, limit=40):
    """Every combination of a template's random lists (each "![a|b]" fixed to one option), at most `limit`."""
    texts = []
    def collect(items):
        for _, kind, value in items:
            if kind == SUBKEY: collect(value)
            elif kind == STRING:
                for match in re.finditer(r'(!!?)\[([^\]]*)\]', value):
                    if match.group(0) not in texts: texts.append(match.group(0))
    collect(entries)
    combos = [{}]
    for text in texts:
        options = list(dict.fromkeys(o for o in re.match(r'!!?\[([^\]]*)\]', text).group(1).split('|') if o))
        combos = [dict(c, **{text: o}) for c in combos for o in options][:limit]
    return [resolve(entries, lambda text, c=c: _Fixed(c[text])) for c in combos]


class _Fixed:
    def __init__(self, value): self.value = value
    def choice(self, options): return self.value


def build(recorded, gamemodes_text):
    """(pool bytes, plan dict). The pool rotates with the Armory: the DLL serves variant (cycle % size) as the mission
    of the current Armory rotation (cycle = now / armory_rotation_seconds + Refresh offset)."""
    templates = [t for t in recorded_templates(recorded) if playable(t[2])]
    if not templates: raise ValueError('The recorded mission schema has no playable templates')
    mapgroups = mapgroups_from(gamemodes_text)
    per_template = [[(mission, v) for v in variants(entries)] for _, mission, entries in templates]
    pool = []
    for round_index in range(max(len(v) for v in per_template)):  # interleave so consecutive missions differ
        pool += [v[round_index % len(v)] for v in per_template if round_index < len(v)]
    body = bytearray()
    plan = {'variants': []}
    for index, (mission, resolved) in enumerate(pool):
        body += _field(1, _field(1, index) + _field(2, write_kv([(mission, SUBKEY, resolved)])))
        plan['variants'].append(describe(mission, resolved, mapgroups))
    return bytes(body), plan


def prepare(proxy_directory, config):
    from native_finishes import Source
    from native_tradeups import atomic_write
    proxy = Path(proxy_directory)
    recorded = proxy / RECORDED
    if not config.get('missions_enabled', 1):
        for name in (SCHEMA_FILE, PLAN_FILE):
            if (proxy / name).exists(): (proxy / name).unlink()
        return 'disabled'
    if not recorded.is_file(): return 'skipped: no recorded mission schema (%s)' % RECORDED
    data = Source(vpk=proxy.parent.parent / 'csgo' / 'pak01_dir.vpk').read('gamemodes.txt')
    body, plan = build(recorded.read_bytes(), data.decode('utf-8', 'replace') if data else '')
    (proxy / SCHEMA_FILE).write_bytes(body)
    atomic_write(proxy / PLAN_FILE, json.dumps(plan, indent=1, sort_keys=True) + '\n')
    return '%d mission variants written; they rotate with the Armory' % len(plan['variants'])

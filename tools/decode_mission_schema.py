"""Decode a recorded 9226 RecurringMissionSchema (cs2_gc_replay/9226.bin) to JSON: periods and their binary-KV mission
templates. Usage: python decode_mission_schema.py 9226.bin out.json. Binary KV here ends objects with 0x0b (also 0x08);
9 = one-byte int, 10 = int 0."""
import sys, struct, json
data = open(sys.argv[1], 'rb').read()
def varint(b, i):
    v = s = 0
    while True:
        c = b[i]; i += 1; v |= (c & 127) << s; s += 7
        if c < 128: return v, i
def fields(b):
    i = 0; out = []
    while i < len(b):
        key, i = varint(b, i); n, w = key >> 3, key & 7
        if w == 0: v, i = varint(b, i)
        elif w == 2: l, i = varint(b, i); v = b[i:i+l]; i += l
        elif w == 5: v = b[i:i+4]; i += 4
        elif w == 1: v = b[i:i+8]; i += 8
        else: raise ValueError(w)
        out.append((n, w, v))
    return out
def kv(b, i=0):
    obj = {}
    while i < len(b):
        t = b[i]; i += 1
        if t in (8, 11): return obj, i
        e = b.index(0, i); name = b[i:e].decode('utf-8', 'replace'); i = e + 1
        if t == 0: v, i = kv(b, i)
        elif t == 1: e = b.index(0, i); v = b[i:e].decode('utf-8', 'replace'); i = e + 1
        elif t == 2: v = struct.unpack_from('<i', b, i)[0]; i += 4
        elif t == 3: v = struct.unpack_from('<f', b, i)[0]; i += 4
        elif t == 7: v = struct.unpack_from('<Q', b, i)[0]; i += 8
        elif t == 9: v = b[i]; i += 1
        elif t == 10: v = 0
        elif t == 6: v = list(b[i:i+4]); i += 4
        else: raise ValueError('kv type %d at %d' % (t, i))
        obj[name] = v
    return obj, i
result = []
for n, w, v in fields(data):
    if n != 1: continue
    period = None; templates = []
    for m, w2, v2 in fields(v):
        if m == 1: period = v2
        elif m == 2:
            t, _ = kv(v2); templates.append(t)
    result.append({'period': period, 'templates': templates})
json.dump(result, open(sys.argv[2], 'w'), indent=1)
for r in result: print(r['period'], len(r['templates']), [list(t.keys())[:3] for t in r['templates']][:3])

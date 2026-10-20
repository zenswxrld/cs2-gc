"""Prepare a narrowly scoped CS2 recipe override for the native trade-up screen.

Only existing trade-up input-quality conditions and duplicate StatTrak recipe enable
flags change. The original schema is never edited. A dedicated search-path folder
is mounted through the installed game's own gameinfo.gi, backed up before editing.
"""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re

OWNER = 'cs2-gc-native-mixed-v1'
FOLDER = 'cs2_gc_native'
MOUNT = 'Game\tcs2_gc_native // cs2_gc native tradeups'
TOKEN = re.compile(r'\s+|//[^\r\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|[{}]|[^\s{}"]+')
RARITIES = ('common', 'uncommon', 'rare', 'mythical', 'legendary', 'ancient')


@dataclass
class Node:
    key: str
    value: str = None
    children: list = None
    start: int = 0
    end: int = 0
    opening: int = 0

    def one(self, key):
        found = [child for child in self.children or [] if child.key == key]
        if len(found) != 1:
            raise ValueError('Expected exactly one schema field: ' + key)
        return found[0]

    def text(self, key):
        child = self.one(key)
        if child.children is not None:
            raise ValueError('Expected a value: ' + key)
        return child.value


def parse(text):
    tokens = []
    position = 1 if text.startswith('\ufeff') else 0
    while position < len(text):
        match = TOKEN.match(text, position)
        if not match:
            raise ValueError('Malformed KeyValues near offset ' + str(position))
        raw = match.group()
        position = match.end()
        if raw.isspace() or raw.startswith('//') or raw.startswith('/*'):
            continue
        value = re.sub(r'\\(["\\])', r'\1', raw[1:-1]) if raw.startswith('"') else raw
        tokens.append((value, match.start(), match.end(), raw))
    index = 0

    def nodes(block=False, depth=0):
        nonlocal index
        if depth > 128: raise ValueError('Excessive KeyValues nesting')
        result = []
        while index < len(tokens):
            key, _, _, raw_key = tokens[index]
            if raw_key == '}':
                if not block: raise ValueError('Unexpected closing brace')
                index += 1
                return result
            if raw_key == '{': raise ValueError('Missing KeyValues key')
            index += 1
            if index >= len(tokens): raise ValueError('Missing KeyValues value')
            value, start, end, raw = tokens[index]
            index += 1
            if raw == '{':
                children = nodes(True, depth + 1)
                result.append(Node(key, children=children, opening=end))
            elif raw == '}': raise ValueError('Missing KeyValues value')
            else: result.append(Node(key, value, start=start, end=end))
        if block: raise ValueError('Unclosed KeyValues block')
        return result

    return Node('root', children=nodes())


def patch_recipes(source):
    recipes = parse(source).one('items_game').one('recipes')
    normal, tracked, edits = {}, {}, []
    for recipe in recipes.children or []:
        fields = {node.key: node for node in recipe.children or []}
        if (fields.get('name', Node('')).value != '#RT_MP_A' or
                fields.get('category', Node('')).value != 'crafting' or
                fields.get('filter', Node('')).value != '-3'):
            continue
        inputs = recipe.one('input_items').children
        if not inputs or len(inputs) != 1: raise ValueError('Changed trade-up input layout')
        conditions = inputs[0].one('conditions').children
        by_field = {}
        for condition in conditions or []:
            field = condition.text('field')
            if field in by_field: raise ValueError('Duplicate trade-up condition')
            by_field[field] = condition
        rarity = by_field['*rarity'].text('value')
        quality = by_field['*quality']
        qualities = set(quality.text('value').split(','))
        if rarity not in RARITIES or quality.text('operator') != 'string==':
            raise ValueError('Changed trade-up rarity/quality rules')
        if by_field['craft_class'].text('value') != 'weapon':
            raise ValueError('Trade-up is not restricted to weapons')
        required = '5' if rarity == 'ancient' else '10'
        if inputs[0].key != required or recipe.text('di_A') != required:
            raise ValueError('Changed trade-up input count')
        disabled = recipe.one('disabled')
        if disabled.value not in ('0', '1'): raise ValueError('Changed recipe enable flag')
        if qualities in ({'unique', 'tournament'}, {'unique', 'strange', 'tournament'}):
            if rarity in normal or '*kill_eater_score_type' in by_field:
                raise ValueError('Ambiguous normal trade-up recipe')
            normal[rarity] = recipe.key
            if disabled.value != '0': raise ValueError('Normal trade-up recipe is disabled')
            value = quality.one('value')
            edits.append((value.start, value.end, '"unique,strange,tournament"'))
        elif qualities == {'strange'}:
            if rarity in tracked or by_field['*kill_eater_score_type'].text('value') != '0':
                raise ValueError('Changed StatTrak trade-up recipe')
            tracked[rarity] = recipe.key
            # Force both first-selection variants through the broadened shared recipe.
            edits.append((disabled.start, disabled.end, '"1"'))
        else: raise ValueError('Unrecognised trade-up qualities')
    if set(normal) != set(RARITIES) or set(tracked) != set(RARITIES):
        raise ValueError('Expected the six normal and six StatTrak recipes from the inspected CS2 schema')
    result = source
    for start, end, replacement in sorted(edits, reverse=True):
        result = result[:start] + replacement + result[end:]
    return result, {'normal_recipes': normal, 'disabled_stattrak_recipes': tracked}


def mount_gameinfo(source, enabled=True, folder=FOLDER, comment='cs2_gc native tradeups'):
    search = parse(source).one('GameInfo').one('FileSystem').one('SearchPaths')
    owned = re.compile(r'\r?\n[ \t]*Game[ \t]+' + re.escape(folder) + r'[ \t]*// ' + re.escape(comment) + r'\r?\n')
    if not enabled:
        return owned.sub('', source)
    paths = [node for node in search.children or [] if node.key == 'Game' and node.value == folder]
    if paths:
        if len(paths) != 1 or len(owned.findall(source)) != 1:
            raise ValueError('Unowned or duplicate native search path; leaving gameinfo unchanged')
        return source
    if not any(node.key == 'Game' and node.value == 'csgo' for node in search.children or []):
        raise ValueError('Installed gameinfo does not contain the inspected CS2 base search path')
    newline = '\r\n' if '\r\n' in source else '\n'
    insertion = newline + '\t\t\tGame\t' + folder + ' // ' + comment + newline
    return source[:search.opening] + insertion + source[search.opening:]


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w', encoding='utf-8', newline='') as output:
        output.write(text); output.flush(); os.fsync(output.fileno())
    temporary.replace(path)


def read_text(path):
    # Preserve BOM and line endings; only validated token spans / our mount line change.
    with path.open('r', encoding='utf-8', newline='') as source:
        return source.read()


def prepare(proxy_directory, enabled=True):
    proxy_directory = Path(proxy_directory).resolve()
    game = proxy_directory.parent.parent
    gameinfo = game / 'csgo/gameinfo.gi'
    schema = proxy_directory / 'items_game.txt'
    mod = game / FOLDER
    manifest_path = mod / 'cs2_gc_native_manifest.json'
    if not gameinfo.is_file():
        return 'unavailable: installed game/csgo/gameinfo.gi not found'
    current_gameinfo = read_text(gameinfo)
    if not enabled:
        if not manifest_path.exists(): return 'disabled'
        manifest = json.loads(read_text(manifest_path))
        if manifest.get('owner') != OWNER: raise ValueError('Native folder is not owned by this feature')
        original = mount_gameinfo(current_gameinfo, False)
        if original != current_gameinfo:
            atomic_write(gameinfo, original)
            return 'disabled; restart CS2 to restore native homogeneous recipes'
        return 'disabled'
    if not schema.is_file():
        return 'unavailable: items_game.txt is missing beside the proxy DLL'
    source = read_text(schema)
    patched, details = patch_recipes(source)
    mounted = mount_gameinfo(current_gameinfo)
    existing = None
    if manifest_path.exists():
        existing = json.loads(read_text(manifest_path))
        if existing.get('owner') != OWNER: raise ValueError('Native folder is not owned by this feature')
    elif mod.exists() and any(mod.iterdir()):
        raise ValueError('Native folder already contains unowned files; refusing to overwrite it')
    target = mod / 'scripts/items/items_game.txt'
    if target.exists():
        previous_hash = digest(read_text(target))
        if previous_hash != digest(patched) and (not existing or previous_hash != existing.get('output_sha256')):
            raise ValueError('Native recipe override was edited externally; refusing to overwrite it')
    manifest = dict(owner=OWNER, source_sha256=digest(source), output_sha256=digest(patched), **details)
    # Reserve ownership before writing assets, so a failed setup can be resumed safely.
    atomic_write(manifest_path, json.dumps(manifest, indent=2) + '\n')
    changed = not target.exists() or read_text(target) != patched or mounted != current_gameinfo
    if not target.exists() or read_text(target) != patched: atomic_write(target, patched)
    if mounted != current_gameinfo:
        backup = gameinfo.with_name(gameinfo.name + '.cs2_gc_native_backup')
        if not backup.exists():
            with backup.open('x', encoding='utf-8', newline='') as output:
                output.write(current_gameinfo); output.flush(); os.fsync(output.fileno())
        atomic_write(gameinfo, mounted)
    return ('prepared; RESTART CS2 ONCE to load native mixed trade-ups' if changed else
            'installed: shared native normal/StatTrak recipes; live selection still needs verification')

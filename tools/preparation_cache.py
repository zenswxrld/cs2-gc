"""Cache complete native preparation; generated packs remain the source of truth.

Hash helper/config/asset inputs and small authoritative output files. Large VPK
payloads use file identity, size and nanosecond modification time, so a warm
launch does not read/recreate thousands of loose material resources.
"""
import hashlib
import json
from pathlib import Path
import sys

VERSION = 1
FILENAME = 'cs2_gc_prepare_cache.json'


def digest(path):
    if not path.is_file():
        return None
    result = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def stamp(path):
    info = path.stat()
    return [info.st_size, info.st_mtime_ns, info.st_ino]


class PreparationCache:
    def __init__(self, proxy, config, helpers=None):
        self.proxy = Path(proxy).resolve()
        self.game = self.proxy.parent.parent
        self.config = config
        self.helpers = Path(helpers) if helpers is not None else Path(__file__).parent
        self.path = self.proxy / FILENAME
        self.reason = 'no complete preparation cache'

    def inputs(self):
        required = [self.proxy / 'items_game.txt', self.game / 'csgo/pak01_dir.vpk']
        if not all(p.is_file() for p in required):
            return None
        files = set(required)
        files.update(self.helpers.glob('*.py'))
        for folder in ('collection_icons', 'weapon_patterns'):
            files.update(p for p in (self.helpers / folder).rglob('*') if p.is_file())
        files.update(self.helpers.glob('*.png'))
        files.update(self.proxy / n for n in ('gold_pools.txt',))
        files.add(self.game / 'csgo/steam.inf')
        files.add(self.proxy / 'cs2_gc_replay/2501.bin')
        payload = {'version': VERSION, 'game': str(self.game), 'config': self.config,
                   'python': list(sys.version_info[:3]),
                   'files': {str(p): digest(p) for p in sorted(files)},
                   'archives': {str(p): stamp(p) for p in sorted((self.game / 'csgo').glob('pak*.vpk'))},
                   'binaries': {str(p): stamp(p) for p in
                       (self.proxy / 'steam_api64.dll', self.proxy / 'cs2_gc_debug.exe') if p.is_file()}}
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()

    def outputs(self):
        packs, metadata = {}, {}
        for folder in sorted(self.game.glob('cs2_gc_*')):
            if not folder.is_dir():
                continue
            # The launcher deliberately reshuffles bot names on every start.
            # Its small pack is rebuilt independently on a cache hit.
            if folder.name not in ('cs2_gc_bots', 'cs2_gc_bot_labels'):
                packs.update({str(p): stamp(p) for p in sorted(folder.glob('*.vpk'))})
                metadata.update({str(p): digest(p) for p in sorted(folder.glob('*manifest.json'))})
        for path in [self.game / 'csgo/gameinfo.gi',
                     self.game / 'cs2_gc_native/cs2_gc_schema_stamp.txt',
                     self.game / 'cs2_gc_native/scripts/items/items_game.txt'] + [
                self.proxy / name for name in ('cs2_gc_finish_ids.json', 'cs2_gc_skin_families.txt',
                    'cs2_gc_collection_previews.json', 'cs2_gc_black_market_reel.json',
                    'cs2_gc_weapon_palettes.json', 'cs2_gc_store_2501.bin', 'vpk.signatures')]:
            metadata[str(path)] = digest(path)
        return {'packs': packs, 'metadata': metadata}

    def hit(self):
        try:
            cached = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(cached, dict):
                return False
            current = self.inputs()
            if current is None or cached.get('inputs') != current:
                self.reason = 'helpers, game assets or configuration changed'
                return False
            if cached.get('outputs') != self.outputs():
                self.reason = 'generated packs, mounts or finish metadata changed'
                return False
            self.reason = 'validated complete native preparation'
            return True
        except (OSError, ValueError, TypeError):
            return False

    def save(self):
        inputs = self.inputs()
        if inputs is None:
            return
        data = dict(inputs=inputs, outputs=self.outputs())
        temporary = self.path.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(data, sort_keys=True, indent=1) + '\n', encoding='utf-8')
        temporary.replace(self.path)

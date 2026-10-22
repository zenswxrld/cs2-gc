"""Transport local care choices only; inventory grants remain in the GC."""
from pathlib import Path
import re
from native_tradeups import atomic_write


class CarePackageBridge:
    def __init__(self, directory, cfg_dir, pid):
        self.directory = Path(directory)
        self.pid = pid
        self.log = Path(cfg_dir).parent / 'console.log'
        self.position = 0
        self.pending = b''
        self.requests = []
        boot = self.directory / 'cs2_gc_console_boot.txt'
        self.nonce = boot.read_text().strip() if boot.exists() else ''
        if not re.fullmatch('[0-9a-f]{32}', self.nonce):
            self.pattern = None
            print('Care claims unavailable: restart through the updated launcher.', flush=True)
            return
        cursor = self.directory / 'cs2_gc_care_boot.txt'
        fields = cursor.read_text().split() if cursor.exists() else []
        if len(fields) == 2 and fields[0] == self.nonce and fields[1].isdigit():
            self.position = int(fields[1])
        self.pattern = re.compile(rb'(?:^|[\]\s])cs2gc_' + self.nonce.encode() +
                                  rb'_care_([1-9][0-9]{0,9})_(7|11|13|14) 1(?:\.0+)?$')

    def poll(self):
        if self.pattern is None:
            return
        if self.log.exists():
            if self.log.stat().st_size < self.position:
                self.position = 0
                self.pending = b''
            with self.log.open('rb') as source:
                source.seek(self.position)
                data = source.read(1024 * 1024)
                self.position = source.tell()
            lines = (self.pending + data).split(b'\n')
            self.pending = lines.pop()
            if len(self.pending) > 4096:
                self.pending = b'!'
            for line in lines:
                if len(line) > 4096:
                    continue
                match = self.pattern.search(line.rstrip(b'\r'))
                if not match:
                    continue
                generation, mask = map(int, match.groups())
                choice = (generation, mask)
                if generation <= 0xffffffff and choice not in self.requests and len(self.requests) < 32:
                    self.requests.append(choice)
        pending = self.directory / 'cs2_gc_care_request.txt'
        processing = self.directory / 'cs2_gc_care_processing.txt'
        if self.requests and not pending.exists() and not processing.exists():
            generation, mask = self.requests[0]
            atomic_write(pending, f'{self.pid} {generation} {mask} {self.nonce}\n')
            self.requests.pop(0)

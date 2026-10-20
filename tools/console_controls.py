"""Offline console aliases transported through CS2's -condebug console.log.

No engine offsets, dev-only commands or extra native interface hooks. Alias
expansion emits a session-specific exact line. Only freshly appended matching
lines are accepted; command history and previous launches cannot grant stars.
"""
from pathlib import Path
import re
import secrets
from native_tradeups import atomic_write


class ConsoleControls:
    def __init__(self, rewards, cfg_dir, pid):
        self.rewards = rewards
        self.pid = pid
        self.log = Path(cfg_dir).parent / 'console.log'
        boot = rewards.directory / 'cs2_gc_console_boot.txt'
        nonce = boot.read_text().strip() if boot.exists() else ''
        self.nonce = nonce if re.fullmatch('[0-9a-f]{32}', nonce) else secrets.token_hex(16)
        self.position = self.log.stat().st_size if self.log.exists() else 0
        self.pending = b''
        self.offset = rewards.state.get('console_rotation', 0) if rewards.state.get('console_pid') == pid else 0
        if type(self.offset) is not int or not 0 <= self.offset <= 1000000:
            raise ValueError('Invalid console rotation offset')
        cursor = rewards.directory / 'cs2_gc_console.txt'
        old = cursor.read_text().split() if cursor.exists() else []
        rewards.state.setdefault('console_stars', int(old[1]) if len(old) == 3 and old[1].isdigit() else 0)
        if type(rewards.state['console_stars']) is not int or not 0 <= rewards.state['console_stars'] <= (1 << 64) - 1:
            raise ValueError('Invalid console star cursor')
        # The game prints echo output as '[Console] <text>', so the line may carry a tag before the code. The code is a
        # random per-launch value; the line must end right after the command, so an echoed alias definition (which ends
        # in a quote) or another command never matches.
        self.pattern = re.compile(rb'(?:^|[\]\s])CS2GC_' + self.nonce.encode() + rb' (stars (100|1000)|rotate)$')
        self.polls = 0
        self.warned = set()
        print(f"Console controls watching {self.log} (exists={self.log.exists()}, size={self.position}); "
              "test commands need the game started with -condebug and 'exec cs2_gc_console' run once", flush=True)
        self.publish()
        text = ('// Local offline controls. Launch with -insecure -condebug. Execute once per game launch.\n'
                'setinfo cs2_gc_rotation_offset 0\n'
                f'alias cs2_gc_give_stars "echo CS2GC_{self.nonce} stars 100"\n'
                f'alias cs2_gc_give_stars_1000 "echo CS2GC_{self.nonce} stars 1000"\n'
                f'alias cs2_gc_force_rotation "incrementvar cs2_gc_rotation_offset 0 1000000 1; echo CS2GC_{self.nonce} rotate"\n'
                'echo Local GC commands loaded: cs2_gc_give_stars, cs2_gc_give_stars_1000, cs2_gc_force_rotation\n')
        atomic_write(Path(cfg_dir) / 'cs2_gc_console.cfg', text)

    def publish(self):
        self.rewards.state['console_pid'] = self.pid
        self.rewards.state['console_rotation'] = self.offset
        self.rewards.save()
        atomic_write(self.rewards.directory / 'cs2_gc_console.txt',
                     f"{self.pid} {self.rewards.state['console_stars']} {self.offset}\n")

    def warn_once(self, key, message):
        if key not in self.warned:
            self.warned.add(key)
            print('Console controls: ' + message, flush=True)

    def poll(self):
        self.polls += 1
        if not self.log.exists():
            if self.polls >= 60:
                self.warn_once('missing', f'{self.log} does not exist after a minute; launch CS2 with -condebug '
                               '(cs2_gc_debug.exe does this) or the commands cannot reach the helper')
            return
        size = self.log.stat().st_size
        if size < self.position:
            self.position = 0; self.pending = b''
        with self.log.open('rb') as source:
            source.seek(self.position)
            data = source.read(1024 * 1024)
            self.position = source.tell()
        lines = (self.pending + data).split(b'\n')
        self.pending = lines.pop()
        # Bound malformed / enormous non-command log lines.
        if len(self.pending) > 4096: self.pending = b'!'
        changed = False
        for line in lines:
            match = self.pattern.search(line.rstrip(b'\r'))
            if not match:
                if b'CS2GC_' in line:
                    self.warn_once('nonce', 'saw a command line with a different launch code; an alias from an '
                                   'earlier launch is still defined. Run exec cs2_gc_console again, or restart CS2 via '
                                   'cs2_gc_debug.exe')
                continue
            if match[1] == b'rotate': self.offset = min(1000000, self.offset + 1)
            else: self.rewards.state['console_stars'] = min((1 << 64) - 1, self.rewards.state['console_stars'] + int(match[2]))
            changed = True
        if changed:
            self.publish()
            print(f"Console controls: test stars total={self.rewards.state['console_stars']}, rotation offset={self.offset}", flush=True)

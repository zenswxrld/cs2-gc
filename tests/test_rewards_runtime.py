import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from rewards_runtime import InstanceLock, ParentProcess


class BackgroundRewards(unittest.TestCase):
    def test_lock_released_and_manual_mode_has_no_parent(self):
        with tempfile.TemporaryDirectory() as folder:
            with InstanceLock(folder) as first:
                self.assertTrue(first)
                with InstanceLock(folder) as second:
                    self.assertFalse(second)
            with InstanceLock(folder) as third:
                self.assertTrue(third)
        self.assertTrue(ParentProcess().alive())
        with self.assertRaises(ValueError): ParentProcess(0)

    def test_real_helper_stops_with_parent_and_second_instance_cannot_pay(self):
        with tempfile.TemporaryDirectory(prefix='cs2 rewards with spaces ') as folder:
            directory = Path(folder)
            cfg = directory / 'cfg'
            cfg.mkdir()
            with socket.socket() as reserve:
                reserve.bind(('127.0.0.1', 0))
                port = reserve.getsockname()[1]
            parent = subprocess.Popen([sys.executable, '-c', 'import sys; sys.stdin.read()'], stdin=subprocess.PIPE)
            command = [sys.executable, str(ROOT / 'tools/gsi_rewards.py'), '--proxy-dir', str(directory),
                       '--cfg-dir', str(cfg), '--port', str(port), '--parent-pid', str(parent.pid),
                       '--log-file', str(directory / 'rewards.log')]
            child = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            try:
                deadline = time.monotonic() + 10
                state_path = directory / 'cs2_gc_gsi_state.json'
                while not state_path.exists():
                    if child.poll() is not None:
                        self.fail('Helper failed: ' + child.stderr.read().decode())
                    if time.monotonic() > deadline: self.fail('Helper did not start')
                    time.sleep(.02)
                state = json.loads(state_path.read_text())
                original = state_path.read_bytes()
                duplicate = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
                self.assertEqual(duplicate.returncode, 0)
                self.assertEqual(state_path.read_bytes(), original)
                self.assertIn('already running', duplicate.stdout.decode())
                packet = {'auth': {'token': state['token']},
                          'provider': {'appid': 730, 'steamid': 'test', 'timestamp': 1},
                          'map': {'name': 'de_test', 'phase': 'live', 'round': 0},
                          'player': {'steamid': 'test', 'team': 'T', 'activity': 'playing',
                                     'match_stats': {'kills': 0, 'mvps': 0}, 'state': {'round_killhs': 0}}}
                def post():
                    request = Request(f'http://127.0.0.1:{port}/', json.dumps(packet).encode(), {'Content-Type': 'application/json'})
                    with urlopen(request, timeout=3) as response: self.assertEqual(response.status, 200)
                post()
                packet['player']['match_stats']['kills'] = 1
                post(); post()
                self.assertEqual(json.loads(state_path.read_text())['total'], 5)
                parent.stdin.close()
                parent.wait(timeout=3)
                self.assertEqual(child.wait(timeout=5), 0)
                self.assertIn('rewards helper stopped', (directory / 'rewards.log').read_text())
                self.assertEqual((directory / 'cs2_gc_rewards.txt').read_text().strip(), '5')
                self.assertTrue((cfg / 'gamestate_integration_cs2_gc.cfg').exists())
                with InstanceLock(directory) as released: self.assertTrue(released)
            finally:
                if parent.poll() is None: parent.kill(); parent.wait()
                if parent.stdin and not parent.stdin.closed: parent.stdin.close()
                if child.poll() is None: child.kill(); child.wait()
                child.stderr.close()

    def test_port_in_use_does_not_create_or_change_reward_state(self):
        with tempfile.TemporaryDirectory() as folder, socket.socket() as occupied:
            occupied.bind(('127.0.0.1', 0)); occupied.listen()
            result = subprocess.run([sys.executable, str(ROOT / 'tools/gsi_rewards.py'), '--proxy-dir', folder,
                                     '--port', str(occupied.getsockname()[1]), '--log-file', str(Path(folder) / 'rewards.log')],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((Path(folder) / 'cs2_gc_gsi_state.json').exists())


if __name__ == '__main__': unittest.main()

#!/usr/bin/env python3
"""Local CS2 gameplay -> cumulative XP bridge. Standard library only; bot matches included.

Run beside the local proxy, with --cfg-dir pointing at game/csgo/cfg once.
Never writes the inventory: the proxy owns the atomic profile/pass/credit save.
"""
import argparse
import hmac
import json
import os
from pathlib import Path
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer

MAX_TOTAL = (1 << 64) - 1


def integer(value, default=0):
    return value if type(value) is int and value >= 0 else default


def atomic_text(path, text):
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w', encoding='utf-8', newline='\n') as output:
        output.write(text)
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(path)


class Rewards:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.path = self.directory / 'cs2_gc_gsi_state.json'
        if self.path.exists():
            self.state = json.loads(self.path.read_text(encoding='utf-8'))
            if (not isinstance(self.state, dict) or not isinstance(self.state.get('token'), str)
                    or not self.state['token'] or type(self.state.get('total')) is not int
                    or not 0 <= self.state['total'] <= MAX_TOTAL):
                raise ValueError('Invalid GSI state; refusing to overwrite it')
        else:
            # Preserve the cumulative cursor if the bridge state alone was removed.
            cursor = self.directory / 'cs2_gc_rewards.txt'
            total = int(cursor.read_text().strip()) if cursor.exists() else 0
            if not 0 <= total <= MAX_TOTAL:
                raise ValueError('Invalid reward cursor')
            self.state = {'token': secrets.token_hex(32), 'total': total, 'last': None}
        self.save()

    def save(self):
        # Commit deduplication and cumulative XP together before publishing the cursor.
        atomic_text(self.path, json.dumps(self.state, separators=(',', ':')) + '\n')
        atomic_text(self.directory / 'cs2_gc_rewards.txt', str(self.state['total']) + '\n')

    def accept(self, packet):
        if not isinstance(packet, dict):
            return False
        auth = packet.get('auth') or {}
        if not isinstance(auth, dict) or not isinstance(auth.get('token'), str):
            return False
        if not hmac.compare_digest(auth['token'], self.state['token']):
            return False
        provider, player, game_map = (packet.get(k) or {} for k in ('provider', 'player', 'map'))
        if not all(isinstance(v, dict) for v in (provider, player, game_map)):
            return False
        # Spectating a bot must not turn the bot's kills into the local player's rewards.
        if (provider.get('appid') != 730 or not provider.get('steamid')
                or player.get('steamid') != provider['steamid']
                or player.get('team') not in ('T', 'CT') or player.get('activity') != 'playing'):
            return True
        stats, state = player.get('match_stats') or {}, player.get('state') or {}
        if not isinstance(stats, dict) or not isinstance(state, dict):
            return False
        if not all(type(stats.get(k)) is int and stats[k] >= 0 for k in ('kills', 'mvps')):
            return True
        timestamp = integer(provider.get('timestamp'))
        last = self.state.get('last')
        current = {'player': provider['steamid'], 'map': game_map.get('name'),
                   'round': integer(game_map.get('round')), 'phase': game_map.get('phase'),
                   'kills': stats['kills'], 'mvps': stats['mvps'],
                   'headshots': integer(state.get('round_killhs')), 'timestamp': timestamp,
                   'finished': False}
        if last and timestamp < last['timestamp']:
            return True
        earned = 0
        same = (last and current['player'] == last['player'] and current['map'] == last['map']
                and current['round'] >= last['round'] and current['kills'] >= last['kills']
                and current['mvps'] >= last['mvps'])
        if same and current['phase'] in ('live', 'gameover') and last['phase'] == 'live':
            earned += (current['kills'] - last['kills']) * 5
            earned += (current['mvps'] - last['mvps']) * 25
            old_hs = last['headshots'] if current['round'] == last['round'] else 0
            earned += max(0, current['headshots'] - old_hs) * 3
            if current['phase'] == 'gameover' and not last.get('finished'):
                earned += 600
        if same and current['phase'] == 'gameover':
            current['finished'] = True
        # First snapshot/reconnect/restart only establishes a baseline, never pays old scoreboard stats.
        self.state['last'] = current
        self.state['total'] = min(MAX_TOTAL, self.state['total'] + earned)
        self.save()
        return True


def config_text(token, port):
    return f'''"CS2 GC local progression"
{{
    "uri" "http://127.0.0.1:{port}/"
    "timeout" "5.0"
    "buffer" "0.1"
    "throttle" "0.1"
    "heartbeat" "5.0"
    "auth" {{ "token" "{token}" }}
    "data"
    {{
        "provider" "1"
        "map" "1"
        "player_id" "1"
        "player_state" "1"
        "player_match_stats" "1"
    }}
}}
'''


def handler_for(rewards):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 262144:
                    self.send_error(413)
                    return
                packet = json.loads(self.rfile.read(length))
                accepted = rewards.accept(packet)
                self.send_response(200 if accepted else 403)
                self.send_header('Content-Length', '0')
                self.end_headers()
            except (ValueError, TypeError, KeyError):
                self.send_error(400)
            except OSError:
                # Failure must be retryable; never acknowledge an unpersisted reward.
                self.send_error(503)

        def log_message(self, *_):
            pass  # Payloads contain local Steam identifiers; do not log them.
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proxy-dir', type=Path, required=True, help='Directory containing the local proxy DLL')
    parser.add_argument('--cfg-dir', type=Path, help='Install only gamestate_integration_cs2_gc.cfg here, then restart CS2')
    parser.add_argument('--port', type=int, default=31923)
    args = parser.parse_args()
    if not args.proxy_dir.is_dir() or not 1 <= args.port <= 65535:
        parser.error('Use an existing proxy directory and a valid port')
    rewards = Rewards(args.proxy_dir)
    if args.cfg_dir:
        if not args.cfg_dir.is_dir():
            parser.error('--cfg-dir must be the existing game/csgo/cfg directory')
        atomic_text(args.cfg_dir / 'gamestate_integration_cs2_gc.cfg', config_text(rewards.state['token'], args.port))
    with HTTPServer(('127.0.0.1', args.port), handler_for(rewards)) as server:
        server.timeout = 5
        print('Local CS2 XP bridge listening. Keep this window open while playing bot matches.')
        server.serve_forever()


if __name__ == '__main__':
    main()

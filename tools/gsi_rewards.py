#!/usr/bin/env python3
"""Local CS2 gameplay -> cumulative XP bridge. Standard library only; bot matches included.

Run beside the local proxy, with --cfg-dir pointing at game/csgo/cfg once.
Never writes the inventory: the proxy owns the atomic profile/pass/credit save.
"""
import argparse
import hmac
import json
import os
import lzma
import struct
from pathlib import Path
import secrets
import time
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gameplay_config import load as load_gameplay
from console_controls import ConsoleControls
import premier_rating
from native_tradeups import prepare as prepare_native_tradeups
from rotate_armory import prepare as prepare_armory_rotation
from native_scoreboard import prepare as prepare_native_scoreboard
from native_store import prepare as prepare_native_store
from skip_container_confirm import prepare as prepare_container_confirm
from rewards_runtime import InstanceLock, ParentProcess, serve_until_parent_exits
import contextlib
import traceback
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
        self.config = load_gameplay(self.directory)
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
        match_cursor = self.directory / 'cs2_gc_matches.txt'
        if 'matches' not in self.state:
            self.state['matches'] = int(match_cursor.read_text().strip()) if match_cursor.exists() else 0
        if type(self.state['matches']) is not int or not 0 <= self.state['matches'] <= MAX_TOTAL:
            raise ValueError('Invalid completed-match counter')
        self.state.setdefault('premier', premier_rating.initial(self.config))
        premier = self.state['premier']
        if not isinstance(premier, dict) or any(type(premier.get(key)) is not int or premier[key] < 0
                for key in ('rating', 'wins', 'losses', 'ties')) or premier['rating'] > 99999:
            raise ValueError('Invalid local Premier state')
        self.last_received = None
        self.save()

    def save(self):
        # Commit deduplication and cumulative XP together before publishing the cursor.
        atomic_text(self.path, json.dumps(self.state, separators=(',', ':')) + '\n')
        atomic_text(self.directory / 'cs2_gc_rewards.txt', str(self.state['total']) + '\n')
        atomic_text(self.directory / 'cs2_gc_matches.txt', str(self.state['matches']) + '\n')
        if self.config['premier_enabled']:
            rank = self.state['premier']
            atomic_text(self.directory / 'cs2_gc_premier.txt',
                        f"{rank['rating']} {rank['wins']} {self.config['premier_placement_wins']}\n")

    def accept(self, packet):
        if not isinstance(packet, dict):
            return False
        auth = packet.get('auth') or {}
        if not isinstance(auth, dict) or not isinstance(auth.get('token'), str):
            return False
        if not hmac.compare_digest(auth['token'], self.state['token']):
            return False
        if self.last_received is None:
            print('Game data received. Waiting for local-player live match statistics.', flush=True)
        self.last_received = time.monotonic()
        provider, player, game_map = (packet.get(k) or {} for k in ('provider', 'player', 'map'))
        if not all(isinstance(v, dict) for v in (provider, player, game_map)):
            return False
        # Spectating a bot must not turn the bot's kills into the local player's rewards.
        if (provider.get('appid') != 730 or not provider.get('steamid')
                or player.get('steamid') != provider['steamid']
                or player.get('team') not in ('T', 'CT')
                or (player.get('activity') != 'playing' and game_map.get('phase') != 'gameover')):
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
            earned += (current['kills'] - last['kills']) * self.config['kill_xp']
            earned += (current['mvps'] - last['mvps']) * self.config['mvp_xp']
            old_hs = last['headshots'] if current['round'] == last['round'] else 0
            earned += max(0, current['headshots'] - old_hs) * self.config['headshot_xp']
            if current['phase'] == 'gameover' and not last.get('finished'):
                earned += self.config['match_complete_xp']
                self.state['matches'] = min(MAX_TOTAL, self.state['matches'] + 1)
                result = premier_rating.outcome(game_map, player.get('team'))
                if result and self.config['premier_enabled']:
                    self.state['premier'] = premier_rating.apply(self.state['premier'], result, self.config)
                    print(premier_rating.status(self.state['premier'], self.config), flush=True)
        if same and current['phase'] == 'gameover':
            current['finished'] = True
        # First snapshot/reconnect/restart only establishes a baseline, never pays old scoreboard stats.
        self.state['last'] = current
        self.state['total'] = min(MAX_TOTAL, self.state['total'] + earned)
        self.save()
        if earned:
            print(f"Earned {earned} XP; total {self.state['total']}; completed matches {self.state['matches']}.", flush=True)
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
    parser.add_argument('--parent-pid', type=int, help='Exit when the launching game process closes')
    parser.add_argument('--log-file', type=Path, help='Write diagnostics here instead of a console window')
    args = parser.parse_args()
    if (not args.proxy_dir.is_dir() or not 1 <= args.port <= 65535
            or (args.parent_pid is not None and args.parent_pid <= 0)):
        parser.error('Use an existing proxy directory and a valid port')
    with InstanceLock(args.proxy_dir) as acquired:
        if not acquired:
            if sys.stdout:
                print('Rewards helper is already running for this game directory.')
            return
        if args.log_file:
            # No tokens or packet payloads are logged. Rotate just this helper's diagnostic log.
            if args.log_file.exists() and args.log_file.stat().st_size > 1024 * 1024:
                args.log_file.replace(args.log_file.with_suffix('.previous.log'))
            with args.log_file.open('a', encoding='utf-8', buffering=1) as output:
                with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                    try:
                        run(args)
                    except Exception:
                        traceback.print_exc()
                        raise SystemExit(1)
        else:
            run(args)


def run(args):
    parent = ParentProcess(args.parent_pid)
    try:
        if not parent.alive():
            return
        run_with_parent(args, parent)
    finally:
        parent.close()


def run_with_parent(args, parent):
    # Bind before loading/writing state: another (including older) helper may own this port.
    with HTTPServer(('127.0.0.1', args.port), BaseHTTPRequestHandler) as server:
        rewards = Rewards(args.proxy_dir)
        if args.cfg_dir:
            if not args.cfg_dir.is_dir():
                raise ValueError('--cfg-dir must be the existing game/csgo/cfg directory')
            config_path = args.cfg_dir / 'gamestate_integration_cs2_gc.cfg'
            content = config_text(rewards.state['token'], args.port)
            if not config_path.exists() or config_path.read_text(encoding='utf-8') != content:
                atomic_text(config_path, content)
                print('GSI config installed/updated. If this is the first setup, restart CS2 once to load it.', flush=True)
        try:
            native_status = prepare_native_tradeups(args.proxy_dir, bool(rewards.config['mixed_stattrak_tradeups']), rewards.config)
            print('Native trade-up UI: ' + native_status, flush=True)
        except (OSError, ValueError, KeyError) as error:
            # A changed schema or missing game file must not stop earned XP/stars.
            print('Native trade-up UI setup skipped: ' + str(error), flush=True)
        try:
            print('Native Armory rotation: ' + prepare_armory_rotation(args.proxy_dir, rewards.config), flush=True)
        except (OSError, ValueError, KeyError) as error:
            print('Native Armory rotation setup skipped: ' + str(error), flush=True)
        try:
            print('Native Premier scoreboard: ' + prepare_native_scoreboard(args.proxy_dir, rewards.config), flush=True)
        except (OSError, ValueError, KeyError) as error:
            print('Native Premier scoreboard setup skipped: ' + str(error), flush=True)
        try:
            print('Native terminal Store: ' + prepare_native_store(args.proxy_dir, rewards.config), flush=True)
        except (OSError, ValueError, KeyError, EOFError, lzma.LZMAError, struct.error) as error:
            print('Native terminal Store setup skipped: ' + str(error), flush=True)
        try:
            print('Native container confirmation: ' + prepare_container_confirm(args.proxy_dir, rewards.config), flush=True)
        except (OSError, ValueError, KeyError) as error:
            print('Native container confirmation setup skipped: ' + str(error), flush=True)
        server.RequestHandlerClass = handler_for(rewards)
        if args.cfg_dir and rewards.config['premier_enabled']:
            difficulty_path = args.cfg_dir / 'cs2_gc_premier_bots.cfg'
            last_difficulty = [-1]
            def write_difficulty():
                difficulty = premier_rating.bot_difficulty(rewards.state['premier'])
                if difficulty == last_difficulty[0]: return
                atomic_text(difficulty_path, '// Local Premier bot difficulty; execute before spawning bots.\n'
                            + f'bot_difficulty {difficulty}\n')
                last_difficulty[0] = difficulty
            write_difficulty()
            print('Local Premier bot config prepared. In the local server console: exec cs2_gc_premier_bots', flush=True)
        print('Local CS2 rewards bridge running' + (' in background; exits with CS2.' if args.parent_pid else ' in manual diagnostic mode.'), flush=True)
        console = ConsoleControls(rewards, args.cfg_dir, args.parent_pid) if args.cfg_dir and args.parent_pid else None
        if console: print('Console controls prepared: launch with -condebug, then exec cs2_gc_console in game.', flush=True)
        next_status = [time.monotonic() + 30]
        def after_request():
            if console: console.poll()
            if args.cfg_dir and rewards.config['premier_enabled']:
                write_difficulty()
            if time.monotonic() < next_status[0]: return
            next_status[0] = time.monotonic() + 30
            if rewards.last_received is None:
                print('Waiting for CS2: restart the game after starting this helper; then enter a bot match.', flush=True)
            elif time.monotonic() - rewards.last_received > 30:
                print('No game data for 30 seconds. Check that CS2 is running with the installed GSI config.', flush=True)

        serve_until_parent_exits(server, parent, after_request)
        print('CS2 closed; rewards helper stopped.', flush=True)


if __name__ == '__main__':
    main()

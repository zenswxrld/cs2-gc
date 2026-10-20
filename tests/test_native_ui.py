from pathlib import Path
import copy
import json
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import native_resources as resources
import native_scoreboard as scoreboard
import native_store
import gameplay_config
import price_sheet
import skip_container_confirm
from test_native_tradeups import GAMEINFO
from test_price_sheet import SHEET, tool as fixture_sheet

SOURCE = '''// FindChildTraverse('jsRatingEmblem')
function draw(oPlayer, stat) {
 switch (stat) {
 case 'skillgroup': {
  oPlayer.fallback = true;
  const old = oPlayer.GetGameStat('comp_ranking');
  const type = oPlayer.GetGameStat('comp_type');
  const options = {};
  if (old > 0) RatingEmblem.SetXuid(options);
 } break;
 }
}
'''


def resource(source, other=True):
    # Fixture follows the independently documented header12/version4 resource layout.
    payload = source.encode() + b'\0'
    blocks = [(b'DATA', payload)]
    if other: blocks = [(b'REDI', b'keep original metadata'), (b'SrMa', b'old source mapping')] + blocks
    result = bytearray(struct.pack('<IHHII', 0, 12, 4, 8, len(blocks)) + bytes(12 * len(blocks)))
    for i, (kind, data) in enumerate(blocks):
        result.extend(bytes(-len(result) % 16))
        struct.pack_into('<4sII', result, 16 + 12 * i, kind, len(result) - (20 + 12 * i), len(data))
        result.extend(data)
    struct.pack_into('<I', result, 0, len(result))
    return bytes(result)


def resource_v2(source):
    # The installed game's compiled Panorama scripts (.vts_c): header 12 / version 2 with RED2, DATA and STAT blocks.
    blocks = [(b'RED2', b'resource edit info'), (b'DATA', source.encode() + b'\0'), (b'STAT', b'stats')]
    result = bytearray(struct.pack('<IHHII', 0, 12, 2, 8, len(blocks)) + bytes(12 * len(blocks)))
    for i, (kind, data) in enumerate(blocks):
        result.extend(bytes(-len(result) % 16))
        struct.pack_into('<4sII', result, 16 + 12 * i, kind, len(result) - (20 + 12 * i), len(data))
        result.extend(data)
    struct.pack_into('<I', result, 0, len(result))
    return bytes(result)


def vpk(directory, payload, split=False, preload=0, extension='vjs_c', folder='panorama/scripts'):
    small, remainder = payload[:preload], payload[preload:]
    archive = 0 if split else 0x7fff
    tree = (extension.encode() + b'\0' + folder.encode() + b'\0scoreboard\0' +
            struct.pack('<IHHIIH', zlib.crc32(payload), len(small), archive, 2, len(remainder), 0xffff) +
            small + b'\0\0\0')
    directory.write_bytes(struct.pack('<7I', 0x55aa1234, 2, len(tree), 0, 0, 0, 0) + tree +
                          (b'' if split else b'xx' + remainder))
    if split: directory.with_name('pak01_000.vpk').write_bytes(b'xx' + remainder)


class NativeUI(unittest.TestCase):
    def test_installed_vts_c_version2_resource_is_found_patched_and_keeps_its_layout(self):
        # The real game names these scripts .vts_c and writes resource version 2; the lookup and parser used to
        # insist on .vjs_c and version 4, so no native patch ever mounted.
        original = resource_v2(SOURCE)
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder) / 'pak01_dir.vpk'
            vpk(directory, original, extension='vts_c')
            found, actual = resources.vpk_file(directory, scoreboard.ASSET, aliases=True, with_path=True)
            self.assertEqual(actual, 'panorama/scripts/scoreboard.vts_c')
            self.assertEqual(found, original)
        changed = resources.patch_installed_script(original, actual,
            lambda source: scoreboard.patch(source, gameplay_config.DEFAULTS))
        blocks = dict(resources.script_blocks(changed))
        self.assertEqual(struct.unpack_from('<H', changed, 6)[0], 2)           # the file's own version is kept
        self.assertEqual(blocks[b'RED2'], b'resource edit info')              # other blocks are carried over
        self.assertEqual(blocks[b'STAT'], b'stats')
        self.assertIn(b'cs2_gc native Premier badges', blocks[b'DATA'])
        with self.assertRaises(ValueError):                                    # other versions are still refused
            resources.script_blocks(original[:6] + struct.pack('<H', 3) + original[8:])

    def test_raw_installed_js_alias_and_backslash_paths_are_not_compiled_resources(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder) / 'pak01_dir.vpk'
            vpk(directory, SOURCE.encode(), extension='js', folder='panorama\\scripts')
            original, actual = resources.vpk_file(directory, scoreboard.ASSET, aliases=True, with_path=True)
            self.assertEqual(actual, 'panorama/scripts/scoreboard.js')
            changed = resources.patch_installed_script(original, actual,
                lambda source: scoreboard.patch(source, gameplay_config.DEFAULTS))
            self.assertTrue(changed.startswith(b'//'))
            self.assertIn(b'cs2_gc native Premier badges', changed)
            self.assertNotEqual(changed, original)

    @unittest.skipUnless(shutil.which('node'), 'Node is optional for the executable confirmation fixture')
    def test_one_click_open_and_hidden_rent_apply_only_to_local_containers(self):
        source = '''
    function OpenConfirmPopup(type, itemId, contextPanel) {
        confirms++;
    }
    function _OnPopupActionPressed(actionType, contextPanel) { opens++; }
    function buttons(elRentalBar, itemId) {
            let RentBtn = elRentalBar.FindChildInLayoutFile('RentBtn');
    }
'''
        patched = skip_container_confirm.patch(source)
        script = patched + '''
const assert = require('assert'); let confirms = 0, opens = 0;
OpenConfirmPopup('open', '1000000000001', {}); assert.equal(opens, 1); assert.equal(confirms, 0);
OpenConfirmPopup('open', '50', {}); assert.equal(confirms, 1);
OpenConfirmPopup('rent', '1000000000001', {}); assert.equal(confirms, 2);
const rent = {visible:true}; const bar = {FindChildInLayoutFile:() => rent};
buttons(bar, '1000000000001'); assert.equal(rent.visible, false);
buttons(bar, '50'); assert.equal(rent.visible, true);
'''
        subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)
        self.assertEqual(skip_container_confirm.patch(source, False, False), source)

    def test_vpk_embedded_chunk_and_preload_crc_and_no_archive_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder) / 'pak01_dir.vpk'
            for split in (False, True):
                for preload in (0, 7):
                    vpk(directory, b'original script resource', split, preload)
                    before = directory.read_bytes()
                    self.assertEqual(resources.vpk_file(directory, scoreboard.ASSET), b'original script resource')
                    self.assertEqual(before, directory.read_bytes())
                    with self.assertRaises(ValueError): resources.vpk_file(directory, 'missing.vjs_c')
            chunk = directory.with_name('pak01_000.vpk')
            chunk.write_bytes(b'xxcorrupt')
            with self.assertRaises(ValueError): resources.vpk_file(directory, scoreboard.ASSET)

    def test_resource_patch_preserves_metadata_and_refuses_unknown_or_broken_layout(self):
        original = resource(SOURCE)
        result = resources.rewrite_script(original, lambda source: scoreboard.patch(source, gameplay_config.DEFAULTS))
        blocks = dict(resources.script_blocks(result))
        self.assertEqual(blocks[b'REDI'], b'keep original metadata')
        self.assertNotIn(b'SrMa', blocks)
        self.assertIn(b'cs2_gc native Premier badges', blocks[b'DATA'])
        bad = bytearray(original); struct.pack_into('<H', bad, 6, 3)
        for data in (bytes(bad), original[:-1], b'not a resource'):
            with self.assertRaises(ValueError): resources.rewrite_script(data, lambda source: source)
        with self.assertRaises(ValueError): scoreboard.patch('unknown client script', gameplay_config.DEFAULTS)

    def test_install_backup_disable_other_addons_and_external_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            game = Path(folder) / 'game'
            proxy = game / 'bin/win64'; proxy.mkdir(parents=True)
            info = game / 'csgo/gameinfo.gi'; info.parent.mkdir()
            info.write_text(GAMEINFO)
            directory = info.parent / 'pak01_dir.vpk'; vpk(directory, resource(SOURCE))
            old_archive = directory.read_bytes()
            self.assertIn('RESTART', scoreboard.prepare(proxy, gameplay_config.DEFAULTS))
            self.assertIn('installed', scoreboard.prepare(proxy, gameplay_config.DEFAULTS))
            self.assertEqual(directory.read_bytes(), old_archive)
            self.assertIn('Game csgo/addons/other_mod', info.read_text())
            config = dict(gameplay_config.DEFAULTS, premier_scoreboard=0)
            self.assertIn('disabled', scoreboard.prepare(proxy, config))
            self.assertEqual(info.read_text(), GAMEINFO)
            scoreboard.prepare(proxy, gameplay_config.DEFAULTS)
            target = game / scoreboard.FOLDER / scoreboard.ASSET
            target.write_bytes(b'edited by another tool')
            with self.assertRaises(ValueError): scoreboard.prepare(proxy, gameplay_config.DEFAULTS)
            self.assertEqual(target.read_bytes(), b'edited by another tool')

    @unittest.skipUnless(shutil.which('node'), 'Node is optional; required for executable Panorama UI fixture')
    def test_unranked_ranked_wins_changes_bot_badges_and_fallback_in_javascript(self):
        script = scoreboard.patch(SOURCE, gameplay_config.DEFAULTS) + '''
const assert = require('assert');
let score = 1000, wins = 0, mode = 'competitive', queued = false, calls = [];
const badge = { visible: false, IsValid: () => true };
const MyPersonaAPI = { GetXuid: () => 'me' };
const MockAdapter = { GetGameModeInternalName: () => mode, IsFakePlayer: id => id === 'bot' };
const GameStateAPI = { IsQueuedMatchmakingMode_Team: () => queued, IsDemoOrHltv: () => false };
const FriendsListAPI = { GetFriendCompetitiveRank: () => score, GetFriendCompetitiveWins: () => wins };
const RatingEmblem = { SetXuid: options => calls.push(options) };
const player = id => ({m_xuid:id, m_elPlayer:{m_elSkillGroup:badge}, m_oStats:{}, GetGameStat:() => -1});
let me = player('me'); draw(me, 'skillgroup');
assert.equal(badge.visible, true); assert.equal(calls.at(-1).leaderboard_details.score, 0);
wins = 1; draw(me, 'skillgroup'); assert.equal(calls.at(-1).leaderboard_details.matchesWon, 1);
assert.equal(calls.length, 2); // Wins changed even while still unranked: redraw.
score = 4000; wins = 10; draw(me, 'skillgroup');
assert.equal(calls.at(-1).leaderboard_details.score, 4000);
draw(player('bot'), 'skillgroup'); assert.equal(calls.at(-1).rating_type, 'Premier');
let other = player('other'); draw(other, 'skillgroup'); assert.equal(other.fallback, true);
queued = true; me = player('me'); draw(me, 'skillgroup'); assert.equal(me.fallback, true);
console.log('native badge fixture passed');
'''
        subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)

    def test_native_terminal_store_adds_missing_schema_entries_preserves_message_and_is_idempotent(self):
        source = '''"items_game" { "items" {
         "5176" { "name" "terminal_one" "attributes" { "volatile container" { "value" "1" } } }
         "5181" { "name" "terminal_two" "attributes" { "volatile container" { "value" "1" } } }
         "50" { "name" "ordinary" }
        } }'''
        tree = copy.deepcopy(SHEET)
        original = fixture_sheet.build_message(fixture_sheet.encode_kv(tree)) + price_sheet.write_field(6, 0, 7)
        original += price_sheet.write_field(9, 1, b'12345678')
        result, added = native_store.patch(original, source)
        self.assertEqual(added, 2)
        self.assertEqual(native_store.patch(result, source), (result, 0))
        changed = price_sheet.decode_kv(price_sheet.decompress(price_sheet.read_message(result)[2]))
        entries = price_sheet.section(changed, 'store', 'entries')
        self.assertEqual([name for name, _ in entries[-2:]], ['terminal_one', 'terminal_two'])
        self.assertNotIn('ordinary', dict(entries))
        self.assertIn((6, 0, 7), price_sheet.read_fields(result))
        self.assertIn((9, 1, b'12345678'), price_sheet.read_fields(result))
        self.assertEqual(price_sheet.section(changed, 'store', 'currencies'), price_sheet.section(tree, 'store', 'currencies'))
        self.assertEqual(price_sheet.section(changed, 'store', 'store_banner_layout'), price_sheet.section(tree, 'store', 'store_banner_layout'))


if __name__ == '__main__': unittest.main()

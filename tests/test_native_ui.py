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
function _GetPlayerRowForGameMode() {
        let mode = MockAdapter.GetGameModeInternalName(false);
        let skirmish = MockAdapter.GetGameModeInternalName(true);
        return 'snippet_scoreboard-classic__row--comp';
}
function draw(oPlayer, stat) {
 switch (stat) {
 case 'skillgroup': {
  oPlayer.fallback = true;
  const old = oPlayer.GetGameStat('comp_ranking');
  const type = oPlayer.GetGameStat('comp_type');
  const options = {};
  if (old > 0) RatingEmblem.SetXuid(options);
 } break;
 case 'ping': {
                    oPlayer.m_elPlayer?.SetHasClass('bot', oPlayer.GetGameStat('is_fake_player'));
                    let szCustomLabel = _GetCustomStatTextValue('ping', oPlayer);
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
    def test_offline_competitive_uses_the_premier_row_layout(self):
        patched = scoreboard.patch(SOURCE, gameplay_config.DEFAULTS)
        row = patched[patched.index('function _GetPlayerRowForGameMode'):patched.index('function draw')]
        self.assertIn("row--premier", row)
        self.assertIn("mode === 'competitive'", row)

    @unittest.skipUnless(shutil.which('node'), 'Node required for the scoreboard ping fixture')
    def test_bots_show_a_steady_fake_ping_instead_of_the_bot_tag(self):
        patched = scoreboard.patch(SOURCE, gameplay_config.DEFAULTS)
        script = patched + '''
const assert = require('assert');
const classes = {}, label = {SetHasClass: (name, on) => { classes['label:' + name] = on; }};
let shown = [];
function _GetCustomStatTextValue() { return null; }
function _GenericUpdateStatDirect(player, stat, value) { shown.push(value); }
function bot(fake) { return {m_xuid: fake ? '0' : '765', m_elPlayer: {SetHasClass: (name, on) => { classes[name] = on; }},
                     GetGameStat: name => name === 'is_fake_player' ? fake : name === 'slot' ? 3 : 0}; }
globalThis.elLabel = label;
for (let i = 0; i < 20; ++i) draw(bot(true), 'ping');
assert.equal(classes.bot, false);
assert.equal(classes['label:sb-row__cell--ping__label--bot'], false);
assert(shown.every(ping => ping >= 15 && ping <= 75));
assert.equal(new Set(shown).size, 1);  // rapid refreshes keep the same value
const realNow = Date.now; let clock = realNow();
Date.now = () => clock;
shown = [];
for (let i = 0; i < 200; ++i) { clock += 9000; draw(bot(true), 'ping'); }
Date.now = realNow;
assert(Math.max(...shown) - Math.min(...shown) <= 10);
for (let i = 1; i < shown.length; ++i) assert(Math.abs(shown[i] - shown[i - 1]) <= 2);
'''
        result = subprocess.run(['node', '-e', script.replace('const m_localBotSeed = Math.floor(Math.random() * 4294967296) >>> 0;', 'var m_localBotSeed = 7;')],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('_LocalBotPing', scoreboard.patch(SOURCE, dict(gameplay_config.DEFAULTS, bot_fake_ping=0)))

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
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True)
        self.assertEqual(result.returncode,0,result.stderr)
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
        script = 'Math.random = () => .314159;\n' + scoreboard.patch(SOURCE, gameplay_config.DEFAULTS) + '''
const assert = require('assert');
let score = 1000, wins = 0, mode = 'competitive', queued = false, calls = [];
const badge = { visible: false, IsValid: () => true };
const $ = { Msg: () => {} };
const MyPersonaAPI = { GetXuid: () => 'me' };
const MockAdapter = { GetGameModeInternalName: () => mode, IsFakePlayer: id => id.startsWith('bot') };
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
const bot = player('bot'); draw(bot, 'skillgroup'); assert.equal(calls.at(-1).rating_type, 'Premier');
const assigned = calls.at(-1).leaderboard_details.score;
assert.notEqual(assigned,4000); assert.ok(Math.abs(assigned-4000)<=1200);
score=4300; draw(bot,'skillgroup'); assert.equal(calls.at(-1).leaderboard_details.score,assigned);
draw(player('bot2'),'skillgroup'); assert.notEqual(calls.at(-1).leaderboard_details.score,assigned);
let other = player('other'); draw(other, 'skillgroup'); assert.equal(other.fallback, true);
queued = true; me = player('me'); draw(me, 'skillgroup'); assert.equal(me.fallback, true);
console.log('native badge fixture passed');
'''
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_store_removes_case_entries_and_tiles_while_retaining_terminal_and_other_goods(self):
        from test_price_sheet import ITEMS_GAME
        source=ITEMS_GAME
        tree=copy.deepcopy(SHEET)
        entries=price_sheet.section(tree,'store','entries')
        entries.append(('case_alias',[('item_link','crate_one'),('prices',[('USD',1)])]))
        original=fixture_sheet.build_message(fixture_sheet.encode_kv(tree))
        result,_=native_store.patch(original,source,terminals_enabled=False)
        changed=price_sheet.decode_kv(price_sheet.decompress(price_sheet.read_message(result)[2]))
        self.assertNotIn('case_alias',dict(price_sheet.section(changed,'store','entries')))
        self.assertNotIn('4001',dict(price_sheet.section(changed,'store','store_banner_layout')))
        self.assertIn('Name Tag',dict(price_sheet.section(changed,'store','entries')))
        self.assertEqual(native_store.patch(result,source,terminals_enabled=False),(result,0))

    def test_store_sells_the_schemas_chicken_feed_on_the_tools_tab(self):
        from test_price_sheet import ITEMS_GAME
        source=ITEMS_GAME.replace('"items"\n    {','"items"\n    { "4949" { "name" "chicken_feed" "item_class" "chicken_feed" }',1)
        self.assertNotEqual(source,ITEMS_GAME)
        original=fixture_sheet.build_message(fixture_sheet.encode_kv(copy.deepcopy(SHEET)))
        result,_=native_store.patch(original,source,terminals_enabled=False)
        changed=price_sheet.decode_kv(price_sheet.decompress(price_sheet.read_message(result)[2]))
        self.assertEqual(dict(dict(price_sheet.section(changed,'store','entries'))['chicken_feed'])['item_link'],'chicken_feed')
        self.assertEqual(dict(dict(price_sheet.section(changed,'store','store_banner_layout'))['4949'])['custom_format'],'single')
        self.assertEqual(native_store.patch(result,source,terminals_enabled=False),(result,0))

    def test_store_removes_all_key_tools_and_their_banner_rows(self):
        from test_price_sheet import ITEMS_GAME
        source=ITEMS_GAME.replace('"prefabs"\n    {', '"prefabs"\n    { "key_alias" { "prefab" "weapon_case_key" }').replace(
            '"items"\n    {','"items"\n    { "9900" { "name" "orphan_key" "prefab" "key_alias" }')
        tree=copy.deepcopy(SHEET)
        entries=price_sheet.section(tree,'store','entries')
        entries.append(('unlinked',[('item_link','orphan_key'),('prices',[('USD',1)])]))
        layout=price_sheet.section(tree,'store','store_banner_layout')
        layout.extend([('1203',[('custom_format','single')]),('9900',[('custom_format','single')])])
        original=fixture_sheet.build_message(fixture_sheet.encode_kv(tree))
        result,_=native_store.patch(original,source,terminals_enabled=False)
        changed=price_sheet.decode_kv(price_sheet.decompress(price_sheet.read_message(result)[2]))
        remaining=dict(price_sheet.section(changed,'store','entries'))
        self.assertNotIn('Weapon Case Key',remaining)
        self.assertNotIn('unlinked',remaining)
        self.assertIn('Name Tag',remaining)
        banners=dict(price_sheet.section(changed,'store','store_banner_layout'))
        self.assertNotIn('1203',banners);self.assertNotIn('9900',banners)
        self.assertEqual(native_store.patch(result,source,terminals_enabled=False),(result,0))

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


class OfferNumbers(unittest.TestCase):
    def test_first_offer_is_first_and_the_last_is_the_total(self):
        import native_offer_numbers, subprocess, shutil
        patched = native_offer_numbers.patch(native_offer_numbers.ANCHOR, 5)
        if not shutil.which('node'): self.skipTest('Node needed')
        script = 'var m_numOfferCounter = 0;\n' + patched + """
const assert = require('assert');
m_numOfferCounter = 4; assert.equal(_CurrentOfferNumber(), 1);
m_numOfferCounter = 3; assert.equal(_CurrentOfferNumber(), 2);
m_numOfferCounter = 0; assert.equal(_CurrentOfferNumber(), 5);
m_numOfferCounter = 9; assert.equal(_CurrentOfferNumber(), 1);
"""
        subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)


class WritePath(unittest.TestCase):
    def test_placeholder_is_the_first_game_path_and_stays_first(self):
        import native_resources, native_tradeups, tempfile
        with tempfile.TemporaryDirectory() as folder:
            game = Path(folder) / 'game'
            (game / 'csgo').mkdir(parents=True); (game / 'bin/win64').mkdir(parents=True)
            info = game / 'csgo/gameinfo.gi'
            native_tradeups.atomic_write(info, GAMEINFO)
            proxy = game / 'bin/win64'

            def first_game():
                search = native_tradeups.parse(native_tradeups.read_text(info)).one('GameInfo').one('FileSystem').one('SearchPaths')
                return next(node.value for node in search.children if node.key == 'Game')

            self.assertIn('RESTART', native_resources.ensure_first_game_path(proxy))
            self.assertEqual(first_game(), 'cs2_gc_first')
            self.assertTrue('installed' in native_resources.ensure_first_game_path(proxy))
            # Another override mounted later goes above it; the next run moves the placeholder back to the top.
            native_tradeups.atomic_write(info, native_tradeups.mount_gameinfo(
                native_tradeups.read_text(info), True, 'cs2_gc_offers', 'cs2_gc offers'))
            self.assertEqual(first_game(), 'cs2_gc_offers')
            native_resources.ensure_first_game_path(proxy)
            self.assertEqual(first_game(), 'cs2_gc_first')
            self.assertIn('keep this addon', native_tradeups.read_text(info))

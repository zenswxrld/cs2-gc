from pathlib import Path
import sys
import unittest
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import armory_rotation_catalog as catalog
import gameplay_config
import native_tradeups
import rotate_armory
from inventory_item import collect, parse

SCHEMA = '''"items_game" {
 "items" {
  "1" { "name" "crate_a" "prefab" "weapon_case_base" "associated_item" "3"
    "attributes" { "set supply crate series" { "value" "1" } } }
  "2" { "name" "crate_b" "prefab" "weapon_case_base" "associated_item" "3"
    "attributes" { "set supply crate series" { "value" "2" } } }
  "3" { "name" "key" }
  "4" { "name" "crate_sticker_pack_kat2014_01" }
  "5" { "name" "crate_sticker_pack_stockh2021_legends" }
  "6" { "name" "crate_sticker_pack_not_curated" }
  "7" { "name" "coupon - crate_sticker_pack_kat2014_01" }
 }
 "client_loot_lists" {
  "set_spy_tech" { "weapon_test" "1" }
  "set_graphic_design" { "weapon_test" "1" }
  "set_xpshop_wpn_01" { "weapon_test" "1" }
  "removed_items" { "public_list_contents" "1" "[cu_m4a1_howling]weapon_m4a1" "1" }
  "keychain_pack_a_lootlist" { "charm_a" "1" }
  "keychain_pack_b_lootlist" { "charm_b" "1" }
  "keychain_pack_a_rare" { "charm_a" "1" }
  "sticker_pack_a_lootlist" { "sticker_a" "1" }
  "sticker_pack_b_lootlist" { "sticker_b" "1" }
  "set_unrelated" { "weapon_test" "1" }
 }
 "seasonaloperations" { "11" { "redeemable_goods" "xpshop" "metadata" "keep"
  "operational_point_redeemable" { "item_name" "lootlist:set_spy_tech" "points" "4" }
  "operational_point_redeemable" { "item_name" "lootlist:keychain_pack_a_lootlist" "points" "3" }
 } }
}'''


class ArmoryRotation(unittest.TestCase):
    def test_only_catalogue_rows_change_and_all_slots_have_independent_pools(self):
        changed, slots = catalog.patch_catalogue(SCHEMA, gameplay_config.DEFAULTS)
        old, new = collect(parse(SCHEMA)), collect(parse(changed))
        self.assertEqual(old['items'], new['items'])
        self.assertEqual(old['client_loot_lists'], new['client_loot_lists'])
        campaign = native_tradeups.parse(changed).one('items_game').one('seasonaloperations').one('11')
        self.assertEqual(campaign.text('metadata'), 'keep')
        self.assertEqual(set(slots.values()), {'case', 'capsule', 'charm', 'sticker', 'collection', 'limited'})
        self.assertEqual({k for k, v in slots.items() if v == 'capsule'},
                         {'crate_sticker_pack_kat2014_01', 'crate_sticker_pack_stockh2021_legends'})
        self.assertEqual({k for k, v in slots.items() if v == 'charm'},
                         {'lootlist:keychain_pack_a_lootlist', 'lootlist:keychain_pack_b_lootlist'})
        self.assertNotIn('lootlist:set_unrelated', slots)
        self.assertEqual(catalog.patch_catalogue(changed, gameplay_config.DEFAULTS)[1], slots)
        disabled = dict(gameplay_config.DEFAULTS, armory_howl_enabled=0)
        self.assertNotIn('lootlist:removed_items', catalog.catalogue(SCHEMA, disabled))

    @unittest.skipUnless(shutil.which('node'), 'Node needed for executable timer fixture')
    def test_javascript_picks_one_from_each_pool_and_closes_stale_inspect(self):
        source = '''    const m_elContentPanel = root;
    function _UpdateShopGoods(m_nTrack) {
        aShopItemsData.forEach((element) => {
            _MakeShopTile(element);
            _MakeNavButton(element);
        });
    }
    function buy(ShopEntry) { MissionsAPI.ActionRedeemOperationGoods(m_nTrack, ShopEntry.shop_index, 1); }
'''
        categories = {'case_a': 'case', 'case_b': 'case', 'charm_a': 'charm', 'charm_b': 'charm', 'capsule': 'capsule'}
        script = '''const assert = require('assert'); let now = 0, closed = 0;
Date.now = () => now * 1000;
const tiles = {}, navs = {}; const label = {};
const parent = {FindChildInLayoutFile: () => label};
const root = {IsValid: () => true, FindChildInLayoutFile: id =>
 id === 'id-xpshop-top-nav' ? parent : tiles[id] || navs[id] || {}};
const GameInterfaceAPI = {GetSettingString: () => '0'};
const $ = {GetContextPanel: () => root, Schedule: () => 1, CancelScheduled: () => {}, DispatchEvent: () => {}};
const aShopItemsData = ['case_a', 'case_b', 'charm_a', 'charm_b', 'capsule'].map(item_name => ({item_name}));
function _MakeShopTile(e) { tiles[e.item_name] = {}; }
function _MakeNavButton(e) { navs[e.item_name + '-nav'] = {}; }
function _DeleteInspectGrid() { closed++; }
function _CancelTimeoutForRewardItem() {}
''' + rotate_armory.patch(source, gameplay_config.DEFAULTS, categories) + '''
_UpdateShopGoods(11);
const visible = () => Object.keys(tiles).filter(k => tiles[k].visible).sort();
assert.deepEqual(visible(), ['capsule', 'case_a', 'charm_a']);
now = 899; _LocalRotationRefresh(); assert.equal(closed, 0);
now = 900; _LocalRotationRefresh();
assert.deepEqual(visible(), ['capsule', 'case_b', 'charm_b']); assert.equal(closed, 1);
assert.equal(label.text, 'Armory refresh: 15:00');
now = 1800; _LocalRotationRefresh();
assert.deepEqual(visible(), ['capsule', 'case_a', 'charm_a']);
'''
        subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)


class ConsoleControls(unittest.TestCase):
    def test_launcher_nonce_is_reused_and_helper_restart_keeps_rotation(self):
        import tempfile
        from console_controls import ConsoleControls
        from gsi_rewards import Rewards
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); proxy = root / 'bin'; proxy.mkdir()
            cfg = root / 'csgo/cfg'; cfg.mkdir(parents=True)
            (proxy / 'cs2_gc_console_boot.txt').write_text('b' * 32 + '\n')
            control = ConsoleControls(Rewards(proxy), cfg, 100)
            self.assertEqual(control.nonce, 'b' * 32)
            control.offset = 3; control.publish()
            restarted = ConsoleControls(Rewards(proxy), cfg, 100)
            self.assertEqual(restarted.offset, 3)
            self.assertEqual(restarted.nonce, control.nonce)
            next_game = ConsoleControls(Rewards(proxy), cfg, 101)
            self.assertEqual(next_game.offset, 0)

    def test_exact_session_lines_partial_reads_and_restart_do_not_replay_grants(self):
        import tempfile
        from console_controls import ConsoleControls
        from gsi_rewards import Rewards
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            proxy = root / 'bin'; proxy.mkdir()
            cfg = root / 'csgo/cfg'; cfg.mkdir(parents=True)
            log = cfg.parent / 'console.log'
            log.write_bytes(b'old console history\n')
            rewards = Rewards(proxy)
            control = ConsoleControls(rewards, cfg, 100)
            prefix = 'CS2GC_' + control.nonce
            with log.open('ab') as output:
                output.write(('] alias x "echo ' + prefix + ' stars 100"\n' + prefix + ' stars 10\n' + prefix + ' stars 100').encode())
            control.poll()
            self.assertEqual(rewards.state['console_stars'], 0)
            with log.open('ab') as output:
                output.write(('\r\n' + prefix + ' rotate\n' + prefix + ' stars 1000\n').encode())
            control.poll(); control.poll()
            self.assertEqual(rewards.state['console_stars'], 1100)
            self.assertEqual((proxy / 'cs2_gc_console.txt').read_text().split(), ['100', '1100', '1'])
            restarted = ConsoleControls(Rewards(proxy), cfg, 101)
            restarted.poll()
            self.assertEqual(restarted.rewards.state['console_stars'], 1100)
            self.assertEqual(restarted.offset, 0)
            with log.open('ab') as output: output.write((prefix + ' stars 100\n').encode())
            restarted.poll()
            self.assertEqual(restarted.rewards.state['console_stars'], 1100)
            self.assertIn('cs2_gc_give_stars', (cfg / 'cs2_gc_console.cfg').read_text())


if __name__ == '__main__': unittest.main()

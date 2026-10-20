"""Prepare the installed native Armory script for matching per-category rotation."""
import argparse
import json
from pathlib import Path
from gameplay_config import load

ANCHOR = '        aShopItemsData.forEach((element) => {\n'
END = '''            _MakeNavButton(element);
        });'''
INSERT = '''    // Local GC Armory rotation: generated settings must match cs2_gc_gameplay.cfg.
    const m_localRotation = __SETTINGS__;
    let m_localRotationItems = [];
    let m_localRotationTick;
    let m_localRotationCycle = -1;
    let m_localRotationActive = [];
    function _LocalRotationRefresh() {
        const root = $.GetContextPanel();
        if (!root.IsValid()) return;
        const entries = m_localRotationItems.slice().sort((a, b) => a.item_name < b.item_name ? -1 : a.item_name > b.item_name ? 1 : 0);
        if (!entries.length || !m_localRotation.enabled) return;
        const now = Math.floor(Date.now() / 1000);
        const offset = parseInt(GameInterfaceAPI.GetSettingString('cs2_gc_rotation_offset')) || 0;
        const cycle = Math.floor(now / m_localRotation.seconds) + Math.max(0, Math.min(1000000, offset));
        const pools = {};
        entries.forEach(entry => {
            const slot = m_localRotation.categories[entry.item_name];
            if (slot) (pools[slot] || (pools[slot] = [])).push(entry);
        });
        const active = [];
        if (Object.keys(pools).length) {
            Object.keys(pools).sort().forEach(slot => {
                const pool = pools[slot];
                active.push(pool[cycle % pool.length].item_name);
            });
        } else {
            const count = Math.min(m_localRotation.slots, entries.length);
            const start = ((cycle % entries.length) * count) % entries.length;
            for (let i = 0; i < count; ++i) active.push(entries[(start + i) % entries.length].item_name);
        }
        entries.forEach(entry => {
            const show = active.indexOf(entry.item_name) !== -1;
            const tile = m_elContentPanel.FindChildInLayoutFile(entry.item_name);
            const nav = root.FindChildInLayoutFile(entry.item_name + '-nav');
            if (tile) {
                tile.visible = show;
                if (show && m_localRotation.categories[entry.item_name] === 'limited') {
                    const timer = tile.FindChildInLayoutFile('id-xpshop-tile-limitedtimer');
                    if (timer) timer.SetDialogVariable('limitedtimeleft', 'Refreshes with Armory');
                }
            }
            if (nav) nav.visible = show;
        });
        const parent = root.FindChildInLayoutFile('id-xpshop-top-nav');
        let label = parent.FindChildInLayoutFile('id-local-rotation-countdown');
        if (!label) label = $.CreatePanel('Label', parent, 'id-local-rotation-countdown');
        const remaining = m_localRotation.seconds - now % m_localRotation.seconds;
        m_localRotationActive = active;
        label.text = 'Armory refresh: ' + Math.floor(remaining / 60) + ':' + ('0' + remaining % 60).slice(-2);
        if (m_localRotationCycle !== -1 && m_localRotationCycle !== cycle) {
            _DeleteInspectGrid();
            _CancelTimeoutForRewardItem();
            const main = root.FindChildInLayoutFile('id-nav-show-main-tiles-btn');
            if (main) $.DispatchEvent('Activated', main, 'mouse');
        }
        m_localRotationCycle = cycle;
        m_localRotationTick = $.Schedule(1, _LocalRotationRefresh);
    }
'''


def patch(source, config, categories=None):
    if config['armory_howl_enabled'] and not categories:
        raise ValueError('Howl requires the matching generated native catalogue')
    if source.count(ANCHOR) != 1 or source.count(END) != 1 or 'const m_elContentPanel =' not in source:
        raise ValueError('Target xpshop.js differs from the inspected build')
    if 'm_localRotation' in source: raise ValueError('Source is already patched')
    settings = {'enabled': bool(config['armory_rotation_enabled']),
                'seconds': config['armory_rotation_seconds'], 'slots': config['armory_rotation_slots'],
                'categories': categories or {}}
    source = source.replace('    function _UpdateShopGoods(m_nTrack) {',
                            INSERT.replace('__SETTINGS__', json.dumps(settings)) + '    function _UpdateShopGoods(m_nTrack) {', 1)
    source = source.replace(END, END + '''
        m_localRotationItems = aShopItemsData;
        if (m_localRotationTick) $.CancelScheduled(m_localRotationTick);
        _LocalRotationRefresh();''', 1)
    purchase = 'MissionsAPI.ActionRedeemOperationGoods(m_nTrack, ShopEntry.shop_index,'
    if categories:
        if source.count(purchase) != 1: raise ValueError('Changed native Armory redemption handler')
        source = source.replace(purchase, "if (m_localRotation.enabled && m_localRotationActive.indexOf(ShopEntry.item_name) === -1) return;\n                " + purchase, 1)
        source = source.replace('element.items_in_row = itemsInRows[element.ui_order];', 'element.items_in_row = 1;')
        source = source.replace("elTile.SetDialogVariable('name', ShopEntry.callout ? $.Localize(ShopEntry.callout) : ShopEntry.item_name);",
            "elTile.SetDialogVariable('name', ShopEntry.callout ? $.Localize(ShopEntry.callout) : (ShopEntry.lootlist.length === 1 ? InventoryAPI.GetItemName(ShopEntry.lootlist[0]) : ShopEntry.item_name.replace('lootlist:', '')));")
    return source


def prepare(proxy_directory, config):
    from native_resources import install_override
    from native_tradeups import FOLDER, OWNER
    proxy = Path(proxy_directory)
    manifest = proxy.parent.parent / FOLDER / 'cs2_gc_native_manifest.json'
    categories = {}
    if config['armory_rotation_enabled']:
        data = json.loads(manifest.read_text(encoding='utf-8'))
        if data.get('owner') != OWNER or not data.get('armory_catalogue'):
            raise ValueError('Matching native Armory catalogue is not prepared')
        categories = data['armory_catalogue']
    return install_override(proxy, enabled=config['armory_rotation_enabled'], folder='cs2_gc_armory',
        comment='cs2_gc native armory', owner='cs2-gc-armory-ui-v1',
        asset='panorama/scripts/xpshop.vjs_c', patch=lambda source: patch(source, config, categories))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--proxy-dir', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = patch(args.source.read_text(encoding='utf-8'), load(args.proxy_dir))
    with args.out.open('x', encoding='utf-8', newline='\n') as output: output.write(result)

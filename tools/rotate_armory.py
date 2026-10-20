"""Prepare the installed native Armory script for matching per-category rotation."""
import argparse
import json
import re
from pathlib import Path
from gameplay_config import load

ANCHOR = '        aShopItemsData.forEach((element) => {\n'
END = '''            _MakeNavButton(element);
        });'''
INSERT = '''    // Local GC Armory rotation: generated settings must match cs2_gc_gameplay.cfg.
    const m_localRotation = __SETTINGS__;
    let m_localCategory = 'all';
    let m_localPage = 0;
    let m_localViewKey = '';
    function _LocalCatalogueControls() {
        const root = $.GetContextPanel();
        let bar = m_elContentPanel.FindChildInLayoutFile('cs2gc-category-bar');
        if (bar) return;
        bar = $.CreatePanel('Panel', m_elContentPanel, 'cs2gc-category-bar');
        bar.style.width = '100%'; bar.style.height = '40px';
        bar.style.flowChildren = 'right'; bar.style.verticalAlign = 'top';
        const categories = [['all','ALL'],['collection','COLLECTIONS'],['charm','CHARMS'],['sticker','STICKERS'],
            ['case','CASES'],['capsule','CAPSULES'],['limited','LIMITED'],['agent','AGENTS']];
        categories.forEach(pair => {
            const button = $.CreatePanel('Button', bar, 'cs2gc-category-' + pair[0]);
            button.style.padding = '8px 12px'; button.style.marginRight = '4px';
            const label = $.CreatePanel('Label', button, '', {text:pair[1]});
            label.style.fontSize = '17px'; label.style.fontFamily = 'Stratum2 Bold'; label.style.color = '#d9eeee';
            button.SetPanelEvent('onactivate', () => {
                m_localCategory = pair[0]; m_localPage = 0;
                m_elContentPanel.SetHasClass('xpshop-grids-visible', false);
                _LocalRotationRefresh();
            });
        });
        [['previous','<',-1],['next','>',1]].forEach(action => {
            const button = $.CreatePanel('Button', bar, 'cs2gc-page-' + action[0]);
            button.style.padding = '8px 12px';
            const label = $.CreatePanel('Label', button, '', {text:action[1]});
            label.style.fontSize = '18px'; label.style.color = '#ffffff';
            button.SetPanelEvent('onactivate', () => {m_localPage += action[2]; _LocalRotationRefresh();});
        });
        const page = $.CreatePanel('Label', bar, 'cs2gc-page-number');
        page.style.fontSize = '17px'; page.style.padding = '8px'; page.style.color = '#b8d3cc';
        const clock = $.CreatePanel('Label', bar, 'cs2gc-armory-clock');
        clock.style.fontSize = '17px'; clock.style.padding = '8px'; clock.style.color = '#e8d8a0';
        const row = m_elContentPanel.FindChildInLayoutFile('id-xpshop-row-1');
        if (row) {row.GetParent().style.marginTop = '44px'; row.GetParent().style.height = '94%';}
        $.Msg('cs2_gc Armory build 16: category controls mounted');
    }
    function _LocalCataloguePage(entries, active) {
        const groups = {};
        entries.filter(e => active.indexOf(e.item_name) !== -1 && (m_localCategory === 'all' ||
            m_localRotation.categories[e.item_name] === m_localCategory)).forEach(e => {
                const row = e.ui_order || '3'; (groups[row] || (groups[row] = [])).push(e);
            });
        const capacity = {'1':4,'2':3,'3':4};
        const pages = Math.max(1, ...Object.keys(groups).map(row => Math.ceil(groups[row].length / (capacity[row] || 4))));
        m_localPage = (m_localPage % pages + pages) % pages;
        const view = [];
        Object.keys(groups).forEach(row => {
            const count = capacity[row] || 4;
            // Rows with fewer pages retain their offers while longer rows page.
            const page = m_localPage % Math.ceil(groups[row].length / count);
            groups[row].slice(page * count, (page + 1) * count).forEach(e => view.push(e.item_name));
        });
        const bar = m_elContentPanel.FindChildInLayoutFile('cs2gc-category-bar');
        if (bar) {
            bar.FindChildInLayoutFile('cs2gc-page-number').text = (m_localPage + 1) + ' / ' + pages;
            bar.FindChildInLayoutFile('cs2gc-page-previous').enabled = pages > 1;
            bar.FindChildInLayoutFile('cs2gc-page-next').enabled = pages > 1;
            ['all','collection','charm','sticker','case','capsule','limited','agent'].forEach(category => {
                const button = bar.FindChildInLayoutFile('cs2gc-category-' + category);
                button.style.backgroundColor = m_localCategory === category ? '#347e7dbb' : '#173432bb';
            });
        }
        return view;
    }
    let m_localRotationItems = [];
    let m_localRotationTick;
    let m_localRotationCycle = -1;
    let m_localRotationActive = [];
    let m_localRotationLogged = -1;
    function _LocalRotationRefresh() {
        const root = $.GetContextPanel();
        if (!root.IsValid()) return;
        if (m_localRotationTick) $.CancelScheduled(m_localRotationTick);
        _LocalCatalogueControls();
        const entries = m_localRotationItems.slice().sort((a, b) => a.item_name < b.item_name ? -1 : a.item_name > b.item_name ? 1 : 0);
        if (!entries.length || !m_localRotation.enabled) return;
        const now = Math.floor(Date.now() / 1000);
        const offset = parseInt(GameInterfaceAPI.GetSettingString('cs2_gc_rotation_offset')) || 0;
        if (m_localRotationLogged !== offset) {
            m_localRotationLogged = offset;
            $.Msg('cs2_gc armory rotation hook: offset=' + offset + ' raw=[' + GameInterfaceAPI.GetSettingString('cs2_gc_rotation_offset') + ']');
        }
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
                const count = Math.min(m_localRotation.counts[slot] === undefined ? 1 : m_localRotation.counts[slot], pool.length);
                const start = ((cycle % pool.length) * count) % pool.length;
                for (let i = 0; i < count; ++i) active.push(pool[(start + i) % pool.length].item_name);
            });
        } else {
            const count = Math.min(m_localRotation.slots, entries.length);
            const start = ((cycle % entries.length) * count) % entries.length;
            for (let i = 0; i < count; ++i) active.push(entries[(start + i) % entries.length].item_name);
        }
        const view = _LocalCataloguePage(entries, active);
        entries.forEach(entry => {
            const show = view.indexOf(entry.item_name) !== -1;
            const tile = m_elContentPanel.FindChildInLayoutFile(entry.item_name);
            const nav = root.FindChildInLayoutFile(entry.item_name + '-nav');
            if (tile) {
                tile.visible = show;
                if (show && m_localRotation.categories[entry.item_name] === 'limited') {
                    const oldArt = tile.FindChildTraverse('id-xpshop-limited-item-carousel');
                    if (oldArt) oldArt.visible = false;
                    const actual = tile.FindChildInLayoutFile('id-xpshop-tile-single-image');
                    if (actual && entry.lootlist && entry.lootlist.length) {
                        actual.itemid = entry.lootlist[0]; actual.visible = true;
                    }
                    const timer = tile.FindChildInLayoutFile('id-xpshop-tile-limitedtimer');
                    if (timer) timer.SetDialogVariable('limitedtimeleft', 'Refreshes with Armory');
                }
            }
            if (nav) nav.visible = show;
        });
        const remaining = m_localRotation.seconds - now % m_localRotation.seconds;
        m_localRotationActive = active;
        const text = 'Armory refresh: ' + Math.floor(remaining / 60) + ':' + ('0' + remaining % 60).slice(-2);
        const bar = m_elContentPanel.FindChildInLayoutFile('cs2gc-category-bar');
        if (bar) bar.FindChildInLayoutFile('cs2gc-armory-clock').text = text;
        const parents = [root.FindChildInLayoutFile('id-xpshop-top-nav')];
        parents.forEach((parent, index) => {
            if (!parent) return;
            const id = index ? 'id-local-rotation-countdown-main' : 'id-local-rotation-countdown';
            let label = parent.FindChildInLayoutFile(id);
            if (!label) {
                label = $.CreatePanel('Label', parent, id);
                label.style.fontSize = index ? '18px' : '15px';
                label.style.color = '#e8d8a0';
                label.style.margin = index ? '6px 0px 0px 0px' : '0px 12px';
                if (index) { label.style.horizontalAlign = 'right'; label.style.marginTop = '8px'; }
                else { label.style.verticalAlign = 'center'; label.style.horizontalAlign = 'left'; label.style.marginLeft = '20px'; }
            }
            label.text = text;
        });
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


PREPARE = '''        // Resolve each tile from its own native row, without inherited thumbnails or shared model artwork.
        aShopItemsData.forEach(entry => {
            const slot = m_localRotation.categories[entry.item_name];
            if (slot === 'agent') {
                entry.lootlist = m_localRotation.agents.map(name => InventoryAPI.GetFauxItemIDFromDefAndPaintIndex(
                    InventoryAPI.GetItemDefinitionIndexFromDefinitionName(name), 0));
                entry.local_agent = true;
                entry.entry_type = 'lootlist'; entry.lootlist_item_type = 'agent';
                entry.tile_width = 160; entry.tile_height = 160;
            }
            if (!entry.callout && entry.lootlist && entry.lootlist.length === 1)
                entry.callout = InventoryAPI.GetItemName(entry.lootlist[0]);
        });
'''


def patch_previews(source):
    carousel = '''                    let elLimitedCarousel = $.CreatePanel('Carousel', elTile, '');
                    elLimitedCarousel.BLoadLayoutSnippet('limited-item-carousel');
                    elLimitedCarousel.hittest = false;
                    elLimitedCarousel.hittestchildren = false;'''
    source = source.replace(carousel, "                    elTile.FindChildInLayoutFile('id-xpshop-tile-single-image').itemid = ShopEntry.lootlist[0];", 1)
    # Avoid old map scenes retaining another entry's model: the inspect grid uses
    # the existing native InspectModelImage path for fixed/limited goods.
    grid = "                let elModel = elShopTile.FindChild('id-grid-item-model');"
    # An optional preview change must not disable rotation/catalogue controls.
    source = source.replace(grid, "                if (ShopEntry.local_agent) return;\n" + grid, 1)
    create = "    function CreateShopTile(elTilesContainer, itemId, ShopEntry) {"
    agent = '''
        if (ShopEntry.local_agent) {
            const panel = $.CreatePanel('Panel', elTilesContainer, itemId, {class:'xpshop__inspect-grid__tile'});
            panel.style.width = '160px'; panel.style.height = '160px';
            $.CreatePanel('ItemImage', panel, '', {itemid:itemId, style:'width:100%;height:100%;'});
            MakeShopTileInfoElements(panel, itemId, ShopEntry);
            return panel;
        }'''
    source = source.replace(create, create + agent, 1)
    source = source.replace('shuffledArray[iScrollingTile];', 'shuffledArray[iScrollingTile % shuffledArray.length];')
    # Rebind callbacks when stock UI reuses panels after a catalogue refresh.
    source = source.replace("        elTile.FindChildInLayoutFile('id-new-item-tag')", "        elTile.SetPanelEvent('onactivate', () => _UpdateInspectGrid(ShopEntry));\n        elTile.FindChildInLayoutFile('id-new-item-tag')", 1)
    nav_end = "    function _CancelTimeoutForRewardItem() {"
    nav_binding = "        elBtn.SetPanelEvent('onactivate', () => _UpdateInspectGrid(ShopEntry));\n"
    previous = "        }\n    }\n" + nav_end
    source = source.replace(previous, "        }\n" + nav_binding + "    }\n" + nav_end, 1)
    # Fallback icons are actual native item images, not guessed item-set SVG names.
    end = '''            _MakeNavButton(element);
        });'''
    icons = '''
            if (!element.ui_set_image && element.lootlist && element.lootlist.length) {
                const nav = $.GetContextPanel().FindChildInLayoutFile(element.item_name + '-nav');
                const stock = nav && nav.FindChild('id-xpshop-nav-btn-img');
                if (stock) stock.visible = false;
                if (nav && !nav.FindChild('local-item-icon'))
                    $.CreatePanel('ItemImage', nav, 'local-item-icon', {itemid:element.lootlist[0], style:'width:36px;height:36px;'});
            }'''
    source = source.replace(end, "            _MakeNavButton(element);" + icons + "\n        });", 1)
    route = '''
            const currentTile = m_elContentPanel.FindChildInLayoutFile(element.item_name);
            if (currentTile) currentTile.SetPanelEvent('onactivate', () => _UpdateInspectGrid(element));
            const currentNav = $.GetContextPanel().FindChildInLayoutFile(element.item_name + '-nav');
            if (currentNav) currentNav.SetPanelEvent('onactivate', () => _UpdateInspectGrid(element));
'''
    source = source.replace('            _MakeNavButton(element);', '            _MakeNavButton(element);' + route, 1)
    # Category controls remain visible while inspecting; switching categories returns to tiles.
    return source


def patch(source, config, categories=None, agents=None):
    if config['armory_howl_enabled'] and not categories:
        raise ValueError('Howl requires the matching generated native catalogue')
    if source.count(ANCHOR) != 1 or source.count(END) != 1 or 'const m_elContentPanel =' not in source:
        raise ValueError('Target xpshop.js differs from the inspected build')
    if 'm_localRotation' in source: raise ValueError('Source is already patched')
    settings = {'enabled': bool(config['armory_rotation_enabled']),
                'seconds': config['armory_rotation_seconds'], 'slots': config['armory_rotation_slots'],
                'categories': categories or {}, 'agents': agents or [],
                'counts': {slot: config.get('armory_' + slot + '_slots', 1) for slot in
                           ('collection', 'case', 'capsule', 'charm', 'sticker', 'limited', 'agent')}}
    source = source.replace('    function _UpdateShopGoods(m_nTrack) {',
                            INSERT.replace('__SETTINGS__', json.dumps(settings)) + '    function _UpdateShopGoods(m_nTrack) {', 1)
    source = source.replace(ANCHOR, PREPARE + ANCHOR, 1) if categories else source
    source = source.replace(END, END + '''
        m_localRotationItems = aShopItemsData;
        if (m_localRotationTick) $.CancelScheduled(m_localRotationTick);
        _LocalRotationRefresh();''', 1)
    purchase = 'MissionsAPI.ActionRedeemOperationGoods(m_nTrack, ShopEntry.shop_index,'
    if categories:
        if source.count(purchase) != 1: raise ValueError('Changed native Armory redemption handler')
        source = source.replace(purchase, "if (m_localRotation.enabled && m_localRotationActive.indexOf(ShopEntry.item_name) === -1) return;\n                " + purchase, 1)
        source = source.replace('element.items_in_row = itemsInRows[element.ui_order];', "element.items_in_row = element.ui_order === '2' ? 3 : 4;")
        source = patch_previews(source)
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
    from armory_rotation_catalog import agent_names
    agents = agent_names((proxy / 'items_game.txt').read_text(encoding='utf-8-sig')) if categories else []
    return install_override(proxy, enabled=config['armory_rotation_enabled'], folder='cs2_gc_armory',
        comment='cs2_gc native armory', owner='cs2-gc-armory-ui-v1',
        asset='panorama/scripts/xpshop.vjs_c', patch=lambda source: patch(source, config, categories, agents))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--proxy-dir', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = patch(args.source.read_text(encoding='utf-8'), load(args.proxy_dir))
    with args.out.open('x', encoding='utf-8', newline='\n') as output: output.write(result)

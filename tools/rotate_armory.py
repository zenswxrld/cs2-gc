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
    function _LocalOpenEntry(entry) {
        // The stock InventoryUpdate re-activates whichever tab button is checked. Check this entry's button too,
        // otherwise the next inventory update jumps back to an older tab.
        const nav = $.GetContextPanel().FindChildInLayoutFile(entry.item_name + '-nav');
        if (nav && nav.IsValid()) nav.checked = true;
        _LocalShowGrid(entry);
    }
    function _LocalShowGrid(entry) {
        // Never leave the previous tab's grid on screen when this entry's grid fails to build or refresh.
        try { _UpdateInspectGrid(entry); } catch (error) { $.Msg('cs2_gc armory: ' + entry.item_name + ': ' + error); }
        const container = m_elContentPanel.FindChildInLayoutFile('id-xpshop-inspect-container');
        if (container && container.FindChildInLayoutFile(entry.item_name + '-grid'))
            _UpdateVisibleInspectGrid(container, entry.item_name + '-grid');
    }
    function _LocalCatalogueControls() {
        const root = $.GetContextPanel();
        // One stock-style page (4 / 3 / 4); the bar under the green line only holds the countdown.
        let bar = m_elContentPanel.FindChildInLayoutFile('cs2gc-category-bar');
        if (bar) return;
        bar = $.CreatePanel('Panel', m_elContentPanel, 'cs2gc-category-bar');
        bar.style.width = '100%'; bar.style.height = '32px';
        bar.style.flowChildren = 'none'; bar.style.verticalAlign = 'top';
        const row = m_elContentPanel.FindChildInLayoutFile('id-xpshop-row-1');
        if (row) {row.GetParent().style.marginTop = '36px'; row.GetParent().style.height = '94%';}
        $.Msg('cs2_gc Armory: single 4/3/4 page mounted');
    }
    function _LocalCataloguePage(entries, active, cycle) {
        const offers = entries.filter(e => active.indexOf(e.item_name) !== -1);
        // One limited item takes the big tile; with several active ones it rotates instead of always the first by name.
        const limited = offers.filter(e => m_localRotation.categories[e.item_name] === 'limited');
        const featured = limited.length ? [limited[(cycle || 0) % limited.length]] : [];
        const groups = {};
        offers.filter(e => featured.indexOf(e) === -1).forEach(e => {
            const row = e.ui_order || '3'; (groups[row] || (groups[row] = [])).push(e);
        });
        Object.keys(groups).forEach(row => {
            const types = {};
            groups[row].forEach(entry => {
                const kind = m_localRotation.categories[entry.item_name] || 'other';
                (types[kind] || (types[kind] = [])).push(entry);
            });
            const kinds = Object.keys(types).sort(), ordered = [];
            const length = Math.max(...kinds.map(kind => types[kind].length));
            for (let index = 0; index < length; ++index)
                kinds.forEach(kind => {if (types[kind][index]) ordered.push(types[kind][index]);});
            groups[row] = ordered;
        });
        // A single stock-style page: 4 small / 3 large / 4 small. The limited item takes one of the 3 large slots.
        const capacity = {'1':4,'2':3,'3':4};
        const view = featured.map(e => e.item_name);
        Object.keys(groups).forEach(row => {
            const room = Math.max(0, (capacity[row] || 4) - featured.filter(e => (e.ui_order || '2') === row).length);
            groups[row].slice(0, room).forEach(e => view.push(e.item_name));
        });
        m_localFeatured = featured.length ? featured[0].item_name : null;
        return view;
    }
    function _LocalPlaceAgentTiles(container, entry) {
        const width = Math.floor(container.actuallayoutwidth / container.actualuiscale_x);
        const height = Math.floor(container.actuallayoutheight / container.actualuiscale_y) - 112; // reserve native purchase bar
        if (width <= 0 || height <= 0) return;
        const cards = container.Children().filter(panel => panel.Data().localAgentPreview);
        const columns = Math.min(4, Math.max(1, Math.floor(width / 228)));
        const areaHeight = Math.max(80, height - 174);
        const rows = Math.min(2, Math.max(1, Math.floor((areaHeight + 16) / 224)));
        const cardWidth = Math.min(212, Math.floor(width / columns) - 16);
        const cardHeight = Math.min(208, areaHeight);
        const capacity = columns * rows;
        const pages = Math.max(1, Math.ceil(cards.length / capacity));
        const data = container.Data();
        data.localAgentPage = ((data.localAgentPage || 0) % pages + pages) % pages;
        const first = data.localAgentPage * capacity;
        const visibleCount = Math.min(capacity, cards.length - first);
        const usedColumns = Math.min(columns, visibleCount);
        const usedRows = Math.ceil(visibleCount / columns);
        const left = (width - usedColumns * (cardWidth + 16) + 16) / 2;
        const top = 110 + Math.max(0, (areaHeight - usedRows * (cardHeight + 16) + 16) / 2);
        container.style.overflow = 'clip';
        cards.forEach((panel, index) => {
            const local = index - first;
            panel.visible = local >= 0 && local < capacity;
            if (!panel.visible) return;
            panel.style.width = cardWidth + 'px'; panel.style.height = cardHeight + 'px';
            panel.style.x = left + local % columns * (cardWidth + 16) + 'px';
            panel.style.y = top + Math.floor(local / columns) * (cardHeight + 16) + 'px';
        });
        let pager = container.FindChildInLayoutFile('cs2gc-agent-pages');
        if (!pager) {
            pager = $.CreatePanel('Panel', container, 'cs2gc-agent-pages');
            pager.style.width = '300px'; pager.style.height = '44px'; pager.style.flowChildren = 'right';
            ['previous','label','next'].forEach(kind => {
                if (kind === 'label') {
                    const label = $.CreatePanel('Label', pager, 'cs2gc-agent-page-number');
                    label.style.width = '204px'; label.style.fontSize = '20px';
                    label.style.textAlign = 'center'; label.style.verticalAlign = 'center'; label.style.color = '#d5e7e7';
                    return;
                }
                const button = $.CreatePanel('Button', pager, 'cs2gc-agent-' + kind);
                button.style.width = '48px'; button.style.height = '44px'; button.style.backgroundColor = '#315c60dd';
                const label = $.CreatePanel('Label', button, '', {text:kind === 'previous' ? '<' : '>'});
                label.style.fontSize = '30px'; label.style.color = '#ffffff';
                label.style.horizontalAlign = 'center'; label.style.verticalAlign = 'center';
                button.SetPanelEvent('onactivate', () => {
                    data.localAgentPage += kind === 'previous' ? -1 : 1;
                    _LocalPlaceAgentTiles(container, entry);
                });
            });
        }
        pager.style.x = (width - 300) / 2 + 'px'; pager.style.y = height - 48 + 'px';
        pager.FindChildInLayoutFile('cs2gc-agent-page-number').text = (first + 1) + '–' + (first + visibleCount) + ' / ' + cards.length;
        pager.FindChildInLayoutFile('cs2gc-agent-previous').enabled = pages > 1;
        pager.FindChildInLayoutFile('cs2gc-agent-next').enabled = pages > 1;
        const grid = m_elContentPanel.FindChildInLayoutFile(entry.item_name + '-grid');
        if (grid) {
            grid.SetDialogVariable('use-text', 'Recruit a random agent');
            grid.SetDialogVariable('desc-text', 'One random agent from the pool below.');
            grid.SetDialogVariable('confirm-text', 'Recruit one random agent?');
        }
    }
    let m_localRotationItems = [];
    let m_localFeatured = null;
    function _LocalCentreFeatured() {
        // After visibility is set: put the limited tile right after the first visible tile of its row (on screen),
        // so it is always the middle of the three large tiles.
        if (!m_localFeatured) return;
        const tile = m_elContentPanel.FindChildInLayoutFile(m_localFeatured);
        const parent = tile && tile.GetParent ? tile.GetParent() : null;
        if (!parent || !parent.Children || !parent.MoveChildAfter) return;
        const others = parent.Children().filter(child => child !== tile && child.visible);
        if (others.length) parent.MoveChildAfter(tile, others[0]);
    }
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
        const view = _LocalCataloguePage(entries, active, cycle);
        entries.forEach(entry => {
            const show = view.indexOf(entry.item_name) !== -1;
            const tile = m_elContentPanel.FindChildInLayoutFile(entry.item_name);
            const nav = root.FindChildInLayoutFile(entry.item_name + '-nav');
            if (tile) {
                tile.visible = show;
                if (show && entry.local_agent) {
                    const portraits = tile.FindChildInLayoutFile('id-xpshop-tile-carousel');
                    if (portraits) {
                        portraits.style.width = '55%'; portraits.style.horizontalAlign = 'right';
                        portraits.style.marginRight = '12px'; portraits.hittest = false; portraits.hittestchildren = false;
                        portraits.Children().forEach(image => {
                            image.style.width = '100%'; image.style.height = '100%';
                            image.style.horizontalAlign = 'right'; image.hittest = false;
                        });
                    }
                }
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
        _LocalCentreFeatured();
        const remaining = m_localRotation.seconds - now % m_localRotation.seconds;
        m_localRotationActive = active;
        const text = 'Armory refresh: ' + Math.floor(remaining / 60) + ':' + ('0' + remaining % 60).slice(-2);
        const bar = m_elContentPanel.FindChildInLayoutFile('cs2gc-category-bar');
        // One countdown, white, CS UI font, under the green line on the right of the arrow bar (it stays visible in tabs).
        if (bar) {
            let label = bar.FindChildInLayoutFile('id-local-rotation-countdown');
            if (!label) {
                label = $.CreatePanel('Label', bar, 'id-local-rotation-countdown');
                label.style.fontSize = '18px'; label.style.color = '#ffffff';
                label.style.horizontalAlign = 'right'; label.style.verticalAlign = 'center';
            }
            label.text = text;
            // Refresh button: the same console alias as cs2_gc_force_rotation, so the GC rotates with the page.
            if (!bar.FindChildInLayoutFile('cs2gc-refresh-armory')) {
                const button = $.CreatePanel('Button', bar, 'cs2gc-refresh-armory');
                button.style.horizontalAlign = 'left'; button.style.verticalAlign = 'center';
                button.style.height = '28px'; button.style.padding = '0px 14px';
                button.style.backgroundColor = '#2f6b55cc'; button.style.border = '1px solid #6fbf9a88';
                const caption = $.CreatePanel('Label', button, '', {text: 'REFRESH ARMORY'});
                caption.style.fontSize = '16px'; caption.style.color = '#ffffff'; caption.style.verticalAlign = 'center';
                button.SetPanelEvent('onactivate', () => {
                    // The alias tells the GC (its echo is counted by the helper); the page offset is set here directly
                    // because incrementvar on the setinfo variable only advanced once.
                    const next = (parseInt(GameInterfaceAPI.GetSettingString('cs2_gc_rotation_offset')) || 0) + 1;
                    GameInterfaceAPI.ConsoleCommand('cs2_gc_force_rotation');
                    GameInterfaceAPI.ConsoleCommand('setinfo cs2_gc_rotation_offset ' + next);
                    $.DispatchEvent('CSGOPlaySoundEffect', 'UIPanorama.generic_button_press', 'MOUSE');
                    $.Schedule(0.2, _LocalRotationRefresh);
                });
            }
            // Line the button's left edge up with the tiles (it sat at the far left of the page).
            const refresh = bar.FindChildInLayoutFile('cs2gc-refresh-armory');
            const tiles = m_elContentPanel.FindChildInLayoutFile('id-xpshop-row-1');
            if (refresh && tiles && tiles.IsValid() && tiles.GetPositionWithinWindow && bar.GetPositionWithinWindow) {
                const gap = (tiles.GetPositionWithinWindow().x - bar.GetPositionWithinWindow().x) / (bar.actualuiscale_x || 1);
                if (tiles.actuallayoutwidth > 0 && gap > 0) refresh.style.marginLeft = Math.round(gap) + 'px';
            }
            // Line the right edge up with the Credits Balance block (always shown; the pass button hides at 5 passes).
            const anchor = root.FindChildInLayoutFile('id-xpshop-balance');
            if (anchor && anchor.IsValid() && bar.GetPositionWithinWindow && anchor.GetPositionWithinWindow) {
                const barRight = bar.GetPositionWithinWindow().x + bar.actuallayoutwidth;
                const anchorRight = anchor.GetPositionWithinWindow().x + anchor.actuallayoutwidth;
                const gap = (barRight - anchorRight) / (bar.actualuiscale_x || 1);
                if (anchor.actuallayoutwidth > 0 && gap > 0) label.style.marginRight = Math.round(gap) + 'px';
            }
        }
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
            entry.local_terminal = slot === 'terminal';
            if (slot === 'agent') {
                entry.lootlist = m_localRotation.agents.map(name => InventoryAPI.GetFauxItemIDFromDefAndPaintIndex(
                    InventoryAPI.GetItemDefinitionIndexFromDefinitionName(name), 0));
                entry.local_agent = true;
                entry.entry_type = 'lootlist'; entry.lootlist_item_type = 'agent';
                entry.tile_width = 160; entry.tile_height = 160;
            }
            if (!entry.callout && entry.lootlist && entry.lootlist.length === 1)
                entry.callout = InventoryAPI.GetItemName(entry.lootlist[0]);
            if (slot === 'capsule' && entry.lootlist && entry.lootlist.length === 1) {
                // Buying a capsule gives one of its stickers, so show its stickers like a sticker collection.
                const stickers = _GetLootListForReward(entry.lootlist[0]).filter(id => id && id !== '0' && id !== entry.lootlist[0]);
                if (stickers.length > 1) {
                    entry.lootlist = stickers;
                    entry.entry_type = 'lootlist'; entry.lootlist_item_type = 'sticker';
                    entry.tile_width = m_stickerTileWidth; entry.tile_height = m_stickerTileWidth;
                    entry.on_item_activate = _OpenFullScreenInspectItem;
                    delete entry.suffix_loc_string;
                }
            }
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
            const panel = $.CreatePanel('Panel', elTilesContainer, itemId);
            panel.Data().localAgentPreview = true;
            panel.style.width = '212px'; panel.style.height = '222px'; panel.style.flowChildren = 'down';
            panel.style.backgroundColor = '#18343be8'; panel.style.border = '1px solid #59818466';
            const portrait = $.CreatePanel('ItemImage', panel, '', {itemid:itemId});
            portrait.style.width = '100%'; portrait.style.height = '76%'; portrait.hittest = false;
            const name = $.CreatePanel('Label', panel, '', {text:InventoryAPI.GetItemName(itemId)});
            name.style.width = '100%'; name.style.height = '44px'; name.style.padding = '4px 8px';
            name.style.fontSize = '16px'; name.style.textAlign = 'center'; name.style.color = '#e6efef';
            return panel;
        }'''
    source = source.replace(create, create + agent, 1)
    source = source.replace("if (ShopEntry.entry_type !== 'crate') {", "if (ShopEntry.local_terminal || ShopEntry.entry_type !== 'crate') {", 1)
    placement = '    function PlaceTiles(elTilesContainer, ShopEntry) {'
    source = source.replace(placement, placement + "\n        if (ShopEntry.local_agent) { _LocalPlaceAgentTiles(elTilesContainer, ShopEntry); return; }", 1)

    source = source.replace('shuffledArray[iScrollingTile];', 'shuffledArray[iScrollingTile % shuffledArray.length];')
    # Rebind callbacks when stock UI reuses panels after a catalogue refresh.
    source = source.replace("        elTile.FindChildInLayoutFile('id-new-item-tag')", "        elTile.SetPanelEvent('onactivate', () => _LocalOpenEntry(ShopEntry));\n        elTile.FindChildInLayoutFile('id-new-item-tag')", 1)
    nav_end = "    function _CancelTimeoutForRewardItem() {"
    nav_binding = "        elBtn.SetPanelEvent('onactivate', () => _LocalShowGrid(ShopEntry));\n"
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
            if (currentTile) currentTile.SetPanelEvent('onactivate', () => _LocalOpenEntry(element));
            const currentNav = $.GetContextPanel().FindChildInLayoutFile(element.item_name + '-nav');
            if (currentNav) currentNav.SetPanelEvent('onactivate', () => _LocalShowGrid(element));
'''
    source = source.replace('            _MakeNavButton(element);', '            _MakeNavButton(element);' + route, 1)
    # Capsule (crate) grids can lack an ItemPreviewPanel; the stock refresh then threw before switching grids,
    # leaving the previous tab (often Random Agent) on screen.
    source = source.replace('if (elModel.PanZoomEnabled()) {', 'if (elModel && elModel.PanZoomEnabled()) {')
    source = source.replace("$.Schedule(.25, () => elModel.TransitionToCamera('cam_case_open', 1));",
                            "$.Schedule(.25, () => { if (elModel && elModel.IsValid()) elModel.TransitionToCamera('cam_case_open', 1); });", 1)
    # The knife-only Black Market Case lists thousands of knives; draw a shuffled sample instead of freezing the page.
    source = source.replace('let aCrateLootlist = _GetLootListForReward(itemId);',
                            'let aCrateLootlist = _GetLootListForReward(itemId);\n                        if (aCrateLootlist.length > 96) aCrateLootlist = aCrateLootlist.sort(() => 0.5 - Math.random()).slice(0, 96);', 1)
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
                           ('collection', 'case', 'capsule', 'charm', 'sticker', 'limited', 'agent', 'terminal')}}
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

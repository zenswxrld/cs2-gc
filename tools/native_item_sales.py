"""OfflineCS-style native Sell for Stars action; backend owns prices and removal.

Native InventoryAPI.DeleteItem -> CMsgDeleteItem (1004) is the existing inventory
path. Eligible local deletions become sales just as in OfflineCS; no console/BAT.
"""
import json
from pathlib import Path
from inventory_item import collect, parse, as_dict
from armory_rotation_catalog import agent_names
from price_sheet import find_case_items
from native_resources import install_override


def settings(source, config):
    sections = collect(parse(source))
    names = {as_dict(v).get('name'): str(k) for k, v in sections.get('items', {}).items() if isinstance(v, list)}
    agents = agent_names(source)
    flat = {}
    gold_definitions = []
    def percent(price, value): return max(1, price * value // 100) if price and value else 0
    for name in agents:
        flat[names[name]] = percent(config['armory_agent_price'], config['sell_agent_percent'])
    for case, _, definition, key_index in find_case_items(sections):
        flat[str(key_index)] = 5
        flat[definition] = percent(2, config['sell_container_percent'])
    # Container classification uses the same native prefab family as the C++ schema loader.
    prefabs = sections.get('prefabs', {})
    def chain(node, depth=0):
        values = as_dict(node); result = set(values.get('prefab', '').split())
        if depth < 8:
            for name in list(result):
                if name in prefabs: result |= chain(prefabs[name], depth + 1)
        return result
    def resolve(node, key, depth=0):
        values = as_dict(node)
        if key in values: return values[key]
        if depth < 8:
            for name in values.get('prefab', '').split():
                if name in prefabs:
                    found = resolve(prefabs[name], key, depth + 1)
                    if found is not None: return found
        return None
    for definition, node in sections.get('items', {}).items():
        if not isinstance(node, list): continue
        values = as_dict(node); name = values.get('name', '')
        ancestors = chain(node)
        if 'weapon_case_base' in ancestors and 'weapon_case_souvenirpkg' not in ancestors:
            key = resolve(node, 'associated_item')
            associated = resolve(node, 'associated_items')
            if isinstance(associated, list) and associated: key = associated[0][0]
            if key and str(key).isdigit(): flat[str(key)] = 5
        if 'hands_paintable' in ancestors or resolve(node, 'item_class') == 'weapon_knife':
            gold_definitions.append(str(definition))
        if name == 'musickit': flat[definition] = config['sell_music_kit']
        elif 'weapon_case_base' in ancestors:
            attributes = resolve(node, 'attributes')
            series = as_dict(attributes).get('set supply crate series') if isinstance(attributes, list) else None
            if series and not ('volatile_pricing' in ancestors and 'weapon_case_selfopening_collection' in ancestors):
                flat.setdefault(definition, percent(1, config['sell_container_percent']))
    return {'enabled': bool(config['item_sales_enabled']), 'flat': flat,
            'rarity': [0] + [config['sell_' + key] for key in ('consumer', 'industrial', 'mil_spec', 'restricted', 'classified', 'covert')],
            'goldDefinitions': gold_definitions, 'gold': config['sell_knife_glove'], 'stickerPercent': config['sell_sticker_percent']}


PRICE = '''
    // Local inventory only. Prices mirror the OfflineCS rarity/percentage rules.
    const cs2gcSell = __SETTINGS__;
    function _LocalSalePrice(id) {
        const numeric = Number(id);
        if (!cs2gcSell.enabled || numeric <= 1000000000000 || numeric >= 2000000000000) return 0;
        const definition = String(InventoryAPI.GetItemDefinitionIndex(id));
        if (Object.prototype.hasOwnProperty.call(cs2gcSell.flat, definition)) return cs2gcSell.flat[definition];
        const rarity = InventoryAPI.GetItemRarity(id);
        const base = cs2gcSell.rarity[rarity] || 0;
        if (ItemInfo.IsSticker(id) || ItemInfo.IsPatch(id) || ItemInfo.IsSprayPaint(id) || ItemInfo.IsSpraySealed(id) || ItemInfo.IsKeychain(id))
            return base && cs2gcSell.stickerPercent ? Math.max(1, Math.floor(base * cs2gcSell.stickerPercent / 100)) : 0;
        if ((cs2gcSell.goldDefinitions || []).indexOf(definition) !== -1 || ItemInfo.IsMelee(id) || ItemInfo.IsGloves(id)) return cs2gcSell.gold;
        return ItemInfo.IsWeapon(id) ? base : 0;
    }
'''


def patch(source, data):
    anchor = '        let validEntries = ItemContextEntries.FilterEntries(id, populateFilterText);'
    if source.count(anchor) != 1 or source.count('    function _PopulateContextMenu(id, populateFilterText) {') != 1 or '_LocalSalePrice' in source:
        raise ValueError('Changed or already patched inventory context menu')
    addition = '''
        const price = _LocalSalePrice(id);
        if (price > 0) {
            const button = $.CreatePanel('Button', elParent, 'cs2gc-sell-item');
            button.AddClass('TopSeparator');
            $.CreatePanel('Label', button, '', {text: 'Sell for ' + price + ' stars'});
            button.SetPanelEvent('onactivate', () => {
                $.DispatchEvent('ContextMenuEvent', '');
                UiToolkitAPI.ShowGenericPopupYesNo('Sell item for stars',
                    'Sell ' + InventoryAPI.GetItemName(id) + ' for ' + price + ' stars? This removes the item, including attached stickers or charms.',
                    '', () => InventoryAPI.DeleteItem(id), () => {});
            });
        }
'''
    # Read the definition via the same native name-to-index path already used by Armory.
    code = PRICE.replace('__SETTINGS__', json.dumps(data)).replace(
        'InventoryAPI.GetItemDefinitionIndex(id)', 'InventoryAPI.GetItemDefinitionIndexFromDefinitionName(InventoryAPI.GetItemDefinitionName(id))')
    bottom = '        if (!validEntries.length) {'
    if source.count(bottom) != 1: raise ValueError('Changed inventory context-menu footer')
    source = source.replace('    function _PopulateContextMenu(id, populateFilterText) {', code + '\n    function _PopulateContextMenu(id, populateFilterText) {', 1)
    source = source.replace(anchor, anchor + '''
        const localItem = Number(id) > 1000000000000 && Number(id) < 2000000000000;
        if (localItem) validEntries = validEntries.filter(entry => entry.name !== 'sell' && entry.name !== 'marketlisting');
''', 1)
    return source.replace(bottom, addition + '        if (!validEntries.length && price <= 0) {', 1)


def prepare(directory, config):
    directory = Path(directory)
    data = settings((directory / 'items_game.txt').read_text(encoding='utf-8-sig'), config)
    return install_override(directory, enabled=config['item_sales_enabled'], folder='cs2_gc_sales',
        comment='cs2_gc native item sales', owner='cs2-gc-sales-v1',
        asset='panorama/scripts/context_menus/context_menu_inventory_item.vts_c', patch=lambda source: patch(source, data))

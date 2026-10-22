"""Sell several items at once in CS2's own storage-unit multi-select picker (user: "cs2 has a multi select ui for
storage units, could that be used?").

popup_select_item_for_capability already supports multi-select for the casketstore/casketretrieve capabilities
(inv-multi-select-allow, OnItemActivated, selectedItemCount/GetSelectedItemId). The inventory context menu opens it
with the local capability 'cs2gc_sell' (native_item_sales.py); this patch makes that capability multi-select, lists
the whole inventory, and turns the picker's confirm button into a sale: each sellable item goes through the same
InventoryAPI.DeleteItem sale as the single Sell for stars action, so the GC prices and pays every one.
"""
from pathlib import Path

from native_item_sales import price_code, settings
from native_resources import install_override

CAPABILITY = 'cs2gc_sell'
HELPERS = '''
    // cs2_gc multi-sell: sale prices and the sale itself (the same DeleteItem sale as the context menu's Sell).
    function _LocalMultiSellPrices(ids) {
        const priced = ids.map(id => [id, _LocalSalePrice(id)]);
        return {sellable: priced.filter(pair => pair[1] > 0), kept: priced.filter(pair => pair[1] <= 0).length,
                total: priced.reduce((sum, pair) => sum + Math.max(0, pair[1]), 0)};
    }
    function _LocalSelectedIds() {
        const ids = [];
        for (let i = 0; i < _m_elItemList.selectedItemCount; i++) ids.push(_m_elItemList.GetSelectedItemId(i).toString());
        return ids;
    }
    // User: "can we make it show only sellable items". The native list has no sale filter, so tiles worth 0 stars
    // (default loadout items, storage units, tools) are hidden; re-checked while open since the list refills.
    function _LocalSellableOnly() {
        if (!_m_cp.IsValid() || !SelectItemForCapability.oCapabilityInfo.popupVisible) return;
        _m_elItemList.Children().forEach(tile => {
            const sellable = _LocalSalePrice(tile.GetAttributeString('itemid', '0')) > 0;
            if (tile.visible !== sellable) tile.visible = sellable;
        });
        $.Schedule(0.25, _LocalSellableOnly);
    }
    function _LocalMultiSell(ids) {
        const prices = _LocalMultiSellPrices(ids);
        if (!prices.sellable.length) {
            UiToolkitAPI.ShowGenericPopupOk('Sell items for stars', 'None of the selected items can be sold for stars.', '', () => {});
            return;
        }
        UiToolkitAPI.ShowGenericPopupYesNo('Sell items for stars',
            'Sell ' + prices.sellable.length + ' item' + (prices.sellable.length === 1 ? '' : 's') + ' for ' + prices.total +
            ' stars? This removes them, including attached stickers or charms.' +
            (prices.kept ? ' ' + prices.kept + ' selected item' + (prices.kept === 1 ? '' : 's') + ' can not be sold and will be kept.' : ''),
            '', () => prices.sellable.forEach(pair => InventoryAPI.DeleteItem(pair[0])), () => {});
    }
'''
ANCHORS = {
    'init': '        SelectItemForCapability.oCapabilityInfo.popupVisible = true;\n',
    'title': "        _m_cp.SetDialogVariable('title', $.Localize(szPrefixString, _m_cp));\n",
    'filter': "        let capabilityFilter = SelectItemForCapability.oCapabilityInfo.capability + ':' + SelectItemForCapability.oCapabilityInfo.initialItemId + filterApplicationToPhantomItems;\n",
    'display': '        elMultiSelectDisplay.visible = true;\n',
    'activate': "        if (SelectItemForCapability.oCapabilityInfo.capability === 'casketretrieve') {\n",
    'proceed': '        switch (capability) {\n',
    'helpers': '    function _UpdateMultiSelectDisplay() {\n',
}
IS_SELL = "SelectItemForCapability.oCapabilityInfo.capability === '%s'" % CAPABILITY


def patch(source, data):
    if '_LocalMultiSell' in source: raise ValueError('Multi-select picker already patched')
    if any(source.count(anchor) != 1 for anchor in ANCHORS.values()):
        raise ValueError('Installed multi-select picker changed; no patch written')
    insert = {
        'init': '        if (%s) SelectItemForCapability.oCapabilityInfo.bIsMultiSelect = true;\n' % IS_SELL,
        'title': ("        if (%s) { _m_cp.AddClass('PopupSelectItemForCapability_casketstore'); "
                  "_m_cp.SetDialogVariable('title', 'Select items to sell for stars'); }\n") % IS_SELL,
        'filter': "        if (%s) { capabilityFilter = ''; $.Schedule(0.05, _LocalSellableOnly); }  // sellable tiles only\n" % IS_SELL,
        'display': ("        if (%s) {\n"
                    "            const total = _LocalMultiSellPrices(_LocalSelectedIds()).total;\n"
                    "            const button = _m_cp.FindChildInLayoutFile('id-popup-select-multi-item-btn');\n"
                    "            const relabel = panel => panel.Children().forEach(child => {\n"
                    "                if (child.paneltype === 'Label') child.text = 'Sell for ' + total + ' stars'; else relabel(child); });\n"
                    "            relabel(button);\n"
                    "            button.enabled = total > 0;\n"
                    "        }\n") % IS_SELL,
    }
    for key, code in insert.items():
        source = source.replace(ANCHORS[key], ANCHORS[key] + code, 1)
    source = source.replace(ANCHORS['proceed'], '        if (%s) { _LocalMultiSell(arrItemIDs); ClosePopUp(); return; }\n'
                            % IS_SELL + ANCHORS['proceed'], 1)
    source = source.replace(ANCHORS['activate'],
        "        if (%s) {\n"
        "            itemTile.FindAncestor('id-popup-select-item-list').OnItemActivated(itemid);\n"
        "            _UpdateMultiSelectDisplay();\n"
        "            return;\n"
        "        }\n" % IS_SELL + ANCHORS['activate'], 1)
    return source.replace(ANCHORS['helpers'], price_code(data) + HELPERS + ANCHORS['helpers'], 1)


def prepare(directory, config):
    directory = Path(directory)
    data = settings((directory / 'items_game.txt').read_text(encoding='utf-8-sig'), config)
    return install_override(directory, enabled=config['item_sales_enabled'], folder='cs2_gc_multisell',
        comment='cs2_gc native multi-sell', owner='cs2-gc-multisell-v1',
        asset='panorama/scripts/popups/popup_select_item_for_capability.vts_c', patch=lambda source: patch(source, data))

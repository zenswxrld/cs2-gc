import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import native_multi_sell

# The parts of the installed popup_select_item_for_capability.js the patch anchors on, in their real order.
SOURCE = '''    let _m_cp = $.GetContextPanel();
    let _m_elItemList = _m_cp.FindChildInLayoutFile('id-popup-select-item-list');
    const oCapabilityInfo = {capability: '', initialItemId: '', bIsMultiSelect: false};
    const SelectItemForCapability = {oCapabilityInfo};
    function Init() {
        SelectItemForCapability.oCapabilityInfo.capability = _m_cp.GetAttributeString("capability", '');
        SelectItemForCapability.oCapabilityInfo.bIsMultiSelect = (SelectItemForCapability.oCapabilityInfo.capability === "casketstore");
        SelectItemForCapability.oCapabilityInfo.popupVisible = true;
        _SetTitle(); UpdateSort(); _UpdateMultiSelectDisplay();
    }
    function _SetTitle() {
        let szPrefixString = '#inv_select_item_use_capability';
        _m_cp.SetDialogVariable('title', $.Localize(szPrefixString, _m_cp));
    }
    function UpdateSort() {
        let filterApplicationToPhantomItems = ',is_rental:false';
        let capabilityFilter = SelectItemForCapability.oCapabilityInfo.capability + ':' + SelectItemForCapability.oCapabilityInfo.initialItemId + filterApplicationToPhantomItems;
        filters.push(capabilityFilter);
    }
    function _UpdateMultiSelectDisplay() {
        const elMultiSelectDisplay = _m_cp.FindChildInLayoutFile('id-popup-select-multi-item-display');
        if (!SelectItemForCapability.oCapabilityInfo.bIsMultiSelect) { elMultiSelectDisplay.visible = false; return; }
        _m_cp.FindChildInLayoutFile('id-popup-select-multi-item-btn').enabled = (_m_elItemList.selectedItemCount > 0);
        elMultiSelectDisplay.visible = true;
    }
    function ClosePopUp() { closed++; }
    function _OnItemTileActivated(itemTile, itemid) {
        if (SelectItemForCapability.oCapabilityInfo.capability === 'casketretrieve') {
            return;
        }
        ClosePopUp();
    }
    function ProceedForMultiStatusCapabilityPopup() {
        let capability = SelectItemForCapability.oCapabilityInfo.capability;
        let arrItemIDs = [];
        for (let i = 0; i < _m_elItemList.selectedItemCount; i++) arrItemIDs.push(_m_elItemList.GetSelectedItemId(i).toString());
        switch (capability) {
            case 'casketstore': stored++; break;
        }
        ClosePopUp();
    }
'''
DATA = {'enabled': True, 'flat': {}, 'rarity': [0, 1, 2, 5, 10, 25, 50], 'gold': 150, 'stickerPercent': 50}


class MultiSell(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node required')
    def test_storage_picker_sells_the_selected_items_after_confirmation(self):
        script = '''const assert = require('assert'); let closed = 0, stored = 0, confirm, ok; const filters = [], deleted = [];
const selected = []; const caption = {paneltype: 'Label', text: 'Store', Children: () => []};
const panels = {'id-popup-select-item-list': {get selectedItemCount() { return selected.length; }, GetSelectedItemId: i => selected[i],
  OnItemActivated: id => { const at = selected.indexOf(id); at < 0 ? selected.push(id) : selected.splice(at, 1); }},
 'id-popup-select-multi-item-display': {}, 'id-popup-select-multi-item-btn': {Children: () => [{paneltype: 'Panel', Children: () => [caption]}]}};
const root = {FindChildInLayoutFile: id => panels[id], GetAttributeString: () => 'cs2gc_sell', AddClass: c => root.cls = c,
 SetDialogVariable: (k, v) => root[k] = v};
const $ = {GetContextPanel: () => root, Localize: s => s};
const rarity = {'1000000000001': 3, '1000000000002': 5, '1000000000003': 0};
const InventoryAPI = {GetItemDefinitionName: () => 'weapon', GetItemDefinitionIndexFromDefinitionName: () => 7,
 GetItemRarity: id => rarity[id], DeleteItem: id => deleted.push(id)};
const ItemInfo = {IsKeychain: () => false, IsSticker: () => false, IsPatch: () => false, IsSprayPaint: () => false,
 IsSpraySealed: () => false, IsMelee: () => false, IsGloves: () => false, IsWeapon: id => rarity[id] > 0};
const UiToolkitAPI = {ShowGenericPopupYesNo: (t, text, i, yes, no) => confirm = {text, yes, no},
 ShowGenericPopupOk: (t, text) => ok = text};
''' + native_multi_sell.patch(SOURCE, DATA) + '''
Init();
assert.equal(SelectItemForCapability.oCapabilityInfo.bIsMultiSelect, true);
assert.deepEqual(filters, ['']);  // the whole inventory
assert.equal(root.title, 'Select items to sell for stars');
const tile = {FindAncestor: () => panels['id-popup-select-item-list']};
for (const id of ['1000000000001', '1000000000002', '1000000000003']) _OnItemTileActivated(tile, id);
assert.equal(closed, 0); assert.equal(selected.length, 3);
assert.equal(caption.text, 'Sell for 30 stars');
ProceedForMultiStatusCapabilityPopup();
assert.equal(stored, 0); assert.equal(closed, 1); assert.deepEqual(deleted, []);
assert.ok(confirm.text.includes('Sell 2 items for 30 stars') && confirm.text.includes('1 selected item can not be sold'));
confirm.no(); assert.deepEqual(deleted, []);
confirm.yes(); assert.deepEqual(deleted, ['1000000000001', '1000000000002']);
selected.length = 0; selected.push('1000000000003'); _UpdateMultiSelectDisplay();
assert.equal(panels['id-popup-select-multi-item-btn'].enabled, false);
ProceedForMultiStatusCapabilityPopup(); assert.ok(ok.includes('None of the selected items'));
'''
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_changed_picker_fails_closed(self):
        with self.assertRaises(ValueError):
            native_multi_sell.patch(SOURCE.replace('        switch (capability) {\n', ''), DATA)


if __name__ == '__main__':
    unittest.main()

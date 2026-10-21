"""Open local GC cases directly with one matching key, or keylessly in free mode.

Patches the native context action; stock case animations remain in the decodable popup.
"""
from native_resources import install_override

FOLDER = 'cs2_gc_open'
COMMENT = 'cs2_gc open cases without the key picker'
OWNER = 'cs2-gc-skip-key-select-v1'
ASSET = 'panorama/scripts/common/item_context_entries.vjs_c'
ANCHOR = """                    $.DispatchEvent('ContextMenuEvent', '');
                    return;
                }
                $.DispatchEvent('ShowSelectItemForCapabilityPopup', id, '', 'decodable');"""
INSERT = """                    $.DispatchEvent('ContextMenuEvent', '');
                    return;
                }
                // cs2_gc: a local case with exactly one matching key skips the key picker.
                const localGcCase = Number(id);
                if (!InventoryAPI.IsTool(id) && localGcCase > 1000000000000 && localGcCase < 2000000000000 &&
                    InventoryAPI.GetChosenActionItemsCount(id, 'decodable') === 1) {
                    const elPanel = UiToolkitAPI.ShowCustomLayoutPopup('popup-inspect-' + id, 'file://{resources}/layout/popups/popup_capability_decodable.xml');
                    elPanel.Data().oSettings = {
                        item_id: id,
                        tool_id: InventoryAPI.GetChosenActionItemIDByIndex(id, 'decodable', 0),
                        work_type: 'decodeable'
                    };
                    return;
                }
                $.DispatchEvent('ShowSelectItemForCapabilityPopup', id, '', 'decodable');"""


def patch(source, keyless=False):
    if 'cs2_gc: a local case' in source: raise ValueError('Script is already patched')
    if source.count(ANCHOR) != 1 or 'InventoryAPI.GetChosenActionItemIDByIndex(' not in source:
        raise ValueError('Installed item_context_entries layout has changed; no patch was written')
    result = source.replace(ANCHOR, INSERT, 1)
    if keyless:
        branch = "                if (InventoryAPI.GetChosenActionItemsCount(id, 'decodable') === 0) {"
        if result.count(branch) != 1: raise ValueError('Installed keyless opening branch changed')
        direct = """                // cs2_gc free-case mode: native unlock popup with no key tool, even if old keys remain.
                const localFreeId = Number(id);
                if (!InventoryAPI.IsTool(id) && localFreeId > 1000000000000 && localFreeId < 2000000000000 &&
                    !InventoryAPI.GetItemAttributeValue(id, '{uint32}volatile container')) {
                    const popup = UiToolkitAPI.ShowCustomLayoutPopup('popup-inspect-' + id, 'file://{resources}/layout/popups/popup_capability_decodable.xml');
                    popup.Data().oSettings = {item_id:id, work_type:'decodeable'};
                    return;
                }
"""
        result = result.replace(branch,direct+branch,1)
    return result


def prepare(proxy_directory, config):
    return install_override(proxy_directory, enabled=bool(config.get('skip_key_selection', 1)),
                            folder=FOLDER, comment=COMMENT, owner=OWNER, asset=ASSET, patch=lambda source: patch(source, bool(config.get('free_case_keys', 1))))

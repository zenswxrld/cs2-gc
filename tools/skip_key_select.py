"""Open local GC cases straight into the unlock screen when exactly one matching key is owned.

With free_case_keys every local case has one key, so the stock "Select an item to use with ..." page only ever
offers that key. Patches the user's own item_context_entries script: the open_package action passes the single
key as tool_id to the stock popup_capability_decodable, exactly as picking it on that page would.
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


def patch(source):
    if 'cs2_gc: a local case' in source: raise ValueError('Script is already patched')
    if source.count(ANCHOR) != 1 or 'InventoryAPI.GetChosenActionItemIDByIndex(' not in source:
        raise ValueError('Installed item_context_entries layout has changed; no patch was written')
    return source.replace(ANCHOR, INSERT, 1)


def prepare(proxy_directory, config):
    return install_override(proxy_directory, enabled=bool(config.get('skip_key_selection', 1)),
                            folder=FOLDER, comment=COMMENT, owner=OWNER, asset=ASSET, patch=patch)

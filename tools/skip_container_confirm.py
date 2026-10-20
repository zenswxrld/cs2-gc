"""Prepare a Panorama SOURCE override for the local GC's container confirmation.

Input: extracted popup_inspect_rental-bar.js from the target client.
Output: patched .ts source, to be compiled/mounted using the target game's Panorama toolchain.
The rewards helper can also prepare a dedicated compiled override from the installed VPK.
"""
import argparse
from pathlib import Path

ANCHOR = '    function OpenConfirmPopup(type, itemId, contextPanel) {\n'
INSERT = '''        // Local GC inventory IDs only. Keep rental and real inventory confirmations intact.
        const localGcItem = Number(itemId);
        if (type === 'open' && localGcItem > 1000000000000 && localGcItem < 2000000000000) {
            _OnPopupActionPressed(type, contextPanel);
            return;
        }
'''


def patch(source, skip_confirmation=True, hide_rent=True):
    if source.count(ANCHOR) != 1 or 'function _OnPopupActionPressed(actionType, contextPanel)' not in source:
        raise ValueError('Target script differs from the inspected build; no patch was written')
    if 'const localGcItem =' in source:
        raise ValueError('Source is already patched')
    if skip_confirmation:
        source = source.replace(ANCHOR, ANCHOR + INSERT, 1)
    if hide_rent:
        rent_anchor = "            let RentBtn = elRentalBar.FindChildInLayoutFile('RentBtn');\n"
        if source.count(rent_anchor) != 1:
            raise ValueError('Target rental button layout changed; no patch was written')
        source = source.replace(rent_anchor, rent_anchor + '''            // Hide rental on local GC containers; preserve real inventory and X-Ray restrictions.
            const localContainerId = Number(itemId);
            RentBtn.visible = !(localContainerId > 1000000000000 && localContainerId < 2000000000000);
''', 1)
    return source


def prepare(proxy_directory, config):
    from native_resources import install_override
    return install_override(proxy_directory,
        enabled=bool(config['skip_container_confirmation'] or config['hide_rent_button']),
        folder='cs2_gc_confirm', comment='cs2_gc skip local container confirmation',
        owner='cs2-gc-container-confirm-v1',
        asset='panorama/scripts/popups/popup_inspect_rental-bar.vjs_c',
        patch=lambda source: patch(source, bool(config['skip_container_confirmation']), bool(config['hide_rent_button'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    content = patch(args.source.read_text(encoding='utf-8'))
    with args.out.open('x', encoding='utf-8', newline='\n') as out:
        out.write(content)

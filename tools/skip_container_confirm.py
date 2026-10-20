"""Prepare a Panorama SOURCE override for the local GC's container confirmation.

Input: extracted popup_inspect_rental-bar.js from the target client.
Output: patched .ts source, to be compiled/mounted using the target game's Panorama toolchain.
This does not patch game binaries or install an unverified resource override.
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


def patch(source):
    if source.count(ANCHOR) != 1 or 'function _OnPopupActionPressed(actionType, contextPanel)' not in source:
        raise ValueError('Target script differs from the inspected build; no patch was written')
    if 'const localGcItem =' in source:
        raise ValueError('Source is already patched')
    return source.replace(ANCHOR, ANCHOR + INSERT, 1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    content = patch(args.source.read_text(encoding='utf-8'))
    with args.out.open('x', encoding='utf-8', newline='\n') as out:
        out.write(content)

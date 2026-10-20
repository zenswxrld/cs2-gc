"""Prepare a native Armory rotation/countdown SOURCE override, not a mounted resource.

Use the target build's extracted xpshop.js; compile/mount the output with that build's
Panorama toolchain. No schema or binary patches are made. Regenerate after config edits.
"""
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
    function _LocalRotationRefresh() {
        const root = $.GetContextPanel();
        if (!root.IsValid()) return;
        const entries = m_localRotationItems.slice().sort((a, b) => a.item_name < b.item_name ? -1 : a.item_name > b.item_name ? 1 : 0);
        if (!entries.length || !m_localRotation.enabled) return;
        const now = Math.floor(Date.now() / 1000);
        const cycle = Math.floor(now / m_localRotation.seconds);
        const count = Math.min(m_localRotation.slots, entries.length);
        const start = ((cycle % entries.length) * count) % entries.length;
        const active = [];
        for (let i = 0; i < count; ++i) active.push(entries[(start + i) % entries.length].item_name);
        entries.forEach(entry => {
            const show = active.indexOf(entry.item_name) !== -1;
            const tile = m_elContentPanel.FindChildInLayoutFile(entry.item_name);
            const nav = root.FindChildInLayoutFile(entry.item_name + '-nav');
            if (tile) tile.visible = show;
            if (nav) nav.visible = show;
        });
        const parent = root.FindChildInLayoutFile('id-xpshop-top-nav');
        let label = parent.FindChildInLayoutFile('id-local-rotation-countdown');
        if (!label) label = $.CreatePanel('Label', parent, 'id-local-rotation-countdown');
        const remaining = m_localRotation.seconds - now % m_localRotation.seconds;
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


def patch(source, config):
    if config['armory_howl_enabled']:
        raise ValueError('Howl native redeem bridge is not installed yet. Set armory_howl_enabled=0 before preparing this UI override; do not mount a mismatched rotation.')
    if source.count(ANCHOR) != 1 or source.count(END) != 1 or 'const m_elContentPanel =' not in source:
        raise ValueError('Target xpshop.js differs from the inspected build')
    if 'm_localRotation' in source: raise ValueError('Source is already patched')
    settings = {'enabled': bool(config['armory_rotation_enabled']),
                'seconds': config['armory_rotation_seconds'], 'slots': config['armory_rotation_slots']}
    source = source.replace('    function _UpdateShopGoods(m_nTrack) {',
                            INSERT.replace('__SETTINGS__', json.dumps(settings)) + '    function _UpdateShopGoods(m_nTrack) {', 1)
    source = source.replace(END, END + '''
        m_localRotationItems = aShopItemsData;
        if (m_localRotationTick) $.CancelScheduled(m_localRotationTick);
        _LocalRotationRefresh();''', 1)
    return source


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--proxy-dir', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = patch(args.source.read_text(encoding='utf-8'), load(args.proxy_dir))
    with args.out.open('x', encoding='utf-8', newline='\n') as output: output.write(result)

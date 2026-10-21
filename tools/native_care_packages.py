"""Reuse CS2's native care-package tiles and StoreRedeemFreeRewards for local 3-of-4 rewards.

Uses the inspected rankup_redemption_store and the captured PersonalStore (SO type 4). No invented UI APIs.
"""
from native_resources import install_override

HELPER = '''    function _LocalCarePackage() {
        const store = GetPersonalStore();
        return store && Object.values(store.items || {}).every(id => Number(id) > 1000000000000 && Number(id) < 2000000000000);
    }
'''
CLAIM = '''        // cs2_gc: a package grants exactly three picks, never one/two or all four.
        if (_LocalCarePackage() && _GetSelectedItems().length !== 3) { _PulseItems(); return; }
'''
TIME = '''        if (_LocalCarePackage()) {
            $.GetContextPanel().FindChildrenWithClassTraverse('rrs__title').forEach(label => label.text = 'CARE PACKAGE');
            $.GetContextPanel().SetDialogVariable('time-to-week-rollover', '');
            $.GetContextPanel().SetDialogVariable('frame-badge-text', m_redeemableBalance > 0 ? 'CHOOSE 3 OF 4 REWARDS' : 'REWARDS CLAIMED');
            $.GetContextPanel().SetDialogVariable('frame-desc-text', m_redeemableBalance > 0 ?
                'Choose three rewards. Your choices are saved until claimed.' : 'Earn another package by completing a match or leveling up.');
            m_schTimer = $.Schedule(30, _UpdateTime);
            return;
        }
'''
UPDATE = '''        // A new store generation (or a completed claim) is the native inventory acknowledgement.
        const localStore = GetPersonalStore();
        if (_LocalCarePackage() && localStore &&
            (localStore.generation_time !== m_timeStamp || !localStore.redeemable_balance)) {
            if (m_timeoutScheduleHandle) { $.CancelScheduled(m_timeoutScheduleHandle); m_timeoutScheduleHandle = null; }
            $.GetContextPanel().RemoveClass('waiting');
        }
'''


def patch(source):
    if 'function _LocalCarePackage()' in source: raise ValueError('Care-package script already patched')
    for anchor in ('    function GetPersonalStore() {', '    function OnRedeem() {',
                   '    function _UpdateTime() {', '    function OnInventoryUpdated() {'):
        if source.count(anchor) != 1: raise ValueError('Installed care-package script changed; no patch written')
    source = source.replace('    function GetPersonalStore() {',HELPER+'    function GetPersonalStore() {',1)
    for anchor,code in [('    function OnRedeem() {',CLAIM),('    function _UpdateTime() {',TIME),
                        ('    function OnInventoryUpdated() {',UPDATE)]:
        source=source.replace(anchor,anchor+'\n'+code,1)
    source=source.replace('Object.values(objStore.items)', 'Object.values(objStore.items || {})')
    return source


def prepare(directory, config):
    return install_override(directory, enabled=bool(config['care_packages_enabled']), folder='cs2_gc_care',
        comment='cs2_gc native care packages', owner='cs2-gc-care-packages-v1',
        asset='panorama/scripts/rankup_redemption_store.vts_c', patch=patch)

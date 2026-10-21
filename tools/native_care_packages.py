"""Reuse CS2's native care-package tiles and StoreRedeemFreeRewards for local 3-of-4 rewards.

Uses the inspected rankup_redemption_store and the captured PersonalStore (SO type 4). No invented UI APIs.
"""
from native_resources import install_override

HELPER = '''    function _LocalCarePackage() {
        const store = GetPersonalStore();
        return store && Object.values(store.items || {}).every(id => Number(id) >= 3000000000000 && Number(id) < 3017179869184);
    }
'''
PREVIEW = """        // cs2_gc: display native catalogue previews, never synthetic unowned econ objects.
        const localChoice = _LocalCarePackage();
        const choiceToken = itemId;
        if (localChoice && itemId !== '-') {
            const encoded = Number(itemId) - 3000000000000;
            const definition = encoded % 65536;
            const paint = Math.floor(encoded / 65536) % 65536;
            itemId = InventoryAPI.GetFauxItemIDFromDefAndPaintIndex(definition, paint);
        }
"""
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
    preview = "    function _CreateItemPanel(itemId, index, bFirstTime, claimedItemId = '') {"
    data = '        elGhostItem.Data().itemid = itemId;'
    activate = '        if (!InventoryAPI.IsFauxItemID(itemId)) {'
    if any(source.count(anchor) != 1 for anchor in (preview,data,activate)):
        raise ValueError('Installed care-package tile contract changed; no patch written')
    source=source.replace(preview,preview+'\n'+PREVIEW,1)
    source=source.replace(data,'        elGhostItem.Data().itemid = localChoice ? choiceToken : itemId;',1)
    init = '        ItemTileStore.Init(elGhostItem, oItemData);'
    if source.count(init) != 1: raise ValueError('Installed reward-tile initializer changed')
    source=source.replace(init,init+"\n        if (localChoice) { elGhostItem.SetHasClass('item-claimed', false); elGhostItem.SetHasClass('item-claimslot-expired', false); }",1)

    source=source.replace(activate,'        if (_LocalCarePackage() || !InventoryAPI.IsFauxItemID(itemId)) {',1)
    source=source.replace('Object.values(objStore.items)', 'Object.values(objStore.items || {})')
    return source


def prepare(directory, config):
    return install_override(directory, enabled=bool(config['care_packages_enabled']), folder='cs2_gc_care',
        comment='cs2_gc native care packages', owner='cs2-gc-care-packages-v1',
        asset='panorama/scripts/rankup_redemption_store.vts_c', patch=patch)

"""Reuse CS2's native care-package tiles and StoreRedeemFreeRewards for local 3-of-4 rewards.

Uses the inspected rankup_redemption_store and the captured PersonalStore (SO type 4). No invented UI APIs.
Build 29: offers are real econ items of the account, so the store ids are submitted as they are (see SUBMIT;
old choice tokens are still mapped to faux ids).
"""
from native_resources import install_override

HELPER = '''    function _LocalCarePackage() {
        const store = GetPersonalStore();
        // Build 29: the offers are real items of the account (ids 1e12..2e12); older stores used choice tokens.
        return store && Object.values(store.items || {}).every(id => _LocalCareToken(id) || (Number(id) >= 1000000000000 && Number(id) < 2000000000000));
    }
    function _LocalCareToken(id) {
        return Number(id) >= 3000000000000 && Number(id) < 3017179869184;
    }
    function _LocalCareFauxId(token) {
        const encoded = Number(token) - 3000000000000;
        return InventoryAPI.GetFauxItemIDFromDefAndPaintIndex(encoded % 65536, Math.floor(encoded / 65536) % 65536);
    }
    function _LocalCareLog(text) {
        try { $.Msg('cs2_gc care: ' + (typeof text === 'function' ? text() : text)); } catch (error) {}
    }
'''
PREVIEW = """        // cs2_gc: display native catalogue previews, never synthetic unowned econ objects.
        const localChoice = _LocalCarePackage();
        const choiceToken = itemId;
        if (localChoice && itemId !== '-' && _LocalCareToken(itemId)) itemId = _LocalCareFauxId(itemId);
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
# The supplied log of a failed claim (build 27) has no 9219 frame at all: StoreRedeemFreeRewards(tokens)
# returned without sending. The tokens are not ids the client inventory knows (stock _CreateItemPanel
# drops such ids; official stores list real/faux ids), so submit the faux ids the tiles already render
# and let the GC map them back to the saved offers. Console diagnostics record what was submitted.
SUBMIT = '''        if (_LocalCarePackage()) {
            const tokens = _GetSelectedItems().map(item => item.item_id);
            szItemList = tokens.map(token => _LocalCareToken(token) ? _LocalCareFauxId(token) : token).join(',');
            _LocalCareLog(() => {
                const store = GetPersonalStore();
                const known = list => list.map(id => InventoryAPI.IsItemInfoValid(id) + '/' + InventoryAPI.IsValidItemID(id)).join(',');
                return 'claim generation=' + (store ? store.generation_time : 0) + ' balance=' + m_redeemableBalance +
                    ' tokens=' + tokens.join(',') + ' known=' + known(tokens) + ' submitted=' + szItemList + ' known=' + known(szItemList.split(','));
            });
        }
'''
TIMEOUT = '''        if (_LocalCarePackage()) _LocalCareLog('claim timed out: no free_reward_redeemed notification within 10s');
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
    submit = '        StoreAPI.StoreRedeemFreeRewards(szItemList);'
    timeout = '    function _RedemptionTimedOut() {'
    if source.count(submit) != 1 or source.count(timeout) != 1 or source.count('        let szItemList = ') != 1:
        raise ValueError('Installed reward claim handler changed; no patch written')
    source=source.replace(submit,SUBMIT+submit,1)
    source=source.replace(timeout,timeout+'\n'+TIMEOUT,1)
    source=source.replace('Object.values(objStore.items)', 'Object.values(objStore.items || {})')
    return source


def prepare(directory, config):
    return install_override(directory, enabled=bool(config['care_packages_enabled']), folder='cs2_gc_care',
        comment='cs2_gc native care packages', owner='cs2-gc-care-packages-v1',
        asset='panorama/scripts/rankup_redemption_store.vts_c', patch=patch)

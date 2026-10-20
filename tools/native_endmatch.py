"""Native offline results tab using actual cached inventory, profile and Premier data.

CS2's stock rank/XP panels wait for engine-owned data-ready flags. This adds a
local results panel to the existing EndOfMatch sequence without fake GC message
IDs or guessed Panorama interfaces. It never grants or acknowledges an item.
"""
import json
from native_resources import install_override

SCRIPT = '''
    // cs2_gc local results: use live cache values, never manufacture rewards in UI.
    let m_localResultsBaseline = null;
    let m_localResultsOldRating = 0;
    let m_localResultsPanel = null;
    let m_localResultsOpen = false;
    let m_localResultsDrawn = {};
    let m_localResultsTick = null;
    function _LocalUnacknowledged() {
        const ids = [];
        const count = InventoryAPI.GetUnacknowledgeItemsCount();
        for (let i = 0; i < count; ++i) {
            const id = String(InventoryAPI.GetUnacknowledgeItemByIndex(i));
            const numeric = Number(id);
            if (numeric > 1000000000000 && numeric < 2000000000000) ids.push(id);
        }
        return ids;
    }
    function _LocalResultsCapture() {
        if (!_m_cP || !_m_cP.IsValid()) return;
        if (!m_localResultsOpen && m_localResultsBaseline === null && MyPersonaAPI.IsInventoryValid()) {
            m_localResultsBaseline = _LocalUnacknowledged();
            m_localResultsOldRating = Number(FriendsListAPI.GetFriendCompetitiveRank(MyPersonaAPI.GetXuid(), 'Premier')) || 0;
        }
        m_localResultsTick = $.Schedule(1, _LocalResultsCapture);
    }
    function _LocalResultsRefresh() {
        if (!m_localResultsOpen || !m_localResultsPanel || !m_localResultsPanel.IsValid()) return;
        const panel = m_localResultsPanel;
        const xuid = MyPersonaAPI.GetXuid();
        const wins = Number(FriendsListAPI.GetFriendCompetitiveWins(xuid, 'Premier')) || 0;
        const score = wins >= __PLACEMENTS__ ? Number(FriendsListAPI.GetFriendCompetitiveRank(xuid, 'Premier')) || 0 : 0;
        const level = Number(MyPersonaAPI.GetCurrentLevel()) || 1;
        panel.FindChildTraverse('local-results-level').text = 'Profile level ' + level;
        const rating = panel.FindChildTraverse('local-results-rating');
        const difference = score && m_localResultsOldRating ? score - m_localResultsOldRating : 0;
        rating.text = score ? 'CS Rating  ' + score + (difference ? '   (' + (difference > 0 ? '+' : '') + difference + ')' : '') :
            'Premier placements  ' + wins + ' / ' + __PLACEMENTS__ + ' wins';
        const items = _LocalUnacknowledged().filter(id => {
            if (m_localResultsBaseline === null || m_localResultsBaseline.indexOf(id) !== -1) return false;
            const pickup = InventoryAPI.GetItemPickupMethod(id) || '';
            return ['purchased', 'purchasedvolatile', 'crafted', 'found_in_crate', 'xpshopredeem'].indexOf(pickup) === -1;
        });
        const list = panel.FindChildTraverse('local-results-items');
        items.forEach(id => {
            if (m_localResultsDrawn[id]) return;
            m_localResultsDrawn[id] = true;
            const tile = $.CreatePanel('Panel', list, '', {style:'width:220px;height:210px;margin:10px;flow-children:down;background-color:#17212bea;'});
            $.CreatePanel('ItemImage', tile, '', {itemid:id, style:'width:210px;height:150px;'});
            const name = $.CreatePanel('Label', tile, '', {text:InventoryAPI.GetItemName(id)});
            name.style.fontSize = '18px'; name.style.width = '210px'; name.style.textAlign = 'center';
            const color = InventoryAPI.GetItemRarityColor(id);
            if (color) name.style.color = color;
        });
        panel.FindChildTraverse('local-results-status').text = Object.keys(m_localResultsDrawn).length ?
            'Rewards added to your inventory' : 'Waiting for local match rewards...';
        $.Schedule(.5, _LocalResultsRefresh);
    }
    function _LocalResultsInitialize() {
        if (GameStateAPI.IsDemoOrHltv() || GameStateAPI.IsQueuedMatchmaking()) return;
        if (!m_localResultsBaseline && MyPersonaAPI.IsInventoryValid()) {
            // Without a pre-match baseline, do not label old unacknowledged items as new drops.
            m_localResultsBaseline = _LocalUnacknowledged();
        }
        m_localResultsOpen = true;
        m_localResultsDrawn = {};
        const layout = _m_cP.FindChildTraverse('id-eom-layout');
        const panel = $.CreatePanel('Panel', layout, 'eom-local-results', {class:'eom-panel'});
        m_localResultsPanel = panel;
        panel.style.width = '100%'; panel.style.height = '100%';
        panel.style.flowChildren = 'down'; panel.style.padding = '110px 100px 30px 100px';
        panel.style.backgroundColor = '#0c1522f5';
        $.CreatePanel('Label', panel, '', {text:'MATCH REWARDS', style:'font-size:36px;color:#e8d8a0;margin-bottom:18px;'});
        $.CreatePanel('Label', panel, 'local-results-rating', {style:'font-size:42px;color:#dddddd;margin-bottom:12px;'});
        $.CreatePanel('Label', panel, 'local-results-level', {style:'font-size:24px;color:#a9c8dc;margin-bottom:25px;'});
        $.CreatePanel('Panel', panel, 'local-results-items', {style:'width:100%;height:250px;flow-children:right;overflow:scroll squish;'});
        $.CreatePanel('Label', panel, 'local-results-status', {style:'font-size:20px;color:#c4d1db;margin-top:18px;'});
        // Stock subpanels register during layout loading. Insert after the victory card.
        $.Schedule(0, () => {
            if (!panel.IsValid() || !m_localResultsOpen) return;
            _m_data._m_arrPanelObjects.splice(Math.min(1, _m_data._m_arrPanelObjects.length), 0, {
                name:'eom-local-results',
                Start: () => {
                    EndOfMatch.SwitchToPanel('eom-local-results');
                    EndOfMatch.StartDisplayTimer(6);
                    _LocalResultsRefresh();
                    $.Schedule(6, () => { if (m_localResultsOpen) EndOfMatch.ShowNextPanel(); });
                }
            });
        });
    }
    _LocalResultsCapture();
'''


def patch(source, config):
    if 'cs2_gc local results' in source: raise ValueError('End-of-match script already patched')
    start = '    function _Initialize() {'
    layout = '        elLayout.BLoadLayoutSnippet(strEomLayoutSnippet);'
    shutdown = '    function _Shutdown() {'
    title = '            elRBtn.FindChildTraverse("id-navbar-button__label").text = $.Localize("#" + elPanel.id);'
    if any(source.count(a) != 1 for a in (start, layout, shutdown, title)):
        raise ValueError('Installed end-of-match layout differs from the inspected client')
    code = SCRIPT.replace('__PLACEMENTS__', str(config['premier_placement_wins']))
    source = source.replace(start, code + '\n' + start, 1)
    source = source.replace(layout, layout + '\n        _LocalResultsInitialize();', 1)
    source = source.replace(title, '            elRBtn.FindChildTraverse("id-navbar-button__label").text = elPanel.id === "eom-local-results" ? "REWARDS & RATING" : $.Localize("#" + elPanel.id);', 1)
    source = source.replace(shutdown, shutdown + '''
        m_localResultsOpen = false;
        m_localResultsPanel = null;
        m_localResultsBaseline = null;
''', 1)
    return source


def prepare(directory, config):
    return install_override(directory, enabled=bool(config.get('end_match_screens', 1)), folder='cs2_gc_results',
        comment='cs2_gc native match results', owner='cs2-gc-results-v1',
        asset='panorama/scripts/endofmatch.vts_c', patch=lambda source: patch(source, config))

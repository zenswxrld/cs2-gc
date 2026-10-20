"""Native offline results tab using actual cached inventory, profile and Premier data.

CS2's stock rank/XP panels wait for engine-owned data-ready flags. This adds a
local results panel to the existing EndOfMatch sequence without fake GC message
IDs or guessed Panorama interfaces. It never grants or acknowledges an item.
"""
from native_resources import install_override

SCRIPT = '''
    // cs2_gc local results: use live cache values, never manufacture rewards in UI.
    let m_localResultsBaseline = null;
    let m_localResultsOldRating = 0;
    let m_localResultsPanel = null;
    let m_localResultsOpen = false;
    let m_localResultsDrawn = {};
    let m_localResultsTick = null;
    let m_localResultsDrops = [];
    let m_localDelayMap = null;
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
    function _LocalCollectDrops() {
        if (m_localResultsBaseline === null) return;
        _LocalUnacknowledged().forEach(id => {
            if (m_localResultsBaseline.indexOf(id) !== -1 || m_localResultsDrops.indexOf(id) !== -1) return;
            const pickup = InventoryAPI.GetItemPickupMethod(id) || '';
            if (['purchased','purchasedvolatile','crafted','found_in_crate','xpshopredeem'].indexOf(pickup) === -1)
                m_localResultsDrops.push(id);
        });
    }
    function _LocalResultsCapture() {
        if (!_m_cP || !_m_cP.IsValid()) return;
        if (!m_localResultsOpen && m_localResultsBaseline === null && MyPersonaAPI.IsInventoryValid()) {
            m_localResultsBaseline = _LocalUnacknowledged();
            m_localResultsOldRating = Number(FriendsListAPI.GetFriendCompetitiveRank(MyPersonaAPI.GetXuid(), 'Premier')) || 0;
        }
        _LocalCollectDrops();
        if (!m_localResultsOpen && !EndOfMatch.LocalBaseline && MyPersonaAPI.IsInventoryValid()) {
            // Start-of-match values for the stock XP bar and rating reveal (native_endmatch_stock.py).
            const xuid = MyPersonaAPI.GetXuid();
            EndOfMatch.LocalBaseline = {
                level: Number(MyPersonaAPI.GetCurrentLevel()) || 1,
                xp: typeof MyPersonaAPI.GetCurrentXp === 'function' ? Number(MyPersonaAPI.GetCurrentXp()) || 0 : 0,
                rating: Number(FriendsListAPI.GetFriendCompetitiveRank(xuid, 'Premier')) || 0,
                wins: Number(FriendsListAPI.GetFriendCompetitiveWins(xuid, 'Premier')) || 0
            };
        }
        if (!GameStateAPI.IsDemoOrHltv() && !GameStateAPI.IsQueuedMatchmaking()) {
            const map = GameStateAPI.GetMapBSPName();
            if (map && map !== m_localDelayMap) {
                GameInterfaceAPI.ConsoleCommand('mp_match_restart_delay __DELAY__');
                m_localDelayMap = map;
            }
        }
        m_localResultsTick = $.Schedule(1, _LocalResultsCapture);
    }
    function _LocalResultsRefresh() {
        if (!m_localResultsOpen || !m_localResultsPanel || !m_localResultsPanel.IsValid()) return;
        const panel = m_localResultsPanel;
        _LocalCollectDrops();
        const items = m_localResultsDrops;
        const list = panel.FindChildTraverse('local-results-items');
        items.forEach(id => {
            if (m_localResultsDrawn[id]) return;
            m_localResultsDrawn[id] = true;
            const tile = $.CreatePanel('Panel', list, '', {style:'width:200px;height:215px;margin:8px;flow-children:down;background-color:#17212bff;border:1px solid #395055;'});
            $.CreatePanel('ItemImage', tile, '', {itemid:id, style:'width:198px;height:150px;'});
            const name = $.CreatePanel('Label', tile, '', {text:InventoryAPI.GetItemName(id)});
            name.style.fontSize = '17px'; name.style.width = '198px'; name.style.textAlign = 'center';
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
        panel.style.flowChildren = 'none'; panel.style.padding = '0px';
        panel.style.backgroundColor = '#0b141ffb';
        const card = $.CreatePanel('Panel', panel, 'local-results-card');
        card.style.width = '1160px'; card.style.height = 'fit-children'; card.style.horizontalAlign = 'center';
        card.style.marginTop = '64px'; card.style.padding = '32px'; card.style.flowChildren = 'down';
        card.style.backgroundColor = '#14232cff'; card.style.border = '1px solid #3d585d';
        $.CreatePanel('Label', card, '', {text:'MATCH DROPS', style:'font-size:24px;color:#e8d8a0;margin-bottom:18px;'});
        $.CreatePanel('Panel', card, 'local-results-items', {style:'width:100%;height:240px;flow-children:right;overflow:scroll squish;'});
        $.CreatePanel('Label', card, 'local-results-status', {style:'font-size:20px;color:#c4d1db;margin-top:18px;'});
        // Stock subpanels register during layout loading. Insert after the victory card.
        $.Schedule(0, () => {
            if (!panel.IsValid() || !m_localResultsOpen) return;
            _m_data._m_arrPanelObjects.splice(Math.min(1, _m_data._m_arrPanelObjects.length), 0, {
                name:'eom-local-results',
                Start: () => {
                    // XP and rating use the stock panels; this tab is only for item drops.
                    _LocalCollectDrops();
                    if (!m_localResultsDrops.length) {
                        const tab = _m_cP.FindChildTraverse('rb--eom-local-results');
                        if (tab) tab.visible = false;
                        EndOfMatch.ShowNextPanel();
                        return;
                    }
                    EndOfMatch.SwitchToPanel('eom-local-results');
                    EndOfMatch.StartDisplayTimer(__DURATION__);
                    _LocalResultsRefresh();
                    $.Schedule(__DURATION__, () => { if (m_localResultsOpen) EndOfMatch.ShowNextPanel(); });
                }
            });
        });
    }
    $.RegisterForUnhandledEvent('PanoramaComponent_MyPersona_InventoryUpdated', _LocalCollectDrops);
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
    code = SCRIPT.replace('__PLACEMENTS__', str(config['premier_placement_wins'])).replace('__DURATION__', str(config['end_match_duration'])).replace('__DELAY__', str(config['match_end_delay']))
    navigate = '    function _NavigateToTab(tab) {'
    if source.count(navigate) != 1: raise ValueError('Changed end-of-match navigation')
    source = source.replace(navigate, navigate + "\n        _m_cP.FindChildTraverse('id-eom-layout').style.height = tab === 'eom-local-results' ? '100%' : '300px';", 1)
    source = source.replace(start, code + '\n' + start, 1)
    source = source.replace(layout, layout + '\n        _LocalResultsInitialize();', 1)
    source = source.replace(title, '            elRBtn.FindChildTraverse("id-navbar-button__label").text = elPanel.id === "eom-local-results" ? "DROPS" : $.Localize("#" + elPanel.id);', 1)
    source = source.replace(shutdown, shutdown + '''
        m_localResultsOpen = false;
        EndOfMatch.LocalBaseline = null;
        m_localResultsPanel = null;
        m_localResultsBaseline = null;
        m_localResultsDrops = [];
''', 1)
    return source


def prepare(directory, config):
    return install_override(directory, enabled=bool(config.get('end_match_screens', 1)), folder='cs2_gc_results',
        comment='cs2_gc native match results', owner='cs2-gc-results-v1',
        asset='panorama/scripts/endofmatch.vts_c', patch=lambda source: patch(source, config))

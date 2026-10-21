"""Drive CS2's own end-of-match XP bar and CS Rating reveal from local GC data.

Offline, the stock EOM_Rank / EOM_Skillgroup panels skip themselves because the engine never marks XP or
skill-group data ready (that data normally arrives from Valve's servers). These patches keep the stock code path
and only feed it local values when the engine data is missing:
- XP: level/XP the local GC already sends during the match, against a baseline taken when the match started
  (EndOfMatch.LocalBaseline, set by the native_endmatch.py patch of endofmatch.js).
- Rating: the local Premier rating/wins before and after the match, in the stock Premier reveal (with the
  promotion animation when the rating changes).
Real matchmaking data, demos and HLTV keep the stock behaviour.
"""
from native_resources import install_override

LOCAL_GUARD = ("typeof EndOfMatch !== 'undefined' && EndOfMatch.LocalBaseline && "
               "!GameStateAPI.IsDemoOrHltv() && !GameStateAPI.IsQueuedMatchmaking()")

RANK_ANCHOR = """        if (!MockAdapter.bXpDataReady(_m_cP))
            return false;
        if (MyPersonaAPI.GetElevatedState() !== 'elevated')
            return false;
        let xPPerLevel = MyPersonaAPI.GetXpPerLevel();
        let oXpData = MockAdapter.XPDataJSO(_m_cP);"""
RANK_INSERT = """        // cs2_gc: offline matches use the local GC's level/XP when the engine has no XP data.
        const localXpData = MockAdapter.bXpDataReady(_m_cP) ? null : _LocalXpData();
        if (!localXpData) {
            if (!MockAdapter.bXpDataReady(_m_cP))
                return false;
            if (MyPersonaAPI.GetElevatedState() !== 'elevated')
                return false;
        }
        let xPPerLevel = MyPersonaAPI.GetXpPerLevel();
        let oXpData = localXpData || MockAdapter.XPDataJSO(_m_cP);"""
RANK_HELPER = """    function _LocalXpData() {
        if (!(__GUARD__) || typeof MyPersonaAPI.GetCurrentXp !== 'function')
            return null;
        const base = EndOfMatch.LocalBaseline;
        const perLevel = Number(MyPersonaAPI.GetXpPerLevel()) || 5000;
        const level = Number(MyPersonaAPI.GetCurrentLevel()) || base.level;
        const xp = Number(MyPersonaAPI.GetCurrentXp()) || 0;
        const gained = (level - base.level) * perLevel + xp - base.xp;
        if (!(gained > 0))
            return null;
        return { current_level: base.level, current_xp: base.xp, xp_progress_data: [{ xp_points: gained, xp_category: 1 }] };
    }
"""

SKILL_ANCHOR = """        if (!MockAdapter.bSkillgroupDataReady(_m_cP))
            return false;
        if (MyPersonaAPI.GetElevatedState() !== 'elevated')
            return false;
        let oSkillgroupData = MockAdapter.SkillgroupDataJSO(_m_cP);
        let localPlayerUpdate = oSkillgroupData[MockAdapter.GetLocalPlayerXuid()];"""
SKILL_INSERT = """        // cs2_gc: offline matches show the local Premier rating change in the stock reveal.
        const localRankData = MockAdapter.bSkillgroupDataReady(_m_cP) ? null : _LocalRankData();
        if (!localRankData) {
            if (!MockAdapter.bSkillgroupDataReady(_m_cP))
                return false;
            if (MyPersonaAPI.GetElevatedState() !== 'elevated')
                return false;
        }
        let localPlayerUpdate = localRankData || MockAdapter.SkillgroupDataJSO(_m_cP)[MockAdapter.GetLocalPlayerXuid()];"""
SKILL_HELPER = """    function _LocalRankData() {
        if (!(__GUARD__))
            return null;
        const base = EndOfMatch.LocalBaseline;
        const xuid = MyPersonaAPI.GetXuid();
        const wins = Number(FriendsListAPI.GetFriendCompetitiveWins(xuid, 'Premier')) || 0;
        const rating = Number(FriendsListAPI.GetFriendCompetitiveRank(xuid, 'Premier')) || 0;
        if (wins === base.wins && rating === base.rating)
            return null;
        const shown = value => wins >= __PLACEMENTS__ ? value : 0;
        const oldRating = base.wins >= __PLACEMENTS__ ? base.rating : 0;
        return { old_rank: oldRating, new_rank: shown(rating), num_wins: wins,
                 rank_change: shown(rating) - oldRating, rank_type: 'Premier' };
    }
"""
# The rating update reaches the client a moment after the final round; wait briefly before skipping the panel.
SKILL_START = """    function Start() {
        if (_DisplayMe()) {"""
SKILL_START_INSERT = """    function Start() {
        if (!MockAdapter.bSkillgroupDataReady(_m_cP) && (__GUARD__) && !_LocalRankData() && _m_cP.Data().m_retries < 8) {
            _m_cP.Data().m_retries++;
            $.Schedule(0.5, Start);
            return;
        }
        _m_cP.Data().m_retries = 0;
        if (_DisplayMe()) {"""


def _insert(source, anchor, insert, helper, marker, name, extra=()):
    if marker in source: raise ValueError(name + ' is already patched')
    if source.count(anchor) != 1: raise ValueError('Installed ' + name + ' layout has changed; no patch was written')
    for old, _ in extra:
        if source.count(old) != 1: raise ValueError('Installed ' + name + ' layout has changed; no patch was written')
    source = source.replace(anchor, insert, 1)
    for old, new in extra: source = source.replace(old, new, 1)
    function = '    function _DisplayMe() {'
    if source.count(function) != 1: raise ValueError('Installed ' + name + ' layout has changed; no patch was written')
    return source.replace(function, helper + function, 1)


def patch_rank(source):
    return _insert(source, RANK_ANCHOR, RANK_INSERT, RANK_HELPER.replace('__GUARD__', LOCAL_GUARD),
                   'function _LocalXpData()', 'end-of-match XP panel')


def patch_skillgroup(source, config):
    helper = SKILL_HELPER.replace('__GUARD__', LOCAL_GUARD).replace('__PLACEMENTS__', str(config['premier_placement_wins']))
    start = SKILL_START_INSERT.replace('__GUARD__', LOCAL_GUARD)
    return _insert(source, SKILL_ANCHOR, SKILL_INSERT, helper, 'function _LocalRankData()', 'end-of-match rating panel',
                   extra=[(SKILL_START, start)])


def prepare(directory, config):
    enabled = bool(config.get('end_match_screens', 1))
    rank = install_override(directory, enabled=enabled, folder='cs2_gc_eom_xp', comment='cs2_gc stock end-of-match XP',
                            owner='cs2-gc-eom-xp-v1', asset='panorama/scripts/endofmatch-rank.vts_c', patch=patch_rank)
    rating = install_override(directory, enabled=enabled and bool(config['premier_enabled']), folder='cs2_gc_eom_rating',
                              comment='cs2_gc stock end-of-match rating', owner='cs2-gc-eom-rating-v1',
                              asset='panorama/scripts/endofmatch-skillgroup.vts_c',
                              patch=lambda source: patch_skillgroup(source, config))
    return 'XP ' + rank + '; rating ' + rating

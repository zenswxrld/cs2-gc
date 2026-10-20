"""Install native Premier scoreboard badges from the user's own compiled script.

Reuses CS2 RatingEmblem/FriendsListAPI calls from the pinned scoreboard/playercard
scripts. Only a dedicated override is written; installed VPKs remain read-only.
"""
import re
from native_resources import install_override

FOLDER = 'cs2_gc_scoreboard'
COMMENT = 'cs2_gc native premier scoreboard'
OWNER = 'cs2-gc-premier-scoreboard-v1'
ASSET = 'panorama/scripts/scoreboard.vjs_c'
INJECT = '''
                    // cs2_gc native Premier badges: reuse the existing rating emblem.
                    const localXuid = MyPersonaAPI.GetXuid();
                    const localMode = MockAdapter.GetGameModeInternalName(false);
                    const isLocal = oPlayer.m_xuid === localXuid;
                    const isBot = MockAdapter.IsFakePlayer(oPlayer.m_xuid);
                    if (isLocal && !oPlayer.m_oStats.cs2gcLogged) {
                        oPlayer.m_oStats.cs2gcLogged = true;
                        $.Msg('cs2_gc scoreboard hook reached: mode=' + localMode +
                              ' queued=' + GameStateAPI.IsQueuedMatchmakingMode_Team());
                    }
                    if ((isLocal || (__BOTS__ && isBot)) &&
                        (localMode === 'competitive' || localMode === 'premier') &&
                        !GameStateAPI.IsQueuedMatchmakingMode_Team() && !GameStateAPI.IsDemoOrHltv()) {
                        const nativeBadge = oPlayer.m_elPlayer && oPlayer.m_elPlayer.m_elSkillGroup;
                        if (nativeBadge && nativeBadge.IsValid()) {
                            let score = FriendsListAPI.GetFriendCompetitiveRank(localXuid, 'Premier');
                            let wins = FriendsListAPI.GetFriendCompetitiveWins(localXuid, 'Premier');
                            score = Number.isFinite(score) && score >= 0 ? score : 0;
                            wins = Number.isFinite(wins) && wins >= 0 ? wins : 0;
                            if (wins < __PLACEMENTS__) score = 0;
                            const badgeKey = 'localPremier:' + score + ':' + wins;
                            nativeBadge.visible = true;
                            if (oPlayer.m_oStats[stat] !== badgeKey) {
                                oPlayer.m_oStats[stat] = badgeKey;
                                RatingEmblem.SetXuid({
                                    root_panel: nativeBadge, full_details: false,
                                    rating_type: 'Premier',
                                    leaderboard_details: { score: score, matchesWon: wins },
                                    local_player: isLocal
                                });
                            }
                        }
                        break;
                    }
'''


ROW_ANCHOR = re.compile(r"(function _GetPlayerRowForGameMode\(\)\s*\{\s*let mode = MockAdapter\.GetGameModeInternalName\(false\);\s*let skirmish = MockAdapter\.GetGameModeInternalName\(true\);)")
ROW_INJECT = '''
        // cs2_gc: offline Competitive uses the row layout that holds the native rating emblem (the Premier row).
        if ((mode === 'competitive' || mode === 'premier') && !GameStateAPI.IsDemoOrHltv())
            return 'snippet_scoreboard-classic__row--premier';'''


def patch(source, config):
    if 'cs2_gc native Premier badges' in source: raise ValueError('Scoreboard is already patched')
    # Require the actual inspected API shape; fail without affecting native files if it changes.
    required = ("oPlayer.GetGameStat('comp_ranking')", "oPlayer.GetGameStat('comp_type')",
                'RatingEmblem.SetXuid(options)', "FindChildTraverse('jsRatingEmblem')")
    if not all(anchor in source for anchor in required): raise ValueError('Installed scoreboard API layout has changed')
    anchor = re.compile(r"(case\s+'skillgroup'\s*:\s*\{)")
    if len(anchor.findall(source)) != 1: raise ValueError('Ambiguous scoreboard skillgroup branch')
    if len(ROW_ANCHOR.findall(source)) != 1: raise ValueError('Ambiguous scoreboard row selector')
    source = ROW_ANCHOR.sub(lambda match: match.group(0) + ROW_INJECT, source, count=1)
    insert = INJECT.replace('__BOTS__', 'true' if config['premier_bot_badges'] else 'false')
    insert = insert.replace('__PLACEMENTS__', str(config['premier_placement_wins']))
    return anchor.sub(lambda match: match.group(0) + insert, source, count=1)


def prepare(proxy_directory, config):
    return install_override(proxy_directory,
        enabled=bool(config['premier_enabled'] and config['premier_scoreboard']),
        folder=FOLDER, comment=COMMENT, owner=OWNER, asset=ASSET,
        patch=lambda source: patch(source, config))

"""Route the native recurring mission card into a local bot session.

Settings/API evidence: inspected mission_tile and mainmenu_play from client 25966348.
This does not implement recurring mission progress or completion rewards.
"""
from native_resources import install_override

START = '    function PlayMission() {'
END = '    function OnRoundStart() {'
REPLACEMENT = '''    let m_localMissionStarting = false;
    function PlayMission() {
        if (m_localMissionStarting) return;
        // cs2_gc: mission launch uses the native listen-server path, never official matchmaking.
        const mission = $.GetContextPanel().Data().m_oMissionData;
        const cfg = GameTypesAPI.GetConfig();
        const mode = mission && mission.gamemode;
        const localModes = ['casual', 'competitive', 'scrimcomp2v2', 'deathmatch', 'gungameprogressive'];
        const type = Object.keys(cfg.gameTypes || {}).find(key =>
            cfg.gameTypes[key].gameModes && Object.prototype.hasOwnProperty.call(cfg.gameTypes[key].gameModes, mode));
        const group = mission && cfg.mapgroups && cfg.mapgroups[mission.mapgroup];
        const maps = group && group.maps ? Object.keys(group.maps) : [];
        const map = mission && mission.map ? mission.map : (maps.length ? maps[Math.floor(Math.random() * maps.length)] : '');
        if (!type || !localModes.includes(mode) || !/^[a-z0-9_]+$/i.test(map)) {
            UiToolkitAPI.ShowGenericPopupOk('Offline mission',
                'This mission has no supported local map and mode. No matchmaking was started.', '', () => {});
            return;
        }
        if (PartyListAPI.GetCount() > 1) {
            UiToolkitAPI.ShowGenericPopupOk('Offline mission', 'Leave your party before starting a local bot mission.', '', () => {});
            return;
        }
        m_localMissionStarting = true;
        // Cancel a previous search and discard its stale session after disconnect.
        LobbyAPI.StopMatchmaking();
        LobbyAPI.CloseSession();
        // Keep a supported bot difficulty; restore a playable difficulty when the saved selection is outside that range.
        const savedDifficulty = Number(GameInterfaceAPI.GetSettingString('player_botdifflast_s'));
        const difficulty = Number.isInteger(savedDifficulty) && savedDifficulty >= 0 && savedDifficulty <= 3 ? savedDifficulty : 2;
        GameTypesAPI.SetCustomBotDifficulty(difficulty);
        const settings = {
            update: {
                Options: {
                    action: 'custommatch', server: 'listen',
                    practicesettings_grenades: 0, practicesettings_infammo: 0,
                    practicesettings_infwarmup: 0, practicesettings_annotations: 0
                },
                Game: {
                    mode: mode, type: type, mapgroupname: 'mg_' + map, map: map,
                    gamemodeflags: mode === 'deathmatch' ? 32 : mode === 'competitive' ? 16 : 0
                }
            },
            delete: { Options: { challengekey: 1 } }
        };
        let attempts = 0;
        function startLocal() {
            const session = LobbyAPI.GetSessionSettings();
            const ready = session && session.options && session.game &&
                session.options.server === 'listen' && session.options.action === 'custommatch' &&
                session.game.mode === mode && session.game.type === type &&
                (!session.game.map || session.game.map === map) && session.game.mapgroupname === 'mg_' + map &&
                Number(session.game.gamemodeflags || 0) === settings.update.Game.gamemodeflags;
            if (ready && LobbyAPI.BIsHost() && !IsSearching()) {
                m_localMissionStarting = false;
                $.DispatchEvent('CSGOPlaySoundEffect', 'mainmenu_mission_start', 'MOUSE');
                LobbyAPI.StartMatchmaking('', '', '', '');
                return;
            }
            if (++attempts >= 30) {
                m_localMissionStarting = false;
                LobbyAPI.StopMatchmaking();
                UiToolkitAPI.ShowGenericPopupOk('Offline mission',
                    'The local bot session was not ready. Try again from the main menu.', '', () => {});
                return;
            }
            if (!LobbyAPI.IsSessionActive()) LobbyAPI.CreateSession();
            if (LobbyAPI.BIsHost()) LobbyAPI.UpdateSessionSettings(settings);
            $.Schedule(0.1, startLocal);
        }
        $.Schedule(0.1, startLocal);
    }
'''


def patch(source):
    if source.count(START) != 1 or source.count(END) != 1 or 'cs2_gc: mission launch' in source:
        raise ValueError('Installed mission launch script changed; no patch written')
    start, end = source.index(START), source.index(END)
    original = source[start:end]
    if end <= start or 'server: "official"' not in original or "LobbyAPI.StartMatchmaking('', '', '', '');" not in original:
        raise ValueError('Installed mission launch contract changed; no patch written')
    return source[:start] + REPLACEMENT + source[end:]


def prepare(directory, config):
    return install_override(directory, enabled=bool(config['offline_mission_launch']), folder='cs2_gc_missions',
        comment='cs2_gc local bot mission launch', owner='cs2-gc-mission-launch-v1',
        asset='panorama/scripts/mission_tile.vts_c', patch=patch)

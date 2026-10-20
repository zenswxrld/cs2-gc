"""Local bot-match rating rules, separate from profile XP and Valve matchmaking."""

def initial(config):
    return {'rating': config['premier_start_rating'], 'wins': 0, 'losses': 0, 'ties': 0, 'last_change': 0}


def outcome(game_map, team):
    # Only round-based competitive results; casual/deathmatch are not Premier placements.
    if game_map.get('mode') != 'competitive' or team not in ('T', 'CT'): return None
    ct, terrorist = game_map.get('team_ct'), game_map.get('team_t')
    if not isinstance(ct, dict) or not isinstance(terrorist, dict): return None
    own, other = (ct.get('score'), terrorist.get('score')) if team == 'CT' else (terrorist.get('score'), ct.get('score'))
    if type(own) is not int or type(other) is not int or min(own, other) < 0 or own + other == 0: return None
    return 'wins' if own > other else 'losses' if own < other else 'ties'


def apply(state, result, config):
    if result not in ('wins', 'losses', 'ties') or not config['premier_enabled']: return state.copy()
    updated = state.copy()
    updated[result] += 1
    delta = config['premier_win_rating'] if result == 'wins' else -config['premier_loss_rating'] if result == 'losses' else 0
    previous = updated['rating']
    updated['rating'] = max(0, min(config['premier_max_rating'], previous + delta))
    updated['last_change'] = updated['rating'] - previous
    return updated


def visible_rating(state, config):
    return state['rating'] if state['wins'] >= config['premier_placement_wins'] else None


def bot_difficulty(state):
    # Local policy mapped to CS2's normal easy/normal/hard/expert bot_difficulty control.
    return min(3, state['rating'] // 5000)


def status(state, config):
    rating = visible_rating(state, config)
    return (f"Local CS Rating: {rating} ({state['last_change']:+d})" if rating is not None else
            f"Local Premier placement wins: {state['wins']}/{config['premier_placement_wins']}")

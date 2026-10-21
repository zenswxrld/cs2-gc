"""Validated cs2_gc_gameplay.cfg shared with the proxy (restart both after edits)."""
DEFAULTS = {
    'end_match_screens': 1, 'end_match_duration': 20, 'match_end_delay': 45,
    'armory_collection_slots': 3,
    'armory_charm_slots': 2,
    'free_case_keys': 1, 'skip_key_selection': 1, 'knife_finishes': 1, 'glove_finishes': 1, 'glove_panel_variants': 1, 'black_market_price': 100,
    'viewmodel_range_percent': 250, 'viewmodel_fov_min': 40, 'viewmodel_fov_max': 90,
    'armory_sticker_slots': 2,
    'armory_case_slots': 2,
    'armory_capsule_slots': 2,
    'armory_limited_slots': 1,
    'armory_agent_slots': 1,
    'armory_agent_price': 50,
    'reward_rare_case_per_10000': 100,
    'care_packages_enabled': 1,
    'bot_hide_tag': 1, 'hide_mainmenu_promo': 1, 'offline_mission_launch': 1,
    'armory_souvenir_slots': 1, 'armory_souvenir_price': 5,
    'armory_terminal_slots': 1, 'armory_terminal_price': 10, 'armory_case_price': 5,
    'match_weekly_pool_only': 1,
    'item_sales_enabled': 1,
    'sell_consumer': 1,
    'sell_industrial': 2,
    'sell_mil_spec': 5,
    'sell_restricted': 10,
    'sell_classified': 25,
    'sell_covert': 50,
    'sell_knife_glove': 72,
    'sell_sticker_percent': 50,
    'sell_music_kit': 10,
    'sell_container_percent': 30,
    'sell_agent_percent': 50,
    'premier_rating_variation': 79,
    'premier_bot_spread': 1200,

    'rewards_auto_start': 1,
    'xp_enabled': 1, 'stars_enabled': 1, 'armory_xp_per_star': 400,
    'kill_xp': 5, 'headshot_xp': 3, 'mvp_xp': 25, 'match_complete_xp': 600,
    'match_drops_enabled': 1, 'match_drop_count': 3, 'match_case_percent': 50, 'match_skin_min_rarity': 3,
    'mixed_stattrak_tradeups': 1, 'pity_enabled': 1, 'pity_soft_at': 10, 'pity_hard_at': 100,
    'case_gold_per_10000': 26, 'terminal_top_per_10000': 64,
    'terminals_enabled': 1, 'terminal_default_offers': 5, 'terminal_lifetime_days': 7,
    'terminal_helper_enabled': 1,
    'armory_rotation_enabled': 1, 'armory_rotation_seconds': 900, 'armory_rotation_slots': 6,
    'armory_rotation_enforce': 0,
    'armory_howl_enabled': 1, 'armory_howl_star_price': 250,
    'premier_enabled': 1, 'premier_placement_wins': 10, 'premier_start_rating': 1000,
    'premier_scoreboard': 1, 'premier_bot_badges': 1, 'bot_fake_ping': 1, 'bot_random_names': 1,
    'level_drops_enabled': 1, 'level_drop_count': 3,
    'skip_container_confirmation': 1,
    'hide_rent_button': 1,
    'armory_pity_enabled': 1, 'armory_pity_soft_at': 10, 'armory_pity_hard_at': 100,
    'armory_top_per_10000': 64,
    'premier_win_rating': 300, 'premier_loss_rating': 100, 'premier_max_rating': 35000,
    'premier_bonus_wins': 0,
}
LIMITS = {key: (0, 1) for key in DEFAULTS}
LIMITS.update({key: (0, 1000000) for key in ('kill_xp', 'headshot_xp', 'mvp_xp', 'match_complete_xp')})
LIMITS.update({'viewmodel_range_percent': (100, 1000), 'viewmodel_fov_min': (1, 179), 'viewmodel_fov_max': (1, 179), 'armory_case_price': (1, 1000000), 'black_market_price': (1, 1000000), 'glove_finishes': (0, 1), 'free_case_keys': (0, 1), 'armory_collection_slots': (0, 6), 'armory_charm_slots': (0, 6), 'armory_sticker_slots': (0, 6), 'armory_case_slots': (0, 6), 'armory_capsule_slots': (0, 6), 'armory_limited_slots': (0, 6), 'armory_agent_slots': (0, 6), 'armory_agent_price': (0, 1000000), 'match_weekly_pool_only': (0, 1), 'item_sales_enabled': (0, 1), 'sell_consumer': (0, 1000000), 'sell_industrial': (0, 1000000), 'sell_mil_spec': (0, 1000000), 'sell_restricted': (0, 1000000), 'sell_classified': (0, 1000000), 'sell_covert': (0, 1000000), 'sell_knife_glove': (0, 1000000), 'sell_sticker_percent': (0, 100), 'sell_music_kit': (0, 1000000), 'sell_container_percent': (0, 100), 'sell_agent_percent': (0, 100), 'premier_rating_variation': (0, 10000), 'premier_bot_spread': (0, 10000)})
LIMITS.update(reward_rare_case_per_10000=(0, 10000), armory_souvenir_slots=(0, 6), armory_souvenir_price=(1, 1000000), armory_terminal_slots=(0, 6), armory_terminal_price=(1, 1000000), end_match_duration=(6, 60), match_end_delay=(25, 120), armory_pity_soft_at=(2, 99), armory_pity_hard_at=(3, 100), armory_top_per_10000=(0, 10000), level_drop_count=(1, 20), armory_howl_star_price=(1, 1000000), premier_placement_wins=(1, 100), premier_start_rating=(0, 99999), premier_win_rating=(0, 10000),
              premier_loss_rating=(0, 10000), premier_max_rating=(1, 99999), premier_bonus_wins=(0, 100), armory_rotation_seconds=(10, 86400), armory_rotation_slots=(1, 60), armory_xp_per_star=(1, 100000), match_drop_count=(1, 20), match_case_percent=(0, 100),
              match_skin_min_rarity=(3, 6), pity_soft_at=(2, 99), pity_hard_at=(3, 100),
              case_gold_per_10000=(0, 10000), terminal_top_per_10000=(0, 10000),
              terminal_default_offers=(1, 100), terminal_lifetime_days=(1, 365))


def parse(text):
    result, seen = DEFAULTS.copy(), set()
    for line in text.splitlines():
        line = line.split('#', 1)[0].strip()
        if not line: continue
        key, equal, value = line.partition('=')
        key, value = key.strip(), value.strip()
        if not equal or key not in result or key in seen or not value.isascii() or not value.isdecimal():
            raise ValueError('Invalid or duplicate gameplay config setting: ' + key)
        number = int(value)
        low, high = LIMITS[key]
        if not low <= number <= high: raise ValueError('Gameplay setting out of range: ' + key)
        result[key] = number
        seen.add(key)
    if result['premier_start_rating'] > result['premier_max_rating']:
        raise ValueError('premier_start_rating must not exceed premier_max_rating')
    if result['pity_soft_at'] >= result['pity_hard_at']:
        raise ValueError('pity_soft_at must be less than pity_hard_at')
    if result['armory_pity_soft_at'] >= result['armory_pity_hard_at']:
        raise ValueError('armory_pity_soft_at must be less than armory_pity_hard_at')
    result['armory_howl_star_price'] = max(250, result['armory_howl_star_price'])
    return result


def load(directory):
    path = directory / 'cs2_gc_gameplay.cfg'
    return parse(path.read_text(encoding='utf-8')) if path.exists() else DEFAULTS.copy()

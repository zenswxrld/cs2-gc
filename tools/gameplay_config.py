"""Validated cs2_gc_gameplay.cfg shared with the proxy (restart both after edits)."""
DEFAULTS = {
    'custom_collection_drop_percent': 15,
    'end_match_screens': 1, 'end_match_duration': 20, 'match_end_delay': 45,
    'armory_collection_slots': 3,
    'armory_charm_slots': 2,
    'free_case_keys': 1, 'skip_key_selection': 1, 'knife_finishes': 1, 'glove_finishes': 1, 'custom_skins_test': 1, 'custom_collections': 0, 'custom_cases': 0, 'custom_collection_tradeups': 1, 'glove_panel_variants': 1, 'black_market_price': 100,
    'viewmodel_range_percent': 250, 'viewmodel_fov_min': 40, 'viewmodel_fov_max': 90,
    'armory_sticker_slots': 2,
    'armory_case_slots': 2,
    'armory_capsule_slots': 2,
    'armory_limited_slots': 1,
    'armory_agent_slots': 1,
    'armory_agent_price': 25,
    'reward_rare_case_per_10000': 100,
    'care_packages_enabled': 1, 'care_packages_from_matches': 0,
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
    'sell_sticker_mil_spec': 2, 'sell_sticker_restricted': 5, 'sell_sticker_classified': 12, 'sell_sticker_covert': 25,
    'sell_max_return_percent': 90,
    'sell_charm_mil_spec': 1, 'sell_charm_restricted': 3, 'sell_charm_classified': 9, 'sell_charm_covert': 25,
    'sell_wear_enabled': 1, 'sell_wear_fn': 125, 'sell_wear_mw': 110, 'sell_wear_ft': 100, 'sell_wear_ww': 80, 'sell_wear_bs': 60,
    'sell_music_kit': 10,
    'sell_container_percent': 30,
    'sell_agent_percent': 50,
    'premier_rating_variation': 79,
    'premier_bot_spread': 1200,

    'rewards_auto_start': 1,
    'xp_enabled': 1, 'profile_xp_percent': 125, 'stars_enabled': 1, 'armory_xp_per_star': 400, 'armory_pass_auto_renew': 1,
    'kill_xp': 5, 'headshot_xp': 3, 'mvp_xp': 25, 'match_complete_xp': 600,
    'plant_xp': 25, 'defuse_xp': 25,
    'kill_stars': 2, 'headshot_stars': 2, 'mvp_stars': 5, 'plant_stars': 5, 'defuse_stars': 5, 'match_complete_stars': 50,
    'match_drops_enabled': 1, 'match_drop_count': 3, 'match_case_percent': 50, 'match_skin_min_rarity': 3,
    'mixed_stattrak_tradeups': 1, 'souvenir_tradeups': 1, 'pity_enabled': 1, 'pity_soft_at': 70, 'pity_hard_at': 100,
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
    'armory_pity_enabled': 1, 'armory_pity_soft_at': 70, 'armory_pity_hard_at': 100,
    'armory_top_per_10000': 50,
    'premier_win_rating': 300, 'premier_loss_rating': 100, 'premier_max_rating': 35000,
    'premier_bonus_wins': 0,
}
LIMITS = {key: (0, 1) for key in DEFAULTS}
LIMITS['custom_collection_drop_percent'] = (0, 100)
LIMITS.update({key:(0,1000000) for key in DEFAULTS if key.startswith('sell_charm_') or key.startswith('sell_sticker_')})
LIMITS.update(sell_sticker_percent=(0, 100), sell_max_return_percent=(1, 95))
LIMITS.update({key:(0,1000) for key in DEFAULTS if key.startswith('sell_wear_') and key!='sell_wear_enabled'})
LIMITS.update({key: (0, 1000000) for key in ('kill_xp', 'headshot_xp', 'mvp_xp', 'match_complete_xp')})
LIMITS.update({key:(0,1000000) for key in ('plant_xp','defuse_xp','kill_stars','headshot_stars','mvp_stars','plant_stars','defuse_stars','match_complete_stars')})
LIMITS.update({'viewmodel_range_percent': (100, 1000), 'viewmodel_fov_min': (1, 179), 'viewmodel_fov_max': (1, 179), 'armory_case_price': (1, 1000000), 'black_market_price': (1, 1000000), 'glove_finishes': (0, 1), 'custom_skins_test': (0, 1), 'custom_collections': (0, 1), 'custom_cases': (0, 1), 'custom_collection_tradeups': (0, 1), 'free_case_keys': (0, 1), 'armory_collection_slots': (0, 6), 'armory_charm_slots': (0, 6), 'armory_sticker_slots': (0, 6), 'armory_case_slots': (0, 6), 'armory_capsule_slots': (0, 6), 'armory_limited_slots': (0, 6), 'armory_agent_slots': (0, 6), 'armory_agent_price': (0, 1000000), 'match_weekly_pool_only': (0, 1), 'item_sales_enabled': (0, 1), 'sell_consumer': (0, 1000000), 'sell_industrial': (0, 1000000), 'sell_mil_spec': (0, 1000000), 'sell_restricted': (0, 1000000), 'sell_classified': (0, 1000000), 'sell_covert': (0, 1000000), 'sell_knife_glove': (0, 1000000), 'sell_sticker_percent': (0, 100), 'sell_music_kit': (0, 1000000), 'sell_container_percent': (0, 100), 'sell_agent_percent': (0, 100), 'premier_rating_variation': (0, 10000), 'premier_bot_spread': (0, 10000)})
LIMITS.update(profile_xp_percent=(50,500), reward_rare_case_per_10000=(0, 10000), armory_souvenir_slots=(0, 6), armory_souvenir_price=(1, 1000000), armory_terminal_slots=(0, 6), armory_terminal_price=(1, 1000000), end_match_duration=(6, 60), match_end_delay=(25, 120), armory_pity_soft_at=(2, 99), armory_pity_hard_at=(3, 100), armory_top_per_10000=(0, 10000), level_drop_count=(1, 20), armory_howl_star_price=(1, 1000000), premier_placement_wins=(1, 100), premier_start_rating=(0, 99999), premier_win_rating=(0, 10000),
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
    return balance(result)


def load(directory):
    path = directory / 'cs2_gc_gameplay.cfg'
    return parse(path.read_text(encoding='utf-8')) if path.exists() else balance(DEFAULTS.copy())


# Star-economy balancing, an exact mirror of cs2_gc BalanceSales (cs2_gc/src/item_sales.cpp): same integer
# arithmetic and the same floating-point operation order, so the native Sell price equals what the GC pays.
COLLECTION_PRICE, CHARM_PRICE, STICKER_PRICE = 4, 3, 1  # catalogue tiles; never cheaper than these
CASE_WEIGHTS = (7992, 1598, 320, 64)
COLLECTION_WEIGHTS = (7992, 1598, 320, 64, 13, 3)

def collection_weights(count):
    if count == 5:return (6400,2500,750,300,50)
    if count == 6:return (4500,3000,1400,750,300,50)
    return COLLECTION_WEIGHTS[:count]


def pity_chance(misses, base, soft_at, hard_at, enabled):
    base = min(base, 10000)
    if not enabled or misses + 1 < soft_at: return base
    if misses + 1 >= hard_at: return 10000
    return base + (10000 - base) * (misses + 2 - soft_at)**2 // (hard_at - soft_at + 1)**2


def pity_rate(base, soft_at, hard_at, enabled):
    expected, survive = 0.0, 1.0
    misses = 0
    while misses < 1000 and survive > 1e-12:
        expected += survive
        survive *= 1.0 - pity_chance(min(misses, 99), base, soft_at, hard_at, enabled) / 10000.0
        misses += 1
    return 1.0 / expected if expected > 0 else 0.0


def _share(value, percent):
    return max(1, value * percent // 100) if value and percent else 0


def _window(values, weights, pity, hit):
    if pity:weights=collection_weights(len(values))
    lower, total = 0.0, 0.0
    for rank in range(len(values) - 1 if pity else len(values)):
        lower += float(weights[rank]) * float(values[rank])
        total += weights[rank]
    lower = lower / total if total > 0 else 0.0
    return hit * float(values[-1]) + (1 - hit) * lower if pity else lower


def _armory_hit(count, c):
    if count < 2: return 1.0
    weights=collection_weights(count)
    total = sum(weights)
    base = max(c['armory_top_per_10000'], weights[count - 1] * 10000 // total)
    return pity_rate(base, c['armory_pity_soft_at'], c['armory_pity_hard_at'], c['armory_pity_enabled'])


def _within(value, price, c):
    return value * 100 <= float(c['sell_max_return_percent']) * price


def _best_of(offer, count):
    merged = {}
    for p, v in offer: merged[v] = merged.get(v, 0.0) + p
    below, result = 0.0, 0.0
    for v in sorted(merged):
        p = merged[v]
        lower, upper = 1.0, 1.0
        for _ in range(count):
            lower *= below
            upper *= below + p
        result += float(v) * (upper - lower)
        below += p
    return result


def _rates(c):
    pity = (c['pity_soft_at'], c['pity_hard_at'], c['pity_enabled'])
    return {'gold': pity_rate(c['case_gold_per_10000'], *pity), 'top': pity_rate(c['terminal_top_per_10000'], *pity),
            'armory': [0.0] + [_armory_hit(count, c) for count in range(1, 7)]}


def sale_diagnostics(c, w, gold, out):
    """Each weapon route's average return as a fraction of its price, for the given values."""
    o = [out(v) for v in w]
    og = out(gold)
    rates = _rates(c)
    g = rates['gold']
    case_values = o[3:7]
    result = {'case': (g * float(og) + (1 - g) * _window(case_values, CASE_WEIGHTS, False, 0)) / c['armory_case_price']}
    if c['terminals_enabled']:
        offer = [(g, og)] + [((1 - g) * CASE_WEIGHTS[r] / 9974.0, case_values[r]) for r in range(4)]
        result['terminal-gold'] = _best_of(offer, c['terminal_default_offers']) / c['armory_terminal_price']
        h = rates['top']
        offer = [(h, o[6])] + [((1 - h) * CASE_WEIGHTS[r] / 9910.0, case_values[r]) for r in range(3)]
        result['terminal-covert'] = _best_of(offer, c['terminal_default_offers']) / c['armory_terminal_price']
    for first in (1, 2):
        for last in range(first + 2, 7):
            values = o[first:last + 1]
            hit = rates['armory'][len(values)]
            result['souvenir %d-%d' % (first, last)] = _window(values, COLLECTION_WEIGHTS, True, hit) / c['armory_souvenir_price']
            if last == 6 and c.get('custom_collections', 0): values = values[:-1] + [max(values[-1], og)]
            result['collection %d-%d' % (first, last)] = _window(values, COLLECTION_WEIGHTS, True, hit) / COLLECTION_PRICE
    return result


def _weapons_within(c, w, gold, out, rates):
    o = [out(v) for v in w]
    og = out(gold)
    g = rates['gold']
    case_values = o[3:7]
    if not _within(g * float(og) + (1 - g) * _window(case_values, CASE_WEIGHTS, False, 0), c['armory_case_price'], c): return False
    if c['terminals_enabled']:
        offer = [(g, og)] + [((1 - g) * CASE_WEIGHTS[r] / 9974.0, case_values[r]) for r in range(4)]
        if not _within(_best_of(offer, c['terminal_default_offers']), c['armory_terminal_price'], c): return False
        h = rates['top']
        offer = [(h, o[6])] + [((1 - h) * CASE_WEIGHTS[r] / 9910.0, case_values[r]) for r in range(3)]
        if not _within(_best_of(offer, c['terminal_default_offers']), c['armory_terminal_price'], c): return False
    for first in (1, 2):
        for last in range(first + 2, 7):
            values = o[first:last + 1]
            hit = rates['armory'][len(values)]
            if not _within(_window(values, COLLECTION_WEIGHTS, True, hit), c['armory_souvenir_price'], c): return False
            if last == 6 and c.get('custom_collections', 0): values = values[:-1] + [max(values[-1], og)]
            if not _within(_window(values, COLLECTION_WEIGHTS, True, hit), COLLECTION_PRICE, c): return False
    return True


def _cap_out(current, limit, enabled, high):
    if not current or not limit: return 0
    most = (((limit + 1) * 100 - 1) // high if high else current) if enabled else limit
    return min(current, most)


def _tiers_within(v, price, minimum_run, singles, c, rates):
    for first in range(3, 7 if singles else 4):
        for last in range(first, 7):
            values = v[first:last + 1]
            count = len(values)
            if singles and (count > 1 or last < 6) and not _within(_window(values, CASE_WEIGHTS, False, 0), price, c): return False
            if count >= minimum_run and not _within(_window(values, COLLECTION_WEIGHTS, True, rates['armory'][count]), price, c): return False
    return True


def _reduce_tiers(v, price, minimum_run, singles, c, rates):
    for t in range(3, 7):
        if _tiers_within(v, price, minimum_run, singles, c, rates): break
        low, high = 0, v[t]
        v[t] = 0
        if not _tiers_within(v, price, minimum_run, singles, c, rates): continue
        while low < high:
            middle = low + (high - low + 1) // 2
            v[t] = middle
            if _tiers_within(v, price, minimum_run, singles, c, rates): low = middle
            else: high = middle - 1
        v[t] = low


WEAPON_KEYS = (None, 'sell_consumer', 'sell_industrial', 'sell_mil_spec', 'sell_restricted', 'sell_classified', 'sell_covert')
STICKER_KEYS = ('sell_sticker_mil_spec', 'sell_sticker_restricted', 'sell_sticker_classified', 'sell_sticker_covert')
CHARM_KEYS = ('sell_charm_mil_spec', 'sell_charm_restricted', 'sell_charm_classified', 'sell_charm_covert')


def wear_model(c):
    if not c['sell_wear_enabled']: return False, 100, 100
    bands = [c['sell_wear_' + band] for band in ('fn', 'mw', 'ft', 'ww', 'bs')]
    nonzero = [band for band in bands if band]
    return True, max(bands), min(nonzero) if nonzero else 0


def balance(c):
    """Lower sale values in place until no purchase route returns more than sell_max_return_percent."""
    enabled, high, low = wear_model(c)
    out = (lambda v: _share(v, high)) if enabled else (lambda v: v)
    inp = (lambda v: _share(v, low)) if enabled else (lambda v: v)
    r = c['sell_max_return_percent']
    rates = _rates(c)
    scale = 1000
    while True:
        w = [0] + [max(1, c[key] * scale // 1000) if c[key] else 0 for key in WEAPON_KEYS[1:]]
        gold = max(1, c['sell_knife_glove'] * scale // 1000) if c['sell_knife_glove'] else 0
        for t in range(1, 6):
            if w[t] and w[t + 1]: w[t + 1] = _cap_out(w[t + 1], r * 10 * inp(w[t]) // 100, enabled, high)
        if w[6]: gold = _cap_out(gold, r * 5 * inp(w[6]) // 100, enabled, high)
        if _weapons_within(c, w, gold, out, rates): break
        if scale == 0:
            w, gold = [0] * 7, 0
            break
        scale -= 1
    for t in range(1, 7): c[WEAPON_KEYS[t]] = w[t]
    c['sell_knife_glove'] = gold
    stickers = [0, 0, 0] + [min(c[key], w[t] * c['sell_sticker_percent'] // 100) for t, key in zip(range(3, 7), STICKER_KEYS)]
    _reduce_tiers(stickers, STICKER_PRICE, 2, True, c, rates)
    for t, key in zip(range(3, 7), STICKER_KEYS): c[key] = stickers[t]
    charms = [0, 0, 0, min(c['sell_charm_mil_spec'], 2)] + [c[key] for key in CHARM_KEYS[1:]]
    _reduce_tiers(charms, CHARM_PRICE, 3, False, c, rates)
    for t, key in zip(range(3, 7), CHARM_KEYS): c[key] = charms[t]
    c['sell_agent_percent'] = min(c['sell_agent_percent'], r)
    while c['sell_agent_percent'] and _share(c['armory_agent_price'], c['sell_agent_percent']) * 100 > r * c['armory_agent_price']:
        c['sell_agent_percent'] -= 1
    while c['sell_container_percent'] and _share(2, c['sell_container_percent']) * 100 > r * c['armory_case_price']:
        c['sell_container_percent'] -= 1
    return c

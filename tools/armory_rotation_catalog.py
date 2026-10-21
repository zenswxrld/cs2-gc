"""Native Armory catalogue, referring only to the installed schema's official goods.

No item, paint-kit, collection or loot-list definitions are created. Capsule pools
are a deliberate curated selection, not a claim of live market popularity rankings.
"""
from inventory_item import collect, parse, as_dict
from native_tradeups import parse as parse_spans
from price_sheet import find_case_items

ARMORY_COLLECTIONS = ('set_graphic_design', 'set_overpass_2024', 'set_realism_camo',
                      'set_spy_tech', 'set_arabesque', 'set_train_2025')
TOURNAMENTS = ('kat2014', 'cologne2014', 'eslkatowice2015', 'eslcologne2015', 'cluj2015', 'columbus2016', 'cologne2016',
               'atlanta2017', 'boston2018', 'katowice2019', 'berlin2019', 'rio2022',
               'stockh2021', 'antwerp2022', 'paris2023', 'cph2024', 'sha2024',
               'aus2025', 'bud2025')
# Team capsules only; exclude individual team packs, souvenir packages and coupons.
TOURNAMENT_GROUPS = ('01', '02', 'legends', 'challengers', 'contenders')
COMMUNITY_CAPSULES = ('crate_sticker_pack_cs20_capsule', 'crate_sticker_pack_csgo10_capsule',
                      'crate_sticker_pack_halo_capsule', 'crate_sticker_pack_hlalyx_capsule',
                      'crate_sticker_pack_skillgroup_capsule', 'crate_sticker_pack_enfu_capsule',
                      'crate_sticker_pack_community01')
LIMITED_PRICES = {'set_xpshop_wpn_01': 25, 'set_xpshop_wpn_02': 15,
                  'set_xpshop_wpn_03': 25, 'set_xpshop_wpn_04': 125}
LIMITED_LISTS = tuple(LIMITED_PRICES)


def catalogue(source, config):
    sections = collect(parse(source))
    lists = sections.get('client_loot_lists', {})
    items = {as_dict(v).get('name'): as_dict(v) for v in sections.get('items', {}).values() if isinstance(v, list)}
    campaign = sections.get('seasonaloperations', {}).get('11')
    if not isinstance(campaign, list) or as_dict(campaign).get('redeemable_goods') != 'xpshop':
        raise ValueError('Expected the inspected native Armory campaign 11')
    goods = {}
    cases = {case[0] for case in find_case_items(sections)}
    terminals = set(terminal_names(source))
    souvenirs = set(souvenir_names(source))

    def add(name, slot, cost, template=None):
        if name in goods: return
        values = dict(template or {})
        values.update(item_name=name, points=str(cost), local_rotation_slot=slot)
        values['ui_order'] = {'collection': '2', 'charm': '1', 'sticker': '1', 'souvenir': '3', 'case': '3', 'capsule': '3', 'limited': '2', 'agent': '1', 'terminal': '3'}[slot]
        values.pop('bidding_cycle', None)
        if slot == 'limited': values['limited_until'] = '2147483647'
        goods[name] = values

    for key, value in campaign:
        if key != 'operational_point_redeemable' or not isinstance(value, list): continue
        data = as_dict(value); name = data['item_name']
        if name == 'lootlist:removed_items' and not config['armory_howl_enabled']: continue
        if not all(isinstance(v, str) for v in data.values()): raise ValueError('Unknown nested Armory goods field')
        if data.get('local_rotation_slot') in ('collection', 'charm', 'sticker', 'case', 'capsule', 'limited', 'agent', 'terminal', 'souvenir'):
            slot = data['local_rotation_slot']
        elif name.startswith('lootlist:keychain_pack_'): slot = 'charm'
        elif name.startswith('lootlist:sticker_pack_'): slot = 'sticker'
        elif name.startswith('lootlist:set_xpshop_wpn_') or data.get('limited_until'): slot = 'limited'
        elif name.startswith('lootlist:'): slot = 'collection'
        elif name in souvenirs: slot = 'souvenir'
        elif name in terminals: slot = 'terminal'
        elif name in cases: slot = 'case'
        else: raise ValueError('Unclassified native Armory good: ' + name)
        if slot == 'terminal' and not config['terminals_enabled']: continue
        cost = LIMITED_PRICES.get(name.removeprefix('lootlist:'), int(data['points'])) if slot == 'limited' else int(data['points'])
        if name == 'lootlist:removed_items': cost = max(250, config['armory_howl_star_price'])
        add(name, slot, cost, data)
    templates = {v['local_rotation_slot']: v for v in goods.values()}
    if config.get('knife_finishes', 1) and 'crate_cs2gc_black_market' in items:
        # The knife-only Black Market Case rotates through the big limited-edition tile.
        # Never cheaper than selling the knife it gives (that would be a free star loop).
        wear_max = max(config.get('sell_wear_'+wear,default) for wear,default in
                       [('fn',125),('mw',110),('ft',100),('ww',80),('bs',60)]) if config.get('sell_wear_enabled',1) else 100
        price = max(config.get('black_market_price', 100), config.get('sell_knife_glove', 72)*wear_max//100 + 1)
        add('crate_cs2gc_black_market', 'limited', price, {'flags': '2'})
        if config.get('glove_finishes', 1) and 'crate_cs2gc_gauntlet' in items:
            add('crate_cs2gc_gauntlet', 'limited', price, {'flags': '2'})  # the glove-only twin, same price

    def loot(name, slot, price):
        if name in lists:
            template = dict(templates.get(slot, {}))
            # Original callout/images describe a different collection. The native item
            # names and set icons are resolved from the actual loot list at render time.
            for key in ('callout', 'ui_image', 'ui_set_image', 'ui_image_thumbnail', 'ui_show_new_tag'):
                template.pop(key, None)
            item_set = sections.get('item_sets', {}).get(name)
            if isinstance(item_set, list) and as_dict(item_set).get('name'):
                template['callout'] = as_dict(item_set)['name']
            elif slot in ('charm', 'sticker'):
                template['callout'] = name.removesuffix('_lootlist').removeprefix('keychain_pack_kc_').removeprefix('sticker_pack_').replace('_', ' ').title()
            add('lootlist:' + name, slot, price, template)

    for name in ARMORY_COLLECTIONS: loot(name, 'collection', 4)
    # Custom colour-family collections (native_skins.py), once the user has checked them with the test case.
    if config.get('custom_collections', 0):
        for name in sorted(n for n in sections.get('item_sets', {}) if n.startswith('set_cs2gc_')): loot(name, 'collection', 4)
    # The current weekly drop pool collections rotate through the collection tiles too.
    for name in sorted(n for n in sections.get('item_sets', {}) if n.startswith('set_timed_drops_')): loot(name, 'collection', 4)
    for name in lists:
        if name.startswith('keychain_pack_') and name.endswith('_lootlist'): loot(name, 'charm', 3)
        if name.startswith('sticker_pack_') and name.endswith('_lootlist'): loot(name, 'sticker', 1)
    for name in sorted(cases): add(name, 'case', config.get('armory_case_price', 5), {'flags': '2'})
    for name in sorted(souvenirs): add(name, 'souvenir', config['armory_souvenir_price'], {'flags': '2'})
    if config['terminals_enabled']:
        for name in sorted(terminals): add(name, 'terminal', config['armory_terminal_price'])
    wanted = set(COMMUNITY_CAPSULES)
    wanted.update('crate_sticker_pack_' + event + '_' + group for event in TOURNAMENTS for group in TOURNAMENT_GROUPS)
    for name in sorted(wanted & items.keys()): add(name, 'capsule', 1)
    for name in LIMITED_LISTS: loot(name, 'limited', LIMITED_PRICES[name])
    agent_lists = sorted(name for name in lists if name.startswith('lootlist_character_operator_dossier_'))
    if config.get('armory_agent_slots', 1) and agent_lists:
        add('lootlist:' + agent_lists[0], 'agent', config.get('armory_agent_price', 50), {'callout': 'Random Agent'})
    if config['armory_howl_enabled']:
        howl = lists.get('removed_items')
        if isinstance(howl, list) and [(k, v) for k, v in howl if k != 'public_list_contents'] == [('[cu_m4a1_howling]weapon_m4a1', '1')]:
            loot('removed_items', 'limited', max(250, config['armory_howl_star_price']))
    return goods


def patch_catalogue(source, config):
    goods = catalogue(source, config)
    top = parse_spans(source).one('items_game')
    campaigns = [n for section in top.children if section.key == 'seasonaloperations'
                 for n in section.children if n.key == '11']
    if len(campaigns) != 1: raise ValueError('Ambiguous native Armory campaign')
    campaign = campaigns[0]
    existing = [n for n in campaign.children if n.key == 'operational_point_redeemable']
    # Replace only native shop rows; preserve operation metadata and all definitions.
    edits = []
    for node in existing:
        start = source.rfind('"operational_point_redeemable"', 0, node.opening)
        if start < 0: raise ValueError('Expected quoted Armory row key')
        edits.append((start, node.end, ''))
    def quote(value):
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'
    rows = '\n'.join('\n\t\t\t"operational_point_redeemable"\n\t\t\t{\n' +
                     ''.join('\t\t\t\t' + quote(k) + '\t' + quote(v) + '\n' for k, v in data.items()) +
                     '\t\t\t}\n' for data in goods.values())
    edits.append((campaign.end - 1, campaign.end - 1, rows))
    for start, end, value in sorted(edits, reverse=True): source = source[:start] + value + source[end:]
    return source, {name: value['local_rotation_slot'] for name, value in goods.items()}


def agent_names(source):
    sections = collect(parse(source))
    prefabs = sections.get('prefabs', {})
    def resolve(node, prop, depth=0):
        values = as_dict(node)
        if prop in values: return values[prop]
        if depth > 8: return None
        for name in values.get('prefab', '').split():
            if name in prefabs:
                value = resolve(prefabs[name], prop, depth + 1)
                if value is not None: return value
        return None
    return sorted(as_dict(node)['name'] for node in sections.get('items', {}).values() if isinstance(node, list)
                  and resolve(node, 'flexible_loadout_category') == 'customplayer'
                  and resolve(node, 'item_quality') == 'unique' and resolve(node, 'model_player'))


def terminal_names(source):
    sections = collect(parse(source))
    prefabs = sections.get('prefabs', {})
    def chain(node, depth=0):
        names = set(as_dict(node).get('prefab', '').split())
        if depth < 8:
            for name in list(names):
                if name in prefabs: names |= chain(prefabs[name], depth + 1)
        return names
    return sorted(as_dict(node)['name'] for node in sections.get('items', {}).values()
                  if isinstance(node, list) and as_dict(node).get('name', '').startswith('crate_')
                  and 'weapon_case_selfopening_collection' in chain(node)
                  and any('volatile_pricing' in name for name in chain(node)))


def souvenir_names(source):
    """Installed keyless souvenir packages whose own series resolves to usable weapon loot.

    Early packages whose loot is server-only are deliberately excluded, rather than sold empty.
    """
    sections = collect(parse(source))
    prefabs = sections.get('prefabs', {})
    lists = sections.get('client_loot_lists', {})
    revolving = sections.get('revolving_loot_lists', {})
    def property(node, key, depth=0):
        values = as_dict(node)
        if key in values: return values[key]
        if depth < 8:
            for parent in reversed(values.get('prefab', '').split()):
                if parent in prefabs:
                    value = property(prefabs[parent], key, depth + 1)
                    if value is not None: return value
        return None
    def souvenir(node, depth=0):
        parents = as_dict(node).get('prefab', '').split()
        return 'weapon_case_souvenirpkg' in parents or (depth < 8 and any(
            name in prefabs and souvenir(prefabs[name], depth + 1) for name in parents))
    def weapon_loot(name, visiting=None):
        visiting = set() if visiting is None else visiting
        if name in visiting or len(visiting) > 8: return False
        visiting = visiting | {name}
        return any((key.startswith('[') and ']weapon_' in key) or (key in lists and weapon_loot(key, visiting))
                   for key, value in lists.get(name, []) if isinstance(value, str))
    result = []
    for node in sections.get('items', {}).values():
        if not isinstance(node, list) or not souvenir(node): continue
        attributes = dict(property(node, 'attributes') or [])
        series = dict(attributes.get('set supply crate series') or []).get('value')
        if series and weapon_loot(revolving.get(series)):
            result.append(as_dict(node)['name'])
    return sorted(result)

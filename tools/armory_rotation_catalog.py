"""Native Armory catalogue, referring only to the installed schema's official goods.

No item, paint-kit, collection or loot-list definitions are created. Capsule pools
are a deliberate curated selection, not a claim of live market popularity rankings.
"""
from inventory_item import collect, parse, as_dict
from native_tradeups import parse as parse_spans
from price_sheet import find_case_items

ARMORY_COLLECTIONS = ('set_graphic_design', 'set_overpass_2024', 'set_realism_camo',
                      'set_spy_tech', 'set_arabesque', 'set_train_2025')
TOURNAMENTS = ('kat2014', 'cologne2014', 'eslkatowice2015', 'eslcologne2015',
               'stockh2021', 'antwerp2022', 'paris2023', 'cph2024', 'sha2024',
               'aus2025', 'bud2025')
# Team capsules only; exclude individual team packs, souvenir packages and coupons.
TOURNAMENT_GROUPS = ('01', '02', 'legends', 'challengers', 'contenders')
COMMUNITY_CAPSULES = ('crate_sticker_pack_cs20_capsule', 'crate_sticker_pack_csgo10_capsule',
                      'crate_sticker_pack_halo_capsule', 'crate_sticker_pack_hlalyx_capsule',
                      'crate_sticker_pack_skillgroup_capsule')
LIMITED_LISTS = ('set_xpshop_wpn_01', 'set_xpshop_wpn_02', 'set_xpshop_wpn_03',
                 'set_xpshop_wpn_04')


def catalogue(source, config):
    sections = collect(parse(source))
    lists = sections.get('client_loot_lists', {})
    items = {as_dict(v).get('name'): as_dict(v) for v in sections.get('items', {}).values() if isinstance(v, list)}
    campaign = sections.get('seasonaloperations', {}).get('11')
    if not isinstance(campaign, list) or as_dict(campaign).get('redeemable_goods') != 'xpshop':
        raise ValueError('Expected the inspected native Armory campaign 11')
    goods = {}
    cases = {case[0] for case in find_case_items(sections)}

    def add(name, slot, cost, template=None):
        if name in goods: return
        values = dict(template or {})
        values.update(item_name=name, points=str(cost), local_rotation_slot=slot)
        values['ui_order'] = {'collection': '2', 'charm': '1', 'sticker': '3', 'case': '3', 'capsule': '3', 'limited': '2'}[slot]
        values.pop('bidding_cycle', None)
        if slot == 'limited': values['limited_until'] = '2147483647'
        goods[name] = values

    for key, value in campaign:
        if key != 'operational_point_redeemable' or not isinstance(value, list): continue
        data = as_dict(value); name = data['item_name']
        if name == 'lootlist:removed_items' and not config['armory_howl_enabled']: continue
        if not all(isinstance(v, str) for v in data.values()): raise ValueError('Unknown nested Armory goods field')
        if data.get('local_rotation_slot') in ('collection', 'charm', 'sticker', 'case', 'capsule', 'limited'):
            slot = data['local_rotation_slot']
        elif name.startswith('lootlist:keychain_pack_'): slot = 'charm'
        elif name.startswith('lootlist:sticker_pack_'): slot = 'sticker'
        elif name.startswith('lootlist:set_xpshop_wpn_') or data.get('limited_until'): slot = 'limited'
        elif name.startswith('lootlist:'): slot = 'collection'
        elif name in cases: slot = 'case'
        else: raise ValueError('Unclassified native Armory good: ' + name)
        add(name, slot, int(data['points']), data)
    templates = {v['local_rotation_slot']: v for v in goods.values()}

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
    for name in lists:
        if name.startswith('keychain_pack_') and name.endswith('_lootlist'): loot(name, 'charm', 3)
        if name.startswith('sticker_pack_') and name.endswith('_lootlist'): loot(name, 'sticker', 1)
    for name in sorted(cases): add(name, 'case', 2, {'flags': '2'})
    wanted = set(COMMUNITY_CAPSULES)
    wanted.update('crate_sticker_pack_' + event + '_' + group for event in TOURNAMENTS for group in TOURNAMENT_GROUPS)
    for name in sorted(wanted & items.keys()): add(name, 'capsule', 1)
    for name in LIMITED_LISTS: loot(name, 'limited', 25)
    if config['armory_howl_enabled']:
        howl = lists.get('removed_items')
        if isinstance(howl, list) and [(k, v) for k, v in howl if k != 'public_list_contents'] == [('[cu_m4a1_howling]weapon_m4a1', '1')]:
            loot('removed_items', 'limited', config['armory_howl_star_price'])
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

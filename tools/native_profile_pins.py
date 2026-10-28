"""Show the local owner's saved collectible definitions in the native flair carousel."""
import json
from pathlib import Path
from native_tradeups import parse
from native_resources import install_override


def owned_definitions(directory):
    proxy=Path(directory)
    inventory=proxy/'cs2_gc_inventory.txt'
    schema=proxy/'items_game.txt'
    if not inventory.is_file() or not schema.is_file():return []
    root=parse(schema.read_text(encoding='utf-8-sig')).one('items_game')
    prefabs={p.key:p for section in root.children if section.key=='prefabs' for p in section.children or []}
    def fields(node):return {f.key:f.value for f in node.children or [] if f.children is None}
    def collectible(node,seen=None):
        values=fields(node)
        if values.get('item_class')=='collectible_item':return True
        seen=set() if seen is None else seen
        for name in values.get('prefab','').split():
            if name not in seen and name in prefabs:
                if collectible(prefabs[name],seen|{name}):return True
        return False
    allowed={int(i.key) for section in root.children if section.key=='items' for i in section.children or [] if i.key.isdecimal() and collectible(i)}
    saved=parse(inventory.read_text(encoding='utf-8-sig')).one('inventory').one('items')
    return sorted({int(row.text('def_index')) for row in saved.children if int(row.text('def_index')) in allowed})


def patch(source,definitions):
    anchor='        let flairItems = FriendsListAPI.GetFriendDisplayItemDefCount(_m_xuid);'
    replacement='''        const localPins = _m_isSelf ? __PINS__ : null;
        let flairItems = localPins ? localPins.length : FriendsListAPI.GetFriendDisplayItemDefCount(_m_xuid);'''.replace('__PINS__',json.dumps(definitions))
    lookup='            let flairDefIdx = FriendsListAPI.GetFriendDisplayItemDefByIndex(_m_xuid, i);'
    name='                let tooltipText = InventoryAPI.GetItemName(flairItemId);'
    for old,new in [(anchor,replacement),(lookup,'            let flairDefIdx = localPins ? localPins[i] : FriendsListAPI.GetFriendDisplayItemDefByIndex(_m_xuid, i);'),
        (name,name+'''
                if (_m_isSelf && flairItemId === InventoryAPI.GetFauxItemIDFromDefAndPaintIndex(FriendsListAPI.GetFriendDisplayItemDefFeatured(_m_xuid), 0)) tooltipText += ' · Equipped';''')]:
        if source.count(old)!=1:raise ValueError('Unknown native player-card contract')
        source=source.replace(old,new,1)
    return source


def prepare(directory,config):
    definitions=owned_definitions(directory)
    return install_override(directory,enabled=True,folder='cs2_gc_profile_pins',comment='cs2_gc owned profile pins',
        owner='cs2-gc-profile-pins-v1',asset='panorama/scripts/playercard.vts_c',patch=lambda source:patch(source,definitions))

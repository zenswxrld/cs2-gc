"""Make the knife-only Black Market Case roll a reel of knives instead of the countdown.

The stock unlock popup (popup_capability_decodable) shows a countdown when the client counts at most one loot list
item, and it collapses an all-knife list into one "rare special item". For our case only, the reel is filled with
real knives sampled by native_finishes.py (cs2_gc_black_market_reel.json); the stop tile still shows the item the
GC actually granted. Every other container keeps the stock behaviour.
"""
import json
from pathlib import Path

from native_resources import install_override

FOLDER = 'cs2_gc_reel'
COMMENT = 'cs2_gc black market case reel'
OWNER = 'cs2-gc-knife-reel-v1'
ASSET = 'panorama/scripts/popups/popup_capability_decodable.vjs_c'
ANCHOR = """        if (lootListCount <= 1) {
            _SetUpCaseOpeningCountdown();
        }"""
INSERT = """        if (lootListCount <= 1 && _LocalKnifeReel(caseId)) {
            _SetUpCaseOpeningScroll();
        }
        else if (lootListCount <= 1) {
            _SetUpCaseOpeningCountdown();
        }"""
HELPER = """    // cs2_gc: the knife-only Black Market Case rolls real knives (sampled when the case was generated).
    const m_localKnifeReel = __REEL__;
    function _LocalKnifeReel(caseId) {
        if (InventoryAPI.GetItemDefinitionName(caseId) !== 'crate_cs2gc_black_market' || !m_localKnifeReel.length)
            return false;
        // Like a real case, every reel tile is the gold Rare Special Item; the knife is revealed after the reel.
        const image = InventoryAPI.GetLootListUnusualItemImage(caseId);
        $.GetContextPanel().Data().unusualItemImagePath = (image || 'econ/weapon_cases/default_rare_item') + '.png';
        $.GetContextPanel().Data().localKnifeReel = true;
        $.GetContextPanel().Data().aItemsInLootlist = m_localKnifeReel.map(pair =>
            ({ id: InventoryAPI.GetFauxItemIDFromDefAndPaintIndex(pair[0], pair[1]), weight: 1 }));
        return true;
    }
"""
FUNCTION = '    function _ShowUnlockAnimation() {'
TILE = "        if ((InventoryAPI.GetItemQuality(itemId) === 3) && $.GetContextPanel().Data().unusualItemImagePath) {"
TILE_INSERT = ("        if (($.GetContextPanel().Data().localKnifeReel || InventoryAPI.GetItemQuality(itemId) === 3) &&"
               " $.GetContextPanel().Data().unusualItemImagePath) {")


def patch(source, reel):
    if '_LocalKnifeReel' in source: raise ValueError('Script is already patched')
    if (source.count(ANCHOR) != 1 or source.count(FUNCTION) != 1 or source.count(TILE) != 1
            or '_SetUpCaseOpeningScroll()' not in source):
        raise ValueError('Installed popup_capability_decodable layout has changed; no patch was written')
    helper = HELPER.replace('__REEL__', json.dumps([[int(a), int(b)] for a, b in reel]))
    return source.replace(ANCHOR, INSERT, 1).replace(FUNCTION, helper + FUNCTION, 1).replace(TILE, TILE_INSERT, 1)


def prepare(proxy_directory, config):
    path = Path(proxy_directory) / 'cs2_gc_black_market_reel.json'
    reel = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else []
    return install_override(proxy_directory, enabled=bool(config.get('knife_finishes', 1)) and bool(reel),
                            folder=FOLDER, comment=COMMENT, owner=OWNER, asset=ASSET,
                            patch=lambda source: patch(source, reel))

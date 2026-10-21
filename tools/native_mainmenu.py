"""Hide only the main-menu RUSH promotion, leaving the mission card available.

Panel id is from the inspected mainmenu_left_column.xml. Installed mainmenu.vts_c is patched in its own VPK.
"""
from native_resources import install_override

ANCHOR = '    function _OnShowMainMenu() {'
INSERT = """
        // cs2_gc: cosmetic only; keep the stock mission card for future offline mission tracking.
        const left = $.GetContextPanel().FindChildInLayoutFile('JsLeftColumn');
        const promo = left && left.FindChildTraverse('id-mainmenu-rush-tile-panel');
        if (promo) { promo.visible = false; promo.style.visibility = 'collapse'; }
"""


def patch(source, care_packages=False, hide_promo=True):
    if source.count(ANCHOR) != 1 or 'cs2_gc: cosmetic only' in source:
        raise ValueError('Installed main menu layout changed; no patch written')
    source=source.replace(ANCHOR, ANCHOR + (INSERT if hide_promo else ""), 1)
    if care_packages:
        anchor = """        if (!$('#MainMenuNavBarHome').checked)
            return;
        const objStore = InventoryAPI.GetCacheTypeElementJSOByIndex("PersonalStore", 0);"""
        replacement = """        // cs2_gc: present saved choices only on Inventory, outside a match.
        if (GameStateAPI.GetMapBSPName()) return;
        if (!$('#MainMenuNavBarInventory').checked)
            return;
        const objStore = InventoryAPI.GetCacheTypeElementJSOByIndex("PersonalStore", 0);"""
        if source.count(anchor) != 1: raise ValueError('Installed care-package notification anchor changed')
        source=source.replace(anchor,replacement,1)
    return source


def prepare(directory, config):
    return install_override(directory, enabled=bool(config['hide_mainmenu_promo'] or config['care_packages_enabled']), folder='cs2_gc_mainmenu',
        comment='cs2_gc main-menu promotion', owner='cs2-gc-mainmenu-v1',
        asset='panorama/scripts/mainmenu.vts_c', patch=lambda source: patch(source,bool(config['care_packages_enabled']),bool(config['hide_mainmenu_promo'])))

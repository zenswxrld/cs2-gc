"""Hide only the main-menu RUSH promotion, leaving the mission card available.

Panel id is from the inspected mainmenu_left_column.xml. Installed mainmenu.vts_c is patched in its own VPK.
"""
from native_resources import install_override
import json

ANCHOR = '    function _OnShowMainMenu() {'
STATS_NAV = """
        const statsNav = $.GetContextPanel().FindChildInLayoutFile('MainMenuNavBarNews');
        if (statsNav) statsNav.FindChildrenWithClassTraverse('mainmenu-top-navbar__radio-btn__label').forEach(label => label.text = 'STATS');
"""
INSERT = """
        // cs2_gc: cosmetic only; keep the stock mission card for future offline mission tracking.
        const left = $.GetContextPanel().FindChildInLayoutFile('JsLeftColumn');
        const promo = left && left.FindChildTraverse('id-mainmenu-rush-tile-panel');
        if (promo) { promo.visible = false; promo.style.visibility = 'collapse'; }
"""


def patch(source, care_packages=False, hide_promo=True, pet_id='0'):
    if source.count(ANCHOR) != 1 or 'cs2_gc: cosmetic only' in source or 'const statsNav =' in source:
        raise ValueError('Installed main menu layout changed; no patch written')
    source=source.replace(ANCHOR, ANCHOR + STATS_NAV + (INSERT if hide_promo else ""), 1)
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
    if str(pet_id).isdigit() and int(pet_id)>1000000000000:
        source=source.replace(ANCHOR,"    let m_localPetApplied=false;\n"+ANCHOR+'''
        if(!m_localPetApplied && MyPersonaAPI.IsInventoryValid()) {
            m_localPetApplied=true;
            const id='__PET_ID__';
            LoadoutAPI.EquipItemInSlot('noteam',id,InventoryAPI.GetDefaultSlot(id));
            $.Schedule(.25,()=>$.DispatchEvent('ForceRestartVanity'));
        }
'''.replace('__PET_ID__',str(pet_id)),1)
    return source


def patch_pet_food(source, owned_ids):
    """The offline match-driven pets do not participate in timed feeding."""
    anchor = '    function _ShowFoodHint(elPanel, petItemId) {'
    if source.count(anchor) != 1 or 'cs2_gc: permanent companion' in source:
        raise ValueError('Installed pet food hint changed; no patch written')
    ids = [str(value) for value in owned_ids if str(value).isdigit() and int(value) > 1000000000000]
    return source.replace(anchor, anchor + '''
        // cs2_gc: permanent companion; growth follows completed matches, not food timers.
        if (__OWNED_IDS__.indexOf(String(petItemId)) !== -1) {
            elPanel.SetHasClass('low-food', false);
            elPanel.SetHasClass('needs-food', false);
            return;
        }
'''.replace('__OWNED_IDS__', json.dumps(ids)), 1)


def prepare(directory, config):
    from companions import snapshot
    pets=snapshot(directory)
    pet_id=pets.get('selected','0')
    menu=install_override(directory, enabled=True, folder='cs2_gc_mainmenu',
        comment='cs2_gc main-menu promotion', owner='cs2-gc-mainmenu-v1',
        asset='panorama/scripts/mainmenu.vts_c', patch=lambda source: patch(source,bool(config['care_packages_enabled']),bool(config['hide_mainmenu_promo']),pet_id))
    food=install_override(directory, enabled=True, folder='cs2_gc_pet_food',
        comment='cs2_gc permanent companion food hint', owner='cs2-gc-pet-food-v1',
        asset='panorama/scripts/vanity_pet_info.vts_c',
        patch=lambda source: patch_pet_food(source,[pet['id'] for pet in pets.get('pets',[])]))
    return menu + '; ' + food

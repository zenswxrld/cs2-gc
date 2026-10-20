"""Show chronological offer numbers (1st, 2nd, ...) in the Arms Dealer laptop.

The installed laptop script labels each offer with the ordinal of the terminal's "offers remaining" counter, which
counts down. This override shows limit minus remaining instead. Only a dedicated override folder is written.
"""
from native_resources import install_override

ANCHOR = '''    function _CurrentOfferNumber() {
        return (m_numOfferCounter < 0) ? -m_numOfferCounter : m_numOfferCounter;
    }
'''
REPLACEMENT = '''    function _CurrentOfferNumber() {
        const remaining = (m_numOfferCounter < 0) ? -m_numOfferCounter : m_numOfferCounter;
        // cs2_gc: count offers up (limit - remaining) instead of showing the remaining counter.
        let limit = 0;
        try { limit = Number(JSON.parse(InventoryAPI.GetVolatileLimits()).limit); } catch (e) { limit = 0; }
        return (limit > 0 && limit >= remaining) ? Math.max(1, limit - remaining) : remaining;
    }
'''


def patch(source):
    if source.count(ANCHOR) != 1:
        raise ValueError('Installed laptop script differs from the inspected build; no patch was written')
    return source.replace(ANCHOR, REPLACEMENT, 1)


def prepare(proxy_directory, config):
    return install_override(proxy_directory, enabled=bool(config['terminals_enabled']),
        folder='cs2_gc_offers', comment='cs2_gc chronological terminal offers',
        owner='cs2-gc-offer-numbers-v1',
        asset='panorama/scripts/popups/popup_offers_laptop_interface.vjs_c', patch=patch)

"""Show chronological offer numbers (1st, 2nd, ...) in the Arms Dealer laptop.

The installed laptop script labels each offer with the ordinal of the terminal's "offers remaining" counter, which
counts down. This override shows (total offers - remaining) instead. The total is the local GC's terminal_default_offers;
the laptop's "Offer limit" setting is a price cap, not an offer count, and is ignored. Only a dedicated override folder
is written.
"""
from native_resources import install_override

ANCHOR = '''    function _CurrentOfferNumber() {
        return (m_numOfferCounter < 0) ? -m_numOfferCounter : m_numOfferCounter;
    }
'''
REPLACEMENT = '''    function _CurrentOfferNumber() {
        const remaining = (m_numOfferCounter < 0) ? -m_numOfferCounter : m_numOfferCounter;
        // cs2_gc: count offers up. The local GC deals __TOTAL__ offers per terminal and counts the remainder down.
        const total = __TOTAL__;
        return (remaining < total) ? total - remaining : 1;
    }
'''


def patch(source, total=5):
    if not 1 <= int(total) <= 100: raise ValueError('terminal_default_offers must be 1..100')
    if source.count(ANCHOR) != 1:
        raise ValueError('Installed laptop script differs from the inspected build; no patch was written')
    return source.replace(ANCHOR, REPLACEMENT.replace('__TOTAL__', str(int(total))), 1)


def prepare(proxy_directory, config):
    return install_override(proxy_directory, enabled=bool(config['terminals_enabled']),
        folder='cs2_gc_offers', comment='cs2_gc chronological terminal offers',
        owner='cs2-gc-offer-numbers-v1',
        asset='panorama/scripts/popups/popup_offers_laptop_interface.vjs_c',
        patch=lambda source: patch(source, config['terminal_default_offers']))

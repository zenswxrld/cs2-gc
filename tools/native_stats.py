"""Prepare the native career page from safe, locally recorded profile counters."""
from native_resources import install_override
from local_stats import snapshot
from career_page import patch

def prepare(directory,config):
    return install_override(directory,enabled=True,folder='cs2_gc_stats',comment='cs2_gc local stats and achievements',
        owner='cs2-gc-stats-v1',asset='panorama/scripts/mainmenu_news.vts_c',patch=lambda source:patch(source,snapshot(directory)))

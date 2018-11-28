from __future__ import unicode_literals, division, absolute_import

import os
import logging
from flexget.manager import manager
from flexget.utils.soup import get_soup

log = logging.getLogger('anidb_cache')

ANIDB_CACHE = '.anidb_cache'


def cached_anidb(func):
    """Load an AniDB entry from cache."""
    def decorator(*args, **kwargs):
        """Logic behind the decorator."""
        anidb_id = args[0].anidb_id
        log.info(vars(args))
        raise Exception('Safety exception!')
        if anidb_id:
            log.trace('We have an anidb_id!')
            cache_file = os.path.join(manager.config_base, ANIDB_CACHE, str(anidb_id) + '.anime')
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as soup_file:
                    soup = get_soup(soup_file, parser='lxml-xml')
                    kwargs.update(soup=soup)
                    soup_file.close()
            else:
                raw_page = args
        func(*args, **kwargs)
    return decorator

from __future__ import unicode_literals, division, absolute_import

import hashlib
import os

from flexget import logging
from flexget.manager import manager
from flexget.utils.soup import get_soup

log = logging.getLogger('anidb_cache')

ANIDB_CACHE = '.anidb_cache'


def cached_anidb(func):
    """Decorator to load an AniDB entry from cache."""
    anidb_anime_string = 'anime: %s'

    def get_blake_name(anidb_cache_name):
        blake = hashlib.new('blake2b')
        blake.update(anidb_cache_name)
        return blake.hexdigest()

    def open_soup(file_path):
        with open(file_path, 'r') as soup_file:
            soup = get_soup(soup_file, parser='lxml-xml')
            soup_file.close()
            return soup
        return None

    def decorator(*args, **kwargs):
        """Logic behind the decorator."""
        anidb_id = args[0].anidb_id
        if anidb_id:
            log.trace('We have an anidb_id!')
            anidb_cache_name = (anidb_anime_string.format(anidb_id)).encode()
            if 'blake2b' in hashlib.algorithms_available:
                log.trace('blake2b is here!')
                cache_file = os.path.join(manager.config_base, ANIDB_CACHE, get_blake_name(anidb_cache_name))
                kwargs.update(soup=open_soup(cache_file))
            if 'soup' not in kwargs or not kwargs['soup']:
                md5digest = hashlib.md5(anidb_cache_name).hexdigest()
                cache_file = os.path.join(manager.config_base, ANIDB_CACHE, md5digest)
                if os.path.exists(cache_file):
                    kwargs.update(soup=open_soup(cache_file))
                    if 'blake2b' in hashlib.algorithms_available:
                        blake_path = os.path.join(manager.config_base, ANIDB_CACHE, get_blake_name(anidb_cache_name))
                        os.rename(cache_file, blake_path)
        func(*args, **kwargs)

    return decorator

from __future__ import unicode_literals, division, absolute_import

import hashlib
import os

from flexget import logging
from flexget.manager import manager
from flexget.utils.soup import get_soup

log = logging.getLogger('anidb_cache')

ANIDB_CACHE = '.anidb_cache'


def cached_anidb(func):
    anidb_anime_string = 'anime: %s'

    def return_cached(*args, **kwargs):
        anidb_id = args[0].anidb_id
        if anidb_id:
            log.trace('We have an anidb_id!')
            anidb_cache_name = (anidb_anime_string % anidb_id).encode()
            if 'blake2b' in hashlib.algorithms_available:
                log.trace('blake2b is here!')
                blake = hashlib.new('blake2b')
                blake.update(anidb_cache_name)
                blakesum = blake.hexdigest()
                cache_file = os.path.join(manager.config_base, ANIDB_CACHE, blakesum)
                if os.path.exists(cache_file):
                    log.debug('%s is in the cache', anidb_id)
                    with open(cache_file, 'r') as cached_file:
                        soup = get_soup(cached_file, parser='lxml')
                        cached_file.close()
                        kwargs.update(soup=soup)
            if 'soup' not in kwargs or not kwargs['soup']:
                md5sum = hashlib.md5(anidb_cache_name).hexdigest()
                cache_file = os.path.join(manager.config_base, ANIDB_CACHE, md5sum)
                if os.path.exists(cache_file):
                    with open(cache_file) as cached_file:
                        soup = get_soup(cached_file, parser='lxml')
                        cached_file.close()
                        kwargs.update(soup=soup)
                    if 'blake2b' in hashlib.algorithms_available:
                        blake = hashlib.new('blake2b')
                        blake.update(anidb_cache_name)
                        blake_path = os.path.join(manager.config_base, ANIDB_CACHE, blake.hexdigest())
                        os.rename(cache_file, blake_path)
        func(*args, **kwargs)

    return return_cached

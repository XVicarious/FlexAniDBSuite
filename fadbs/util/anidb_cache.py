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

    def __get_blake_name(anidb_cache_name):
        blake = hashlib.new('blake2b')
        blake.update(anidb_cache_name)
        return blake.hexdigest()

    def __get_soup(file_path):
        if os.path.exists(file_path):
            with open(file_path, 'r') as cached_file:
                soup = get_soup(cached_file, parser='lxml')
                cached_file.close()
                return soup
        return None

    def return_cached(*args, **kwargs):
        anidb_id = args[0].anidb_id
        if anidb_id:
            log.trace('We have an anidb_id!')
            anidb_cache_name = (anidb_anime_string % anidb_id).encode()
            if 'blake2b' in hashlib.algorithms_available:
                log.trace('blake2b is here!')
                cache_file = os.path.join(manager.config_base, ANIDB_CACHE, __get_blake_name(anidb_cache_name))
                kwargs.update(soup=__get_soup(cache_file))
            if 'soup' not in kwargs or not kwargs['soup']:
                cache_file = os.path.join(manager.config_base, ANIDB_CACHE, hashlib.md5(anidb_cache_name).hexdigest())
                if os.path.exists(cache_file):
                    kwargs.update(soup=__get_soup(cache_file))
                    if 'blake2b' in hashlib.algorithms_available:
                        blake_path = os.path.join(manager.config_base, ANIDB_CACHE, __get_blake_name(anidb_cache_name))
                        os.rename(cache_file, blake_path)
        func(*args, **kwargs)

    return return_cached

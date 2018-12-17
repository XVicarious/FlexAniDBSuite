"""Handles cached files from AniDB."""
import logging

from flexget.logger import FlexGetLogger
from flexget.utils.soup import get_soup

from .. import BASE_PATH

log: FlexGetLogger = logging.getLogger('anidb_cache')

ANIDB_CACHE = BASE_PATH / '.anidb_cache'


def cached_anidb(func):
    """Load an AniDB entry from cache."""
    def decorator(*args, **kwargs):
        """Logic behind the decorator."""
        anidb_id = args[0].anidb_id
        if anidb_id:
            log.trace('We have an anidb_id!')
            cache_file = ANIDB_CACHE / (str(anidb_id) + '.anime')
            soup = None
            if cache_file.exists():
                with open(cache_file, 'r') as soup_file:
                    soup = get_soup(soup_file, parser='lxml-xml')
                    soup_file.close()
            else:
                raw_page = args[0].request_anime()
                with open(cache_file, 'w') as soup_file:
                    soup_file.write(raw_page)
                    soup_file.close()
                soup = get_soup(raw_page, parser='lxml-xml')
            kwargs.update(soup=soup)
        func(*args, **kwargs)
    return decorator

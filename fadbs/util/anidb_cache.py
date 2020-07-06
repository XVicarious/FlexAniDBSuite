"""Handles cached files from AniDB."""
import logging
from pathlib import Path

from bs4 import BeautifulSoup
from loguru import logger
from flexget.utils.soup import get_soup

from .. import BASE_PATH

ANIDB_CACHE = BASE_PATH / '.anidb_cache'


def find_soup(cache_file: Path) -> BeautifulSoup:
    """Find and return some soup."""
    if cache_file.exists():
        logger.trace('Cache of %s exists, loading it', cache_file.stem)
        with open(cache_file, 'r') as soup_file:
            return get_soup(soup_file, parser='lxml-xml')
    return None


def cached_anidb(func):
    """Load an AniDB entry from cache."""

    def decorator(*args, **kwargs):
        """Logic behind the decorator."""
        anidb_id = args[0].anidb_id
        if anidb_id:
            logger.trace('We have an anidb_id!')
            cache_file = ANIDB_CACHE / (str(anidb_id) + '.anime')
            soup = find_soup(cache_file)
            if not soup:
                logger.trace('We don\'t have %s cached, requesting it', anidb_id)
                raw_page = args[0].request_anime()
                if not raw_page:
                    return None
                with open(cache_file, 'w') as soup_file:
                    soup_file.write(raw_page)
                    soup_file.close()
                soup = get_soup(raw_page, parser='lxml-xml')
            kwargs.update(soup=soup)
        func(*args, **kwargs)

    return decorator

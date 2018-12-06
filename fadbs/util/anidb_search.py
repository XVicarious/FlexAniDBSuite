from __future__ import unicode_literals, division, absolute_import

import difflib
import logging
import os
import re
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from datetime import datetime, timedelta

from flexget import plugin
from flexget.manager import manager
from flexget.utils.database import with_session
from flexget.utils.requests import Session, TimedLimiter
from flexget.utils.soup import get_soup

from .api_anidb import Anime, AnimeTitle, AnimeLanguage
from .anidb_parse import AnidbParser

PLUGIN_ID = 'anidb_search'

CLIENT_STR = 'fadbs'
CLIENT_VER = 1

log = logging.getLogger(PLUGIN_ID)

requests = Session()
requests.headers.update({'User-Agent': 'Python-urllib/2.6'})

requests.add_domain_limiter(TimedLimiter('api.anidb.net', '3 seconds'))


class AnidbSearch(object):
    """Search for an anime's id."""

    anidb_title_dump_url = 'http://anidb.net/api/anime-titles.xml.gz'
    xml_cache = {
        'path': os.path.join(manager.config_base, 'anime-titles.xml'),
        'exists': False,
        'modified': None,
    }
    cdata_regex = re.compile(r'.+CDATA\[(.+)\]\].+')

    particle_words = {
        'x-jat': {
            'no', 'wo', 'o', 'na', 'ja', 'ni', 'to', 'ga', 'wa',
        },
    }
    last_lookup = {}

    def __init__(self):
        self.debug = False
        self.xml_cache['exists'] = os.path.exists(self.xml_cache['path'])
        if self.xml_cache['exists']:
            mtime = os.path.getmtime(self.xml_cache['path'])
            self.xml_cache['modified'] = datetime.fromtimestamp(mtime)
        with open(self.xml_cache['path'], 'r') as soup_file:
            self.soup = get_soup(soup_file, parser='lxml-xml')

    @with_session
    def __load_xml_to_database(self, session=None):

        last = session.query(Anime).order_by(Anime.anidb_id.desc()).first()
        log.debug('The last anidb_id we have is for entry %s', last)
        if last:
            last = last.anidb_id
        else:
            last = 0
        animes = self.soup.find_all('anime')
        for anime in animes:
            anidb_id = int(anime['aid'])
            # this doesn't allow for adding new titles to existing entries
            series = None
            if int(last) > anidb_id:
                series = session.query(Anime).filter(Anime.anidb_id == anidb_id).first()
            if not series:
                log.debug('The anime is not in the database, adding it')
                series = Anime()
                series.anidb_id = anidb_id
            titles = anime.find_all('title')
            for title in titles:
                title_lang = title['xml:lang']
                title_type = title['type']
                lang = session.query(AnimeLanguage).filter(AnimeLanguage.name == title_lang).first()
                if not lang:
                    lang = AnimeLanguage(title_lang)
                anime_title = session.query(AnimeTitle)
                anime_title = anime_title.filter(AnimeTitle.name == title.string,
                                                 AnimeTitle.ep_type == title_type,
                                                 AnimeTitle.name == title.string).first()
                if anime_title:
                    log.trace('we already have this title, continuing')
                    continue
                anime_title = AnimeTitle(title.string, lang.name, title_type, series)
                series.titles.append(anime_title)
            if int(last) < anidb_id:
                session.add(series)
        session.commit()

    def __download_anidb_titles(self):
        #anidb_titles = requests.get(self.anidb_title_dump_url)
        #if anidb_titles.status_code >= 400:
        #    raise plugin.PluginError(anidb_titles.status_code, anidb_titles.reason)
        #if os.path.exists(self.xml_cache['path']):
        #    os.rename(self.xml_cache['path'], self.xml_cache['path'] + '.old')
        #with open(self.xml_cache['path'], 'w') as xml_file:
        #    xml_file.write(anidb_titles.text)
        #    xml_file.close()
        new_mtime = os.path.getmtime(self.xml_cache['path'])
        if self.debug:
            new_mtime = datetime.now()
        self.xml_cache['modified'] = datetime.fromtimestamp(new_mtime)
        self.__load_xml_to_database()

    @with_session
    def lookup_series(self, name=None, anidb_id=None, only_cached=False, session=None):
        """Lookup an Anime series and return it."""
        expired = (datetime.now() - self.xml_cache['modified']) > timedelta(1)
        if not self.debug and (not self.xml_cache['exists'] or expired):
            log_mess = 'Cache is expired, %s' if self.xml_cache['exists'] else 'Cache does not exist, %s'
            log.info(log_mess, 'downloading now.')
            self.__download_anidb_titles()

        if not (anidb_id or name):
            raise plugin.PluginError('anidb_id and name are both None, cannot continue.')

        if not anidb_id and 'name' in self.last_lookup and name == self.last_lookup['name']:
            log.debug('anidb_id is not set, but the series_name is a match to the previous lookup')
            log.debug('setting anidb_id for %s to %s', name, self.last_lookup['anidb_id'])
            anidb_id = self.last_lookup['anidb_id']

        if anidb_id:
            log.debug('AniDB id is present and is %s.', anidb_id)
            parser = AnidbParser(anidb_id)
            if not only_cached and (parser.series.expired is None or parser.series.expired):
                parser.parse()
            return parser.series

        log.debug('AniDB id not present, looking up by the title, %s', name)
        series_titles = Anime.titles
        series_filter = series_titles.ilike(name)
        series = session.query(Anime).join(series_titles).filter(series_filter).first()
        if series and (only_cached or (series.expired is not None and not series.expired)):
            self.last_lookup.update(name=name, anidb_id=series.anidb_id)
            return series
        raise plugin.PluginError('No series found with series name: %s', name)

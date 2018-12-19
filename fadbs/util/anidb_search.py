import logging
import os
import pickle
import re
import sys
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Dict, Optional

from bs4 import BeautifulSoup
from fuzzywuzzy import process as fw_process
from sqlalchemy.orm import Session as SQLSession

from flexget import plugin
from flexget.logger import FlexGetLogger
from flexget.utils.database import with_session
from flexget.utils.requests import Session, TimedLimiter
from flexget.utils.soup import get_soup

from .. import BASE_PATH
from .anidb_parse import AnidbParser
from .api_anidb import Anime, AnimeLanguage, AnimeTitle
from .stucture_utils import anime_titles_diff

PLUGIN_ID = 'anidb_search'

CLIENT_STR = 'fadbs'
CLIENT_VER = 1

log: FlexGetLogger = logging.getLogger(PLUGIN_ID)

requests = Session()
requests.headers.update({'User-Agent': 'Python-urllib/2.6'})

requests.add_domain_limiter(TimedLimiter('api.anidb.net', '3 seconds'))

sys.setrecursionlimit(10000)


class AnidbSearch(object):
    """Search for an anime's id."""

    anidb_title_dump_url = 'http://anidb.net/api/anime-titles.xml.gz'
    xml_cache = {
        'path': BASE_PATH / 'anime-titles.xml',
        'exists': False,
        'modified': datetime.fromtimestamp(0),
    }
    cdata_regex = re.compile(r'.+CDATA\[(.+)\]\].+')
    anidb_json = BASE_PATH / 'anime-titles.json'
    particle_words = {
        'x-jat': {
            'no', 'wo', 'o', 'na', 'ja', 'ni', 'to', 'ga', 'wa',
        },
    }
    last_lookup = {}

    def __init__(self):
        self.debug = False
        if self.xml_cache['path'].exists():
            mtime = self.xml_cache['path'].stat().st_mtime
            self.xml_cache['modified'] = datetime.fromtimestamp(mtime)

    @with_session
    def _load_anime_to_db(self, anime_cache: Dict, session: Optional[SQLSession] = None) -> None:
        log.verbose('Starting to load anime to the database')
        db_anime_list = session.query(Anime).join(Anime.titles).all()
        for anidb_id, titles in anime_cache.items():
            log.debug('Starting anime %s', anidb_id)
            db_anime = next((anime for anime in db_anime_list if anime.anidb_id == anidb_id), None)
            if not db_anime:
                log.trace('Anime %s was not found in the database, adding it', anidb_id)
                db_anime = Anime()
                db_anime.anidb_id = anidb_id
            for title in titles:
                log.trace('Checking anime %s title %s', anidb_id, title[0])
                has_title = False
                for db_title in db_anime.titles:
                    eq_title_name = db_title.name == title[0]
                    eq_title_lang = db_title.language == title[1]
                    eq_title_type = db_title.ep_type == title[2]
                    if eq_title_name and eq_title_lang and eq_title_type:
                        log.trace('Anime %s already has this title.', anidb_id)
                        has_title = True
                        break
                if has_title:
                    continue
                log.trace('Anime %s did not have title %s, adding it.', anidb_id, title[0])
                lang = session.query(AnimeLanguage).filter(AnimeLanguage.name == title[1]).first()
                if not lang:
                    lang = AnimeLanguage(title[1])
                    session.add(lang)
                title = AnimeTitle(title[0], lang.name, title[2], parent=db_anime.id_)
                db_anime.titles.append(title)
            session.add(db_anime)
        session.commit()

    def _make_xml_junk(self) -> None:
        expired = (datetime.now() - self.xml_cache['modified']) > timedelta(1)
        if not self.debug and (not self.xml_cache['path'].exists() or expired):
            log_mess = 'Cache is expired, %s' if self.xml_cache['path'].exists() else 'Cache does not exist, %s'
            log.info(log_mess, 'downloading now.')
            # self.__download_anidb_titles()
            self.xml_cache['modified'] = datetime.now()
            cache: Dict = {}
            with open(self.xml_cache['path'], 'r') as soup_file:
                soup = get_soup(soup_file, parser='lxml-xml')
                cache = self._xml_to_dict(soup)
            self._load_anime_to_db(cache)

    def _xml_to_dict(self, soup: BeautifulSoup) -> Dict:
        log.verbose('Transforming anime-titles.xml into a dictionary.')
        cache: Dict = {}
        for anime in soup.find_all('anime'):
            anidb_id = int(anime['aid'])
            log.trace('Adding %s to cache', anidb_id)
            title_list = set()
            for title in anime.find_all('title'):
                log.trace('Adding %s to %s', title.string, anidb_id)
                title_lang = title['xml:lang']
                title_type = title['type']
                title_list.add((title.string, title_lang, title_type))
            cache.update({anidb_id: title_list})
        diffr: Dict = None
        if self.anidb_json.exists():
            log.debug('An old cached dict exists, comparing with the new one')
            old_cache = pickle.load(open(self.anidb_json, 'r'))
            diffr = anime_titles_diff(cache, old_cache)
        log.debug('Saving the dict as a pickle')
        with open(self.anidb_json, 'w') as json_cache:
            pickle.dump(cache, json_cache)
            log.debug('Pickled!')
        return diffr if diffr else cache

    def __download_anidb_titles(self) -> None:
        anidb_titles = requests.get(self.anidb_title_dump_url)
        if anidb_titles.status_code >= HTTPStatus.BAD_REQUEST:
            raise plugin.PluginError(anidb_titles.status_code, anidb_titles.reason)
        if os.path.exists(self.xml_cache['path']):
            os.rename(self.xml_cache['path'], self.xml_cache['path'] + '.old')
        with open(self.xml_cache['path'], 'w') as xml_file:
            xml_file.write(anidb_titles.text)
            xml_file.close()
        if self.debug: # todo: this is dumb here, move it
            self.xml_cache['modified'] = datetime.now()
            return
        mtime = self.xml_cache['path'].stat().st_mtime
        self.xml_cache['modified'] = datetime.fromtimestamp(mtime)

    @with_session
    def lookup_series(self,
            name: Optional[str] = None,
            anidb_id: Optional[int] = None,
            only_cached=False,
            session: Optional[SQLSession] = None):
        """Lookup an Anime series and return it."""
        self._make_xml_junk()
        # If we don't have an id or a name, we cannot find anything
        if not (anidb_id or name):
            raise plugin.PluginError('anidb_id and name are both None, cannot continue.')

        # Check if we previously looked up this title.
        # todo: expand this to not only store the last lookup, also possibly persist this?
        if not anidb_id and 'name' in self.last_lookup and name == self.last_lookup['name']:
            log.debug('anidb_id is not set, but the series_name is a match to the previous lookup')
            log.debug('setting anidb_id for %s to %s', name, self.last_lookup['anidb_id'])
            anidb_id = self.last_lookup['anidb_id']

        series = None

        if anidb_id:
            log.verbose('AniDB id is present and is %s.', anidb_id)
            query = session.query(Anime)
            log.info('Anime anidb_id == %s', anidb_id)
            query = query.filter(Anime.anidb_id == anidb_id)
            series = query.first()
            log.info(series)
        else:
            log.debug('AniDB id not present, looking up by the title, %s', name)
            series = session.query(Anime).join(AnimeTitle).filter(AnimeTitle.name == name).first()
            log.info(series)
            if not series:
                titles = session.query(AnimeTitle).all()
                get_title = lambda title: title if isinstance(title, str) else title.name
                matches = fw_process.extract(name, titles, processor=get_title)
                matches = sorted(matches, key=lambda title: title[1], reverse=True)
                log.info(matches)
                raise plugin.PluginError('This is a test')
                series_id = matches.pop()[0].parent_id
                log.info(series_id)
                series = session.query(Anime).filter(Anime.id_ == series_id).first()
                log.info(series)

        if series:
            log.debug('%s', series)
            if not only_cached and (series.expired is None or series.expired):
                log.debug('%s is expired, refreshing metadata', series.title_main)
                parser = AnidbParser(series.anidb_id)
                parser.parse()
                series = parser.series
                log.debug(series)
            if not anidb_id:
                self.last_lookup.update(name=name, anidb_id=series.anidb_id)
            return series

        raise plugin.PluginError(
                'No series found with series name: %s, when was the last time the cache was updated?', name)

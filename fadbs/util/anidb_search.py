import gzip
import logging
import os
import re
import sys
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Dict, Optional

from fuzzywuzzy import process as fw_process
from sqlalchemy.orm import Session as SQLSession

from flexget import plugin
from flexget.logger import FlexGetLogger
from flexget.utils.database import with_session
from flexget.utils.requests import Session, TimedLimiter

from .. import BASE_PATH
from .anidb_parse import AnidbParser
from .api_anidb import Anime, AnimeLanguage, AnimeTitle
from .path import Path

PLUGIN_ID = 'anidb_search'

CLIENT_STR = 'fadbs'
CLIENT_VER = 1

log: FlexGetLogger = logging.getLogger(PLUGIN_ID)

requests = Session()
requests.headers.update({'User-Agent': 'Python-urllib/2.6'})

requests.add_domain_limiter(TimedLimiter('api.anidb.net', '3 seconds'))


class AnidbSearch(object):
    """Search for an anime's id."""

    anidb_title_dump_url = 'http://anidb.net/api/anime-titles.dat.gz'
    xml_file = Path(BASE_PATH, 'anime-titles.xml')
    cdata_regex = re.compile(r'.+CDATA\[(.+)\]\].+')
    anidb_json = BASE_PATH / 'anime-titles.yml'
    particle_words = {
        'x-jat': {
            'no', 'wo', 'o', 'na', 'ja', 'ni', 'to', 'ga', 'wa',
        },
    }
    title_types = [
        'main',
        'synonym',
        'short',
        'official',
    ]
    last_lookup = {}
    cached_anime: Anime = None

    def __init__(self):
        self.debug = False

    def psv_to_dict(self, filename=xml_file) -> Dict:
        try:
            anime_titles = open(filename, 'r')
        except OSError:
            log.warning('anime_titles.dat was not found, not importing titles')
            return {}
        anime_dict: Dict = {}
        for line in anime_titles:
            if line[0] == '#':
                log.trace('Skipping line due to comment')
                continue
            split_line = line.split('|')
            if len(split_line) < 4:
                log.warning("We don't have all of the information we need, skipping")
                log.debug('line: {0}'.format(line))
                continue
            try:
                aid = int(split_line[0])
            except ValueError:
                log.warning("Can't turn %s into an int, no aid, skipping.", split_line[0])
                continue
            type_index = int(split_line[1])
            if type_index > 3:
                continue
            title_type = self.title_types[type_index - 1]
            if aid not in anime_dict:
                anime_dict[aid] = []
            anime_dict[aid].append([title_type, *split_line[2:]])
        anime_titles.close()
        return anime_dict

    @with_session
    def _load_anime_to_db(self, session=None) -> None:
        # First load up the .dat file, which is really just a pipe separated file
        # First three lines are comments
        # aid|type|lang|title
        # type is i+1 of title_types
        # convert to dict keys are aid, value is an AnimeTitle
        animes: Dict = self.psv_to_dict()
        if not len(animes):
            log.warning('We did not get any anime, bailing')
            return
        for anidb_id, anime in animes.items():
            db_anime = session.query(Anime).join(AnimeTitle).filter(Anime.anidb_id == anidb_id).all()
            add_titles: list = []
            for title in anime:
                title_type = title[0]
                for ani in db_anime:
                    new_title = AnimeTitle(title[2], title[1], title_type, ani.id_)
                    title_exists = False
                    for title2 in ani.titles:
                        if (title2 == new_title):
                            log.trace('%s exists in the database, skipping.', title[1])
                            continue
                        title_exists = True
                    if title_exists:
                        log.debug('adding %s to the titles', title[2])
                        add_titles.append(new_title)
            db_anime[0].titles += add_titles
        session.commit()

    def _make_xml_junk(self) -> None:
        if self.xml_file.exists():
            expired = (datetime.now() - self.xml_file.modified()) > timedelta(1)
        if not self.xml_file.exists() or expired:
            log_mess = 'Cache is expired, %s' if self.xml_file.exists() else 'Cache does not exist, %s'
            log.info(log_mess, 'downloading now.')
            self.__download_anidb_titles()
            self._load_anime_to_db()

    def __download_anidb_titles(self) -> None:
        if self.debug:
            log.debug('In debug mode, not downloading a new dump.')
            return
        anidb_titles = requests.get(self.anidb_title_dump_url)
        if anidb_titles.status_code >= HTTPStatus.BAD_REQUEST:
            raise plugin.PluginError(anidb_titles.status_code, anidb_titles.reason)
        if os.path.exists(self.xml_file):
            os.rename(self.xml_file, str(self.xml_file) + '.old')
        with open(self.xml_file, 'wb') as xml_file:
            # I don't know why, but requests isn't decompressing the requested data when I switched to .dat
            # Maybe I'll put some effort into it some other time.
            unzipped = gzip.decompress(anidb_titles.raw.read())
            xml_file.write(unzipped)

    @with_session
    def lookup_series(self,
                      name: Optional[str] = None, anidb_id: Optional[int] = None,
                      only_cached=False, session: SQLSession = None):
        """Lookup an Anime series and return it."""
        if not session:
            raise plugin.PluginError('We weren\'t given a session!')
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

        log.verbose('%s: %s', anidb_id, name)

        if anidb_id:
            if self.cached_anime and self.cached_anime.anidb_id == anidb_id:
                log.debug('We have aid%s cached, using it', anidb_id)
                series = self.cached_anime
            else:
                log.verbose('AniDB id is present and is %s.', anidb_id)
                query = session.query(Anime)
                query = query.filter(Anime.anidb_id == anidb_id)
                series = query.first()
                log.verbose(series)
        else:
            log.debug('AniDB id not present, looking up by the title, %s', name)
            series = session.query(Anime).join(AnimeTitle).filter(AnimeTitle.name == name).first()
            if not series:
                titles = session.query(AnimeTitle).filter(AnimeTitle.name.like('% '+title_part+' %') for title_part in name.split(' ') if title_part not in self.particle_words['x-jat']).all()
                match = fw_process.extractOne(name, titles)
                log.info('%s: %s, %s', match[0], match[1], name)
                if match and match[1] >= 90:
                    series_id = match[0].parent_id
                    series = session.query(Anime).filter(Anime.id_ == series_id).first()

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
            self.cached_anime = series
            return series

        raise plugin.PluginError(
                'No series found with series name: %s, when was the last time the cache was updated?', name)

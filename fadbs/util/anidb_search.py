import gzip
import logging
import os
import re
from datetime import datetime, timedelta
from http import HTTPStatus
from typing import Dict, List, Optional, Tuple

from flexget import plugin
from flexget.logger import FlexGetLogger
from flexget.utils.database import with_session
from flexget.utils.requests import Session, TimedLimiter
from fuzzywuzzy import process as fw_process
from sqlalchemy.orm import Session as SQLSession

from .. import BASE_PATH
from .anidb_parse import AnidbParser
from .api_anidb import Anime, AnimeTitle
from .path import Path

PLUGIN_ID = 'anidb_search'

CLIENT_STR = 'fadbs'
CLIENT_VER = 1

log: FlexGetLogger = logging.getLogger(PLUGIN_ID)

requests = Session()
requests.headers.update({'User-Agent': 'Python-urllib/2.6'})

requests.add_domain_limiter(TimedLimiter('api.anidb.net', '3 seconds'))


class LastLookup:
    anidb_id: int
    name: Optional[str]

    def __init__(self, anidb_id: int, name: Optional[str]):
        self.anidb_id = anidb_id
        self.name = name


class AnidbSearch(object):
    """Search for an anime's id."""

    anidb_title_dump_url = 'http://anidb.net/api/anime-titles.dat.gz'
    xml_file = Path(BASE_PATH, 'anime-titles.xml')
    cdata_regex = re.compile(r'.+CDATA\[(.+)\]\].+')
    anidb_json = BASE_PATH / 'anime-titles.yml'
    particle_words = {
        'x-jat': {'no', 'wo', 'o', 'na', 'ja', 'ni', 'to', 'ga', 'wa',},
    }
    particle_reg = r'([nwt]?o|[njgw]a|ni)'
    title_types = [
        'main',
        'synonym',
        'short',
        'official',
    ]
    last_lookup: LastLookup = None
    cached_anime = None

    def __init__(self):
        self.debug = False

    @with_session
    def clean_main_titles(self, session=None) -> None:
        titles = session.query(AnimeTitle).filter(AnimeTitle.ep_type == 'main').all()
        old_mains: List[AnimeTitle] = []
        for title in titles:
            title_2 = titles.pop(titles.index(title))
            if any(title_2.parent_id == elem.parent_id for elem in titles):
                old_mains += [title_2]
        log.info(old_mains)

    def line_checks(self, line: str) -> Optional[Tuple[int, List[str]]]:
        """Check if the line for the title is good, if so return it parsed.

        :param line: string to check
        :type line: str
        :rtype: Optional[List[str]]
        """
        split_line: List
        type_index: int
        if line[0] == '#':
            log.trace('Skipping line due to comment')
            return None
        split_line = line.split('|')
        type_index = int(split_line[1])
        if len(split_line) < 4 or type_index > 3:
            if len(split_line) < 4:
                log.warning("We don't have all of the information we need, skipping")
                log.debug('line: %s', line)
            return None
        try:
            aid = int(split_line[0])
        except ValueError:
            log.warning("Can't turn %s into an int, no aid, skipping.", split_line[0])
            return None
        return aid, [self.title_types[type_index - 1], *split_line[2:]]

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
                log.debug('line: %s', line)
                continue
            try:
                aid = int(split_line[0])
            except ValueError:
                log.warning(
                    "Can't turn %s into an int, no aid, skipping.", split_line[0]
                )
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

    def generate_title(
        self, anime_id: int, title: List, current_titles
    ) -> Optional[AnimeTitle]:
        """Generate a title object for an anime if it does not exist and return it.

        :param anime_id: database ID for the anime
        :type anime_id: int
        :param title: title information, ala the title itself and type of title
        :type title: List
        :param current_titles: current titles for this anime
        :rtype: AnimeTitle
        """
        title_itself = title[2].strip()
        new_title = AnimeTitle(title_itself, title[1], title[0], anime_id)
        if new_title not in current_titles:
            log.debug('adding %s to the titles', title_itself)
            return new_title
        log.trace('%s exists in the database, skipping.', title_itself)
        return None

    @with_session
    def _load_anime_to_db(self, session=None) -> None:
        # First load up the .dat file, which is really just a pipe separated file
        # First three lines are comments
        # aid|type|lang|title
        # type is i+1 of title_types
        # convert to dict keys are aid, value is an AnimeTitle
        animes: Dict = self.psv_to_dict()
        if not animes:
            log.warning('We did not get any anime, bailing')
            return
        for anidb_id, anime in animes.items():
            db_anime = (
                session.query(Anime)
                .join(AnimeTitle)
                .filter(Anime.anidb_id == anidb_id)
                .first()
            )
            if not db_anime:
                db_anime = Anime(anidb_id=anidb_id)
                session.add(db_anime)
            for title in anime:
                generated_title = self.generate_title(
                    db_anime.id_, title, db_anime.titles
                )
                if generated_title:
                    db_anime.titles += [generated_title]
        session.commit()

    def _make_xml_junk(self) -> None:
        if self.xml_file.exists():
            expired = (datetime.now() - self.xml_file.modified()) > timedelta(1)
        if not self.xml_file.exists() or expired:
            log_msg = (
                'Cache is expired, %s'
                if self.xml_file.exists()
                else 'Cache does not exist, %s'
            )
            log.info(log_msg, 'downloading now.')
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
            # Requests isn't decompressing the requested data when switched to .dat
            # todo: put some effort into it some other time.
            unzipped = gzip.decompress(anidb_titles.raw.read())
            xml_file.write(unzipped)
        log.info('Downloaded new title dump')

    def generate_like_statement(self, name: str) -> List[str]:
        like_gen: List[str] = []
        for title_part in name.split(' '):
            if title_part not in self.particle_words['x-jat']:
                like_gen += [AnimeTitle.name.like('% {0} %'.format(title_part))]
        return like_gen

    @with_session
    def lookup_series(
        self,
        name: Optional[str] = None,
        anidb_id: Optional[int] = None,
        only_cached=False,
        session: SQLSession = None,
    ):
        """Lookup an Anime series and return it."""
        # self.clean_main_titles()
        if not session:
            raise plugin.PluginError("We weren't given a session!")
        self._make_xml_junk()
        # If we don't have an id or a name, we cannot find anything
        if not (anidb_id or name):
            raise plugin.PluginError(
                'anidb_id and name are both None, cannot continue.'
            )
        # Check if we previously looked up this title.
        # todo: expand this to not only store the last lookup, also possibly persist this?
        if not anidb_id and self.last_lookup and name == self.last_lookup.name:
            log.debug(
                'anidb_id is not set, but the series_name is a match to the previous lookup'
            )
            log.debug('setting anidb_id for %s to %s', name, self.last_lookup.anidb_id)
            anidb_id = self.last_lookup.anidb_id

        series = None

        if anidb_id:
            if self.cached_anime and self.cached_anime.anidb_id == anidb_id:
                log.debug('We have aid%s cached, using it', anidb_id)
                series = self.cached_anime
            else:
                log.debug('AniDB id is present and is %s.', anidb_id)
                query = session.query(Anime)
                query = query.filter(Anime.anidb_id == anidb_id)
                series = query.first()
                log.debug(series)
        else:
            log.debug('AniDB id not present, looking up by the title, %s', name)
            series = (
                session.query(Anime)
                .join(AnimeTitle)
                .filter(AnimeTitle.name == name)
                .first()
            )
            if not series and name:
                like_gen = self.generate_like_statement(name)
                titles = session.query(AnimeTitle).filter(*like_gen).all()
                if not titles:
                    return None
                match = fw_process.extractOne(name, titles)
                log.debug('%s: %s, %s', match[0], match[1], name)
                if match and match[1] >= 90:
                    series_id = match[0].parent_id
                    series = session.query(Anime).filter(Anime.id_ == series_id).first()
                    self.cached_anime = series

        if series:
            log.debug('%s', series)
            if not only_cached and (series.expired is None or series.expired):
                log.debug('%s is expired, refreshing metadata', series.title_main)
                parser = AnidbParser(series.anidb_id)
                parser.parse()
                series = parser.series
                log.debug(series)
            if not anidb_id:
                self.last_lookup = LastLookup(series.anidb_id, name)
            return series

        log.warning(
            'No series found with series name: %s, when was the last time the cache was updated?',
            name,
        )

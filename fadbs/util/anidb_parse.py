"""In charge of fetching and parsing anime from AniDB."""
import logging
from typing import Optional
from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from flexget import plugin
from requests import HTTPError
from sqlalchemy import orm as sa_orm
from flexget.utils import requests
from loguru import logger

from .config import CONFIG
from .api_anidb import Anime
from .anidb_cache import cached_anidb
from .fadbs_session import FadbsSession
from .anidb_parser_new import AnidbAnime
from .anidb_parser_tags import AnidbParserTags
from .anidb_parse_episodes import AnidbParserEpisodes

PLUGIN_ID = 'anidb_parser'

DISABLED = False

requests_ = requests.Session()
requests_.headers.update({'User-Agent': 'Python-urllib/2.6'})

requests_.add_domain_limiter(requests.TimedLimiter('api.anidb.net', '3 seconds'))


class AnidbParser(AnidbParserTags, AnidbParserEpisodes):
    """Download and parse an AniDB entry into the database."""

    client_string = 'fadbs'
    client_version = 2

    anidb_protover = 1

    anidb_endpoint = 'http://api.anidb.net:9001/httpapi'
    anidb_params = {
        'client': client_string,
        'clientver': client_version,
        'protover': anidb_protover,
    }
    anidb_anime_params = {
        'request': 'anime',
        'aid': 0,
    }
    anidb_cache_time = timedelta(days=1)
    fadbs_session: FadbsSession

    def __init__(self, anidb_id: int, fadbs_session: Optional[FadbsSession] = None):
        """Initialize AnidbParser."""
        if fadbs_session:
            self.fadbs_session = fadbs_session
        else:
            self.fadbs_session = FadbsSession()
        self.anidb_id = anidb_id
        self.anidb_anime_params.update(aid=anidb_id)
        self._get_anime()

    def __del__(self):
        logger.trace('YEETING %s', self)
        if self.session:
            self.session.close()

    @property
    def session(self) -> sa_orm.Session:
        return self.fadbs_session.session

    @property
    def requests(self) -> requests.Session:
        return self.fadbs_session.requests

    @pysnooper.snoop('anidb_parse-request_anime.log', depth=2)
    def request_anime(self) -> str:
        """Request an anime from AniDB."""
        banned_until = CONFIG.banned + timedelta(days=1)
        if CONFIG.is_banned():
            raise plugin.PluginError(
                'Banned from AniDB until {0}'.format(banned_until),
            )
        # params = self.anidb_params.copy()
        # params.update(self.anidb_anime_params)
        # params.update({'aid': self.anidb_id})
        # if not self.series.is_airing and self.series.end_date and datetime.utcnow().date() - self.series.end_date > timedelta(days=14):
        #    return
        if not self.series.should_update:
            return None
        params = {'aid': self.anidb_id}
        try:
            page = self.requests.get('https://xvicario.us/anidb', params=params)
            CONFIG.inc_session()
            CONFIG.update_session()
        except HTTPError as http_error:
            logger.warning(http_error.strerror)
            raise http_error
        if page:
            page = page.text
            if page == 'banned':
                CONFIG.set_banned()
                raise plugin.PluginError(
                    'Banned from AniDB until {0}'.format(CONFIG.banned + timedelta(days=1)),
                )
        return page

    def _get_anime(self) -> None:
        self.series = (
            self.session.query(Anime).get({'anidb_id': self.anidb_id})
        )
        if not self.series:
            raise plugin.PluginError(
                'Anime not found? When is the last time the cache was updated?',
            )

    @cached_anidb
    def parse(self, soup: BeautifulSoup = None) -> None:
        """Parse the soup and shove it into the database."""
        if not soup:
            raise plugin.PluginError('The soup did not arrive.')

        parse_anime = AnidbAnime(self.anidb_id, soup)

        with self.session.no_autoflush:
            root = soup.find('anime')

            if not root:
                raise plugin.PluginError(
                    'No anime was found in the soup, did we get passed something bad?',
                )

            logger.trace('Setting series_type')
            self.series.series_type = parse_anime.series_type

            logger.trace('Setting num_episodes')
            self.series.num_episodes = parse_anime.episode_count

            logger.trace('Setting the start and end dates')
            try:
                start = [int(part) for part in parse_anime.startdate.split('-')]
                self.series.start_date = datetime(*start).date()
                end = [int(part) for part in parse_anime.enddate.split('-')]
                self.series.end_date = datetime(*end).date()
            except ValueError:
                logger.warning("Series date isn't a fully qualified date.")

            logger.trace('Setting titles')
            self._set_titles(root.find('titles'))

            # todo: similar, related

            logger.trace('Setting urls')
            self.series.url = parse_anime.official_url

            # todo: creators

            logger.trace('Setting description')
            self.series.description = parse_anime.description

            logger.trace('Setting ratings')
            self.series.permanent_rating = parse_anime.permanent_rating
            self.series.mean_rating = parse_anime.mean_rating

            logger.trace('Setting tags')
            tags = root.find('tags')
            if tags:
                self._set_tags(tags('tag'))

            # todo: characters

            logger.trace('Setting episodes')
            self._set_episodes(root.find('episodes'))

            self.session.add(self.series)

            self.series.updated = datetime.now()

            self.session.commit()

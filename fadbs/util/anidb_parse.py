"""In charge of fetching and parsing anime from AniDB."""
import logging
from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from flexget import plugin
from flexget.logger import FlexGetLogger
from flexget.manager import manager
from flexget.utils import requests
from requests import HTTPError
from sqlalchemy import orm as sa_orm

import utils

from .anidb_cache import cached_anidb
from .anidb_parse_episodes import AnidbParserEpisodes
from .anidb_parser_tags import AnidbParserTags
from .api_anidb import Anime
from .config import CONFIG

PLUGIN_ID = 'anidb_parser'

LOG: FlexGetLogger = logging.getLogger(PLUGIN_ID)

DISABLED = False

requests_ = requests.Session()
requests_.headers.update({'User-Agent': 'Python-urllib/2.6'})

requests_.add_domain_limiter(
    requests.TimedLimiter(
        'api.anidb.net',
        '3 seconds',
    ),
)


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

    def __init__(self, anidb_id: int):
        """Initialize AnidbParser."""
        if manager:
            session = sa_orm.sessionmaker(class_=sa_orm.Session)
            session.configure(bind=manager.engine, expire_on_commit=False)
            self.session = session()
        else:
            self.session = None
        self.anidb_id = anidb_id
        self.anidb_anime_params.update(aid=anidb_id)
        self._get_anime()

    def __del__(self):
        LOG.trace('YEETING %s', self)
        if self.session:
            self.session.close()

    @property
    def requests(self):
        return manager.task_queue.current_task.requests

    def request_anime(self):
        """Request an anime from AniDB."""
        if CONFIG.is_banned():
            raise plugin.PluginError(
                'Banned from AniDB until {0}'.format(
                    CONFIG.banned + timedelta(days=1),
                ),
            )
        # params = self.anidb_params.copy()
        # params.update(self.anidb_anime_params)
        # params.update({'aid': self.anidb_iid})
        if not self.series.is_airing and self.series.end_date and datetime.utcnow().date() - self.series.end_date > timedelta(days=14):
            return
        params = {'aid': self.anidb_id}
        if DISABLED:
            LOG.error('Banned from AniDB probably. Ask DerIdiot')
            return
        try:
            page = requests_.get('anidb_lol', params=params)
            CONFIG.inc_session()
            CONFIG.update_session()
        except HTTPError as http_error:
            LOG.warning(http_error)
            return
        if page:
            page = page.text
        else:
            LOG.warning('Rip no page')
            return
        if page == 'banned':
            CONFIG.set_banned()
            raise plugin.PluginError(
                'Banned from AniDB until {0}'.format(CONFIG.banned + timedelta(days=1)),
            )
        return page

    def _get_anime(self) -> None:
        self.series = self.session.query(Anime)\
            .filter(Anime.anidb_id == self.anidb_id).first()
        if not self.series:
            raise plugin.PluginError(
                'Anime not found? When is the last time the cache was updated?',
            )

    @cached_anidb
    def parse(self, soup: BeautifulSoup = None) -> None:
        """Parse the soup and shove it into the database."""
        if not soup:
            raise plugin.PluginError('The soup did not arrive.')

        with self.session.no_autoflush:
            root = soup.find('anime')

            if not root:
                raise plugin.PluginError(
                    'No anime was found in the soup, did we get passed something bad?',
                )

            LOG.trace('Setting series_type')
            series_type = root.find('type')
            if series_type:
                self.series.series_type = series_type.string

            LOG.trace('Setting num_episodes')
            num_episodes = root.find('episodecount')
            if not num_episodes:
                self.series.num_episodes = 0
            self.series.num_episodes = int(num_episodes.string)

            LOG.trace('Setting the start and end dates')
            self.series.start_date = utils.get_date(root.find('startdate'))
            self.series.end_date = utils.get_date(root.find('enddate'))

            LOG.trace('Setting titles')
            self._set_titles(root.find('titles'))

            # todo: similar, related

            LOG.trace('Setting urls')
            official_url = root.find('url')
            if official_url:
                self.series.url = official_url.string

            # todo: creators

            LOG.trace('Setting description')
            description = root.find('description')
            if description:
                self.series.description = description.string

            LOG.trace('Setting ratings')
            ratings_dict = utils.get_ratings(root.find('ratings'))
            if hasattr(ratings_dict, 'permanent'):
                self.series.permanent_rating = ratings_dict['permanent']
            if hasattr(ratings_dict, 'mean'):
                self.series.mean_rating = ratings_dict['mean']

            LOG.trace('Setting tags')
            tags = root.find('tags')
            if tags:
                self._set_tags(tags('tag'))

            # todo: characters

            LOG.trace('Setting episodes')
            self._set_episodes(root.find('episodes'))

            self.session.add(self.series)

            self.series.updated = datetime.now()

            self.session.commit()

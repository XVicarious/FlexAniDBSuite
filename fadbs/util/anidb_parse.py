import logging
import os
from datetime import datetime, timedelta

from flexget import plugin
from flexget.manager import manager
from flexget.utils.database import with_session

from .anidb_cache import cached_anidb
from .anidb_parsing_interface import AnidbParserTemplate
from .anidb_parser_tags import AnidbParserTags
from .api_anidb import Anime

PLUGIN_ID = 'anidb_parser'

LOG = logging.getLogger(PLUGIN_ID)


class AnidbParser(AnidbParserTemplate, AnidbParserTags):
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
    anidb_ban_file = os.path.join(manager.config_base, '.anidb_ban')

    def __init__(self, anidb_id):
        self.anidb_id = anidb_id
        self.anidb_anime_params.update(aid=anidb_id)

    @property
    def is_banned(self):
        """Check if we are banned from AniDB."""
        banned = False
        banned_until = None
        if os.path.exists(self.anidb_ban_file):
            with open(self.anidb_ban_file, 'r') as aniban:
                tmp_aniban = aniban.read()
                if tmp_aniban:
                    banned = datetime.now() - banned_until < timedelta(days=1)
                    banned_until = datetime.fromtimestamp(float(tmp_aniban))
                    aniban.close()
                if not banned:
                    os.remove(self.anidb_ban_file)
        return banned, banned_until

    @with_session
    @cached_anidb
    def parse(self, soup=None, session=None):
        """Parse the soup and shove it into the database."""
        if not soup:
            raise plugin.PluginError('The soup did not arrive.')

        root = soup.find('anime')

        if not root:
            raise plugin.PluginError('No anime was found in the soup, did we get passed somethign bad?')

        series = session.query(Anime).filter(Anime.anidb_id == self.anidb_id).first()
        if not series:
            series = Anime()
            series.anidb_id = self.anidb_id

        series_type = root.find('type')
        if series_type:
            series.series_type = series_type.string

        num_episodes = root.find('episodecount')
        if not num_episodes:
            series.num_episodes = 0
        series.num_episodes = int(num_episodes)

        self._set_dates(root.find('startdate'), root.find('enddate'))

        self._set_titles(root.find('titles'), session)

        # todo: similar, related

        official_url = root.find('url')
        if official_url:
            series.url = official_url.string

        # todo: creators

        description = root.find('description')
        if description:
            series.description = description.string

        ratings = root.find('ratings')
        if ratings:
            permanent = ratings.find('permanent')
            if permanent:
                series.permanent_rating = float(permanent.string)
                # todo: permanent votes
            mean = ratings.find('temporary')
            if mean:
                series.mean_rating = float(mean.string)
                # todo: mean votes

        self._set_tags(root.find('tags'), session)

        # todo: characters

        self._set_episodes(root.find('episodes'), session)

        session.add(self.series)
        session.commit()

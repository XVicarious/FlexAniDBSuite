"""Class responsible for looking up a series and lazy loading the values."""
import logging
from typing import Dict

from flexget import plugin
from flexget.event import event
from loguru import logger
from flexget.utils.database import with_session
from flexget.utils.log import log_once

from .util import ANIDB_SEARCH

PLUGIN_ID: str = 'fadbs_lookup'



class FadbsLookup(object):
    """Lookup and Return an Anime."""

    @staticmethod
    def _title_dict(series):
        titles: Dict = {}
        for title in series.titles:
            if title.ep_type not in titles:
                titles.update({title.ep_type: []})
            titles[title.ep_type].append(
                {'lang': title.language, 'name': title.name},
            )
        return titles

    field_map = {
        'anidb_id': 'anidb_id',
        'anidb_title_main': 'title_main',
        'anidb_type': 'series_type',
        'anidb_num_episodes': 'num_episodes',
        'anidb_startdate': 'start_date',
        'anidb_enddate': 'end_date',
        'anidb_titles': lambda series: [title.name for title in series.titles],
        # todo: related anime
        # todo: similar anime
        'anidb_official_url': 'url',
        # todo: creators
        'anidb_description': 'description',
        'anidb_rating': 'permanent_rating',
        'anidb_mean_rating': 'mean_rating',
        'anidb_tags': lambda series: {
            genre.genre.anidb_id: [genre.genre.name, genre.weight]
            for genre in series.genres
        },
        'anidb_episodes': lambda series: [
            (episode.anidb_id, episode.number) for episode in series.episodes
        ],
        'anidb_year': 'year',
        'anidb_season': 'season',
    }

    # todo: implement UDP api to get more info
    # UDP gives us more episode information, I think
    # who knows. They've had 15 years to develop this api
    # and it still doesn't include a ton of things
    episode_field_map = {
        'anidb_episode_id': 'anidb_id',
        'anidb_episode_number': 'number',
        'anidb_episode_type': 'ep_type',
        'anidb_episode_airdate': 'airdate',
        'anidb_episode_rating': 'rating',
        'anidb_episode_titles': lambda episode: [
            title.title for title in episode.titles if title.language == 'en'
        ],
        'anidb_episode_votes': 'votes',
    }

    schema = {'type': 'boolean'}

    @plugin.priority(130)
    def on_task_metainfo(self, task, config):
        """Flexget Metainfo Method."""
        if not config:
            return
        for entry in task.entries:
            logger.debug('Looking up: {}', entry.get('title'))
            self.register_lazy_fields(entry)

    def register_lazy_fields(self, entry):
        dict_keys = {**self.field_map, **self.episode_field_map}
        entry.register_lazy_func(self.lazy_loader, dict_keys)

    def lazy_loader(self, entry):
        try:
            self.lookup(entry)
        except plugin.PluginError as err:
            log_once(str(err.value).capitalize(), logger=log)

    @property
    def series_identifier(self):
        """Return what field is used to identify the series."""
        return 'anidb_id'

    @property
    def movie_identifier(self):
        return self.series_identifier

    @plugin.internet(log)
    @with_session
    def lookup(self, entry, session=None):
        """Lookup series, and update the entry."""
        anidb_id = entry.get('anidb_id')
        series_name = entry.get('series_name')
        location = entry.get('location')
        logger.verbose(
            '{}: {} ({}) at {}', entry['title'], series_name, anidb_id, location,
        )
        series = ANIDB_SEARCH.lookup_series(anidb_id=anidb_id, name=series_name)

        # There is a whole part about expired entries here.
        # Possibly increase the default cache time to a week,
        # and let the user set it themselves if they want, to
        # a minimum of 24 hours due to AniDB's policies...

        # todo: trace log attributes?
        if series:
            if not session.object_session(series):
                session.add(series)
            entry.update_using_map(self.field_map, series)
            if 'series_id' in entry:
                entry_id = str(entry['series_id'])
                for episode_entry in series.episodes:
                    if episode_entry.number == entry_id:
                        entry.update_using_map(self.episode_field_map, episode_entry)
                        break


@event('plugin.register')
def register_plugin():
    """Register the plugin with Flexget."""
    plugin.register(
        FadbsLookup,
        PLUGIN_ID,
        api_ver=2,
        interfaces=['task', 'series_metainfo', 'movie_metainfo'],
    )

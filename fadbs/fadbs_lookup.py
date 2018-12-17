"""Class responsible for looking up a series and lazy loading the values."""
import logging
from typing import Type

from flexget import plugin
from flexget.event import event
from flexget.logger import FlexGetLogger
from flexget.utils.database import with_session
from flexget.utils.log import log_once

from .util import ANIDB_SEARCH
from .util.api_anidb import AnimeEpisode

PLUGIN_ID = 'fadbs_lookup'

log: FlexGetLogger = logging.getLogger(PLUGIN_ID)


class FadbsLookup(object):
    """Lookup and Return an Anime."""

    @staticmethod
    def _title_dict(series):
        titles = {}
        for title in series.titles:
            if title.ep_type not in titles:
                titles.update({title.ep_type: []})
            titles[title.ep_type].append({
                'lang': title.language,
                'name': title.name,
            })
        return titles

    field_map = {
        'anidb_id': 'anidb_id',
        'anidb_title_main': lambda series: series.title_main,
        'anidb_type': 'series_type',
        'anidb_num_episodes': 'num_episodes',
        'anidb_startdate': 'start_date',
        'anidb_enddate': 'end_date',
        'anidb_titles': lambda series: FadbsLookup._title_dict(series),
        # todo: related anime
        # todo: similar anime
        'anidb_official_url': 'url',
        # todo: creators
        'anidb_description': 'description',
        'anidb_rating': 'permanent_rating',
        'anidb_mean_rating': 'mean_rating',
        'anidb_tags': lambda series: {
            genre.genre.anidb_id: [genre.genre.name, genre.weight] for genre in series.genres
        },
        'anidb_episodes': lambda series: [(episode.anidb_id, episode.number) for episode in series.episodes],
        'anidb_year': 'year',
        'anidb_season': 'season'}

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
            'anidb_episode_titles': 'titles',
            'anidb_episode_votes': 'votes'}

    schema = {'type': 'boolean'}

    @plugin.priority(130)
    def on_task_metainfo(self, task, config):
        if not config:
            return
        for entry in task.entries:
            log.debug('Looking up: %s', entry.get('title'))
            self.register_lazy_fields(entry)

    def register_lazy_fields(self, entry):
        entry.register_lazy_func(self.lazy_loader, self.field_map)

    def lazy_loader(self, entry):
        try:
            self.lookup(entry)
        except plugin.PluginError as err:
            log_once(str(err.value).capitalize(), logger=log)

    @property
    def series_identifier(self):
        return 'anidb_id'

    @plugin.internet(log)
    @with_session
    def lookup(self, entry, session=None):
        """Lookup series, and update the entry."""

        series = None

        try:
            anidb_id = entry.get('anidb_id', eval_lazy=False)
            series_name = entry.get('series_name')
            log.verbose('%s: %s', anidb_id, series_name)
            series = ANIDB_SEARCH.lookup_series(anidb_id=anidb_id, name=series_name)
        except plugin.PluginError as err:
            raise plugin.PluginError(err)
        except Exception as err:
            raise plugin.PluginError(err)

        # There is a whole part about expired entries here.
        # Possibly increase the default cache time to a week,
        # and let the user set it themselves if they want, to
        # a minimum of 24 hours due to AniDB's policies...

        # todo: trace log attributes?
        if series:
            session.add(series)
            entry.update_using_map(self.field_map, series)
            if 'series_id' in entry:
                episode = None
                for episode_entry in series.episodes:
                    if episode_entry.number == entry['series_id']:
                        episode = episode_entry
                        break
                if episode:
                    entry.update_using_map(self.episode_field_map, episode)


@event('plugin.register')
def register_plugin():
    plugin.register(FadbsLookup, PLUGIN_ID, api_ver=2, interfaces=['task', 'series_metainfo', 'movie_metainfo'])

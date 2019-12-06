import logging

from flexget import plugin
from flexget.event import event
from flexget.utils.database import with_session

from .util import ANIDB_SEARCH

PLUGIN_ID = 'fadbs_est_release'

log = logging.getLogger(PLUGIN_ID)


class EstimateSeriesAniDb(object):
    @plugin.priority(2)
    @with_session
    def estimate(self, entry, session=None):
        """Estimate when the entry episode aired or will air."""
        if any(
            field in entry for field in ['series_name', 'anidb_title_main', 'anidb_id']
        ):
            series = ANIDB_SEARCH.lookup_series(
                anidb_id=entry.get('anidb_id'),
                name=entry.get('anidb_title_main', entry.get('series_name')),
            )
            if series:
                if not session.object_session(series):
                    session.add(series)
                anime_episodes = series.episodes
                series_episode = str(entry.get('series_episode'))
                airdate = [
                    episode.airdate
                    for episode in anime_episodes
                    if episode.number == series_episode
                ]
                airdate = airdate[0] if airdate else None
                return airdate
            return None
        log.debug(
            '%s did not have the required attributes to search for the episode',
            entry['title'],
        )


@event('plugin.register')
def register_plugin():
    plugin.register(
        EstimateSeriesAniDb, PLUGIN_ID, interfaces=['estimate_release'], api_ver=2
    )

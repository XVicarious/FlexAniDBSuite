from __future__ import unicode_literals, division, absolute_import

import difflib
import logging
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from flexget import plugin
from flexget.event import event
from flexget.utils.database import with_session

from .fadbs_lookup import Anime, AnimeTitle

PLUGIN_ID = 'fadbs_est_release'

log = logging.getLogger(PLUGIN_ID)


class EstimateSeriesAniDb(object):
    @plugin.priority(2)
    @with_session
    def estimate(self, entry, ratio=0.9, session=None):
        """Estimate when the entry episode aired or will air."""
        if not all(field in entry for field in ['series_name']):
            log.debug('%s did not have the required attributes to search for the episode', entry['title'])
            return
        exact_match = session.query(AnimeTitle).filter(AnimeTitle.name == entry['series_name'])
        if len(exact_match):
            exact_match = exact_match.first().parent_id
            exact_anime = session.query(Anime).join(Anime.episodes).filter(Anime.id_ == exact_match)
            if len(exact_anime):
                anime_episodes = exact_anime.first().episodes
                series_episode = str(entry.get('series_episode'))
                airdate = [episode.airdate for episode in anime_episodes if episode.number == series_episode]
                airdate = airdate[0] if len(airdate) else None
                return airdate
        pre_anime = session.query(Anime).join(Anime.titles).all()
        log.trace('Retrieved %s Anime from the database.', len(pre_anime))
        seq_matcher = difflib.SequenceMatcher(a=entry.get('series_name').lower())
        titles_match = {}
        for anime in pre_anime:
            log.trace('Checking the titles for aid %s', anime.anidb_id)
            for title in anime.titles:
                log.trace('Checking title "%s" for aid %s', title.name, anime.anidb_id)
                seq_matcher.set_seq2(title.name.lower())
                if seq_matcher.ratio() >= ratio:
                    if anime.anidb_id not in titles_match:
                        titles_match.update({anime.anidb_id: []})
                    log.debug('Adding title "%s" to the possible matches.', title.name)
                    titles_match[anime.anidb_id].append((seq_matcher.ratio(), title.name))
        if not len(titles_match):
            log.info('There were no title matches found "%s"', entry.get('series_name'))
            return
        log.debug('Titles with good matches: %s', titles_match)
        best_anidb_id = (0, 0.0)
        for key_anidb_id, val_ratio_name in titles_match.items():
            log.trace('Checking titles that were retrieved from aid %s', key_anidb_id)
            for tuple_match in val_ratio_name:
                if tuple_match[0] > best_anidb_id[1]:
                    best_anidb_id = (key_anidb_id, tuple_match[0])
                if best_anidb_id[1] == 1:
                    log.debug('%s had a perfect match, this is it.', key_anidb_id)
                    break
            if best_anidb_id[1] == 1:
                break
        episode = entry.get('series_id')
        anime = session.query(Anime).join(Anime.episodes).filter(Anime.anidb_id == best_anidb_id[0]).first()
        if not anime:
            log.error('The query for anime with aid %s was not found.', best_anidb_id[0])
            return
        for sode in anime.episodes:
            try:
                if int(sode.number) == episode:
                    log.debug('Next airdate: %s', sode.airdate)
                    return sode.airdate
            except ValueError:
                pass


@event('plugin.register')
def register_plugin():
    plugin.register(EstimateSeriesAniDb, PLUGIN_ID, interfaces=['estimate_release'], api_ver=2)

from __future__ import unicode_literals, division, absolute_import

import difflib
import logging
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from flexget import plugin
from flexget.event import event
from flexget.utils.database import with_session

from .fadbs_lookup import Anime

PLUGIN_ID = 'fadbs_est_release'

log = logging.getLogger(PLUGIN_ID)


class EstimateSeriesAniDb(object):
    @plugin.priority(2)
    @with_session
    def estimate(self, entry, session=None):
        """ Estimate when the entry episode aired or will air """
        if not all(field in entry for field in ['series_name']):
            log.debug('%s did not have the required attributes to search for the episode', entry['title'])
            return
        pre_anime = session.query(Anime).join(Anime.titles).all()
        titles_match = {}
        for anime in pre_anime:
            for title in anime.titles:
                compar = difflib.SequenceMatcher(a=entry.get('series_name').lower(), b=title.name.lower()).ratio()
                if compar >= 0.75:
                    if anime.anidb_id not in titles_match:
                        titles_match.update({anime.anidb_id: []})
                    titles_match[anime.anidb_id].append((compar, title.name))
        if not len(titles_match):
            log.info('There were no title matches found "%s"', entry.get('series_name'))
            return
        log.trace('Titles with good matches: %s', titles_match)
        best_anidb_id = (0, 0.0)
        for key_anidb_id, val_ratio_name in titles_match.items():
            for tuple_match in val_ratio_name:
                if tuple_match[0] > best_anidb_id[1]:
                    best_anidb_id = (key_anidb_id, tuple_match[0])
                if best_anidb_id[1] == 1.0:
                    break
            if best_anidb_id[1] == 1.0:
                break
        episode = entry.get('series_id')
        anime = session.query(Anime).join(Anime.episodes).filter(Anime.anidb_id == best_anidb_id[0]).first()
        if not anime:
            return
        for sode in anime.episodes:
            try:
                if int(sode.number) == episode:
                    log.debug('Next airdate: %s', sode.airdate)
                    return sode.airdate
            except ValueError:
                pass
        return


@event('plugin.register')
def register_plugin():
    plugin.register(EstimateSeriesAniDb, PLUGIN_ID, interfaces=['estimate_release'], api_ver=2)

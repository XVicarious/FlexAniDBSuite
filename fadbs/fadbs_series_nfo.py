"""FADBS Series NFO Plugin."""
import logging
import os
import re
from pathlib import Path
from typing import List, Tuple

from flexget import plugin
from flexget.event import event
from flexget.logger import FlexGetLogger
from flexget.utils import template

PLUGIN_ID = 'fadbs_series_nfo'

log: FlexGetLogger = logging.getLogger(PLUGIN_ID)


class FadbsSeriesNfo():
    """Series NFO plugin object."""

    schema = {
        'oneOf': [
            {'type': 'boolean', 'default': False},
            {'type': 'object',
             'properties': {
                 'genre_weight': {'type': 'integer', 'default': 500},
                 'spoilers': {
                     'type': 'array',
                     'items': {'type': 'string', 'enum': ['local', 'global']},
                 },
                 'title': {
                     'type': 'object',
                     'properties': {
                         'type': {'type': 'string', 'default': 'main'},
                         'enum': ['main', 'official', 'synonym', 'short'],
                         'lang': {'type': 'string', 'default': 'x-jat'},
                     },
                 },
             },
             },
        ],
    }

    # These are all genres, genres that are True don't have possible overriding sub-genres
    # Genres that are False have possible overriding sub-genres
    # genres with another genre id replace that genre as a genre (if that makes sense)
    # todo: Make this more flexible, what if someone wants a sub-sub-genre to be a genre?
    # todo: don't enforce items to be genres, an anime could have some action but not be
    #       an action anime
    default_genres = {
        2841: True,   # Action
        2282: True,   # Martial arts
        2850: True,   # Adventure
        2853: True,   # Comedy
        2655: True,   # Parody
        2856: True,   # Ecchi
        2851: True,   # Horror
        2858: True,   # Romance
        2849: False,  # Fantasy
        2648: 2849,   # Contemporary Fantasy
        2649: 2849,   # Dark Fantasy
        2647: 2849,   # High Fantasy
        2094: True,   # Magic
        2846: True,   # Science Fiction
        2638: True,   # Mecha
        2623: True,   # Super Power
        2887: True,   # Tragedy
        2864: True,   # Daily Life
        2869: True,   # School Life
        2881: True,   # Sports
    }
    demographic = {
        922,    # Shounen
        1077,   # Shoujo
        1802,   # Seinen
        1846,   # Kodomo
        2614,   # Josei
        2616,   # Mina
    }

    def on_task_output(self, task, config):
        """Cast a spell to make NFO files."""
        log.info('Starting fadbs_series_nfo')
        filename = os.path.expanduser('tvshow.nfo.template')
        episode_template = os.path.expanduser('episode.nfo.template')
        for entry in task.entries:
            log.debug('Starting nfo generation for %s', entry['title'])
            # Load stuff
            if os.path.isdir(entry['location']):
                entry['fadbs_nfo'] = {}
                entry_titles = entry.get('anidb_titles')
                if entry_titles:
                    entry['fadbs_nfo'].update(title=entry['anidb_title_main'])
                else:
                    log.warning('We were not given any titles, skipping...')
                    continue
                entry_tags = entry.get('anidb_tags')
                entry['fadbs_nfo']['genres'] = []
                entry['fadbs_nfo']['tags'] = []
                if entry_tags:
                    genres, tags = self._genres(
                        entry.get('anidb_tags').items(),
                        config['genre_weight'],
                    )
                    entry['fadbs_nfo'].update(genres=genres)
                    entry['fadbs_nfo'].update(tags=tags)
                anime_template = template.render_from_entry(template.get_template(filename), entry)
                nfo_path = Path(entry['location'], 'tvshow.nfo')
                with open(nfo_path, 'wb') as nfo:
                    nfo.write(anime_template.encode('utf-8'))
                continue
            episode_number = entry.get('anidb_episode_number')
            file_path = entry['location']
            path = file_path[:-3] + 'nfo'
            nfo_path = Path(path)
            log.info(nfo_path)
            entry['anidb_episode_extra'] = {}
            entry['anidb_episode_extra']['season'] = 1
            if episode_number:
                try:
                    episode_number = int(episode_number)
                except ValueError:
                    entry['anidb_episode_extra']['season'] = 0
                    num = re.compile(r'\d+$')
                    log.info('type: %s', type(entry['anidb_episode_number']))
                    episode_number = num.match(entry['anidb_episode_number'])
                anime_template = template.render_from_entry(template.get_template(episode_template), entry)
                with open(nfo_path, 'wb') as nfo:
                    nfo.write(anime_template.encode('utf-8'))

    def meets_genre_weight(self, weight: int, genre_weight: int) -> bool:
        return genre_weight <= weight  # or weight == 0

    def _genres(self, anidb_tags, genre_weight) -> Tuple:
        g_and_t: Tuple[List[str], List[str]] = ([], [])
        for aid, tag_info in anidb_tags:
            aid = int(aid)
            name, weight = tag_info
            log.trace('%s: %s, weight %s', aid, name, weight)
            if aid in self.default_genres.keys() and self.meets_genre_weight(weight, genre_weight):
                g_and_t[0].append(name)
                log.debug('Added %s as a genre', name)
                continue
                # todo: remove an overridden genre
            elif aid in self.demographic:
                g_and_t[0].append(name)
                log.debug('Added demographic %s as a genre', name)
                continue
            g_and_t[1].append(name)
        return g_and_t


@event('plugin.register')
def register_plugin():
    """Register fadbs_series_nfo."""
    plugin.register(FadbsSeriesNfo, 'fadbs_series_nfo', api_ver=2)

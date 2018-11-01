import logging
import os

from flexget import plugin
from flexget.event import event
from flexget.utils import template

from .util.stucture_utils import find_in_list_of_dict

PLUGIN_ID = 'fadbs_series_nfo'

log = logging.getLogger(PLUGIN_ID)


class FadbsSeriesNfo(object):

    schema = {
        'oneOf': [
            {'type': 'boolean', 'default': False},
            {'type': 'object',
             'properties': {
                 'genre_weight': {'type': 'integer', 'default': 500},
                 'spoilers': {'type': 'array',
                              'items': {'type': 'string', 'enum': ['local', 'global']}},
                 'title': {'type': 'object',
                           'properties': {
                               'type': {'type': 'string', 'default': 'main'},
                               'emum': ['main', 'official', 'synonym', 'short'],
                               'lang': {'type': 'string', 'default': 'x-jat'}}}}}
        ]
    }

    # These are all genres, genres that are True don't have possible overriding sub-genres
    # Genres that are False have possible overriding sub-genres
    # genres with another genre id replace that genre as a genre (if that makes sense)
    # todo: Make this more flexible, what if someone wants a sub-sub-genre to be a genre?
    default_genres = {
        2841: True, 2282: True,  # Action and martial arts
        2850: True,  # Adventure
        2853: True, 2655: True,  # Comedy and parody
        2856: True,  # Ecchi ;)
        2851: True,  # Horror
        2858: True,  # Romance
        2849: False, 2648: 2849, 2649: 2849, 2647: 2849, 2094: True,  # Fantasy and friends, and magic
        2846: True, 2638: True,  # Science Fiction and Mecha
        2623: True,  # Super Power
        2887: True,  # Tragedy
        2614: True, 1846: True, 2616: True, 1802: True, 1077: True, 922: True,  # Target Audiences
        2864: True, 2869: True,  # Daily Life and School Life
        2881: True  # Sports
    }

    def on_task_output(self, task, config):
        log.info('Starting fadbs_series_nfo')
        filename = os.path.expanduser('tvshow.nfo.template')
        for entry in task.entries:
            log.debug('Starting nfo generation for %s', entry['title'])
            # Load stuff
            entry['fadbs_nfo'] = {}
            entry_titles = entry.get('anidb_titles')
            if entry_titles:
                entry['fadbs_nfo'].update(title=self.__main_title(config, entry_titles))
            else:
                log.warning('We were not given any titles, skipping...')
                continue
            entry_tags = entry.get('anidb_tags')
            if entry_tags:
                fadbs_nfo = self.__genres(entry.get('anidb_tags').items(), config['genre_weight'])
                entry['fadbs_nfo'].update(genres=fadbs_nfo[0])
                entry['fadbs_nfo'].update(tags=fadbs_nfo[1])
            template_ = template.render_from_entry(template.get_template(filename), entry)
            nfo_path = os.path.join(entry['location'], 'tvshow.nfo')
            with open(nfo_path, 'wb') as nfo:
                nfo.write(template_.encode('utf-8'))
                nfo.close()

    def __genres(self, anidb_tags, genre_weight):
        genres = []
        tags = []
        for aid, info in anidb_tags:
            log.trace('%s: %s, weight %s', aid, info[0], info[1])
            if aid in self.default_genres or info[1] >= genre_weight:
                genres.append(info[0])
                # todo: remove an overridden genre
                continue
            tags.append(info[0])
        log.info('Genres: %s', genres)
        log.info('Tags: %s', tags)
        return genres, tags

    @staticmethod
    def __main_title(config, titles):
        title = None
        if 'type' in config and 'lang' in config:
            title = find_in_list_of_dict(config['type'], 'lang', config['lang'], 'name')
        if title is None or (isinstance(config, bool) and config):
            return find_in_list_of_dict(titles['main'], 'lang', 'x-jat', 'name')
        return title


@event('plugin.register')
def register_plugin():
    plugin.register(FadbsSeriesNfo, 'fadbs_series_nfo', api_ver=2)

import logging
import os

from flexget import plugin
from flexget.event import event
from flexget.utils import template

PLUGIN_ID = 'fadbs_series_nfo'

log = logging.getLogger(PLUGIN_ID)


class FadbsSeriesNfo(object):

    plugin_path = os.path.realpath(__file__)
    last_sep = plugin_path.rfind(os.sep)
    nfo_path = plugin_path[:last_sep] + os.sep + 'templates' + os.sep + 'task' + os.sep + 'tvshow.nfo.template'

    schema = {
        'type': 'object',
        'properties': {
            'genre_weight': {'type': 'integer', 'default': 400},
            'spoilers': {'type': 'array', 'items': {'type': 'string', 'enum': ['local', 'global']}}
        }
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
        filename = os.path.expanduser('tvshow.nfo.template')
        for entry in task.entries:
            # Load stuff
            entry_tags = entry.get('anidb_tags')
            if entry_tags is None:
                return
            entry['fadbs_nfo']['genres'], entry['fadbs_nfo']['tags'] = \
                self.__genres(entry.get('anidb_tags').items(), config['genre_weight'])
            template_ = template.render_from_entry(template.get_template(filename), entry)
            with open(entry.get('anidb_name') + '.tvshow.nfo', 'wb') as nfo:
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


@event('plugin.register')
def register_plugin():
    plugin.register(FadbsSeriesNfo, 'fadbs_series_nfo', api_ver=2)

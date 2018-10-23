import logging
import os

from flexget import plugin
from flexget.event import event
from flexget.utils import template

from .fadbs_lookup import FadbsLookup

PLUGIN_ID = 'fadbs_series_nfo'

log = logging.getLogger(PLUGIN_ID)


class FadbsSeriesNfo(object):

    plugin_path = os.path.realpath(__file__)
    last_sep = plugin_path.rfind(os.sep)
    nfo_path = plugin_path[:last_sep] + os.sep + 'templates' + os.sep + 'task' + os.sep + 'tvshow.nfo.template'

    schema = {
        'type': 'object',
        'properties': {
            'genre_weight': {'type': 'integer', 'default': 300},
            'spoilers': {'type': 'array', 'items': {'type': 'string', 'enum': ['local', 'global']}}
        }
    }

    def on_task_output(self, task, config):
        for entry in task.entries:
            self.__generate_nfo(entry)

    def __generate_nfo(self, entry):
        filename = os.path.expanduser('tvshow.nfo.template')
        # Load stuff
        log.debug(FadbsLookup.schema)
        for key in FadbsLookup.schema.keys():
            log.debug(entry.get(key))
        template_ = template.render_from_entry(template.get_template(filename), entry)
        log.debug(template_.encode('utf-8'))


@event('plugin.register')
def register_plugin():
    plugin.register(FadbsSeriesNfo, 'fadbs_series_nfo', api_ver=2)

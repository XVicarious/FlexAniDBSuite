import logging
import os

from flexget import plugin
from flexget.event import event
from jinja2 import Template

PLUGIN_ID = 'fadbs_series_nfo'

log = logging.getLogger(PLUGIN_ID)


class FadbsSeriesNfo(object):
    plugin_path = os.path.realpath(__file__)
    last_sep = plugin_path.rfind(os.sep)
    nfo_path = plugin_path[:last_sep] + os.sep + 'templates' + os.sep + 'tvshow.template.nfo'

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
        template = Template(self.nfo_path)

        template.render(entry=entry)


@event('plugin.register')
def register_plugin():
    plugin.register(FadbsSeriesNfo, 'fadbs_series_nfo', api_ver=2)

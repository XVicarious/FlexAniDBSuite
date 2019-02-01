import logging
from typing import List, Set, Tuple
from flexget.plugin import PluginError
from flexget import plugin
from flexget.event import event
from flexget.logger import FlexGetLogger
from flexget.config_schema import process_config
from flexget.plugins.filter.series import FilterSeriesBase
from flexget.plugins.parsers.parser_common import remove_dirt
from flexget.utils.database import with_session

from .util.api_anidb import Anime, AnimeTitle

LOG: FlexGetLogger = logging.getLogger('fadbs_series')


class EveryAnime(FilterSeriesBase):

    @property
    def schema(self):
        return {
            'type': 'object',
            'properties': {
                'settings': self.settings_schema,
                'from': {'$ref': '/schema/plugins?phase=input'},
            },
            'required': ['from'],
            'additionalProperties': False,
        }

    titles_main: List[Tuple[int, str]]
    titles_all: List[Tuple[int, str]]

    def title_available(self, title, anidb_id):
        for main_title in self.titles_main:
            if title == main_title[1]:
                return False
        for general_title in self.titles_all:
            if title == general_title[1] and anidb_id < general_title[0]:
                return False
        return True

    @with_session
    def on_task_prepare(self, task, config, session=None):
        series: dict = dict()
        self.titles_main = session.query(Anime.anidb_id, Anime.title_main).all()
        self.titles_all = session.query(Anime.anidb_id, AnimeTitle.name).join(Anime.titles).all()
        for input_name, input_config in config.get('from', {}).items():
            input = plugin.get_plugin_by_name(input_name)
            method = input.phase_handlers['input']
            try:
                result = method(task, input_config)
            except PluginError as e:
                LOG.warning('Error during input plugin %s: %s', input_name, e)
                continue
            if not result:
                LOG.warning('Input %s did not return anything', input_name)
                continue
            for entry in result:
                if not entry.get('anidb_id', None):
                    LOG.warning('need anidb_id, rip you')
                    continue
                anime = session.query(Anime).join(AnimeTitle).filter(Anime.anidb_id == entry['anidb_id']).first()
                if not anime:
                    LOG.warning('anidb_id %s wasn\'t in the database', entry['anidb_id'])
                    continue
                if entry.get('anidb_title_main'):
                    name = entry['anidb_title_main']
                elif entry.get('anidb_name'):
                    name = entry['anidb_name']
                else:
                    name = entry['title']
                name = remove_dirt(name)
                s_entry = series.setdefault(name, {})
                s_entry['set'] = {'anidb_id': entry['anidb_id']}
                s_entry['alternate_name'] = []
                series_titles: List[str] = list({self.clean_title(title.name) for title in anime.titles})
                for title in series_titles:
                    if self.title_available(title):
                        s_entry['alternate_name'].append(title)
                s_entry['prefer_specials'] = False
                s_entry['assume_special'] = True
                s_entry['identified_by'] = 'sequence'
                for key, schema in self.settings_schema['properties'].items():
                    if 'anime_series_' + key in entry:
                        errors = process_config(entry['anime_series_' + key], schema, set_defaults=False)
                        if errors:
                            LOG.debug('not settings series option %s for %s. errors: %s', key, entry['anidb_title_main'], errors)
                        else:
                            s_entry[key] = entry['anime_series_' + key]
        if not series:
            LOG.info('no seiries :(')
            return

        series_config = {'generated_series': [dict([x]) for x in series.items()]}
        if 'settings' in config:
            series_config['settings'] = {'generated_series': config['settings']}
        self.merge_config(task, series_config)

    def clean_title(self, title: str) -> str:
        title = remove_dirt(title)
        title = title.replace('&', 'and')
        title = title.replace('-', '')
        title = ' '.join(title.split())
        return title


@event('plugin.register')
def register_plugin():
    plugin.register(EveryAnime, 'fadbs_series', api_ver=2)

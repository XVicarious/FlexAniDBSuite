# -*- coding: utf-8 -*-
"""Generate Flexget Series from Anime Database."""
import logging
from typing import List

from flexget import plugin
from flexget.components.parsing.parsers.parser_common import clean_value
from flexget.components.series.series import FilterSeriesBase
from flexget.config_schema import process_config
from flexget.entry import Entry
from flexget.event import event
from flexget.logger import FlexGetLogger
from flexget.plugin import PluginError
from flexget.task import Task
from flexget.utils.database import with_session

from .util.api_anidb import Anime, AnimeTitle

LOG: FlexGetLogger = logging.getLogger('fadbs_series')


class EveryAnime(FilterSeriesBase):
    """Plugin class."""

    @property
    def schema(self):
        """Return the schema for the plugin."""
        return {
            'type': 'object',
            'properties': {
                'settings': self.settings_schema,
                'from': {
                    '$ref': '/schema/plugins?phase=input',
                },
                'fixes': {
                    'type': ['object', 'array'],
                    'items': {
                        'type': 'object',
                        'additionalProperties': self.settings_schema,
                    },
                },
            },
            'required': ['from'],
            'additionalProperties': False,
        }

    titles_main = None  #: List[Tuple[int, str]]
    titles_all = None  #: List[Tuple[int, str]]

    def available_titles(self, series_titles, anidb_id) -> List:
        """Return all titles from series_titles that are available to be used."""
        return [
            title for title in series_titles if self.title_available(title, anidb_id)
        ]

    def title_available(self, title, anidb_id):
        """Return if the requested title is available to be used."""
        if title in self.titles_main:
            return False
        for general_title in self.titles_all:
            if title == general_title[1] and int(anidb_id) < general_title[0]:
                return False
        return True

    @staticmethod
    def set_settings_key(config_fixes: dict, key: str, schema: dict, name: str, anidb_id: int):
        """Set a settings key, otherwise yell at the user.

        :param config_fixes: manual fixes for series that don't track properly
        :type config_fixes: dict
        :param key:
        :type key: str
        :param schema:
        :type schema: dict
        :param name: anime name
        :type name: str
        :param anidb_id: AniDB id
        :type anidb_id: int
        """
        fixed_setting = config_fixes[anidb_id][key]
        errors = process_config(fixed_setting, schema, set_defaults=False)
        if errors:
            LOG.warning('yada yada %s for %s errors %s', key, name, errors)
        LOG.verbose('%s (%s): {%s: %s}', name, anidb_id, key, fixed_setting)
        return fixed_setting

    @staticmethod
    def generate_entry_config(entry: Entry, key: str, name: str, schema: dict):
        errors = process_config(entry['anime_series_' + key], schema, set_defaults=False)
        if not errors:
            return entry['anime_series_' + key]
        LOG.warning('Not settings series option %s for %s. errors: %s', key, name, errors)
        return None

    @with_session
    def on_task_prepare(self, task: Task, config: dict, session=None):
        """Flexget Prepare method."""
        series: dict = {}
        self.titles_main = gen_titles_main()
        self.titles_all = session.query(Anime.anidb_id, AnimeTitle.name).join(Anime.titles).all()
        for input_name, input_config in config.get('from', {}).items():
            input_plugin = plugin.get_plugin_by_name(input_name)
            method = input_plugin.phase_handlers['input']
            try:
                input_results = method(task, input_config)
            except PluginError as plugin_error:
                error_string = str(plugin_error)
                LOG.warning('Error during input plugin %s: %s', input_name, error_string)
                continue
            if not input_results:
                LOG.warning('Input %s did not return anything', input_name)
                continue
            for entry in input_results:
                if not entry.get('anidb_id', None):
                    LOG.warning('need anidb_id, rip you')
                    continue
                anidb_id = int(entry['anidb_id'])
                anime = session.query(Anime).join(AnimeTitle)\
                    .filter(Anime.anidb_id == anidb_id, AnimeTitle.ep_type != 'short').first()
                if not anime:
                    LOG.warning("%s (a%s) wasn't in the database", entry['title'], anidb_id)
                    continue
                name = clean_value(anime.title_main)
                if not name:
                    LOG.warning("%s didn't have a proper series name", entry['title'])
                    continue
                s_entry = series.setdefault(name, {})
                LOG.trace('%s: %s', anidb_id, anime.title_main)
                s_entry['set'] = {'anidb_id': anidb_id}
                s_entry['alternate_name'] = []
                series_titles: List[str] = list({clean_value(title.name) for title in anime.titles})
                s_entry['alternate_name'] += self.available_titles(series_titles, anidb_id)
                s_entry['prefer_specials'] = False
                s_entry['assume_special'] = True
                s_entry['identified_by'] = 'sequence'
                s_entry['special_ids'] = [
                    'OP', 'ED', 'NCOP', 'NCED', 'Creditless OP', 'Creditless ED',
                ]
                for key, schema in self.settings_schema['properties'].items():
                    if 'fixes' not in config:
                        continue
                    if 'anime_series_' + key in entry:
                        s_entry[key] = EveryAnime.generate_entry_config(entry, key, name, schema)
                    if anidb_id in config['fixes'].keys() and key in config['fixes'][anidb_id]:
                        fixed_setting =\
                            self.set_settings_key(config.get('fixes'), key, schema, name, anidb_id)
                        if key in s_entry and isinstance(s_entry[key], list):
                            if not isinstance(fixed_setting, list):
                                fixed_setting = [fixed_setting]
                            s_entry[key] += fixed_setting
                            continue
                        s_entry[key] = fixed_setting

        if not series:
            LOG.info('no seiries :(')
            return

        series_config = {'anime': [dict([x]) for x in series.items()]}
        if 'settings' in config:
            series_config['settings'] = {'anime': config['settings']}
        self.merge_config(task, series_config)


@with_session
def gen_titles_main(session=None):
    """Generate a list of all anime titles in the database."""
    titles = session.query(AnimeTitle.name).filter(AnimeTitle.ep_type == 'main').all()
    return [title[0] for title in titles]


@event('plugin.register')
def register_plugin():
    """Register fadbs_series."""
    plugin.register(EveryAnime, 'fadbs_series', api_ver=2)

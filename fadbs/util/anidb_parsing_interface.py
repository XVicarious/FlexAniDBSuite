"""Holds parsing specific functions for AnidbParser."""
import logging
import math
from datetime import datetime

from flexget import plugin

from .api_anidb import AnimeEpisode, AnimeEpisodeTitle, AnimeTitle
from .api_anidb import AnimeLanguage

PLUGIN_ID = 'anidb_parser'

LOG = logging.getLogger(PLUGIN_ID)


class AnidbParserTemplate():
    """Functions to manipulate series."""

    date_format = '%Y-%m-%d'

    anime_seasons = [
        'Winter',
        'Spring',
        'Summer',
        'Fall',
    ]

    def _get_anime_season(self, month):
        return self.anime_seasons[math.ceil(month / 3) - 1]

    def _set_dates(self, start_tag, end_tag):
        if start_tag:
            start_parts = start_tag.string.split('-')
            if len(start_parts) == 3:
                self.series.start_date = datetime.strptime(start_tag.string, self.date_format).date()
            else:
                self.series.start_date = None
            if len(start_parts) >= 2:
                month = int(start_parts[1])
                self.series.season = self._get_anime_season(month)
            self.series.year = int(start_parts[0])
        if end_tag:
            if len(end_tag.string.split('-')) == 3:
                self.series.end_date = datetime.strptime(end_tag.string, self.date_format).date()
            else:
                self.series.end_date = None

    def _find_lang(self, lang_name):
        lang = self.session.query(AnimeLanguage).filter(AnimeLanguage.name == lang_name).first()
        if not lang:
            lang = AnimeLanguage(lang_name)
        return lang

    def _set_titles(self, titles_tag):
        if not titles_tag:
            raise plugin.PluginError('titles_tag was None')
        series_id = self.series.id_
        for title in titles_tag.find_all(True, recursive=False):
            lang = self._find_lang(title['xml:lang'])
            anime_title = AnimeTitle(title.string, lang.name, title['type'], series_id)
            self.series.titles.append(anime_title)

    def _get_list_tag(self, tag, key):
        if tag:
            return [
                tag.string,
                tag[key],
            ]
        return [None, None]

    def _set_episodes(self, episodes_tag):
        if not episodes_tag:
            raise plugin.PluginError('episodes_tag was None')
        series_id = self.series.id_
        for episode in episodes_tag.find_all('episode'):
            db_episode = self.session.query(AnimeEpisode)
            db_episode = db_episode.filter(AnimeEpisode.anidb_id == episode['id']).first()
            if not db_episode:
                rating = self._get_list_tag(episode.find('rating'), 'votes')
                number = self._get_list_tag(episode.find('epno'), 'type')
                length = episode.find('length').string if episode.find('length') else None
                airdate = episode.find('airdate')
                if airdate:
                    airdate = datetime.strptime(airdate.string, self.date_format).date()
                db_episode = AnimeEpisode(int(episode['id']), number, length, airdate, rating, series_id)
                episode_id = db_episode.id_
                for episode_title in episode.find_all('title'):
                    lang = self._find_lang(episode_title['xml:lang'])
                    anime_episode_title = AnimeEpisodeTitle(episode_id, episode_title.string, lang.name)
                    db_episode.titles.append(anime_episode_title)
                self.series.episodes.append(db_episode)

import logging
import math
from datetime import datetime
from typing import Type

from flexget import plugin

from .api_anidb import Anime, AnimeEpisode, AnimeEpisodeTitle, AnimeTitle
from .api_anidb import AnimeLanguage

PLUGIN_ID = 'anidb_parser'

LOG = logging.getLogger(PLUGIN_ID)


class AnidbParserTemplate(object):
    """Functions to manipulate series."""

    date_format = '%Y-%m-%d'

    anime_seasons = {
        'Winter',
        'Spring',
        'Summer',
        'Fall',
    }

    series = Type[Anime]

    def get_anime_season(self, month):
        return self.anime_seasons[math.ceil(month)]

    def _set_dates(self, start_tag, end_tag):
        if start_tag:
            start_parts = start_tag.string.split('-')
            if len(start_parts) == 3:
                self.series.start_date = datetime.strptime(start_tag.string, self.date_format).date()
            else:
                self.series.start_date = None
            if len(start_parts) >= 2:
                month = int(start_parts[1])
                self.series.season = self.get_anime_season(month)
            self.series.year = int(start_parts[0])
        if end_tag:
            if len(end_tag.string.split('-')) == 3:
                self.series.end_date = datetime.strptime(end_tag.string, self.date_format).date()
            else:
                self.series.end_date = None

    def _find_lang(self, lang_name, session):
        lang = session.query(AnimeLanguage).filter(AnimeLanguage.name == lang_name).filter()
        if not lang:
            lang = AnimeLanguage(lang_name)
        return lang

    def _set_titles(self, titles_tag, session):
        if not session:
            raise plugin.PluginError('No session to work with!')
        if not titles_tag:
            raise plugin.PluginError('titles_tag was None')
        series_id = self.series.id_
        for title in titles_tag.find_all(True, recursive=False):
            lang = self._find_lang(title['xml:lang'], session)
            anime_title = AnimeTitle(title['name'], lang.name, title['type'], series_id)
            self.series.titles.append(anime_title)

    def _set_episodes(self, episodes_tag, session):
        if not session:
            raise plugin.PluginError('No session to work with!')
        if not episodes_tag:
            raise plugin.PluginError('episodes_tag was None')
        series_id = self.series.id_
        for episode in episodes_tag:
            db_episode = session.query(AnimeEpisode).filter(AnimeEpisode.anidb_id == episode['id']).first()
            if not db_episode:
                rating_tag = episode.find('rating')
                rating = [
                    rating_tag.string,
                    rating_tag['votes'],
                ] if rating_tag else [None, None]
                number_tag = episode.find('epno')
                number = [
                    number_tag.string,
                    number_tag['type'],
                ] if number_tag else [None, None]
                length = episode.find('length').string if episode.find('length') else None
                airdate = episode.find('airdate')
                if airdate:
                    airdate = datetime.strptime(airdate.string, self.date_format).date()
                db_episode = AnimeEpisode(int(episode['id']), number, length, airdate, rating, series_id)
                episode_id = db_episode.id_
                for episode_title in episode.find_all('title'):
                    lang = self._find_lang(episode_title['xml:lang'], session)
                    anime_episode_title = AnimeEpisodeTitle(episode_id, episode_title['name'], lang.name)
                    db_episode.titles.append(anime_episode_title)
                self.series.episodes.append(db_episode)

"""Holds parsing functions for episodes."""
from datetime import datetime
from typing import List

from bs4 import Tag
from sqlalchemy.orm import Session

from flexget import plugin

from .api_anidb import Anime, AnimeEpisode, AnimeEpisodeTitle, AnimeLanguage, AnimeTitle


class AnidbParserEpisodes(object):
    """Functions to parse Anime episodes."""

    series: Anime
    session: Session

    date_format = '%Y-%m-%d'

    def _find_lang(self, lang_name: str) -> AnimeLanguage:
        lang = self.session.query(AnimeLanguage).filter(
                AnimeLanguage.name == lang_name).first()
        if not lang:
            lang = AnimeLanguage(lang_name)
        return lang

    def _set_titles(self, titles_tag: Tag) -> None:
        if not titles_tag:
            raise plugin.PluginError('titles_tag was None')
        series_id = self.series.id_
        for title in titles_tag.find_all(True, recursive=False):
            lang = self._find_lang(title['xml:lang'])
            anime_title = AnimeTitle(title.string, lang.name, title['type'], series_id)
            self.series.titles.append(anime_title)

    def _get_list_tag(self, tag: Tag, key: str) -> List:
        if tag:
            return [
                tag.string,
                tag[key],
            ]
        return [None, None]

    def _get_episode_attrs(self, episode: Tag) -> List:
        episode_id = int(episode['id'])
        rating = self._get_list_tag(episode.find('rating'), 'votes')
        number = self._get_list_tag(episode.find('epno'), 'type')
        length = episode.find('length').string if episode.find('length') else None
        airdate = episode.find('airdate')
        if airdate:
            airdate = datetime.strptime(airdate.string, self.date_format).date()
        return [episode_id, number, length, airdate, rating]

    def _get_episode_titles(self, episode_id: int, episode_titles: List[Tag]) -> List[AnimeEpisodeTitle]:
        titles: List = []
        for title in episode_titles:
            lang = self._find_lang(title['xml:lang'])
            anime_episode_title = AnimeEpisodeTitle(episode_id, title.string, lang.name)
            titles.append(anime_episode_title)
        return titles

    def _set_episodes(self, episodes_tag: Tag) -> None:
        if not episodes_tag:
            raise plugin.PluginError('episodes_tag was None')
        for episode in episodes_tag.find_all('episode'):
            db_episode = self.session.query(AnimeEpisode)
            db_episode = db_episode.filter(AnimeEpisode.anidb_id == episode['id']).first()
            if not db_episode:
                episode_vars = self._get_episode_attrs(episode)
                episode_vars.append(self.series.id_)
                db_episode = AnimeEpisode(*episode_vars)
                episode_id = db_episode.id_
                titles = self._get_episode_titles(episode_id, episode.find_all('title'))
                db_episode.titles.extend(titles)
                self.series.episodes.append(db_episode)

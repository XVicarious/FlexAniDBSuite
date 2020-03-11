"""Holds parsing functions for episodes."""
from datetime import datetime
from typing import Dict, List, Optional

from bs4 import Tag
from sqlalchemy.orm import Session

from .anidb_parser_new import AnidbEpisode
from .api_anidb import Anime, AnimeEpisode, AnimeEpisodeTitle, AnimeLanguage, AnimeTitle
from .utils import get_list_tag


class AnidbParserEpisodes:
    """Functions to parse Anime episodes."""

    series: Anime
    session: Session

    date_format = '%Y-%m-%d'

    def _find_lang(self, lang_name: str) -> AnimeLanguage:
        lang = (
            self.session.query(AnimeLanguage)
            .filter(AnimeLanguage.name == lang_name)
            .first()
        )
        return lang or AnimeLanguage(lang_name)

    def _set_titles(self, titles_tag: Tag) -> None:
        if not titles_tag:
            return  # todo: log
        series_id = self.series.id_
        for title in titles_tag.find_all(True, recursive=False):
            lang = self._find_lang(title['xml:lang'])
            anime_title = AnimeTitle(title.string, lang.name, title['type'], series_id)
            if anime_title not in self.series.titles:
                self.series.titles.append(anime_title)

    def _get_episode_attrs(self, episode: Tag) -> Dict:
        # anidb_id, number, length, airdate, rating, parent
        attrs = {
            'anidb_id': int(episode['id']),
            'length': episode.find('length').string if episode.find('length') else None,
        }
        epno = episode.find('epno')
        if epno:
            attrs['number'] = get_list_tag(epno, 'type')
        rating = episode.find('rating')
        if rating:
            attrs['rating'] = get_list_tag(rating, 'votes')
        airdate = episode.find('airdate')
        if airdate:
            attrs['airdate'] = datetime.strptime(
                airdate.string, self.date_format
            ).date()
        return attrs

    def _get_episode_titles(
        self, episode_id: int, episode_titles: List[Tag],
    ) -> List[AnimeEpisodeTitle]:
        titles: List = []
        for title in episode_titles:
            lang = self._find_lang(title['xml:lang'])
            anime_episode_title = AnimeEpisodeTitle(episode_id, title.string, lang.name)
            titles.append(anime_episode_title)
        return titles

    def _find_episode(self, anidb_id: int) -> Optional[AnimeEpisode]:
        return (
            self.session.query(AnimeEpisode)
            .filter(AnimeEpisode.anidb_id == anidb_id)
            .first()
        )

    def _set_episodes2(self, episodes: List[AnidbEpisode]) -> List[AnimeEpisode]:
        set_episodes = []
        for episode in episodes:
            if self._find_episode(episode.anidb_id):
                continue
            set_episodes += [
                AnimeEpisode(
                    anidb_id=episode.anidb_id,
                    length=episode.length,
                    airdate=episode.airdate,
                    number=episode.epno[0],
                    rating=episode.rating[0],
                ),
            ]
        return set_episodes

    def _set_episodes(self, episodes_tag: Tag) -> None:
        if not episodes_tag:
            return
        for episode in episodes_tag.find_all('episode'):
            db_episode = self.session.query(AnimeEpisode)
            db_episode = db_episode.filter(
                AnimeEpisode.anidb_id == episode['id']
            ).first()
            if not db_episode:
                episode_vars = self._get_episode_attrs(episode)
                episode_vars['parent'] = self.series.id_
                db_episode = AnimeEpisode(**episode_vars)
                episode_id = db_episode.id_
                titles = self._get_episode_titles(episode_id, episode.find_all('title'))
                db_episode.titles.extend(titles)
                self.series.episodes.append(db_episode)

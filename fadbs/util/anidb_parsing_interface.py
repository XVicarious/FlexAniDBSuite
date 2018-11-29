import logging
import math
from datetime import datetime
from typing import Type

from flexget import plugin

from .api_anidb import Anime, AnimeEpisode, AnimeEpisodeTitle, AnimeGenre, AnimeGenreAssociation, AnimeLanguage, AnimeTitle
from .anidb_structs import default_tag_blacklist

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
            lang = self._find_lang(title['xml:lang'])
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
                    lang = self._find_lang(episode_title['xml:lang'])
                    anime_episode_title = AnimeEpisodeTitle(episode_id, episode_title['name'], lang.name)
                    db_episode.titles.append(anime_episode_title)
                self.series.episodes.append(db_episode)

    def _recurse_remove_tags(self, tags, tag_id):
        intermediate_tags = [tag_id]
        idx = 0
        while idx < len(tags):
            tmp_tag = tags[idx]
            tmp_tag_id = int(tmp_tag['id'])
            tmp_tag_parent_id = int(tmp_tag['parentid']) if 'parentid' in tmp_tag.attrs else 0
            if tmp_tag_parent_id in intermediate_tags:
                intermediate_tags.append(tmp_tag_id)
                tags.remove(tmp_tag)
                idx = 0
            else:
                idx += 1

    def _remove_blacklist_tags(self, tags):
        temp_tags = tags.copy()
        for tag in temp_tags:
            name = tag.find('name')
            name = name.string if name else ''
            LOG.trace('Checking %s (%s)', name, tag['id'])
            if tag['id'] in default_tag_blacklist:
                LOG.debug('%s (%s) in the blacklist... Taking action.', name, tag['id'])
                if default_tag_blacklist.get(tag['id']):
                    LOG.debug('%s (%s) is set to True... Recursively removing tags.', name, tag['id'])
                    self._recurse_remove_tags(tags, tag['id'])
                tags.remove(tag)

    def _set_tags(self, tags_tags, session):
        if not session:
            return plugin.PluginError('session is None')
        if not tags_tags:
            return plugin.PluginError('tags_tags is None')
        self._remove_blacklist_tags(tags_tags)
        tags_list = sorted(tags_tags, key=lambda tag: tag['parentid'] if 'parentid' in tag.attrs else 0)
        for tag in tags_list:
            name = tag.find('name')
            name = name.string if name else ''
            db_tag = session.query(AnimeGenre).filter(AnimeGenre.anidb_id == int(tag['id'])).first()
            if not db_tag:
                LOG.debug('%s is not in the tag list, adding', name)
                db_tag = AnimeGenre(int(tag['id']), name)
            tag_parent_id = int(tag['parentid']) if 'parentid' in tag.attrs else 0
            if db_tag.parent_id is None and tag_parent_id and tag_parent_id not in default_tag_blacklist.keys():
                parent_tag = session.query(AnimeGenre).filter(AnimeGenre.anidb_id == tag_parent_id).first()
                if parent_tag:
                    db_tag.parent_id = parent_tag.id_
                else:
                    LOG.trace('Genre %s parent genre, %s is not in the database yet. When it is found, it will be added', name, tag_parent_id)
                series_genre = session.query(AnimeGenreAssociation).filter(
                        AnimeGenreAssociation.anidb_id == self.series.id_,
                        AnimeGenreAssociation.genre_id == tag.id_).first()
                if not series_genre:
                    series_genre = AnimeGenreAssociation(genre=tag)
                    self.series.genres.append(series_genre)
                if series_genre != int(tag['weight']):
                    series_genre.genre_weight = int(tag['weight'])

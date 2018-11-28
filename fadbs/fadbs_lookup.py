from __future__ import unicode_literals, division, absolute_import

from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from datetime import datetime
import logging

from flexget import plugin
from flexget.event import event
from flexget.utils.database import with_session
from flexget.utils.log import log_once

from .util.api_anidb import Anime, AnimeGenre, AnimeTitle, AnimeLangauge, AnimeGenreAssociation
from .util.api_anidb import AnimeEpisode, AnimeEpisodeTitle
from .util import AnidbParser, AnidbSearch

PLUGIN_ID = 'fadbs_lookup'

log = logging.getLogger(PLUGIN_ID)


class FadbsLookup(object):
    """Lookup and Return an Anime."""

    @staticmethod
    def _title_dict(series):
        titles = {}
        for title in series.titles:
            if title.ep_type not in titles:
                titles.update({title.ep_type: []})
            titles[title.ep_type].append({
                'lang': title.language,
                'name': title.name,
            })
        return titles

    field_map = {
        'anidb_id': 'anidb_id',
        'anidb_title_main': lambda series: series.title_main,
        'anidb_type': 'series_type',
        'anidb_num_episodes': 'num_episodes',
        'anidb_startdate': 'start_date',
        'anidb_enddate': 'end_date',
        'anidb_titles': lambda series: FadbsLookup._title_dict(series),
        # todo: related anime
        # todo: similar anime
        'anidb_official_url': 'url',
        # todo: creators
        'anidb_description': 'description',
        'anidb_rating': 'permanent_rating',
        'anidb_mean_rating': 'mean_rating',
        'anidb_tags': lambda series: dict(
            (genre.genre.anidb_id, [genre.genre.name, genre.genre_weight]) for genre in series.genres),
        'anidb_episodes': lambda series: dict((episode.anidb_id, episode.number) for episode in series.episodes),
        'anidb_year': 'year',
        'anidb_season': 'season'}

    # todo: implement UDP api to get more info
    # UDP gives us more episode information, I think
    # who knows. They've had 15 years to develop this api
    # and it still doesn't include a ton of things
    episode_map = {
            'anidb_episode_id': 'anidb_id',
            'anidb_episode_number': 'number',
            'anidb_episode_type': 'ep_type',
            'anidb_episode_airdate': 'airdate',
            'anidb_episode_rating': 'rating',
            'anidb_episode_votes': 'votes'}

    # A tag id with True will remove that tag and all decedents, False just removes that tag
    default_tag_blacklist = {
        -1: True,
        30: True,
        2931: True,
        2604: False,
        2605: False,
        6230: False,
        6246: False,
        3683: False,
        2606: False,
        2607: False,
        2608: False,
        2609: False,
        2610: False,
        2612: False,
        2613: False,
        2611: False,
        6151: False,
        6173: False
    }

    schema = {'type': 'boolean'}

    @plugin.priority(130)
    def on_task_metainfo(self, task, config):
        if not config:
            return
        for entry in task.entries:
            log.debug('Looking up: %s', entry.get('title'))
            self.register_lazy_fields(entry)

    @plugin.priority(130)
    def on_task_metainfo2(self, task, config):
        if not config:
            return
        for entry in task.entries:
            if entry.get('series_name') or entry.get('anidb_id', eval_lazy=False):
                # todo: thinking of using "in_" for this.
                pass

    def register_lazy_fields(self, entry):
        entry.register_lazy_func(self.lazy_loader, self.field_map)

    def lazy_loader(self, entry):
        try:
            self.lookup(entry)
        except plugin.PluginError as err:
            log_once(str(err.value).capitalize(), logger=log)

    @property
    def series_identifier(self):
        return 'anidb_id'

    @plugin.internet(log)
    @with_session
    def lookup(self, entry, search_allowed=True, session=None):
        # Try to guarantee we have the AniDB id
        entry_title = entry.get('title', eval_lazy=False)
        if entry.get('anidb_id', eval_lazy=False):
            log.debug('The AniDB id is already there, and it is %s', entry['anidb_id'])
        elif entry.get('series_name', eval_lazy=False) and search_allowed:
            log.debug('No AniDB present, searching by series_name.')
            entry['anidb_id'] = AnidbSearch().by_name(entry['series_name'])
            if not entry['anidb_id']:
                raise plugin.PluginError('The series AniDB id was not found.')
        else:
            raise plugin.PluginError('anidb_id and series_name were not present for {0}.'.format(entry_title))

        series = session.query(Anime).filter(Anime.anidb_id == entry['anidb_id']).first()

        if series and not series.expired:
            log.debug('series exists and it is not expired')  # todo: TEMP
            entry.update_using_map(self.field_map, series)
            return

        if series is not None:
            log.debug('series is not none')  # todo: TEMP
            session.commit()

        # There is a whole part about expired entries here.
        # Possibly increase the default cache time to a week,
        # and let the user set it themselves if they want, to
        # a minimum of 24 hours due to AniDB's policies...

        try:
            series = self._parse_new_series(entry['anidb_id'], session)
        except UnicodeDecodeError:
            log.error('Unable to determine encoding for %s. Try installing chardet', entry['anidb_id'])
            series = Anime()
            series.anidb_id = entry['anidb_id']
            session.add(series)
            session.commit()
            raise plugin.PluginError('Invalid parameter', log)
        except ValueError as valueError:
            raise valueError

        # todo: trace log attributes?

        entry.update_using_map(self.field_map, series)

    def _remove_blacklist(self, genres):
        temp_genres = genres.copy()
        for genre in temp_genres:
            log.trace('Checking %s (%s)', genre['name'], genre['id'])
            if genre['id'] in self.default_tag_blacklist:
                log.debug('%s (%s) is in the blacklist... Taking action.', genre['name'], genre['id'])
                if self.default_tag_blacklist.get(genre['id']):
                    log.debug('%s (%s) is set to true in the blacklist... Purging it\'s decendants.', genre['name'],
                              genre['id'])
                    intermediate_genres = [genre['id']]
                    i = 0
                    while i < len(genres):
                        log.trace('%s of %s', i, len(genres) - 1)
                        if genres[i]['parentid'] in intermediate_genres:
                            log.debug('%s (%s) decends from %s (%s), removing.', genres[i]['name'], genres[i]['id'],
                                      genre['name'], genre['id'])
                            intermediate_genres.append(genres[i]['id'])
                            genres.remove(genres[i])
                            i = 0
                        else:
                            i += 1
                genres.remove(genre)
        return genres

    def _add_genres(self, series, genres, session):
        genres = self._remove_blacklist(genres)
        genres_list = sorted(genres, key=lambda k: k['parentid'])
        for item in genres_list:
            genre = session.query(AnimeGenre).filter(AnimeGenre.anidb_id == item['id']).first()
            if not genre:
                log.debug('%s is not in the genre list, adding', item['name'])
                genre = AnimeGenre(item['id'], item['name'])
            if genre.parent_id is None and item['parentid']:
                parent_genre = session.query(AnimeGenre).filter(AnimeGenre.anidb_id == item['parentid']).first()
                if parent_genre:
                    genre.parent_id = parent_genre.id
                else:
                    log.trace("Genre %s parent genre, %s, is not in the database yet. \
                               When it's found, it will be added", item['name'], item['parentid'])
            series_genre = session.query(AnimeGenreAssociation).filter(
                    AnimeGenreAssociation.anidb_id == series.id_,
                    AnimeGenreAssociation.genre_id == genre.id_).first()
            if not series_genre:
                series_genre = AnimeGenreAssociation(genre=genre, genre_weight=item['weight'])
                series.genres.append(series_genre)
            if series_genre.genre_weight != item['weight']:
                series_genre.genre_weight = item['weight']
        return series

    def _add_episodes(self, series, episodes, session):
        for item in episodes:
            episode = session.query(AnimeEpisode).filter(AnimeEpisode.anidb_id == item['id']).first()
            if not episode:
                rating = [item['rating'], item['votes']]
                number = [item['episode_number'], item['episode_type']]
                episode = AnimeEpisode(item['id'], number, item['length'], item['airdate'], rating, series.id_)
                for item_title in item['titles']:
                    lang = session.query(AnimeLangauge).filter(AnimeLangauge.name == item_title['lang']).first()
                    if not lang:
                        lang = AnimeLangauge(item_title['lang'])
                    episode.titles.append(AnimeEpisodeTitle(episode.id_, item_title['name'], lang.name))
            series.episodes.append(episode)
        return series

    def _add_titles(self, series, titles, session):
        for item in titles:
            lang = session.query(AnimeLangauge).filter(AnimeLangauge.name == item['lang']).first()
            if not lang:
                lang = AnimeLangauge(item['lang'])
            series.titles.append(AnimeTitle(item['name'], lang.name, item['type'], series.id_))
        return series

    def _parse_new_series(self, anidb_id, session):

        def debug_parse(what):
            log.debug('Parsing %s for AniDB %s', what, anidb_id)

        parser = AnidbParser(anidb_id)
        log.verbose('Starting to parse AniDB %s', anidb_id)
        parser.parse()

        log.debug('Parsed AniDB %s', anidb_id)
        log.debug('Populating the Anime')
        series = session.query(Anime).filter(Anime.anidb_id == anidb_id).first()
        if not series:
            series = Anime()
            series.anidb_id = anidb_id
        series.series_type = parser.type
        series.num_episodes = parser.num_episodes
        series.start_date = parser.dates['start']
        series.year = parser.year
        # todo: make this better
        try:
            series.end_date = parser.dates['end']
        except KeyError:
            pass
        # end
        series.url = parser.official_url
        series.description = parser.description
        if parser.ratings:
            permanent_rating = parser.ratings['permanent']
            series.permanent_rating = None if permanent_rating is None else permanent_rating['rating']
            mean_rating = parser.ratings['mean']
            series.mean_rating = None if mean_rating is None else mean_rating['rating']

        debug_parse('genres')
        series = self._add_genres(series, parser.genres, session)

        debug_parse('episodes')
        series = self._add_episodes(series, parser.episodes, session)

        debug_parse('titles')
        series = self._add_titles(series, parser.titles, session)

        series.updated = datetime.utcnow()

        session.add(series)

        return series


@event('plugin.register')
def register_plugin():
    plugin.register(FadbsLookup, PLUGIN_ID, api_ver=2, interfaces=['task', 'series_metainfo', 'movie_metainfo'])

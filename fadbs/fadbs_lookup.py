from __future__ import unicode_literals, division, absolute_import

from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from datetime import datetime

from flexget import db_schema, plugin
from flexget import logging
from flexget.db_schema import UpgradeImpossible
from flexget.event import event
from flexget.utils.database import with_session
from flexget.utils.log import log_once
from sqlalchemy import Table, Column, Integer, Float, String, Unicode, DateTime, Text, Date
from sqlalchemy.orm import relation, relationship
from sqlalchemy.schema import ForeignKey, Index

from .util import AnidbParser, AnidbSearch

SCHEMA_VER = 1

Base = db_schema.versioned_base('fadbs_lookup', SCHEMA_VER)

creators_table = Table('anidb_anime_creators', Base.metadata,
                       Column('anidb_id', Integer, ForeignKey('anidb_series.id')),
                       Column('creator_id', Integer, ForeignKey('anidb_creators.id')),
                       Index('ix_anidb_anime_creators', 'anidb_id', 'creator_id'))
Base.register_table(creators_table)

# characters_table = Table('anidb_anime_characters', Base.metadata,
#                          Column('anidb_id', Integer, ForeignKey('anidb_series.id')),
#                          Column('character_id', Integer, ForeignKey('anidb_characters.id')),
#                          Index('ix_anidb_anime_characters', 'anidb_id', 'character_id'))
# Base.register_table(characters_table)

episodes_table = Table('anidb_anime_episodes', Base.metadata,
                       Column('anidb_id', Integer, ForeignKey('anidb_series.id')),
                       Column('episode_id', Integer, ForeignKey('anidb_episodes.id')),
                       Index('ix_anidb_anime_episodes', 'anidb_id', 'episode_id'))
Base.register_table(episodes_table)

PLUGIN_ID = 'fadbs_lookup'

log = logging.getLogger(PLUGIN_ID)


class AnimeGenreAssociation(Base):
    __tablename__ = 'anidb_genreassociation'

    anidb_id = Column(Integer, ForeignKey('anidb_series.id'), primary_key=True)
    genre_id = Column(Integer, ForeignKey('anidb_genres.id'), primary_key=True)
    genre_weight = Column(Integer)
    genre = relationship("AnimeGenre")


class Anime(Base):
    __tablename__ = 'anidb_series'

    id = Column(Integer, primary_key=True)
    anidb_id = Column(Integer)
    series_type = Column(Unicode)
    num_episodes = Column(Integer)
    start_date = Column(Date)
    end_date = Column(Date)
    titles = relation("AnimeTitle")
    # todo: related anime, many to many?
    # todo: similar anime, many to many?
    url = Column(String)
    creators = relation("AnimeCreator", secondary=creators_table, backref='series')
    description = Column(Text)
    permanent_rating = Column(Float)
    mean_rating = Column(Float)
    genres = relationship("AnimeGenreAssociation")
    # characters = relation('AnimeCharacter', secondary=characters_table, backref='series')
    episodes = relation('AnimeEpisode', secondary=episodes_table, backref='series')
    year = Column(Integer)
    season = Column(String)

    updated = Column(DateTime)

    @property
    def title_main(self):
        for title in self.titles:
            if title.ep_type == 'main':
                return title.name

    @property
    def expired(self):
        if self.updated is None:
            log.debug("updated is None: %s", self)
            return True
        tdelta = datetime.utcnow() - self.updated
        if tdelta.total_seconds() >= AnidbParser.RESOURCE_MIN_CACHE:
            return True
        log.info('This entry will expire in: %s seconds', AnidbParser.RESOURCE_MIN_CACHE - tdelta.total_seconds())
        return False

    def __repr__(self):
        return '<Anime(name=%s,type=%s,year=%s)>' % (self.titles, self.series_type, 0)


class AnimeGenre(Base):
    __tablename__ = 'anidb_genres'

    id = Column(Integer, primary_key=True)
    anidb_id = Column(Integer, unique=True)
    parent_id = Column(Integer, ForeignKey('anidb_genres.id'))
    name = Column(String)

    def __init__(self, anidb_id, name):
        self.anidb_id = anidb_id
        self.name = name
        self.parent_id = None


class AnimeCreator(Base):
    __tablename__ = 'anidb_creators'

    id = Column(Integer, primary_key=True)
    anidb_id = Column(Integer)
    creator_type = Column(Unicode)
    name = Column(Unicode)

    def __init__(self, anidb_id, creator_type, name):
        self.anidb_id = anidb_id
        self.creator_type = creator_type
        self.name = name


class AnimeTitle(Base):
    __tablename__ = 'anidb_titles'

    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey('anidb_series.id'))
    name = Column(Unicode)
    language = Column(Unicode, ForeignKey('anidb_languages.name'))
    ep_type = Column(Unicode)

    def __init__(self, name, language, ep_type, parent):
        self.name = name
        self.language = language
        self.ep_type = ep_type
        self.parent_id = parent


class AnimeLangauge(Base):
    __tablename__ = 'anidb_languages'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode)

    def __init__(self, language):
        self.name = language


class AnimeEpisode(Base):
    __tablename__ = 'anidb_episodes'

    id = Column(Integer, primary_key=True)
    anidb_id = Column(Integer)
    parent_id = Column(Integer, ForeignKey('anidb_series.id'))
    number = Column(Unicode)
    ep_type = Column(String)
    length = Column(Integer)
    airdate = Column(Date)
    rating = Column(Float)
    votes = Column(Integer)
    titles = relation('AnimeEpisodeTitle')

    def __init__(self, anidb_id, number, length, airdate, rating, parent):
        self.anidb_id = anidb_id
        self.number = number[0]
        self.ep_type = number[1]
        self.length = length
        self.airdate = airdate
        self.rating = rating[0]
        self.votes = rating[1]
        self.parent_id = parent


class AnimeEpisodeTitle(Base):
    __tablename__ = 'anidb_episodetitles'

    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey('anidb_episodes.id'))
    title = Column(Unicode)
    language = Column(Unicode, ForeignKey('anidb_languages.name'))

    def __init__(self, parent_id, title, langauge):
        self.parent_id = parent_id
        self.title = title
        self.language = langauge


@db_schema.upgrade('fadbs_lookup')
def upgrade(ver, session):
    if ver is None:
        raise UpgradeImpossible('Resetting %s caches because bad data may have been cached.' % PLUGIN_ID)
    return ver


class FadbsLookup(object):

    @staticmethod
    def _title_dict(series):
        titles = {}
        for title in series.titles:
            if title.ep_type not in titles:
                titles.update({title.ep_type: []})
            titles[title.ep_type].append({
                'lang': title.language,
                'name': title.name
            })
        return titles

    field_map = {
        'anidb_id': 'anidb_id',
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
        entry_title_extension = entry_title[-4:]
        if entry.get('anidb_id', eval_lazy=False):
            log.debug('The AniDB id is already there, and it is %s', entry['anidb_id'])
        elif entry.get('series_name', eval_lazy=False) and search_allowed:
            log.debug('No AniDB present, searching by series_name.')
            entry['anidb_id'] = AnidbSearch().by_name(entry['series_name'])
            if not entry['anidb_id']:
                raise plugin.PluginError('The series AniDB id was not found.')
        elif entry_title and entry_title_extension != '.mkv' and entry_title_extension != '.mp4':
            log.debug('No AniDB id, no series_name... Attempting title (not promising anything)')
            entry['anidb_id'] = AnidbSearch().by_name(entry['title'])
            if not entry['anidb_id']:
                raise plugin.PluginError('The series AniDB id was not found :(.')
        else:
            raise plugin.PluginError('anidb_id and series_name were not present.')

        series = session.query(Anime).filter(Anime.anidb_id == entry['anidb_id']).first()

        if series and not series.expired:
            entry.update_using_map(self.field_map, series)
            return

        if series is not None:
            session.commit()

        # There is a whole part about expired entries here.
        # Possibly increase the default cache time to a week,
        # and let the user set it themselves if they want, to
        # a minimum of 24 hours due to AniDB's policies...

        try:
            series = self.__parse_new_series(entry['anidb_id'], session)
        except UnicodeDecodeError:
            log.error('Unable to determine encoding for %s. Try installing chardet', entry['anidb_id'])
            series = Anime()
            series.anidb_id = entry['anidb_id']
            session.add(series)
            session.commit()
            raise plugin.PluginError('Invalid parameter', log)
        except ValueError:
            raise plugin.PluginError('invalid parameter', log)

        # todo: trace log attributes?

        entry.update_using_map(self.field_map, series)

    @staticmethod
    def __query_and_filter(session, what, sql_filter):
        return session.query(what).filter(sql_filter)

    def __remove_blacklist(self, genres):
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

    def __add_genres(self, series, genres, session):
        genres = self.__remove_blacklist(genres)
        genres_list = sorted(genres, key=lambda k: k['parentid'])
        for item in genres_list:
            genre = self.__query_and_filter(session, AnimeGenre, AnimeGenre.anidb_id == item['id']).first()
            if not genre:
                log.debug('%s is not in the genre list, adding', item['name'])
                genre = AnimeGenre(item['id'], item['name'])
            if genre.parent_id is None and item['parentid']:
                parent_genre = \
                    self.__query_and_filter(session, AnimeGenre, AnimeGenre.anidb_id == item['parentid']).first()
                if parent_genre:
                    genre.parent_id = parent_genre.id
                else:
                    log.trace("Genre %s parent genre, %s, is not in the database yet. \
                               When it's found, it will be added", item['name'], item['parentid'])
            series_genre = AnimeGenreAssociation(genre=genre, genre_weight=item['weight'])
            series.genres.append(series_genre)
        return series

    def __add_episodes(self, series, episodes, session):
        for item in episodes:
            episode = self.__query_and_filter(session, AnimeEpisode, AnimeEpisode.anidb_id == item['id']).first()
            if not episode:
                rating = [item['rating'], item['votes']]
                number = [item['episode_number'], item['episode_type']]
                episode = AnimeEpisode(item['id'], number, item['length'], item['airdate'], rating, series.id)
                for item_title in item['titles']:
                    lang = self.__query_and_filter(session, AnimeLangauge,
                                                   AnimeLangauge.name == item_title['lang']).first()
                    if not lang:
                        lang = AnimeLangauge(item_title['lang'])
                    episode.titles.append(AnimeEpisodeTitle(episode.id, item_title['name'], lang.name))
            series.episodes.append(episode)
        return series

    def __add_titles(self, series, titles, session):
        for item in titles:
            lang = session.query(AnimeLangauge).filter(AnimeLangauge.name == item['lang']).first()
            if not lang:
                lang = AnimeLangauge(item['lang'])
            series.titles.append(AnimeTitle(item['name'], lang.name, item['type'], series.id))
        return series

    def __parse_new_series(self, anidb_id, session):

        def __debug_parse(what):
            log.debug('Parsing %s for AniDB %s', what, anidb_id)

        parser = AnidbParser(anidb_id)
        log.verbose('Starting to parse AniDB %s', anidb_id)
        parser.parse()

        log.debug('Parsed AniDB %s', anidb_id)
        log.debug('Populating the Anime')
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

        __debug_parse('genres')
        series = self.__add_genres(series, parser.genres, session)

        __debug_parse('episodes')
        series = self.__add_episodes(series, parser.episodes, session)

        __debug_parse('titles')
        series = self.__add_titles(series, parser.titles, session)

        series.updated = datetime.utcnow()

        session.add(series)

        return series


@event('plugin.register')
def register_plugin():
    plugin.register(FadbsLookup, PLUGIN_ID, api_ver=2, interfaces=['task', 'series_metainfo', 'movie_metainfo'])

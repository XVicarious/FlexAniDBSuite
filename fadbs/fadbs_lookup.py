from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
from datetime import datetime

from sqlalchemy import Table, Column, Integer, Float, String, Unicode, Boolean, DateTime, Text, Date
from sqlalchemy.schema import ForeignKey, Index
from sqlalchemy.orm import relation

from flexget import db_schema, plugin
from flexget.db_schema import UpgradeImpossible
from flexget.event import event
from flexget.entry import Entry
from flexget.utils.log import log_once
from flexget.utils.database import with_session

from fadbs.util import AnidbParser, AnidbSearch

SCHEMA_VER = 1

Base = db_schema.versioned_base('anidb_lookup', SCHEMA_VER)

genres_table = Table('anidb_anime_genres', Base.metadata,
                     Column('anidb_id', Integer, ForeignKey('anidb_series.id')),
                     Column('genre_id', Integer, ForeignKey('anidb_genres.id')),
                     Index('ix_anidb_anime_genres', 'anidb_id', 'genre_id'))
Base.register_table(genres_table)

creators_table = Table('anidb_anime_creators', Base.metadata,
                       Column('anidb_id', Integer, ForeignKey('anidb_series.id')),
                       Column('creator_id', Integer, ForeignKey('anidb_creators.id')),
                       Index('ix_anidb_anime_creators', 'anidb_id', 'creator_id'))
Base.register_table(creators_table)

#characters_table = Table('anidb_anime_characters', Base.metadata,
#                         Column('anidb_id', Integer, ForeignKey('anidb_series.id')),
#                         Column('character_id', Integer, ForeignKey('anidb_characters.id')),
#                         Index('ix_anidb_anime_characters', 'anidb_id', 'character_id'))
#Base.register_table(characters_table)

episodes_table = Table('anidb_anime_episodes', Base.metadata,
                       Column('anidb_id', Integer, ForeignKey('anidb_series.id')),
                       Column('episode_id', Integer, ForeignKey('anidb_episodes.id')),
                       Index('ix_anidb_anime_episodes', 'anidb_id', 'episode_id'))
Base.register_table(episodes_table)


PLUGIN_ID = 'fadbs_lookup'

log = logging.getLogger(PLUGIN_ID)


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
    genres = relation('AnimeGenre', secondary=genres_table, backref='series')
    #characters = relation('AnimeCharacter', secondary=characters_table, backref='series')
    episodes = relation('AnimeEpisode', secondary=episodes_table, backref='series')

    updated = Column(DateTime)

    @property
    def expired(self):
        log.debug(type(self.updated))
        if self.updated is None:
            log.debug("updated is None: %s", self)
            return True
        tdelta = datetime.utcnow() - self.updated.python_type.astimezone()
        if tdelta.total_seconds() >= AnidbParser.RESOURCE_MIN_CACHE:
            return True
        log.info('This entry will expire in: %s seconds', AnidbParser.RESOURCE_MIN_CACHE - tdelta.total_seconds())
        return False

    def __repr__(self):
        return '<Anime(name=%s,type=%s,year=%s)>' % (self.titles, self.series_type, 0)


class AnimeGenre(Base):
    __tablename__ = 'anidb_genres'

    id = Column(Integer, primary_key=True)
    anidb_id = Column(Integer)
    parent_id = Column(Integer, ForeignKey('anidb_genres.id'))
    name = Column(String)
    weight = Column(Integer)
    local_spoiler = Column(Boolean)
    global_spoiler = Column(Boolean)
    verified = Column(Boolean)

    def __init__(self, anidb_id, name, weight, local_spoiler, global_spoiler, verified):
        self.anidb_id = anidb_id
        self.name = name
        self.weight = weight
        self.local_spoiler = local_spoiler
        self.global_spoiler = global_spoiler
        self.verified = verified


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

    def __init__(self, name, language, ep_type):
        self.name = name
        self.language = language
        self.ep_type = ep_type


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

    def __init__(self, anidb_id, number, ep_type, length, airdate, rating, votes):
        self.anidb_id = anidb_id
        self.number = number
        self.ep_type = ep_type
        self.length = length
        self.airdate = airdate
        self.rating = rating
        self.votes = votes


class AnimeEpisodeTitle(Base):
    __tablename__ = 'anidb_episodetitles'

    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey('anidb_episodes.id'))
    title = Column(Unicode)
    language = Column(Unicode, ForeignKey('anidb_languages.name'))

    def __init__(self, title, langauge):
        self.title = title
        self.language = langauge


@db_schema.upgrade('fadbs_lookup')
def upgrade(ver, session):
    if ver is None:
        raise UpgradeImpossible('Resetting %s caches because bad data may have been cached.' % PLUGIN_ID)
    return ver


class FadbsLookup(object):

    field_map = {
        'anidb_titles': lambda series: [title.name for title in series.titles],
        'anidb_type': 'series_type',
        'anidb_num_episodes': 'num_episodes',
        'anidb_rating': 'permanent_rating',
        'anidb_mean_rating': 'mean_rating',
        'anidb_official_url': 'url',
        'anidb_startdate': 'start_date',
        'anidb_enddate': 'end_date',
        'anidb_description': 'description',
        'anidb_tags': lambda series: dict((genre.anidb_id, genre.name) for genre in series.genres),
        'anidb_episodes': lambda series: dict((episode.anidb_id, episode.number) for episode in series.episodes)
    }

    schema = {'type': 'boolean'}

    @plugin.priority(130)
    def on_task_metainfo(self, task, config):
        if not config:
            return
        for entry in task.entries:
            log.debug(entry)
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

        from flexget import manager

        # Try to guarantee we have the AniDB id
        if entry.get('anidb_id', eval_lazy=False):
            log.debug("One less request... adbid: %s", entry['anidb_id'])
        elif entry.get('title', eval_lazy=False):
            log.debug('We need to find that id, lets give it a search...')
            searcher = AnidbSearch()
            entry['anidb_id'] = searcher.by_name_exact(entry['title'])
        else:
            raise plugin.PluginError("Oh no, we didn't do it :(")

        series = session.query(Anime).filter(Anime.anidb_id == entry['anidb_id']).first()

        if series and not series.expired:
            entry.update_using_map(self.field_map, series)
            return

        # There is a whole part about expired entries here.
        # Possibly increase the default cache time to a week,
        # and let the user set it themselves if they want, to
        # a minimum of 24 hours due to AniDB's policies...

        try:
            series = self.__parse_new_series(entry['anidb_id'], session)
        except UnicodeDecodeError:
            log.error('Unable to determine encoding for %s. Something something chardet', entry['anidb_id'])
            series = Anime()
            series.anidb_id = entry['anidb_id']
            session.add(series)
            session.commit()
            raise plugin.PluginError('Invalid parameter', log)
        except ValueError as err:
            if manager.options.debug:
                log.exception(err)
            raise plugin.PluginError('invalid parameter', log)

        # todo: trace log attributes?

        entry.update_using_map(self.field_map, series)

    @staticmethod
    def __parse_new_series(anidb_id, session):
        parser = AnidbParser()
        parser.parse(anidb_id)
        series = Anime()
        series.series_type = parser.type
        series.num_episodes = parser.num_episodes
        series.start_date = parser.dates['start']
        series.end_date = parser.dates['end']
        series.url = parser.official_url
        series.description = parser.description
        series.permanent_rating = parser.ratings['permanent']['rating']
        series.mean_rating = parser.ratings['mean']['rating']
        genres_list = sorted(parser.genres, key=lambda k: k['parentid'])
        for item in genres_list:
            genre = session.query(AnimeGenre).filter(AnimeGenre.anidb_id == item['id']).first()
            if not genre:
                genre = AnimeGenre(item['id'], item['name'], item['weight'],
                                   item['localspoiler'], item['globalspoiler'], item['verified'])
            series.genres.append(genre)
        for item in parser.episodes:
            episode = session.query(AnimeEpisode).filter(AnimeEpisode.anidb_id == item['id']).first()
            if not episode:
                episode = AnimeEpisode(item['id'], item['episode_number'], item['episode_type'],
                                       item['length'], item['airdate'], item['rating'], item['votes'])
                log.debug("aid:%s, episode: %s", anidb_id, item)
                for item_title in item['titles']:
                    lang = session.query(AnimeLangauge).filter(AnimeLangauge.name == item_title['lang'])
                    if not lang:
                        lang = AnimeLangauge(item_title['lang'])
                    episode.titles.append(AnimeEpisodeTitle(item_title['name'], lang))
            series.episodes.append(episode)
        for item in parser.titles:
            lang = session.query(AnimeLangauge).filter(AnimeLangauge.name == item['lang'])
            if not lang:
                lang = AnimeLangauge(item['lang'])
            series.titles.append(AnimeTitle(item['name'], lang, item['type']))
        series.updated = datetime.utcnow()
        session.add(series)
        return series


@event('plugin.register')
def register_plugin():
    plugin.register(FadbsLookup, PLUGIN_ID, api_ver=2, interfaces=['task', 'series_metainfo', 'movie_metainfo'])

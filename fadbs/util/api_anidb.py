""" AniDB Database Table Things """
from __future__ import unicode_literals, division, absolute_import
import logging
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from sqlalchemy import Table, Column, Integer, Float, String, Unicode, DateTime, Text, Date
from sqlalchemy.orm import relation, relationship
from sqlalchemy.schema import ForeignKey, Index
from flexget import db_schema
from datetime import datetime
from flexget.db_schema import UpgradeImpossible
from .anidb_parse import AnidbParser


SCHEMA_VER = 1

Base = db_schema.versioned_base('api_anidb', SCHEMA_VER)


def _table_master(table_name, index_table_name, left_id, right_id):
    return Table(table_name, Base.metadata,
                 Column(left_id[0], ForeignKey(left_id[1])),
                 Column(right_id[0], ForeignKey(right_id[1])),
                 Index(index_table_name, left_id[0], right_id[0]))


#creators_table = _table_master('anidb_anime_creators', 'ix_anidb_anime_creators',
#                               ['anidb_series_id', 'anidb_series.id'], ['creator_id', 'anidb_creators.id'])
#Base.register_table(creators_table)
#
#creator_job_table = _table_master('anidb_creator_jobs', 'ix_anidb_creator_jobs',
#                                  ['creator_id', 'anidb_creators.id'], ['job_id', 'anidb_genres.id'])
#Base.register_table(creator_job_table)

# characters_table = Table('anidb_anime_characters', Base.metadata,
#                          Column('anidb_id', Integer, ForeignKey('anidb_series.id')),
#                          Column('character_id', Integer, ForeignKey('anidb_characters.id')),
#                          Index('ix_anidb_anime_characters', 'anidb_id', 'character_id'))
# Base.register_table(characters_table)

episodes_table = _table_master('anidb_anime_episodes', 'ix_anidb_anime_episodes',
                               ['anidb_series_id', 'anidb_series.id'], ['episode_id', 'anidb_episodes.id'])
Base.register_table(episodes_table)

PLUGIN_ID = 'api_anidb'

log = logging.getLogger(PLUGIN_ID)


class Anime(Base):
    """ Define an Anime from AniDB """
    __tablename__ = 'anidb_series'

    id = Column(Integer, primary_key=True)
    anidb_id = Column(Integer, unique=True)
    series_type = Column(Unicode)
    num_episodes = Column(Integer)
    start_date = Column(Date)
    end_date = Column(Date)
    titles = relation("AnimeTitle")
    # todo: related = relationship('AnimeRelatedAssociation')
    # todo: similar anime, many to many?
    url = Column(String)
    creators = relationship('AnimeCreatorAssociation')
    description = Column(Text)
    permanent_rating = Column(Float)
    mean_rating = Column(Float)
    genres = relationship('AnimeGenreAssociation')
    # characters = relation('AnimeCharacter', secondary=characters_table, backref='series')
    episodes = relation('AnimeEpisode', secondary=episodes_table, backref='series')
    year = Column(Integer)
    season = Column(String)

    updated = Column(DateTime)

    @property
    def title_main(self):
        """ Title Considered the "Main" Title on AniDB """
        for title in self.titles:
            if title.ep_type == 'main':
                return title.name

    @property
    def expired(self):
        """ AniDB Allows us to grab an entry once every 24 hours, lets stick to that """
        if self.updated is None:
            log.debug("updated is None: %s", self)
            return True
        tdelta = datetime.utcnow() - self.updated
        if tdelta.total_seconds() >= AnidbParser.RESOURCE_MIN_CACHE:
            return True
        log.info('This entry will expire in: %s seconds', AnidbParser.RESOURCE_MIN_CACHE - tdelta.total_seconds())
        return False

    def __repr__(self):
        return '<Anime(name=%s,type=%s,year=%s)>' % (self.title_main, self.series_type, 0)


class AnimeGenreAssociation(Base):
    """ Information pertaining to genres to specific series """
    __tablename__ = 'anidb_genreassociation'

    anidb_id = Column(Integer, ForeignKey('anidb_series.id'), primary_key=True)
    genre_id = Column(Integer, ForeignKey('anidb_genres.id'), primary_key=True)
    genre_weight = Column(Integer)
    genre = relationship("AnimeGenre")


#class AnimeRelatedAssociation(Base):
#    """ Information pertaining to related anime """
#    __tablename__ = 'anidb_animerelatedassociation'
#
#    from_id = Column(Integer, ForeignKey('anidb_series.id'), primary_key=True)
#    to_id = Column(Integer, ForeignKey('anidb_series.id'), primary_key=True)
#    relation_type = Column(Unicode)


class AnimeGenre(Base):
    """ Define a Genre/Tag from AniDB """
    __tablename__ = 'anidb_genres'

    id = Column(Integer, primary_key=True)
    anidb_id = Column(Integer, unique=True)
    parent_id = Column(Integer, ForeignKey('anidb_genres.id'))
    name = Column(String)

    def __init__(self, anidb_id, name):
        self.anidb_id = anidb_id
        self.name = name
        self.parent_id = None


class AnimeCreatorAssociation(Base):
    """ Connecting creators to Anime and their jobs """
    __tablename__ = 'anidb_creatorassociation'

    series_id = Column(Integer, ForeignKey('anidb_series.id'), primary_key=True)
    creator_id = Column(Integer, ForeignKey('anidb_creators.id'), primary_key=True)
    series_job = Column(Integer, ForeignKey('anidb_genres.id'))
    character = Column(Integer, ForeignKey('anidb_characters.id'))


class AnimeCreator(Base):
    """ Creators, includes writers, original authors, and seiyuus """
    __tablename__ = 'anidb_creators'

    id = Column(Integer, primary_key=True)
    anidb_id = Column(Integer, unique=True)
    anime_association = relationship('AnimeCreatorAssociation')
    # todo: actual "type", UDP api "type" 1='person', 2='company', 3='collaboration'
    name = Column(Unicode)
    jp_name = Column(Unicode)

    def __init__(self, anidb_id, creator_type, name):
        self.anidb_id = anidb_id
        self.creator_type = creator_type
        self.name = name


class AnimeCharacter(Base):
    """ Characters in Anime """
    __tablename__ = 'anidb_characters'

    id = Column(Integer, primary_key=True)
    anidb_id = Column(Integer, unique=True)
    jp_name = Column(Unicode)
    main_name = Column(Unicode)
    # todo: character type indicies are "subject to changes"
    # todo: character gender indicies are "subject to changes"
    # todo: mapping of characters to animes
    # todo: mapping of characters to episodes

    def __init__(self, anidb_id, names):
        self.anidb_id = anidb_id
        self.jp_name = names['official']
        self.main_name = names['main']


class AnimeTitle(Base):
    """ Titles of Anime """
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
    """ Language names for anime (ex: jp, en, x-jat) """
    __tablename__ = 'anidb_languages'

    id = Column(Integer, primary_key=True)
    name = Column(Unicode)

    def __init__(self, language):
        self.name = language


class AnimeEpisode(Base):
    """ Individual episodes of an anime """
    __tablename__ = 'anidb_episodes'

    id = Column(Integer, primary_key=True)
    anidb_id = Column(Integer, unique=True)
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
    """ Titles for Individual anime episodes """
    __tablename__ = 'anidb_episodetitles'

    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey('anidb_episodes.id'))
    title = Column(Unicode)
    language = Column(Unicode, ForeignKey('anidb_languages.name'))

    def __init__(self, parent_id, title, langauge):
        self.parent_id = parent_id
        self.title = title
        self.language = langauge


@db_schema.upgrade('api_anidb')
def upgrade(ver, session):
    """ Upgrade the database when something has changed """
    if ver is None:
        raise UpgradeImpossible('Resetting %s caches because bad data may have been cached.' % PLUGIN_ID)
    return ver

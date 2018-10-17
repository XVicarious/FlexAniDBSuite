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

from fadbs.util import AnidbParser


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

characters_table = Table('anidb_anime_characters', Base.metadata,
                         Column('anidb_id', Integer, ForeignKey('anidb_series.id')),
                         Column('character_id', Integer, ForeignKey('anidb_characters.id')),
                         Index('ix_anidb_anime_characters', 'anidb_id', 'character_id'))
Base.register_table(characters_table)

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
    title = relation("AnimeTitle")
    # todo: related anime, many to many?
    # todo: similar anime, many to many?
    url = Column(String)
    creators = relation("AnimeCreators", secondary=creators_table, backref='series')
    description = Column(Text)
    permanent_rating = Column(Float)
    mean_rating = Column(Float)
    genres = relation('AnimeGenre', secondary=genres_table, backref='series')
    characters = relation('AnimeCharacters', secondary=characters_table, backref='series')
    episodes = relation('AnimeEpisodes', secondary=episodes_table, backref='series')

    updated = Column(DateTime)

    @property
    def expired(self):
        log.debug(type(self.updated))
        if self.updated is None:
            log.debug("updated is None: %s", self)
            return True
        tdelta = datetime.utcnow() - self.updated.python_type.astimezone()
        if tdelta.total_seconds() >= 24 * 60 * 60:
            return True
        log.info('This entry will expire in: %s seconds', 24 * 60 * 60 - tdelta.total_seconds())
        return False


class AnimeGenres(Base):
    __tablename__ = 'anidb_genres'

    id = Column(Integer, primary_key=True)
    anidb_id = Column(Integer)
    parent_id = Column(Integer, ForeignKey('anidb_genres.id'))
    name = Column(String)
    weight = Column(Integer)
    local_spoiler = Column(Boolean)
    global_spoiler = Column(Boolean)
    verified = Column(Boolean)


class AnimeCreators(Base):
    __tablename__ = 'anidb_creators'

    id = Column(Integer, primary_key=True)
    anidb_id = Column(Integer)
    creator_type = Column(Unicode)
    name = Column(Unicode)


class AnimeTitle(Base):
    __tablename__ = 'anidb_titles'

    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey('anidb_series.id'))
    title = Column(Unicode)
    language = Column(Unicode, ForeignKey('anidb_languages.language'))
    type = Column(Unicode)


class AnimeLangauges(Base):
    __tablename__ = 'anidb_languages'

    id = Column(Integer, primary_key=True)
    language = Column(Unicode)

    def __init__(self, language):
        self.language = language


class AnimeEpisodes(Base):
    __tablename__ = 'anidb_episodes'

    id = Column(Integer, primary_key=True)
    anidb_id = Column(Integer)
    parent_id = Column(Integer, ForeignKey('anidb_series.id'))
    # todo: Episode Number, and type... Strip the type from the number since we already have type?
    length = Column(Integer)
    airdate = Column(Date)
    rating = Column(Float)
    votes = Column(Integer)
    title = relation('AnimeEpisodeTitles')


class AnimeEpisodeTitles(Base):
    __tablename__ = 'anidb_episodetitles'

    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey('anidb_episodes.id'))
    title = Column(Unicode)
    language = Column(Unicode, ForeignKey('anidb_languages.language'))


class FadbsLookup(object):

    schema = {
        'type': 'object',
        'properties': {
            'name_language': {
                'type': 'string',
                'default': 'x-jat'
            },
            'ratings': {
                'type': 'string',
                'enum': ['permanent', 'mean'],
                'default': 'permanent'
            },
            'min_tag_weight': {
                'type': 'integer',
                'enum': [0, 100, 200, 300, 400, 500, 600],
                'default': 300
            }
        },
        'additionalProperties': False
    }

    def __init__(self):
        pass

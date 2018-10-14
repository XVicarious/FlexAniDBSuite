from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging
from datetime import datetime, timedelta

from sqlalchemy import Table, Column, Integer, Float, String, Unicode, Boolean, DateTime, Text, Date
from sqlalchemy.schema import ForeignKey, Index
from sqlalchemy.orm import relation

from flexget import db_schema, plugin
from flexget.db_schema import UpgradeImpossible
from flexget.event import event
from flexget.entry import Entry
from flexget.utils.log import log_once
from flexget.utils.database import with_session

from .anidb import AnidbParser


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


PLUGIN_ID = 'fadbs_lookup'

log = logging.getLogger(PLUGIN_ID)


class Anime(Base):
    __tablename__ = 'anidb_series'

    id = Column(Integer, primary_key=True)
    series_type = Column(Unicode)
    num_episodes = Column(Integer)
    start_date = Column(Date)
    end_date = Column(Date)
    title = relation("AnimeTitle")
    # todo: related anime
    # todo: similar anime
    url = Column(String)
    creators = relation("AnimeCreators")  # todo: add secondary, backref
    description = Column(Text)
    permanent_rating = Column(Float)
    mean_rating = Column(Float)
    genres = relation('AnimeGenre', secondary=genres_table, backref='series')
    characters = relation('AnimeCharacters')  # todo: add secondary, backref
    episodes = relation('AnimeEpisodes')  # todo: add secondary, backref

    updated = Column(DateTime)


class AnimeGenres(Base):
    __tablename__ = 'anidb_genres'

    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey('anidb_genres.id'))
    name = Column(String)
    weight = Column(Integer)
    local_spoiler = Column(Boolean)
    global_spoiler = Column(Boolean)
    verified = Column(Boolean)


class AnimeEpisodeTitles(Base):
    __tablename__ = 'anidb_episodenames'

    id = Column(Integer, primary_key=True)
    title = Column(Unicode)
    langauge = relation('AnimeTitleLangauges')


class AnimeEpisodes(Base):
    __tablename__ = 'anidb_episodes'

    id = Column(Integer, primary_key=True)
    episode_number = Column(String)
    episode_type = Column(String)
    length = Column(Integer)
    airdate = Column(Date)
    rating = Column(Float)
    votes = Column(Integer)
    title = Column(Unicode, ForeignKey('anidb_languages.language'))


class AnimeCreators(Base):
    __tablename__ = 'anidb_creators'

    id = Column(Integer, primary_key=True)
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

"""AniDB Database Table Things."""
import logging
from datetime import date, datetime, timedelta

from flexget import db_schema
from flexget.components.parsing.parsers.parser_common import remove_dirt
from flexget.db_schema import Meta, UpgradeImpossible, versioned_base
from sqlalchemy import Column, Date, DateTime, Float, Integer, String, Table, Text, Unicode
from sqlalchemy.orm import relation, relationship
from sqlalchemy.schema import ForeignKey, Index

from .config import CONFIG
from .utils import Season, get_anime_season

SCHEMA_VER = 1

Base: Meta = versioned_base('api_anidb', SCHEMA_VER)


def _table_master(table_name, index_table_name, left_id, right_id):
    return Table(table_name, Base.metadata,
                 Column(left_id[0], ForeignKey(left_id[1])),
                 Column(right_id[0], ForeignKey(right_id[1])),
                 Index(index_table_name, left_id[0], right_id[0]))


episodes_table = _table_master('anidb_anime_episodes', 'ix_anidb_anime_episodes',
                               ['anidb_series_id', 'anidb_series.id'], ['episode_id', 'anidb_episodes.id'])
Base.register_table(episodes_table)

PLUGIN_ID = 'api_anidb'

log = logging.getLogger(PLUGIN_ID)


class Anime(Base):
    """Define an Anime from AniDB."""

    __tablename__ = 'anidb_series'

    id_ = Column('id', Integer, primary_key=True)
    anidb_id = Column(Integer, unique=True)
    series_type = Column(Unicode)
    num_episodes = Column(Integer)
    start_date: date = Column(Date)
    end_date: date = Column(Date)
    titles = relationship('AnimeTitle', backref='anidb_series')
    # todo: related = relationship('AnimeRelatedAssociation')
    # todo: similar anime, many to many?
    url = Column(String)
    creators = relationship('AnimeCreatorAssociation')
    description = Column(Text)
    permanent_rating = Column(Float)
    mean_rating = Column(Float)
    genres = relationship('AnimeGenreAssociation', back_populates='anime')
    # characters = relation('AnimeCharacter', secondary=characters_table, backref='series')
    episodes = relation('AnimeEpisode', secondary=episodes_table, backref='anidb_series')
    _year = Column('year', Integer)
    _season = Column('season', String)

    updated = Column(DateTime)

    @property
    def title_main(self):
        """Title Considered the "Main" Title on AniDB."""
        for title in self.titles:
            if title.ep_type == 'main':
                return title.name

    @property
    def clean_title_main(self):
        """Title cleaned for use as a series name."""
        return remove_dirt(self.title_main)

    @property
    def expired(self) -> bool:
        """Check if we can download a new cache from AniDB, 24 hour hard limit."""
        if self.updated is None:
            return True
        tdelta = datetime.utcnow() - self.updated
        if tdelta >= timedelta(1) and CONFIG.can_request():
            return True
        log.debug('This entry will expire in: %s seconds', timedelta(1) - tdelta)
        return False

    @property
    def year(self) -> int:
        """Return the year that the anime first aired."""
        return self.start_date.year

    @property
    def season(self) -> Season:
        """Return season that the anime first aired."""
        return get_anime_season(self.start_date.month)

    def __repr__(self):
        return '<Anime(name={0},aid={1})>'.format(self.title_main, self.anidb_id)


class AnimeGenreAssociation(Base):
    """Information pertaining to genres to specific series."""

    __tablename__ = 'anidb_genreassociation'

    anime_id = Column(Integer, ForeignKey('anidb_series.id'), primary_key=True)
    genre_id = Column(Integer, ForeignKey('anidb_genres.id'), primary_key=True)

    weight = Column(Integer)
    genre = relationship('AnimeGenre', back_populates='anime')
    anime = relationship('Anime', back_populates='genres')

    def __init__(self, genre, weight):
        self.genre = genre
        self.weight = weight


class AnimeGenre(Base):
    """Define a Genre/Tag from AniDB."""

    __tablename__ = 'anidb_genres'

    id_ = Column('id', Integer, primary_key=True)
    anidb_id = Column(Integer, unique=True)
    name = Column(String)
    anime = relationship('AnimeGenreAssociation', back_populates='genre')
    children = relationship('AnimeGenre')
    parent_id = Column(Integer, ForeignKey('anidb_genres.anidb_id'))

    def __init__(self, anidb_id, name):
        self.anidb_id = anidb_id
        self.name = name


class AnimeCreatorAssociation(Base):
    """Connecting creators to Anime and their jobs."""

    __tablename__ = 'anidb_creatorassociation'

    series_id = Column(Integer, ForeignKey('anidb_series.id'), primary_key=True)
    creator_id = Column(Integer, ForeignKey('anidb_creators.id'), primary_key=True)
    series_job = Column(Integer, ForeignKey('anidb_genres.id'))
    character = Column(Integer, ForeignKey('anidb_characters.id'))


class AnimeCreator(Base):
    """Creators, includes writers, original authors, and seiyuus."""

    __tablename__ = 'anidb_creators'

    id_ = Column('id', Integer, primary_key=True)
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
    """Characters in Anime."""

    __tablename__ = 'anidb_characters'

    id_ = Column('id', Integer, primary_key=True)
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
    """Titles of Anime."""

    __tablename__ = 'anidb_titles'

    id_ = Column('id', Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey('anidb_series.id'))
    name = Column(Unicode)
    language = Column(Unicode, ForeignKey('anidb_languages.name'))
    ep_type = Column(Unicode)

    def __init__(self, name, language, ep_type, parent):
        self.name = name
        self.language = language
        self.ep_type = ep_type
        self.parent_id = parent

    def __eq__(self, other):
        return (self.parent_id == other.parent_id and
                self.language == other.language and
                self.name == other.name and
                self.ep_type == other.ep_type)

    def __repr__(self):
        return '<AnimeTitle name="{0}", parent_id={1}>'.format(self.name, self.parent_id)


class AnimeLanguage(Base):
    """Language names for anime (ex: jp, en, x-jat)."""

    __tablename__ = 'anidb_languages'

    id_ = Column('id', Integer, primary_key=True)
    name = Column(Unicode)

    def __init__(self, language):
        self.name = language


class AnimeEpisode(Base):
    """Individual episodes of an Anime."""

    __tablename__ = 'anidb_episodes'

    id_ = Column('id', Integer, primary_key=True)
    anidb_id = Column(Integer, unique=True)
    parent_id = Column(Integer, ForeignKey('anidb_series.id'))
    number = Column(Unicode)
    ep_type = Column(String)
    length = Column(Integer)
    airdate = Column(Date)
    rating = Column(Float)
    votes = Column(Integer)
    titles = relation('AnimeEpisodeTitle')

    def __init__(self, anidb_id: int, number: str, length: int, airdate: datetime, rating: float, parent: int):
        self.anidb_id = anidb_id
        self.number = number[0]
        self.ep_type = number[1]
        self.length = length
        self.airdate = airdate
        self.rating = rating[0]
        self.votes = rating[1]
        self.parent_id = parent


class AnimeEpisodeTitle(Base):
    """Titles for individual Anime episodes."""

    __tablename__ = 'anidb_episodetitles'

    id_ = Column('id', Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey('anidb_episodes.id'))
    title = Column(Unicode)
    language = Column(Unicode, ForeignKey('anidb_languages.name'))

    def __init__(self, parent_id, title, langauge):
        self.parent_id = parent_id
        self.title = title
        self.language = langauge


@db_schema.upgrade('api_anidb')
def upgrade(ver, session):
    """Upgrade the database when something has changed."""
    if ver is None:
        raise UpgradeImpossible('Resetting {0} caches because bad data may have been cached.'.format(PLUGIN_ID))
    return ver

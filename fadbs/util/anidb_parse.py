from __future__ import unicode_literals, division, absolute_import

import logging
import os
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from datetime import datetime, timedelta

from bs4 import Tag
from flexget import plugin
from flexget.manager import manager
from flexget.utils.requests import Session, TimedLimiter
from flexget.utils.soup import get_soup

from .anidb_cache import cached_anidb, ANIDB_CACHE

PLUGIN_ID = 'anidb_parse'

CLIENT_STR = 'fadbs'
CLIENT_VER = 1

log = logging.getLogger(PLUGIN_ID)

requests = Session()
requests.headers.update({'User-Agent': 'Python-urllib/2.6'})

requests.add_domain_limiter(TimedLimiter('api.anidb.net', '3 seconds'))


class AnidbParser(object):
    """Fetch and parse an AniDB API entry."""

    anidb_xml_url = 'http://api.anidb.net:9001/httpapi?client={0}&clientver={1}&protover=1'.format(CLIENT_STR, CLIENT_VER)
    anidb_endpoint = 'http://api.anidb.net:9001/httpapi'
    anidb_params = {
        'client': CLIENT_STR,
        'clientver': CLIENT_VER,
        'protover': 1,
    }
    anidb_anime_url = anidb_xml_url + '&request=anime&aid=%s'

    anidb_ban_file = os.path.join(manager.config_base, '.anidb_ban')

    @property
    def is_banned(self):
        """Check if we are banned from AniDB."""
        if os.path.exists(self.anidb_ban_file):
            with open(self.anidb_ban_file, 'r') as aniban:
                aniban_str = aniban.read()
                if not aniban_str:
                    os.remove(self.anidb_ban_file)
                    return False, None
                banned_date = datetime.fromtimestamp(float(aniban_str))
                aniban.close()
                if datetime.now() - banned_date < timedelta(1):
                    return True, banned_date + timedelta(1)
                os.remove(self.anidb_ban_file)
        return False, None

    DATE_FORMAT = '%Y-%m-%d'

    RESOURCE_MIN_CACHE = 24 * 60 * 60

    seasons = {
        ('Winter', range(1, 4)),
        ('Spring', range(4, 7)),
        ('Summer', range(7, 10)),
        ('Fall', range(10, 13))
    }

    def __init__(self, anidb_id):
        self.anidb_id = anidb_id
        self.type = None  # type
        self.num_episodes = None  # episodecount
        self.dates = {}  # startdate, enddate
        self.titles = []  # titles > title
        self.related_anime = []  # relatedanime
        self.similar_anime = []  # similaranime
        self.official_url = None  # url
        self.creators = []  # creators
        self.description = None  # description
        self.ratings = None
        self.genres = []  # tags
        self.characters = []  # characters
        self.episodes = []  # episodes
        self.year = None
        self.season = None

    def __str__(self):
        return '<AnidbParser (name={0}, anidb_id={1})>'.format('WIP', self.anidb_id)

    def __append_title(self, title):
        self.titles.append({
            'name': title.string,
            'lang': title['xml:lang'],
            'type': title['type'],
        })

    def __append_related(self, related):
        self.related_anime.append({
            'id': int(related['id']),
            'type': related['type'],
            'name': related.string,
        })

    def __append_similar(self, similar):
        self.similar_anime.append({
            'id': int(similar['id']),
            'approval': similar['approval'],
            'total': similar['total'],
            'name': similar.string,
        })

    def __append_creator(self, creator):
        self.creators.append({
            'id': int(creator['id']),
            'type': creator['type'],
            'name': creator.string,
        })

    def __append_genre(self, tag):
        self.genres.append({
            'id': int(tag['id']),
            'parentid': int(tag['parentid']) if 'parentid' in tag.attrs else 0,
            'name': tag.find('name').string,
            'weight': int(tag['weight']),
            'localspoiler': bool(tag['localspoiler']),
            'globalspoiler': bool(tag['globalspoiler']),
            'verified': bool(tag['verified']),
        })

    def __append_character(self, character):
        character_type = character.find('charactertype')
        seiyuu = character.find('seiyuu')
        rating = character.find('rating')
        description = character.find('description')
        self.characters.append({
            'id': int(character['id']),
            'type': character['type'],
            'rating': None if rating is None else rating.string,
            'gender': character.find('gender').string,
            'character_type': {
                'id': character_type['id'],
                'name': character_type.string,
            },
            'description': None if description is None else description.string,
            'seiyuu': {
                'id': None if seiyuu is None else seiyuu['id'],
                'name': None if seiyuu is None else seiyuu.string,
            },
        })

    @staticmethod
    def __find_episode_titles(ep_titles_contents):
        titles = []
        for title in ep_titles_contents:
            if isinstance(title, Tag):
                titles.append({
                    'name': title.string,
                    'lang': title['xml:lang'],
                })
        return titles

    def __append_episode(self, episode):
        ep_number = episode.find('epno')
        rating = episode.find('rating')
        ep_airdate = episode.find('airdate')
        self.episodes.append({
            'id': int(episode['id']),
            'episode_number': ep_number.string,
            'episode_type': ep_number['type'],
            'length': episode.find('length').string,
            'airdate': None if ep_airdate is None else datetime.strptime(ep_airdate.string, self.DATE_FORMAT).date(),
            'rating': None if rating is None else rating.string,
            'votes': None if rating is None else rating['votes'],
            'titles': self.__find_episode_titles(episode.find_all('title')),
        })

    @staticmethod
    def __parse_tiered_tag(contents, callback):
        if contents is None:
            log.warning('%s passed None to __parse_tiered_tag', callback.__name__)
            return
        for item in contents.find_all(True, recursive=False):
            callback(item)

    def __set_dates(self, start_tag, end_tag):
        if start_tag:
            start_parts = start_tag.string.split('-')
            if len(start_parts) == 3:
                self.dates['start'] = datetime.strptime(start_tag.string, self.DATE_FORMAT).date()
            else:
                self.dates['start'] = None
            if len(start_parts) >= 2:
                month = int(start_parts[1])
                self.season = [season[0] for season in self.seasons if month in season[1]][0]
            self.year = int(start_parts[0])

        if end_tag:
            if len(end_tag.string.split('-')) == 3:
                self.dates['end'] = datetime.strptime(end_tag.string, self.DATE_FORMAT).date()
            else:
                self.dates['end'] = None

    def __set_sim_rel(self, similar_tag, related_tag):
        if similar_tag is not None:
            self.__parse_tiered_tag(similar_tag, self.__append_similar)

        if related_tag is not None:
            self.__parse_tiered_tag(related_tag, self.__append_related)

    def request_anime(self):
        if self.is_banned[0]:
            raise plugin.PluginError('Banned from AniDB until {0}'.format(self.is_banned[1]))
        params = self.anidb_params.copy()
        params.update(request='anime', aid=self.anidb_id)
        log.info(params)
        raise plugin.PluginError('Safety raise')
        page = requests.get(self.anidb_endpoint, params=params)
        page = page.text
        if '500' in page and 'banned' in page.lower():
            time_now = datetime.now().timestamp()
            with open(self.anidb_ban_file, 'w') as aniban:
                aniban.write(str(time_now))
                aniban.close()
            raise plugin.PluginError('Banned from AniDB until {0}'.format(time_now + timedelta(1)))
        return page

    @cached_anidb
    def parse(self, soup=None):
        """Parse the xml file that we recieved from AniDB."""
        if not soup:
            raise plugin.PluginError('anidb_cache didn\'t give us anything.')

        root = soup.find('anime')

        try:
            self.type = root.find('type').string
        except AttributeError:
            pass

        try:
            self.num_episodes = int(root.find('episodecount').string)
        except AttributeError:
            self.num_episodes = 0

        self.__set_dates(root.find('startdate'), root.find('enddate'))

        self.__parse_tiered_tag(root.find('titles'), self.__append_title)

        self.__set_sim_rel(root.find('similaranime'), root.find('related_anime'))

        try:
            self.official_url = root.find('url').string
        except AttributeError:
            pass

        self.__parse_tiered_tag(root.find('creators'), self.__append_creator)

        tag_description = root.find('description')
        if tag_description is not None:
            self.description = tag_description.string

        ratings_tag = root.find('ratings')
        if ratings_tag is not None:
            permanent_tag = ratings_tag.find('permanent')
            mean_tag = ratings_tag.find('temporary')
            self.ratings = {
                'permanent': {
                    'rating': permanent_tag.string,
                    'votes': permanent_tag['count'],
                },
                'mean': {
                    'rating': mean_tag.string,
                    'votes': mean_tag['count'],
                },
            }

        tag_root = root.find('tags')
        if tag_root is not None:
            self.__parse_tiered_tag(root.find('tags'), self.__append_genre)

        character_root = root.find('characters')
        if character_root is not None:
            self.__parse_tiered_tag(root.find('characters'), self.__append_character)

        episodes_root = root.find('episodes')
        if episodes_root is not None:
            self.__parse_tiered_tag(root.find('episodes'), self.__append_episode)

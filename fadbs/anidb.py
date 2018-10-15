from __future__ import unicode_literals, division, absolute_import

from datetime import datetime
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from bs4 import Tag

from flexget.utils.soup import get_soup
from flexget.utils.requests import Session, TimedLimiter

PLUGIN_ID = 'fadbs.util.anidb'

CLIENT_STR = 'fadbs'
CLIENT_VER = 1

log = logging.getLogger(PLUGIN_ID)

requests = Session()
requests.headers.update({'User-Agent': 'Python-urllib/2.6'})

requests.add_domain_limiter(TimedLimiter('api.anidb.net', '2 seconds'))


class AnidbSearch(object):

    anidb_xml_url = 'http://api.anidb.net:9001/httpapi?request=anime'
    prelook_url = 'http://anisearch.outrance.pl?task=search&query=%s'

    def __init__(self):
        self.debug = False

    def by_name(self, anime_name):
        pass


class AnidbParser(object):
    """ Fetch and parse an AniDB API entry """

    anidb_xml_url = 'http://api.anidb.net:9001/httpapi?request=anime&aid=%s'

    DATE_FORMAT = '%Y-%m-%d'

    def __init__(self):
        self.anidb_id = None  # anime.attr.id
        self.type = None  # type
        self.num_episodes = None  # episodecount
        self.dates = None  # startdate, enddate
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

    def __str__(self):
        return '<AnidbParser (name=%s, anidb_id=%s)>' % ('WIP', self.anidb_id)

    def __parse_titles(self, titles_contents):
        for title in titles_contents:
            if type(title) is Tag:
                self.titles.append({
                    'title': title.string,
                    'lang': title['xml:lang'],
                    'type': title['type']
                })

    def __parse_related(self, related_contents):
        for related in related_contents:
            if type(related) is Tag:
                self.related_anime.append({
                    'id': related['id'],
                    'type': related['type'],
                    'name': related.string
                })

    def __parse_similar(self, similar_contents):
        for similar in similar_contents:
            if type(similar) is Tag:
                self.similar_anime.append({
                    'id': similar['id'],
                    'approval': similar['approval'],
                    'total': similar['total'],
                    'name': similar.string
                })

    def __parse_creators(self, creator_contents):
        for creator in creator_contents:
            if type(creator) is Tag:
                self.creators.append({
                    'id': creator['id'],
                    'type': creator['type'],
                    'name': creator.string
                })

    def __parse_genres(self, tags_contents):
        for tag in tags_contents:
            if type(tag) is Tag:
                self.genres.append({
                    'id': tag['id'],
                    'parentid': tag['parentid'] if 'parentid' in tag.attrs else None,
                    'name': tag.find('name').string,
                    'weight': tag['weight'],
                    'localspoiler': bool(tag['localspoiler']),
                    'globalspoiler': bool(tag['globalspoiler']),
                    'verified': bool(tag['verified'])
                })

    def __parse_characters(self, characters_contents):
        for character in characters_contents:
            if type(character) is Tag:
                character_type = character.find('charactertype')
                seiyuu = character.find('seiyuu')
                rating = character.find('rating')
                description = character.find('description')
                self.characters.append({
                    'id': character['id'],
                    'type': character['type'],
                    'rating': None if rating is None else rating.string,
                    'gender': character.find('gender').string,
                    'character_type': {
                        'id': character_type['id'],
                        'name': character_type.string
                    },
                    'description': None if description is None else description.string,
                    'seiyuu': {
                        'id': None if seiyuu is None else seiyuu['id'],
                        'name': None if seiyuu is None else seiyuu.string
                    }
                })

    def __parse_episodes(self, episodes_contents):
        for episode in episodes_contents:
            if type(episode) is Tag:
                titles = []
                for title in episode.find('title'):
                    if type(title) is Tag:
                        titles.append({
                            'title': title.string,
                            'lang': title['xml:lang']
                        })
                ep_number = episode.find('epno')
                rating = episode.find('rating')
                self.episodes.append({
                    'id': episode['id'],
                    'episode_number': ep_number.string,
                    'episode_type': ep_number['type'],
                    'length': episode.find('length').string,
                    'airdate': datetime.strptime(episode.find('airdate').string, self.DATE_FORMAT).date(),
                    'rating': rating.string,
                    'votes': rating['votes'],
                    'titles': titles
                })

    def parse(self, anidb_id, soup=None):
        self.anidb_id = anidb_id
        url = self.anidb_xml_url % self.anidb_id

        if not soup:
            page = requests.get(url, params={'client': CLIENT_STR, 'clientver': CLIENT_VER, 'protover': 1})
            print(page.url)
            soup = get_soup(page.text)

        root = soup.find('anime')

        self.type = root.find('type').string
        self.num_episodes = root.find('episodecount').string

        start_tag = root.find('startdate')
        end_tag = root.find('enddate')
        self.dates = {
            'start': None if start_tag is None else datetime.strptime(start_tag.string, self.DATE_FORMAT).date(),
            'end': None if end_tag is None else datetime.strptime(end_tag.string, self.DATE_FORMAT).date()
        }

        self.__parse_titles(root.find('titles'))

        related_tag = root.find('relatedanime')
        if related_tag is not None:
            self.__parse_related(related_tag)

        similar_tag = root.find('similaranime')
        if similar_tag is not None:
            self.__parse_similar(similar_tag)

        self.official_url = root.find('url').string
        self.__parse_creators(root.find('creators'))
        self.description = root.find('description').string

        ratings_tag = root.find('ratings')
        permanent_tag = ratings_tag.find('permanent')
        mean_tag = ratings_tag.find('temporary')
        self.ratings = {
            'permanent': {
                'rating': permanent_tag.string,
                'votes': permanent_tag['votes']
            },
            'mean': {
                'rating': mean_tag.string,
                'votes': mean_tag['votes']
            }
        }
        self.__parse_genres(root.find('tags'))
        self.__parse_characters(root.find('characters'))
        self.__parse_episodes(root.find('episodes'))

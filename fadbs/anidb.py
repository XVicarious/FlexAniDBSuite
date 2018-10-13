from __future__ import unicode_literals, division, absolute_import

from datetime import datetime
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring

import logging

from bs4 import Tag

from flexget.utils.soup import get_soup
from flexget.utils.requests import Session, TimedLimiter
from flexget.plugin import get_plugin_by_name, PluginError

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

    def by_name(self, aid):
        pass


class AnidbParser(object):

    anidb_xml_url = 'http://api.anidb.net:9001/httpapi?request=anime&aid=%s'

    DATE_FORMAT = '%Y-%m-%d'

    def __init__(self):
        self.anidb_id = None  # anime.attr.id
        self.type = None  # type
        self.num_episodes = None  # episodecount
        self.start_date = None  # startdate
        self.end_date = None  # enddate
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
            self.titles.append({
                'title': title.string,
                'lang': title['xml:lang'],
                'type': title['type']
            })

    def __parse_related(self, related_contents):
        for related in related_contents:
            self.related_anime.append({
                'id': related['id'],
                'type': related['type'],
                'name': related.string
            })

    def __parse_similar(self, similar_contents):
        for similar in similar_contents:
            self.similar_anime.append({
                'id': similar['id'],
                'approval': similar['approval'],
                'total': similar['total'],
                'name': similar.string
            })

    def __parse_creators(self, creator_contents):
        for creator in creator_contents:
            self.creators.append({
                'id': creator['id'],
                'type': creator['type'],
                'name': creator.string
            })

    def __parse_genres(self, tags_contents):
        for tag in tags_contents:
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
            self.characters.append({
                'id': character['id'],
                'type': character['type'],
                'rating': character.contents.rating.string,
                'gender': character.contents.gender.string,
                'character_type': {
                    'id': character.contents.charactertype['id'],
                    'name': character.contents.charactertype.string
                },
                'description': character.contents.description.string,
                'seiyuu': {
                    'id': character.contents.seiyuu['id'],
                    'name': character.contents.seiyuu.string
                }
            })

    def __parse_episodes(self, episodes_contents):
        for episode in episodes_contents:
            titles = []
            for title in episode.find('title'):
                titles.append({
                    'title': title.string,
                    'lang': title['xml:lang']
                })
            self.episodes.append({
                'id': episode['id'],
                'episode_number': episode.contents.number.string,
                'episode_type': episode.contents.number['type'],
                'length': episode.contents.length.string,
                'airdate': datetime.strptime(episode.contents.airdate, self.DATE_FORMAT),
                'rating': episode.contents.rating.string,
                'votes': episode.contents.rating['votes'],
                'titles': titles
            })

    def parse(self, anidb_id, soup=None):
        self.anidb_id = anidb_id
        url = self.anidb_xml_url % self.anidb_id

        if not soup:
            page = requests.get(url, params={'client': CLIENT_STR, 'clientver': CLIENT_VER, 'protover': 1})
            print(page.url)
            soup = get_soup(page.text)

        print(soup)
        root = soup.find('anime')

        self.type = root.find('type').string
        self.num_episodes = root.find('episodecount').string
        self.start_date = datetime.strptime(root.find('startdate').string, self.DATE_FORMAT)
        self.end_date = datetime.strptime(root.find('enddate').string, self.DATE_FORMAT)
        self.__parse_titles(root.find('titles'))
        self.__parse_related(root.find('relatedanime'))
        self.__parse_similar(root.find('similaranime'))
        self.official_url = root.find('url').string
        self.__parse_creators(root.find('creators'))
        self.description = root.find('description').string
        ratings_tag = root.find('ratings')
        self.ratings = {
            'permanent': ratings_tag.find('permanent').string,
            'mean': ratings_tag.find('temporary').string
        }
        self.__parse_genres(root.find('tags'))
        self.__parse_characters(root.find('characters'))
        self.__parse_episodes(root.find('episodes'))

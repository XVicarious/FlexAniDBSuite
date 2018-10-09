from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from past.builtins import basestring

import xml
import logging

from bs4 import Tag

from flexget.utils.soup import get_soup
from flexget.utils.requests import Session, TimedLimiter
from flexget.plugin import get_plugin_by_name, PluginError

PLUGIN_ID = 'fadbs.util.anidb'

log = logging.getLogger(PLUGIN_ID)

requests = Session()
requests.headers.update({'User-Agent': 'Python-urllib/2.6'})

requests.add_domain_limiter(TimedLimiter('api.anidb.net', '2 seconds'))


class AnidbSearch(object):

    anidb_xml_url = 'http://api.anidb.net:9001/httpapi?request=anime'
    prelook_url = 'http://anisearch.outrance.pl?task=search&query=%s'

    def __init__(self):
        self.debug = False

    def by_id(self, aid):
        pass


class AnidbParser(object):

    anidb_xml_url = 'http://api.anidb.net:9001/httpapi?request=anime&aid=%s'

    def __init__(self):
        # todo: structure genres better
        # todo: episodes
        # todo: actors
        # todo: staff
        self.genres = []  # tags
        # tag attrs: id, parent_id (if child), weight, localspoiler, globalspoiler, verified
        # name
        self.names = []  # titles > title
        # xml:lang -- the langauge code
        # type -- main -- main title used on AniDB
        # ------- short -- short title for the given language
        # ------- synonym -- ?
        # ------- official -- official translated title
        self.anidb_id = None  # anime attr id
        # [episode_num, length_in_min, airdate_yyyy-mm-dd, titles={en:,ja:,x-jat:}]
        self.episodes = []  # episodes
        self.date = []  # start, end
        self.permanent_rating = None  # ratings > permanent
        self.mean_rating = None  # ratings > temporary
        self.description = None  # description

    def __str__(self):
        return '<AnidbParser (name=%s, anidb_id=%s)>' % ('WIP', self.anidb_id)

    def parse_titles(self, titles_contents):
        titles = []
        for title in titles_contents:
            title_obj = {
                'title': title.string,
                'lang': title['xml:lang'],
                'type': title['type']
            }
            titles.append(title_obj)
        return titles

    def in_genre_children(self, tag_obj, parent_tag_id):
        for child in tag_obj['children']:
            if parent_tag_id == child['id']:
                return [tag_obj['id']]

    def parse_genres(self, tags_contents):
        # tag attrs: id, parent_id (if child), weight, localspoiler, globalspoiler, verified
        tags = []
        for tag in tags_contents:
            tags.append({
                'id': tag['id'],
                'parentid': tag['parentid'] if 'parentid' in tag.attrs else None,
                'name': tag.find('name').string,
                'weight': tag['weight'],
                'localspoiler': bool(tag['localspoiler']),
                'globalspoiler': bool(tag['globalspoiler']),
                'verified': bool(tag['verified'])
            })
        return tags

    def parse(self, anidb_id, soup=None):
        self.anidb_id = anidb_id
        url = self.anidb_xml_url % self.anidb_id

        if not soup:
            page = requests.get(url)
            soup = get_soup(page.text)

        root = soup.find('anime')

        self.names = self.parse_titles(root.find('titles'))
        self.genres = self.parse_genres(root.find('tags'))
        self.description = root.find('description').string
        self.date = [
            root.find('startdate').string,
            root.find('enddate').string
        ]
        self.permanent_rating = root.find('ratings').find('permanent').string
        self.mean_rating = root.find('raatings').find('temporary').string

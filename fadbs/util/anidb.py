from __future__ import unicode_literals, division, absolute_import

import hashlib
import os
import re
import difflib
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from datetime import datetime, timedelta
from bs4 import Tag
from flexget import logging
from flexget import plugin
from flexget.utils.requests import Session, TimedLimiter
from flexget.utils.soup import get_soup
from slugify import slugify

from .anidb_cache import cached_anidb, ANIDB_CACHE

PLUGIN_ID = 'fadbs.util.anidb'

CLIENT_STR = 'fadbs'
CLIENT_VER = 1

log = logging.getLogger(PLUGIN_ID)

requests = Session()
requests.headers.update({'User-Agent': 'Python-urllib/2.6'})

requests.add_domain_limiter(TimedLimiter('api.anidb.net', '2 seconds'))


class AnidbSearch(object):
    """ Search for an anime's id """

    anidb_xml_url = 'http://api.anidb.net:9001/httpapi?request=anime'
    prelook_url = 'http://anisearch.outrance.pl?task=search'
    anidb_title_dump_url = 'http://anidb.net/api/anime-titles.xml.gz'
    cdata_regex = re.compile(r'.+CDATA\[(.+)\]\].+')
    particle_words = {
        'x-jat': {
            'no', 'wo', 'o', 'na', 'ja', 'ni', 'to', 'ga', 'wa'
        }
    }

    def __init__(self):
        self.debug = False

    def __get_title_comparisons(self, original_title, anime_objects, min_ratio=0.65):
        titles = []
        for anime in anime_objects:
            aid = anime['aid']
            for title in anime.find_all('title'):
                title_string = self.cdata_regex.findall(title.string)
                if not len(title_string):
                    continue
                title_string = title_string[0]
                diff_ratio = difflib.SequenceMatcher(a=original_title.lower(), b=title_string.lower()).ratio()
                if diff_ratio == 1.0:
                    log.debug('This is a perfect match, no need to do any more.')
                    titles.clear()
                    titles.append([aid, diff_ratio, title_string])
                    return titles
                if diff_ratio >= min_ratio:
                    log.debug('Title "%s" matches "%s" with %s similarity, which is above %s.',
                              title_string, original_title, diff_ratio, min_ratio)
                    titles.append([aid, diff_ratio, title_string])
        log.verbose('Returning %s titles with at least %s similarity.', len(titles), min_ratio)
        return titles

    def __download_anidb_titles(self, cache_path):
        anidb_titles = requests.get(self.anidb_title_dump_url)
        if anidb_titles.status_code >= 400:
            raise plugin.PluginError(anidb_titles.status_code, anidb_titles.reason)
        with open(cache_path, 'w') as xml_file:
            xml_file.write(anidb_titles.text)
            xml_file.close()

    def by_name(self, anime_name, match_ratio=0.9):
        from flexget.manager import manager
        cache_path = os.path.join(manager.config_base, 'anidb-titles.xml')
        cache_exists = os.path.exists(cache_path)
        cache_mtime = datetime.fromtimestamp(os.path.getmtime(cache_path))
        if not cache_exists or abs(datetime.now() - cache_mtime) > timedelta(1):
            self.__download_anidb_titles(cache_path)
        soup = get_soup(open(cache_path), parser='lxml')
        animes = soup.find_all('anime')
        matcher = difflib.SequenceMatcher(a=anime_name)
        for anime in animes:
            titles = anime.find_all('title')
            for title in titles:
                matcher.set_seq2(title.string)
                if matcher.ratio() > match_ratio:
                    log.debug('Found anime: %s', title.string)
                    return anime['aid']
                log.debug('Match not close enough.')
                log.trace('%s: %s does not match %s close enough.', anime['aid'], title.string, anime_name)


class AnidbParser(object):
    """ Fetch and parse an AniDB API entry """

    anidb_xml_url = 'http://api.anidb.net:9001/httpapi?request=anime&aid=%s'

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
        return '<AnidbParser (name=%s, anidb_id=%s)>' % ('WIP', self.anidb_id)

    def __append_title(self, title):
        self.titles.append({
            'name': title.string,
            'lang': title['xml:lang'],
            'type': title['type']
        })

    def __append_related(self, related):
        self.related_anime.append({
            'id': int(related['id']),
            'type': related['type'],
            'name': related.string
        })

    def __append_similar(self, similar):
        self.similar_anime.append({
            'id': int(similar['id']),
            'approval': similar['approval'],
            'total': similar['total'],
            'name': similar.string
        })

    def __append_creator(self, creator):
        self.creators.append({
            'id': int(creator['id']),
            'type': creator['type'],
            'name': creator.string
        })

    def __append_genre(self, tag):
        self.genres.append({
            'id': int(tag['id']),
            'parentid': int(tag['parentid']) if 'parentid' in tag.attrs else 0,
            'name': tag.find('name').string,
            'weight': int(tag['weight']),
            'localspoiler': bool(tag['localspoiler']),
            'globalspoiler': bool(tag['globalspoiler']),
            'verified': bool(tag['verified'])
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
                'name': character_type.string
            },
            'description': None if description is None else description.string,
            'seiyuu': {
                'id': None if seiyuu is None else seiyuu['id'],
                'name': None if seiyuu is None else seiyuu.string
            }
        })

    @staticmethod
    def __find_episode_titles(ep_titles_contents):
        titles = []
        for title in ep_titles_contents:
            if isinstance(title, Tag):
                titles.append({
                    'name': title.string,
                    'lang': title['xml:lang']
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
            'titles': self.__find_episode_titles(episode.find_all('title'))
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

    @cached_anidb
    def parse(self, soup=None):

        if not soup:
            pre_cache_name = ('anime: %s' % self.anidb_id).encode()
            url = (self.anidb_xml_url + "&client=%s&clientver=%s&protover=1") % (self.anidb_id, CLIENT_STR, CLIENT_VER)
            log.debug('Not in cache. Looking up URL: %s', url)
            page = requests.get(url)
            page = page.text
            # todo: move this to cached_anidb
            from flexget.manager import manager
            if 'blake2b' in hashlib.algorithms_available:
                blake = hashlib.new('blake2b')
                blake.update(pre_cache_name)
                cache_filename = os.path.join(manager.config_base, ANIDB_CACHE, blake.hexdigest())
            else:
                md5sum = hashlib.md5(pre_cache_name).hexdigest()
                cache_filename = os.path.join(manager.config_base, ANIDB_CACHE, md5sum)
            with open(cache_filename, 'w') as cache_file:
                cache_file.write(page)
                cache_file.close()
                log.debug('%s cached.', self.anidb_id)
            # end
            if '500' in page:
                page_copy = page.lower()
                if 'banned' in page_copy:
                    raise plugin.PluginError('Banned from AniDB...', log)
            soup = get_soup(page, parser="lxml")
            # We should really check if we're banned or what...
            if not soup:
                log.warning('Uh oh: %s', url)
                return

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
                    'votes': permanent_tag['count']
                },
                'mean': {
                    'rating': mean_tag.string,
                    'votes': mean_tag['count']
                }
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

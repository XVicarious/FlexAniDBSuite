from __future__ import unicode_literals, division, absolute_import

import os
import re
import difflib
import json
from collections import deque
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from datetime import datetime, timedelta
from flexget import logging, plugin
from flexget.utils.database import with_session
from flexget.utils.requests import Session, TimedLimiter
from flexget.utils.soup import get_soup
from sqlalchemy import orm

from .api_anidb import Anime, AnimeTitle, AnimeLangauge

PLUGIN_ID = 'fadbs.util.anidb_search'

CLIENT_STR = 'fadbs'
CLIENT_VER = 1

log = logging.getLogger(PLUGIN_ID)

requests = Session()
requests.headers.update({'User-Agent': 'Python-urllib/2.6'})

requests.add_domain_limiter(TimedLimiter('api.anidb.net', '2 seconds'))


class AnidbSearch(object):
    """ Search for an anime's id """

    anidb_title_dump_url = 'http://anidb.net/api/anime-titles.xml.gz'
    cdata_regex = re.compile(r'.+CDATA\[(.+)\]\].+')

    particle_words = {
        'x-jat': {
            'no', 'wo', 'o', 'na', 'ja', 'ni', 'to', 'ga', 'wa'
        }
    }

    def __init__(self):
        self.debug = False

    @with_session
    def __load_xml_to_database(self, cache_path, session=None):
        with open(cache_path, 'r') as anidb_dump:
            soup = get_soup(anidb_dump, parser='lxml')
            assert isinstance(session, orm.Session)
            last = session.query(Anime).order_by(Anime.anidb_id.desc()).first()
            if last:
                last = last.anidb_id
            animes = soup.find_all('anime')
            for anime in animes:
                anidb_id = int(anime['aid'])
                if int(last) == anidb_id:
                    log.trace('%s exists in the DB, skipping', anidb_id)
                    continue
                series = session.query(Anime).filter(Anime.anidb_id == anidb_id).first()
                if not series:
                    log.debug('The anime is not in the database, adding it')
                    series = Anime()
                    series.anidb_id = anidb_id
                titles = anime.find_all('title')
                for title in titles:
                    title_lang = title['xml:lang']
                    title_type = title['type']
                    lang = session.query(AnimeLangauge).filter(AnimeLangauge.name == title_lang).first()
                    if not lang:
                        lang = AnimeLangauge(title_lang)
                    anime_title = session.query(AnimeTitle).filter(AnimeTitle.name == title.string,
                                                                   AnimeTitle.ep_type == title_type,
                                                                   AnimeTitle.name == title.string).first()
                    if anime_title:
                        log.debug('we already have this title, continuing')
                        continue
                    anime_title = AnimeTitle(title.string, lang.name, title_type, series)
                    series.titles.append(anime_title)
                session.add(series)
            session.commit()

    def __download_anidb_titles(self, cache_path):
        #anidb_titles = requests.get(self.anidb_title_dump_url)
        #if anidb_titles.status_code >= 400:
        #    raise plugin.PluginError(anidb_titles.status_code, anidb_titles.reason)
        #if os.path.exists(cache_path):
        #    os.rename(cache_path, cache_path + '.old')
        #with open(cache_path, 'w') as xml_file:
        #    xml_file.write(anidb_titles.text)
        #    xml_file.close()
        self.__load_xml_to_database(cache_path)

    def by_name(self, anime_name, match_ratio=0.9):
        from flexget.manager import manager
        cache_path = os.path.join(manager.config_base, 'anidb-titles.xml')
        cache_exists = os.path.exists(cache_path)
        cache_mtime = datetime.fromtimestamp(os.path.getmtime(cache_path))
        if not cache_exists: #or abs(datetime.now() - cache_mtime) > timedelta(1):
            log.debug('Cache is old, downloading new...')
            self.__download_anidb_titles(cache_path)
        title_json = json.load(open(os.path.join(manager.config_base, 'anime_titles.json')))
        index = title_json['index']
        titles = deque(title_json['titles'])
        matcher = difflib.SequenceMatcher(a=anime_name)
        len_titles = len(titles)
        index_of_first = index[anime_name[:1]]
        if index_of_first > len_titles / 2:
            index_of_first -= len_titles
        titles.rotate(index_of_first)
        countdown = 0
        good_match = []
        log.debug('About to find %s in %s titles.', anime_name, len_titles)
        for title in titles:
            matcher.set_seq2(title[0])
            rat = matcher.ratio()
            end_this = False
            if rat > match_ratio:
                if rat == 1.0:
                    log.debug('Found %s, which matches %s perfectly.', title[0], anime_name)
                    return int(title[1])
                if len(good_match):
                    for item in good_match:
                        if int(title[1]) == int(item[1][1]):
                            end_this = True
                            break
                countdown += 5
                if end_this:
                    continue
                good_match.append((rat, title))
                continue
            if countdown > 0:
                countdown -= 1
                if countdown == 0:
                    if len(good_match):
                        good_match.sort(key=lambda x: x[0], reverse=True)
                        return good_match[0][1][1]
        raise plugin.PluginError('Could not find the anidb id for %s' % anime_name)


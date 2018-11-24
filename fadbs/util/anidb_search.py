from __future__ import unicode_literals, division, absolute_import

import difflib
import logging
import os
import re
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin
from datetime import datetime, timedelta

from flexget import plugin
from flexget.manager import manager
from flexget.utils.database import with_session
from flexget.utils.requests import Session, TimedLimiter
from flexget.utils.soup import get_soup

from .api_anidb import Anime, AnimeTitle, AnimeLangauge

PLUGIN_ID = 'anidb_search'

CLIENT_STR = 'fadbs'
CLIENT_VER = 1

log = logging.getLogger(PLUGIN_ID)

requests = Session()
requests.headers.update({'User-Agent': 'Python-urllib/2.6'})

requests.add_domain_limiter(TimedLimiter('api.anidb.net', '3 seconds'))


class AnidbSearch(object):
    """Search for an anime's id."""

    anidb_title_dump_url = 'http://anidb.net/api/anime-titles.xml.gz'
    xml_cache = {
        'path': os.path.join(manager.config_base, 'anime-titles.xml'),
    }
    xml_cache.update({
        'exists': os.path.exists(xml_cache['path']),
        'modified': os.path.getmtime(xml_cache['path']),
    })
    xml_cache_path = xml_cache['path']
    cdata_regex = re.compile(r'.+CDATA\[(.+)\]\].+')

    particle_words = {
        'x-jat': {
            'no', 'wo', 'o', 'na', 'ja', 'ni', 'to', 'ga', 'wa',
        },
    }

    def __init__(self):
        self.debug = False

    @with_session
    def __load_xml_to_database(self, cache_path, session=None):
        with open(cache_path, 'r') as anidb_dump:
            soup = get_soup(anidb_dump, parser='lxml-xml')
            last = session.query(Anime).order_by(Anime.anidb_id.desc()).first()
            if last:
                last = last.anidb_id
            animes = soup.find_all('anime')
            for anime in animes:
                anidb_id = int(anime['aid'])
                # this doesn't allow for adding new titles to existing entries
                if int(last) > anidb_id:
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
                    anime_title = session.query(AnimeTitle)
                    anime_title = anime_title.filter(AnimeTitle.name == title.string,
                                                     AnimeTitle.ep_type == title_type,
                                                     AnimeTitle.name == title.string).first()
                    if anime_title:
                        log.debug('we already have this title, continuing')
                        continue
                    anime_title = AnimeTitle(title.string, lang.name, title_type, series)
                    series.titles.append(anime_title)
                session.add(series)
            session.commit()

    @with_session
    def _load_xml_to_database(self, session=None):
        with open(self.xml_cache_path, 'r') as xml_anime:
            get_soup(xml_anime, parser='lxml-xml')

    def __download_anidb_titles(self):
        #anidb_titles = requests.get(self.anidb_title_dump_url)
        #if anidb_titles.status_code >= 400:
        #    raise plugin.PluginError(anidb_titles.status_code, anidb_titles.reason)
        #if os.path.exists(cache_path):
        #    os.rename(cache_path, cache_path + '.old')
        #with open(cache_path, 'w') as xml_file:
        #    xml_file.write(anidb_titles.text)
        #    xml_file.close()
        self.__load_xml_to_database(self.xml_cache_path)

    @with_session
    def by_name(self, anime_name, match_ratio=0.9, session=None):
        """Search for the given name in our database of Anime.

        anime_name -- name we are searching for
        match_ratio -- what threshold we want to use for matching titles, default 0.9
        session -- SQLAlchemy session. Should be set by @with_session
        """
        abs_diff = abs(datetime.now() - self.xml_cache['modified'])
        if not self.xml_cache['exists'] or abs_diff > timedelta(1):
            log.debug('Cache is old, downloading new...')
            self.__download_anidb_titles()
        matcher = difflib.SequenceMatcher(a=anime_name)
        countdown = 0
        good_match = {}
        possible_titles = session.query(AnimeTitle).all()
        for title in possible_titles:
            matcher.set_seq2(title.name)
            rat = matcher.ratio()
            end_this = False
            if rat > match_ratio:
                if rat == 1:
                    log.debug('Found %s, which matches %s perfectly.', title.name, anime_name)
                    return title.parent_id
                if len(good_match) and title.parent_id in good_match:
                    end_this = True
                countdown += 5
                if end_this:
                    continue
                good_match.update({title.parent_id: (title.name, rat)})
                continue
            if countdown > 0:
                countdown -= 1
                if countdown == 0 and len(good_match):
                    best_id = None
                    for _id, tup in good_match.items():
                        if not best_id or tup[1] > good_match[best_id]:
                            best_id = _id
                    return session.query(Anime).filter(Anime.id_ == _id).first().anidb_id
        raise plugin.PluginError('Could not find the anidb id for {0}'.format(anime_name))

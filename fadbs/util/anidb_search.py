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
        'modified': datetime.fromtimestamp(os.path.getmtime(xml_cache['path'])),
    })
    cdata_regex = re.compile(r'.+CDATA\[(.+)\]\].+')

    particle_words = {
        'x-jat': {
            'no', 'wo', 'o', 'na', 'ja', 'ni', 'to', 'ga', 'wa',
        },
    }

    def __init__(self):
        self.debug = False
        with open(self.xml_cache['path'], 'r') as soup_file:
            self.soup = get_soup(soup_file, parser='lxml-xml')

    @with_session
    def __load_xml_to_database(self, cache_path, session=None):
        if True:
            last = session.query(Anime).order_by(Anime.anidb_id.desc()).first()
            if last:
                last = last.anidb_id
            animes = self.soup.find_all('anime')
            for anime in animes:
                anidb_id = int(anime['aid'])
                # this doesn't allow for adding new titles to existing entries
                series = None
                if int(last) > anidb_id:
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
                        log.trace('we already have this title, continuing')
                        continue
                    anime_title = AnimeTitle(title.string, lang.name, title_type, series)
                    series.titles.append(anime_title)
                if int(last) < anidb_id:
                    session.add(series)
            session.commit()
 
    def __download_anidb_titles(self):
        #anidb_titles = requests.get(self.anidb_title_dump_url)
        #if anidb_titles.status_code >= 400:
        #    raise plugin.PluginError(anidb_titles.status_code, anidb_titles.reason)
        #if os.path.exists(self.xml_cache['path']):
        #    os.rename(self.xml_cache['path'], self.xml_cache['path'] + '.old')
        #with open(self.xml_cache['path'], 'w') as xml_file:
        #    xml_file.write(anidb_titles.text)
        #    xml_file.close()
        new_mtime = os.path.getmtime(self.xml_cache['path'])
        self.xml_cache['modified'] = datetime.fromtimestamp(new_mtime)
        self.__load_xml_to_database(self.xml_cache['path'])

    @with_session
    def by_name(self, anime_name, match_ratio=0.9, session=None):
        """Search for the given name in our database of Anime.

        anime_name -- name we are searching for
        match_ratio -- what threshold we want to use for matching titles, default 0.9
        session -- SQLAlchemy session. Should be set by @with_session
        """
        # Make sure our database is up to date
        abs_diff = abs(datetime.now() - self.xml_cache['modified'])
        log.trace('Cache expires in %s', str(abs_diff))
        if not self.xml_cache['exists'] or abs_diff > timedelta(1):
            log.debug('Cache is old, downloading new...')
            self.__download_anidb_titles()
        # Try to just get an exact match
        exact_title = session.query(AnimeTitle).filter(AnimeTitle.name == anime_name).first()
        if exact_title:
            log.debug('Found an exact title, shortcutting!')
            exact_title_anidb_id = session.query(Anime)
            exact_title_anidb_id = exact_title_anidb_id.filter(Anime.id_ == exact_title.parent_id).first()
            return exact_title_anidb_id.anidb_id
        # If we don't get a perfect match, use some hacky matching.
        log.debug('Exact match not found, searching database.')
        matcher = difflib.SequenceMatcher(a=anime_name)
        countdown = 0
        good_match = {}
        possible_titles = session.query(AnimeTitle).all()
        log.debug('Loaded %s titles from the database...', len(possible_titles))
        for title in possible_titles:
            matcher.set_seq2(title.name)
            rat = matcher.ratio()
            end_this = False
            if rat > match_ratio:
                if len(good_match) and title.parent_id in good_match:
                    end_this = True
                countdown += 5
                if end_this:
                    continue
                good_match.update({title.parent_id: (title.name, rat)})
                continue
            if countdown > 0:
                countdown -= 1
            if countdown == 1 and len(good_match):
                best_id = None
                for _id, tup in good_match.items():
                    if not best_id or tup[1] > good_match[best_id]:
                        best_id = _id
                return session.query(Anime).filter(Anime.id_ == best_id).first().anidb_id
        raise plugin.PluginError('Could not find the anidb id for {0}'.format(anime_name))

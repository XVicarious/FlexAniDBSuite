import os
import sys
from contextlib import contextmanager

from bs4 import BeautifulSoup
import pytest
import yaml
from flexget.manager import Manager

sys.path.append(os.path.abspath('.'))
from fadbs.util import utils, AnidbParser, ANIDB_SEARCH
from fadbs.util.config import Config, open_config
from fadbs.util.fadbs_session import FadbsSession
from fadbs.util.anidb_parser_new import AnidbAnime


class TestParser:

    anime = AnidbAnime(13217, BeautifulSoup(open('fadbs/tests/13217.xml'), 'lxml'))

    def test_normal(self):
        assert self.anime.title
        assert self.anime.title == 'Boku no Kanojo ga Majime Sugiru Shobitch na Ken'

    def test_titles(self):
        assert len(self.anime.all_titles) == 9

    def test_mean_rating(self):
        assert self.anime.mean_rating
        assert self.anime.mean_rating == 5.75

    def test_perm_rating(self):
        assert self.anime.permanent_rating
        assert self.anime.permanent_rating == 3.07

    def test_tags(self):
        assert self.anime.tags
        assert self.anime.tags

    def test_startdate(self):
        assert self.anime.startdate
        assert self.anime.startdate == '2017-10-12'

    def test_enddate(self):
        assert self.anime.enddate
        assert self.anime.enddate == '2017-12-14'

    def test_episodecount(self):
        assert self.anime.episode_count == 10

    def test_seriestype(self):
        assert self.anime.series_type
        assert self.anime.series_type == 'TV Series'

    def test_episodes(self):
        assert self.anime.episodes
        assert self.anime.episodes

    def test_url(self):
        assert self.anime.official_url
        assert self.anime.official_url == 'http://majimesugiru-anime.jp'

    def test_description(self):
        assert self.anime.description
        assert self.anime.description

    def test_episode1_length(self):
        epi = self.anime.episodes[0]
        assert epi.length == 25

    def test_episode1_epno(self):
        epi = self.anime.episodes[0]
        assert epi.epno == ['4', '1']

    def test_episode1_rating(self):
        epi = self.anime.episodes[0]
        assert epi.rating == (5.87, 3)

    def test_episode1_airdate(self):
        epi = self.anime.episodes[0]
        assert epi.airdate == '2017-11-02'


class TestConfig:

    if os.path.exists('fadbs.yml'):
        os.remove('fadbs.yml')
    config: Config = open_config()

    def test_update(self):
        self.config.update_session()

    def test_inc(self):
        self.config.inc_session()

    def is_banned(self):
        self.config.is_banned()

    def can_request(self):
        self.config.can_request()

# -*- coding: utf-8 -*-

from typing import Dict, List, NewType, Optional, Tuple

from bs4 import BeautifulSoup, Tag

from .utils import get_date, get_list_tag, get_ratings, select_parentid

Rating = Tuple[float, int]
Weight = NewType('Weight', int)
AnidbId = NewType('AnidbId', int)


class AnidbEpisode:
    """Store information about anime episodes."""

    anidb_id: AnidbId
    _length: int
    _rating: Rating
    _epno: Tuple[str, str]
    _airdate: str

    def __init__(self, xml_data: Tag):
        """Setup the episode object.

        :param xml_data: raw episode information
        :type xml_data: Tag
        """
        self._soup = xml_data
        self.anidb_id = AnidbId(self._soup['id'])

    @property
    def length(self) -> int:
        """Get the length of the episode in minutes.

        :rtype: int
        """
        if '_length' not in self.__dict__:
            self._length = int(self._soup.find('length').string)
        return self._length

    @property
    def epno(self) -> Tuple[str, str]:
        """Get the episode number, and type.

        :rtype: Tuple[str, str]
        """
        if '_epno' not in self.__dict__:
            self._epno = get_list_tag(self._soup.find('epno'), 'type')
        return self._epno

    @property
    def rating(self) -> Rating:
        """Get the episode rating.

        :rtype: Rating
        """
        if '_rating' not in self.__dict__:
            rate_tag = self._soup.find('rating')
            self._rating = (float(rate_tag.string), int(rate_tag['votes']))
        return self._rating

    @property
    def airdate(self) -> str:
        """Get the date the episode aired.

        :rtype: str
        """
        if '_airdate' not in self.__dict__:
            self._airdate = str(get_date(self._soup.find('airdate')))
        return self._airdate


class AnidbAnime:
    """Hold information about an anime series."""

    anidb_id: AnidbId
    _title: str
    _all_titles: List[Dict[str, str]]
    _series_type: str
    _episode_count: int
    _airdates: Dict[str, str]
    _official_url: str
    _description: str
    _ratings: Dict[str, Rating]
    _tags: Dict[AnidbId, Tuple[str, Weight, AnidbId]]
    _episodes: List[AnidbEpisode]

    def get_tag_str(self, find_tag: str) -> Optional[str]:
        """Get the string inside a specific tag safely.

        :param find_tag: the name of the tag to get the string from
        :type find_tag: str
        :rtype: Optional[str]
        """
        needed_tag = self._soup.find(find_tag)
        if needed_tag:
            return needed_tag.string
        return None

    def __init__(self, anidb_id: int, xml_data: BeautifulSoup):
        self.anidb_id = AnidbId(anidb_id)
        self._soup = xml_data.find('anime')

    def _set_titles(self) -> None:
        titles = self._soup.find('titles')
        self._all_titles = []
        for title in titles.find_all(True, recursive=False):
            anime_title = {
                'name': title.string,
                'type': title['type'],
                'lang': title['xml:lang'],
            }
            self._all_titles += [anime_title]
            if anime_title['type'] == 'main':
                self._title = anime_title['name']

    @property
    def title(self) -> str:
        if '_title' not in self.__dict__:
            self._set_titles()
        return self._title

    @property
    def all_titles(self) -> List[Dict[str, str]]:
        if '_all_titles' not in self.__dict__:
            self._set_titles()
        return self._all_titles

    @property
    def series_type(self) -> str:
        if '_series_type' not in self.__dict__:
            self._series_type = self.get_tag_str('type')
        return self._series_type

    @property
    def episode_count(self) -> int:
        if '_episode_count' not in self.__dict__:
            number = self.get_tag_str('episodecount')
            self._episode_count = 0
            if number:
                self._episode_count = int(number)
        return self._episode_count

    @property
    def official_url(self) -> str:
        if '_official_url' not in self.__dict__:
            self._official_url = self.get_tag_str('url')
        return self._official_url

    @property
    def description(self) -> str:
        if '_description' not in self.__dict__:
            self._description = self.get_tag_str('description')
        return self._description

    def _get_airdate(self, tag_name: str) -> str:
        if '_airdate' not in self.__dict__:
            dt = self._soup.find(tag_name)
            if not dt:
                return ''
            self._airdates = {}
            self._airdates[tag_name] = str(get_date(dt))
        return self._airdates[tag_name]

    @property
    def startdate(self) -> str:
        return self._get_airdate('startdate')

    @property
    def enddate(self) -> str:
        return self._get_airdate('enddate')

    def _get_ratings(self) -> None:
        ratings = get_ratings(self._soup.find('ratings'))
        self._ratings = {}
        if 'permanent' in ratings:
            self._ratings['permanent'] = (ratings['permanent'], 0)
        if 'mean' in ratings:
            self._ratings['mean'] = (ratings['mean'], 0)

    def _get_rating(self, rating_type: str) -> float:
        if '_ratings' not in self.__dict__:
            self._get_ratings()
        return self._ratings[rating_type][0]

    @property
    def mean_rating(self) -> float:
        """Return the mean rating for the anime.

        :rtype: float
        """
        return self._get_rating('mean')

    @property
    def permanent_rating(self) -> float:
        """Return the permanent rating for the anime.

        :rtype: float
        """
        return self._get_rating('permanent')

    def _get_tags(self) -> None:
        tags = self._soup.find('tags')
        if not tags:
            return
        self._tags = {}
        for tag in tags.find_all('tag'):
            name = tag.find('name')
            if not name:
                continue
            name = name.string
            tag_id = tag['id']
            parent_id = AnidbId(int(select_parentid(tag)))
            weight = None
            if 'weight' in tag.attrs:
                weight = Weight(int(tag['weight']))
            self._tags.update({tag_id: (name, weight, parent_id)})

    @property
    def tags(self) -> Dict[AnidbId, Tuple[str, Weight, AnidbId]]:
        """Return the tags for the anime.

        :rtype: Dict[AnidbId, Tuple[str,Weight,AnidbId]]
        """
        if '_tags' not in self.__dict__:
            self._get_tags()
        return self._tags

    def _get_episodes(self) -> None:
        episodes = self._soup.find('episodes')
        if not episodes:
            return
        self._episodes = []
        for episode in episodes.find_all('episode'):
            self._episodes += [AnidbEpisode(episode)]

    @property
    def episodes(self) -> List[AnidbEpisode]:
        """Return the anime episodes.

        :rtype: List[AnidbEpisode]
        """
        if '_episodes' not in self.__dict__:
            self._get_episodes()
        return self._episodes

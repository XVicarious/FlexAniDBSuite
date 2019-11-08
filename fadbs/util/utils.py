"""Functions for parsing AniDB metadata."""
import math
from datetime import date, datetime
from typing import List, NewType

from bs4 import Tag

Season = NewType('Season', str)

SEASONS = [
    Season('Winter'),
    Season('Spring'),
    Season('Summer'),
    Season('Fall'),
]


def get_anime_season(month: int) -> Season:
    """Get anime season based on month."""
    return SEASONS[math.ceil(month / 3) - 1]


def get_date(date_tag: Tag) -> date:
    """Convert a string to a date object."""
    parts = date_tag.string.split('-')
    if len(parts) != 3:
        raise ValueError()
    return datetime.strptime(date_tag.string, '%Y-%m-%d').date()


def get_ratings(ratings_tag: Tag) -> dict:
    """Get the anidb ratings from tag."""
    ratings: dict = {}
    if ratings_tag:
        permanent = ratings_tag.find('permanent')
        if permanent:
            ratings['permanent'] = float(permanent.string)
        mean = ratings_tag.find('temporary')
        if mean:
            ratings['mean'] = float(mean.string)
    return ratings


def select_parentid(tag: Tag) -> int:
    """Extract and return a parent id from a tag."""
    if 'parentid' in tag.attrs:
        return int(tag['parentid'])
    return 0


def get_list_tag(tag: Tag, key: str) -> List:
    """Lazy get a value and name of a tag."""
    return [
        tag.string,
        tag[key],
    ]

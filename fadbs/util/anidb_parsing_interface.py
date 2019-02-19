"""Holds parsing specific functions for AnidbParser."""
import logging
import math
from datetime import datetime
from typing import NewType

from bs4 import Tag
from sqlalchemy.orm import Session

from flexget import plugin
from flexget.logger import FlexGetLogger

from .api_anidb import Anime

PLUGIN_ID = 'anidb_parser'

LOG: FlexGetLogger = logging.getLogger(PLUGIN_ID)

Season = NewType('Season', str)


class AnidbParserTemplate(object):
    """Functions to manipulate series."""

    series: Anime
    session: Session

    date_format = '%Y-%m-%d'

    anime_seasons = [
        Season('Winter'),
        Season('Spring'),
        Season('Summer'),
        Season('Fall'),
    ]

    def _get_anime_season(self, month: int) -> Season:
        return self.anime_seasons[math.ceil(month / 3) - 1]

    def _get_ratings(self, ratings_tag: Tag) -> None:
        if not ratings_tag:
            raise plugin.pluginWarning('Ratings tag was None')
        permanent = ratings_tag.find('permanent')
        if permanent:
            self.series.permanent_rating = float(permanent.string)
            # todo: permanent votes
        mean = ratings_tag.find('temporary')
        if mean:
            self.series.mean_rating = float(mean.string)
            # todo: mean votes

    def _set_dates(self, start_tag: Tag, end_tag: Tag) -> None:
        if start_tag:
            start_parts = start_tag.string.split('-')
            if len(start_parts) == 3:
                self.series.start_date = datetime.strptime(start_tag.string, self.date_format).date()
            else:
                self.series.start_date = None
            if len(start_parts) >= 2:
                month = int(start_parts[1])
                self.series.season = self._get_anime_season(month)
            self.series.year = int(start_parts[0])
        if end_tag:
            if len(end_tag.string.split('-')) == 3:
                self.series.end_date = datetime.strptime(end_tag.string, self.date_format).date()
            else:
                self.series.end_date = None

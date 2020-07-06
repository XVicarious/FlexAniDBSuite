"""Class to parse AniDB tags."""
from typing import List, Optional

from bs4 import Tag
from flexget import plugin
from loguru import logger
from sqlalchemy.orm import Session

from .anidb_structs import DEFAULT_TAG_BLACKLIST
from .api_anidb import Anime, AnimeGenre, AnimeGenreAssociation
from .utils import select_parentid


class AnidbParserTags:
    """Class to parse AniDB tags."""

    session: Session
    series: Anime

    def _recurse_remove_tags(self, tags: List[Tag], tag_id: int) -> None:
        intermediate_tags: List[int] = [tag_id]
        idx = 0
        while idx < len(tags):
            tmp_tag = tags[idx]
            tmp_tag_id = int(tmp_tag['id'])
            tmp_tag_parent_id = (
                int(tmp_tag['parentid']) if 'parentid' in tmp_tag.attrs else 0
            )
            if tmp_tag_parent_id in intermediate_tags:
                intermediate_tags.append(tmp_tag_id)
                tags.remove(tmp_tag)
                idx = 0
                continue
            idx += 1

    def _remove_blacklist_tags(self, tags: List[Tag]) -> None:
        temp_tags = tags.copy()
        for tag in temp_tags:
            name = tag.find('name')
            name = name.string if name else ''
            tag_id = tag['id']
            logger.trace('Checking %s (%s)', name, tag_id)
            if tag_id in DEFAULT_TAG_BLACKLIST:
                logger.debug('{} ({}) in the blacklist... Taking action.', name, tag_id)
                if DEFAULT_TAG_BLACKLIST.get(tag_id):
                    logger.debug(
                        '{} ({}) is set to True... Recursively removing tags.',
                        name,
                        tag_id,
                    )
                    self._recurse_remove_tags(tags, tag_id)
                tags.remove(tag)

    def _get_genre_association(self, tag: Tag, weight: Optional[int]) -> None:
        tag_assoc = (
            self.session.query(AnimeGenreAssociation)
            .filter(
                AnimeGenreAssociation.anime_id == self.series.id_,
                AnimeGenreAssociation.genre_id == tag.id_,
            )
            .first()
        )
        if not tag_assoc:
            tag_assoc = AnimeGenreAssociation(tag, weight)
            self.series.genres.append(tag_assoc)
        if weight and tag_assoc.weight != weight:
            tag_assoc.weight = weight

    def _query_tag(self, anidb_id: int) -> Optional[AnimeGenre]:
        tag = (
            self.session.query(AnimeGenre)
            .filter(AnimeGenre.anidb_id == anidb_id,)
            .first()
        )
        return tag

    def _get_tag(self, anidb_id: int, name: str, just_query=False) -> AnimeGenre:
        db_tag = self._query_tag(anidb_id)
        if not db_tag and not just_query:
            logger.debug('{} is not in the tag list, adding', name)
            return AnimeGenre(anidb_id, name)
        return db_tag

    def _set_tags(self, tags_tags: List[Tag]) -> None:
        self._remove_blacklist_tags(tags_tags)
        tags_list = sorted(tags_tags, key=select_parentid)
        for tag in tags_list:
            name = tag.find('name').string if tag.find('name') else ''
            db_tag = self._get_tag(int(tag['id']), name)
            tag_parent_id = int(select_parentid(tag))
            if (
                tag_parent_id
                and tag_parent_id not in DEFAULT_TAG_BLACKLIST.keys()
                or tag_parent_id
                and not DEFAULT_TAG_BLACKLIST[tag_parent_id]
            ):
                parent_tag = self._query_tag(tag_parent_id)
                if parent_tag:
                    db_tag.parent_id = parent_tag.anidb_id
                else:
                    logger.trace(
                        'Genre %s parent genre, %s is not in the database yet. \
                         When it is found, it will be added',
                        name,
                        tag_parent_id,
                    )
                weight = int(tag['weight']) if 'weight' in tag.attrs else None
                self._get_genre_association(db_tag, weight)

"""Class to parse AniDB tags."""
import logging
from typing import List

from bs4 import Tag
from flexget import plugin
from flexget.logger import FlexGetLogger
from sqlalchemy.orm import Session

from .anidb_structs import DEFAULT_TAG_BLACKLIST
from .api_anidb import Anime, AnimeGenre, AnimeGenreAssociation

LOG: FlexGetLogger = logging.getLogger('anidb_parser')


class AnidbParserTags(object):
    """Class to parse AniDB tags."""

    session: Session
    series: Anime

    def _recurse_remove_tags(self, tags: List[Tag], tag_id: int) -> None:
        intermediate_tags = [tag_id]
        idx = 0
        while idx < len(tags):
            tmp_tag = tags[idx]
            tmp_tag_id = int(tmp_tag['id'])
            tmp_tag_parent_id = int(tmp_tag['parentid']) if 'parentid' in tmp_tag.attrs else 0
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
            LOG.trace('Checking %s (%s)', name, tag['id'])
            if tag['id'] in DEFAULT_TAG_BLACKLIST:
                LOG.debug('%s (%s) in the blacklist... Taking action.', name, tag['id'])
                if DEFAULT_TAG_BLACKLIST.get(tag['id']):
                    LOG.debug('%s (%s) is set to True... Recursively removing tags.', name, tag['id'])
                    self._recurse_remove_tags(tags, tag['id'])
                tags.remove(tag)

    def _select_parentid(self, tag: Tag) -> int:
        if 'parentid' in tag.attrs:
            return int(tag['parentid'])
        return 0

    def _get_genre_association(self, tag: Tag, weight: int) -> None:
        tag_assoc = self.session.query(AnimeGenreAssociation).filter(
                AnimeGenreAssociation.anime_id == self.series.id_,
                AnimeGenreAssociation.genre_id == tag.id_).first()
        if not tag_assoc:
            tag_assoc = AnimeGenreAssociation(tag, weight)
            self.series.genres.append(tag_assoc)
        if weight and tag_assoc.weight != weight:
            tag_assoc.weight = weight

    def _get_tag(self, anidb_id: int, name: str, just_query=False) -> AnimeGenre:
        db_tag = self.session.query(AnimeGenre).filter(
                AnimeGenre.anidb_id == anidb_id).first()
        if not (just_query or db_tag):
            LOG.debug('%s is not in the tag list, adding', name)
            db_tag = AnimeGenre(anidb_id, name)
        return db_tag

    def _set_tags(self, tags_tags: List[Tag]) -> None:
        if tags_tags is None:
            return plugin.PluginError('tags_tags is None')
        self._remove_blacklist_tags(tags_tags)
        tags_list = sorted(tags_tags, key=self._select_parentid)
        for tag in tags_list:
            name = tag.find('name').string if tag.find('name') else ''
            db_tag = self._get_tag(int(tag['id']), name)
            tag_parent_id = int(self._select_parentid(tag))
            if tag_parent_id and tag_parent_id not in DEFAULT_TAG_BLACKLIST.keys() or tag_parent_id and not DEFAULT_TAG_BLACKLIST[tag_parent_id]:
                parent_tag = self._get_tag(tag_parent_id, None, just_query=True)
                if parent_tag:
                    db_tag.parent_id = parent_tag.anidb_id
                else:
                    LOG.trace("""Genre %s parent genre, %s is not in the database yet. \
                              When it is found, it will be added""", name, tag_parent_id)
                weight = int(tag['weight']) if 'weight' in tag.attrs else None
                self._get_genre_association(db_tag, weight)

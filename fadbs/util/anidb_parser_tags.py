"""Class to parse AniDB tags."""
import logging

from flexget import plugin

from .api_anidb import AnimeGenre, AnimeGenreAssociation
from .anidb_structs import DEFAULT_TAG_BLACKLIST

LOG = logging.getLogger('anidb_parser')


class AnidbParserTags():
    """Class to parse AniDB tags."""

    def _recurse_remove_tags(self, tags, tag_id):
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

    def _remove_blacklist_tags(self, tags):
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

    def _select_parentid(self, tag):
        if 'parentid' in tag.attrs:
            return int(tag['parentid'])
        return 0

    def _get_genre_association(self, tag, weight):
        tag_assoc = self.session.query(AnimeGenreAssociation).filter(
                AnimeGenreAssociation.anime_id == self.series.id_,
                AnimeGenreAssociation.genre_id == tag.id_).first()
        if not tag_assoc:
            tag_assoc = AnimeGenreAssociation(tag, weight)
            self.series.genres.append(tag_assoc)
        if weight and tag_assoc.weight != weight:
            tag_assoc.weight = weight

    def _set_tags(self, tags_tags):
        if tags_tags is None:
            return plugin.PluginError('tags_tags is None')
        tags_tags = tags_tags.find_all('tag')
        self._remove_blacklist_tags(tags_tags)
        tags_list = sorted(tags_tags, key=self._select_parentid)
        for tag in tags_list:
            name = tag.find('name')
            name = name.string if name else ''
            db_tag = self.session.query(AnimeGenre).filter(
                    AnimeGenre.anidb_id == int(tag['id'])).first()
            if not db_tag:
                LOG.debug('%s is not in the tag list, adding', name)
                db_tag = AnimeGenre(int(tag['id']), name)
            tag_parent_id = int(self._select_parentid(tag))
            if tag_parent_id and tag_parent_id not in DEFAULT_TAG_BLACKLIST.keys():
                parent_tag = self.session.query(AnimeGenre).filter(
                        AnimeGenre.anidb_id == tag_parent_id).first()
                if parent_tag:
                    db_tag.parent_id = parent_tag.anidb_id
                else:
                    LOG.trace("""Genre %s parent genre, %s is not in the database yet. \
                              When it is found, it will be added""", name, tag_parent_id)
                weight = int(tag['weight']) if 'weight' in tag.attrs else None
                self._get_genre_association(db_tag, weight)

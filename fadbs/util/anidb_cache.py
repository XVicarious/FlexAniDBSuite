from __future__ import unicode_literals, division, absolute_import

from flexget.utils.cache import cached_resource


def get_anidb_cache(url):
    return cached_resource(url, '/home/xvicarious/PyProjects/FlexAniDBSuite/',
                           max_size=1024, directory='anidb_cache')[0]

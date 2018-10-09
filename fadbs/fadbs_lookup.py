from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event

from .anidb import AnidbParser


PLUGIN_ID = 'fadbs_lookup'

log = logging.getLogger(PLUGIN_ID)


class FadbsLookup(object):

    schema = {
        'type': 'object',
        'properties': {
            'name_language': {
                'type': 'string',
                'default': 'x-jat'
            },
            'ratings': {
                'type': 'string',
                'enum': ['permanent', 'mean'],
                'default': 'permanent'
            },
            'min_tag_weight': {
                'type': 'integer',
                'enum': [0, 100, 200, 300, 400, 500, 600],
                'default': 300
            }
        },
        'additionalProperties': False
    }

    def __init__(self):
        pass

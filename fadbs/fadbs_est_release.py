from __future__ import unicode_literals, division, absolute_import

import logging
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

from flexget import plugin
from flexget.event import event

PLUGIN_ID = 'fadbs_est_release'

log = logging.getLogger(PLUGIN_ID)


class EstimateSeriesAniDb(object):
    @plugin.priority(2)
    def estimate(self, entry):
        if not all(field in entry for field in ['series_name', 'series_season']):
            log.debug('Failed first entry :(')
            return
        for k in entry:
            log.debug('%s: %s', k, entry[k])


@event('plugin.register')
def register_plugin():
    plugin.register(EstimateSeriesAniDb, PLUGIN_ID, interfaces=['estimate_release'], api_ver=2)

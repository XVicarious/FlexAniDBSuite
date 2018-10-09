from __future__ import unicode_literals, division, absolute_import
from builtins import *  # noqa pylint: disable=unused-import, redefined-builtin

import logging

from flexget import plugin
from flexget.event import event
from flexget.utils.cached_input import cached
from flexget.entry import Entry

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException

PLUGIN_ID = 'fadbs_wishlist'

log = logging.getLogger(PLUGIN_ID)
USER_ID_RE = r'^\d{1,6}$'


class FadbsWishlist(object):
    """ Fetches your AniDB wishlist and gets the entries from it. """

    anidb_url = 'https://anidb.net/perl-bin/'

    schema = {
        'type': 'object',
        'properties': {
            'user_id': {
                'type': 'integer',
                'pattern': USER_ID_RE,
                'error_message': 'user_id must be in the form of XXXXXX'
            },
            'type': {
                'type': 'string',
                'enum': ['shows', 'movies'],
                'default': 'shows'
            },
            'mode': {
                'type': 'string',
                'enum': ['all', 'undefined', 'watch', 'get', 'blacklist', 'buddy'],
                'default': 'all'
            },
            'pass': {
                'type': 'string'
            },
            'strip_dates': {
                'type': 'boolean',
                'default': False
            }
        },
        'additionalProperties': False,
        'required': ['user_id'],
        'error_required': 'user_id is required'
    }

    def __mode_to_index(self, mode):
        if mode == 'buddy':
            return 11
        return self.schema['properties']['mode']['enum'].index(mode)

    @cached(PLUGIN_ID, persist='2 hours')
    def on_task_input(self, task, config):
        log.verbose('Retrieving AniDB list: wishlist:%s' % config['mode'])

        base_url = self.anidb_url + 'animedb.pl?show=mywishlist&uid=%s' % config['user_id']
        list_mode = '' if config['mode'] == 'all' else '&mode=%s' % self.__mode_to_index(config['mode'])
        list_pass = '' if config['pass'] is None else '&pass=%s' % config['pass']
        comp_link = base_url + list_mode + list_pass

        log.verbose('Opening the driver')
        driver = webdriver.Firefox()
        log.debug('Opening: %s' % comp_link)
        driver.get(comp_link)

        entries = []

        while True:
            list_items = driver.find_elements_by_xpath("//table[@class='wishlist']/tbody/tr")
            for item in list_items:
                entry = Entry()
                entry['id'] = item.get_attribute('id')[1:]  # Each TR's id is "a{aid}", so strip the first character
                for td in item.find_elements_by_tag_name('td'):
                    if 'name' in td.get_attribute('class'):
                        #
                        a_tag = td.find_element_by_tag_name('a')
                        entry['title'] = a_tag.text
                        entry['anidb_name'] = entry['title']
                        entry['type'] = td.find_element_by_xpath(".//span[@class='icons']/span/span").text
                        entry['url'] = self.anidb_url + a_tag.get_attribute('href')
                entries.append(entry)
            try:
                # fixme: this xpath works in firefox itself using $x(xpath), but isn't working here
                next_link = driver.find_element_by_xpath("//ul[contains(@class, 'jump')]/li[@class='next']/a")
            except NoSuchElementException:
                log.info('End of wishlist, we\'re done here.')
                break
            next_link = self.anidb_url + next_link.get_attribute('href')
            log.debug('Opening: %s' % next_link)
            driver.get(next_link)

        log.verbose('Closing the driver.')
        driver.close()

        return entries


@event('plugin.register')
def register_plugin():
    plugin.register(FadbsWishlist, PLUGIN_ID, api_ver=2, interfaces=['task'])

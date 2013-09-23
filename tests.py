# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals, division

# Newer unittest features aren't built in for python 2.6
import sys
if sys.version_info[:2] < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import os
os.environ['SC2BNET_CACHE_DIR'] = 'test_cache'
os.environ['SC2BNET_CACHE_TYPES'] = 'data,profile,ladder'

import requests
import sc2bnet


class Tests(unittest.TestCase):

    def test_grandmaster(self):
        ladder = sc2bnet.load_ladder('kr', 'grandmaster')

    def test_profile_and_ladder(self):
        profile = sc2bnet.load_profile('us', 2358439, 1, 'ShadesofGray')
        profile.load_ladders()
        profile.current_season.rankings[0].ladder.load_details()

    def test_invalid_bnet_id(self):
        with self.assertRaises(requests.HTTPError):
            sc2bnet.load_profile('us', 23589, 1, 'ShadesofGray')

    def test_nocache(self):
        cache = sc2bnet.NoCache()

        # All key access should raise KeyError
        with self.assertRaises(KeyError):
            cache['stuff']

        # Contain should always return false
        self.assertFalse('stuff' in cache)

        # And insertion should not actually do anything
        cache['stuff'] = 'not actually cached'
        self.assertFalse('stuff' in cache)

    def test_filecache(self):
        import os
        import shutil

        # reset the file cache directory each time. FileCache must
        # require that the directory exists.
        shutil.rmtree('test_filecache', ignore_errors=True)
        with self.assertRaises(ValueError):
            cache = sc2bnet.FileCache('test_filecache')
        os.makedirs('test_filecache')

        # Configure to use the test_cache directory and cache ladders
        cache = sc2bnet.FileCache('test_filecache', cache_types=['data', 'ladder'])
        value = dict(hello='world')

        # KeyError should be raised for bad keys
        with self.assertRaises(KeyError):
            value = cache[('a', 'b', 'c')]

        # But not for contains
        self.assertFalse(('a', 'b', 'c') in cache)

        # Ladders should be cached with this configuration
        key = ('us.battle.net', 'en_US', '/api/sc2/ladder/150982')
        cache[key] = value
        self.assertTrue(key in cache)
        self.assertEqual(value, cache[key])

        # Profiles should not be cached with this configuration
        key2 = ('us.battle.net', 'en_US', '/api/sc2/profile/150982/1/alsknflks')
        cache[key2] = value
        self.assertFalse(key2 in cache)

        # clean up
        shutil.rmtree('test_filecache', ignore_errors=True)

    @unittest.expectedFailure
    def test_sc2bnet_error(self):
        """ This should be giving an authentication error, instead getting 500 response."""
        with self.assertRaises(sc2bnet.SC2BnetError):
            factory = sc2bnet.SC2BnetFactory(public_key='sdlkf', private_key='sldkn')
            factory.load_profile('us', 2358439, 1, 'ShadesofGray')

    def test_script(self):
        sc2bnet.main("us --cache-path test_cache --cache-types data,ladder,profile profile 2358439 1 ShadesofGray".split())

if __name__ == '__main__':
    unittest.main()

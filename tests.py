# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals, division

# Newer unittest features aren't built in for python 2.6
import sys
if sys.version_info[:2] < (2, 7):
    import unittest2 as unittest
else:
    import unittest

import sc2bnet

class TestReplays(unittest.TestCase):

	def test_basic(self):
		pass
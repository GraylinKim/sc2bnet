.. currentmodule:: sc2bnet

Getting Started
==============================

All resources are loaded through the :class:`SC2BnetFactory` and resource helper methods.

Loaded resources have the following class Heirarchy::

    Profile
        Portrait - Icon
        Achievements
            Category
            Icon
        Rewards
            Icon
            Achievement
        Matches
        Seasons
            Teams
                PlayerProfiles
                TeamRankings
                    Ladder
    Ladder
        LadderRankings
            PlayerProfiles

Authentication is automatically performed on all requests when given a public and private key. There
are two ways to supply this information. You can set it in the environment prior to importing the
package for the first time::

    import os
    os.environ['SC2BNET_PUBLIC_KEY'] = 'mypublickey'
    os.environ['SC2BNET_PRIVATE_KEY'] = 'myprivatekey'

    import sc2bnet
    profile = sc2bnet.load_profile('us', 2358439, 1, 'ShadesofGray')

or you can create a new :class:`SC2BnetFactory` with the appropriate options::

    import sc2bnet
    bnet = sc2bnet.SC2BnetFactory(public_key='mypublickey', private_key='myprivatekey')

Likewise a cache can be used by specifying the ``SC2BNET_LOCAL_CACHE`` environment variable or by
specifying the ``cache`` option when creating a new factory.


SC2BnetFactory
---------------------

.. autoclass:: SC2BnetFactory
	:members:


Resources
======================

Player Profile
----------------

.. autoclass:: PlayerProfile
	:members:


Ladder
----------------

.. autoclass:: Ladder
	:members:


Achievement
-----------------

.. autoclass:: Achievement
	:members:


Reward
-----------------

.. autoclass:: Reward
	:members:


Support Objects
======================

Season
----------------

.. autoclass:: Season
	:members:


Ladder Ranking
----------------

.. autoclass:: LadderRanking
	:members:


Team
----------------

.. autoclass:: Team
	:members:


Team Ranking
----------------

.. autoclass:: TeamRanking
	:members:


Match
----------------

.. autoclass:: Match
	:members:


Achievement Category
----------------------------

.. autoclass:: AchievementCategory
        :members:


Portrait
-----------------

.. autoclass:: Ladder
	:members:


Icon
-----------------

.. autoclass:: Icon
	:members:


SC2BnetError
-----------------

.. autoclass:: SC2BnetError
	:members:


Contents:

.. toctree::
   :maxdepth: 2



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


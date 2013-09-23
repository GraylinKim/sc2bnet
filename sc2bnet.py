# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals, division

import base64
from datetime import datetime
import hashlib
import hmac
import itertools
import json
import os
import requests
import sys


HOST_BY_REGION = dict(
    us='us.battle.net',
    eu='eu.battle.net',
    kr='kr.battle.net',
    tw='tw.battle.net',
    ch='www.battlenet.com.cn',
    sea='sea.battle.net'
)

HOSTS_BY_LOCALE = dict(
    en_US=['us.battle.net', 'sea.battle.net'],
    es_MX=['us.battle.net'],
    pt_BR=['us.battle.net'],
    en_GB=['eu.battle.net'],
    es_ES=['eu.battle.net'],
    fr_FR=['eu.battle.net'],
    ru_RU=['eu.battle.net'],
    de_DE=['eu.battle.net'],
    pt_PT=['eu.battle.net'],
    pl_PL=['eu.battle.net'],
    it_IT=['eu.battle.net'],
    ko_KR=['kr.battle.net'],
    zh_TW=['tw.battle.net'],
    zh_CN=['www.battlenet.com.cn'],
)

DEFAULT_LOCALE_BY_HOST = {
    'sea.battle.net':'en_US',
    'us.battle.net':'en_US',
    'www.battlenet.com.cn':'zh_CN',
    'tw.battle.net':'zh_TW',
    'kr.battle.net':'ko_KR',
    'eu.battle.net':'en_GB',
}

LADDER_TYPES = dict(
    # FFA is unranked!
    HOTS_SOLO=("HotS", '1v1'),
    HOTS_TWOS=("HotS", '2v2'),
    HOTS_THREES=("HotS", '3v3'),
    HOTS_FOURS=("HotS", '4v4'),
    SOLO=("WoL", '1v1'),
    TWOS=("WoL", '2v2'),
    THREES=("WoL", '3v3'),
    FOURS=("WoL", '4v4'),
)


class SC2BnetError(Exception):
    """Thrown when there are errors in the Web API response."""
    def __init__(self, data):
        super(Exception, self).__init__("{0}: {1}".format(data['code'], data['message']))
        #: The full json response
        self.json = data

        #: The code from the response
        self.code = data['code']

        #: The message from the response
        self.message = data['message']


class NoCache(object):
    def __getitem__(self, key):
        raise KeyError(key)

    def __setitem__(self, key, value):
        pass

    def __contains__(self, key):
        return False


class FileCache(object):
    def __init__(self, cache_path, cache_types=None):
        self.cache_types = cache_types or ['data']
        self.cache_path = os.path.abspath(cache_path)
        if not os.path.exists(self.cache_path):
            raise ValueError("Cache path does not exist: "+self.cache_path)

    def __getitem__(self, key):
        data_type, path = self._get_info(key)
        if data_type in self.cache_types and os.path.exists(path):
            with open(path, 'r') as data_file:
                return json.load(data_file)
        else:
            raise KeyError(key)

    def __setitem__(self, key, value):
        data_type, path = self._get_info(key)
        if data_type in self.cache_types:
            if not os.path.exists(os.path.dirname(path)):
                os.makedirs(os.path.dirname(path))
            with open(path, 'w') as data_file:
                json.dump(value, data_file)

    def __contains__(self, key):
        data_type, path = self._get_info(key)
        if data_type in self.cache_types:
            return os.path.exists(path)
        else:
            return False

    def _get_info(self, key):
        host, locale, path = key
        parts = path[9:].strip("/").split("/")
        data_type = parts[0]
        data_key = '_'.join(parts[1:])
        cache_key = "{0}/{1}/{2}/{3}.json".format(host, locale, data_type, data_key)
        return data_type, os.path.join(self.cache_path, cache_key)


class SC2BnetFactory(object):
    """
    :param preferred_locale: The locale to use when available. Not all regions support all locals.
    :param app_key: Your application key. When non-null it is used to sign your requests to the Web API.
    :param cache_dir: The path to a pre-existing writable folder to cache responses in.
    """
    def __init__(self, preferred_locale=None, public_key=None, private_key=None, cache=None):
        self.cache = NoCache()
        self.preferred_locale = 'en_US'
        self.configure(preferred_locale, public_key, private_key, cache)

        self.__icon = dict()
        self.__reward = dict()
        self.__category = dict()
        self.__achievement = dict()

    def configure(self, preferred_locale=None, public_key=None, private_key=None, cache=None):
        self.public_key = public_key
        self.private_key = private_key
        if cache is not None:
            self.cache = cache
        if preferred_locale is not None:
            self.preferred_locale = preferred_locale

    def load_profile(self, region, bnet_id, realm, name):
        """Load a new :class:`PlayerProfile` using the given options. Profiles are not cached."""
        profile = PlayerProfile(region, bnet_id, realm, name, self)
        profile.load_details()
        return profile

    def load_ladder(self, region, ladder_id, last=False):
        """Load a new :class:`Ladder` from the given id. Ladders are not cached."""
        ladder = Ladder(region, ladder_id, self, last=last)
        ladder.load_details()
        return ladder

    @property
    def icon(self):
        """
        A nested dict of url -> offset -> :class:`Icon` containing all possible icons.
        Lazy loaded and cached in the factory locale.
        """
        if not self.__icon:
            for item in itertools.chain(self.achievement.values(), self.reward.values()):
                if item.icon.offset in self.__icon.get(item.icon.url, {}):
                    pass  # print("Reused Icon: {0}, {1}".format(item.icon.url, item.icon.offset))
                self.__icon.setdefault(item.icon.url, dict())[item.icon.offset] = item.icon
        return self.__icon

    @property
    def achievement(self):
        """
        A  dict of achivementId -> :class:`Achievement` containing all possible achievements.
        Lazy loaded and cached in the factory locale.
        """
        def add_category(category):
            self.__category[category.id] = category
            for subcategory in category.subcategories:
                add_category(subcategory)

        if not self.__achievement:
            data = self.load_data(self.default_host, "/api/sc2/data/achievements")
            for item in data['categories']:
                add_category(AchievementCategory(item, self))
            for item in data['achievements']:
                self.__achievement[item['achievementId']] = Achievement(item, self)
            for category in self.__category.values():
                achievement_id = category.featured_achievement_id
                if achievement_id in self.__achievement:
                    # print("Found {0}".format(achievement_id))
                    category.featured_achievement = self.__achievement[achievement_id]
                elif achievement_id != 0:
                    msg = "Unknown achievement id: {0} for category {1} [{2}]"
                    # print(msg.format(achievement_id, category.title, category.id))
            for achievement in self.__achievement.values():
                achievement.category = self.__category[achievement.category_id]
        return self.__achievement

    @property
    def reward(self):
        """
        A  dict of rewardId -> :class:`Reward` containing all possible rewards.
        Lazy loaded and cached in the factory locale.
        """
        if not self.__reward:
            data = self.load_data(self.default_host, "/api/sc2/data/rewards")
            for item in sum(data.values(), []):
                self.__reward[item['id']] = Reward(item, self)
        return self.__reward

    @property
    def default_host(self):
        return HOSTS_BY_LOCALE[self.preferred_locale][0]

    def load_data(self, host, path, refresh=False):
        # Figure out which localization to use
        if host in HOSTS_BY_LOCALE[self.preferred_locale]:
            locale = self.preferred_locale
        else:
            locale = DEFAULT_LOCALE_BY_HOST[host]

        # Check the cache for an entry
        cache_key = (host, locale, path)
        if not refresh and cache_key in self.cache:
            return self.cache[cache_key]

        # If they have supplied keys, sign the request using documented method:
        #   UrlPath = <HTTP-Request-URI, from the port to the query string>
        #   StringToSign = HTTP-Verb + "\n" +
        #       Date + "\n" +
        #       UrlPath + "\n";
        #   Signature = Base64( HMAC-SHA1( UTF-8-Encoding-Of( PrivateKey ), StringToSign ) );
        #   Header = "Authorization: BNET" + " " + PublicKey + ":" + Signature;
        headers = dict()
        if self.private_key and self.public_key:
            now = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S UTC')
            request_key = "GET\n{0}\n{1}\n".format(now, path).encode('utf8')
            signature = base64.b64encode(hmac.new(self.private_key.encode('utf8'), request_key, hashlib.sha1).digest())
            headers['Date'] = now
            headers['Authorization'] = "BNET {0}:{1}".format(self.public_key, signature)

        # Fetch new data, throwing any http errors upwards
        url = "https://"+host+path+"?locale="+locale
        response = requests.get(url, headers=headers, verify=True)

        try:
            # Try getting data first because many error codes will also have json details.
            data = response.json()

            # Make sure that the API returned an ok result.
            if data.get('status', None) == 'nok':
                raise SC2BnetError(data)
        except ValueError:
            # If the response isn't json it means the API didn't render the response
            # fall back on requests error protocols.
            response.raise_for_status()

            # If the response isn't json and we didn't have an http error code then panic
            raise

        # Replace any existing cache entries
        self.cache[cache_key] = data
        return data


class Achievement(object):
    """Represents a battle.net achievement"""
    def __init__(self, data, factory):
        #: The title of the achievement.
        self.title = data['title']

        #: The description of the achievement.
        self.description = data['description']

        #: The achievement's unique id.
        self.id = data['achievementId']

        #: The id of the achievement's category.
        self.category_id = data['categoryId']

        #: A reference to the achievement's :class:`AchievementCategory` object
        self.category = None

        #: The number of points granted by the achievement
        self.points = data['points']

        #: A reference to the :class:`Icon` for this achievement.
        self.icon = Icon(self.title, data['icon'], factory)


class AchievementCategory(object):
    """Represents a battle.net achievement category"""
    def __init__(self, data, factory):
        #: The category's unique id.
        self.id = data['categoryId']

        #: Categories can be nested arbitrarily deep. These are the category's subcategories
        self.subcategories = [AchievementCategory(d, factory) for d in data.get('children', [])]

        #: Categories can be represented by an icon from a featured achievement.
        #: Categories without featured achievements have a 0 here.
        self.featured_achievement_id = data['featuredAchievementId']

        #: A reference to the featured :class:`Achievement` object if applicable
        self.featured_achievement = None

        #: Category title
        self.title = data['title']


class Icon(object):
    """
    Represents an icon embedded in a compound image.

    TODO: Extract the actual icon, cache the compound image.
    """
    def __init__(self, title, data, factory):
        #: The working title for the icon
        self.title = title

        #: The x shift on the linked compound image for the top left corner of the icon
        self.x = data['x']

        #: The y shift on the linked compound image for the top left corner of the icon
        self.y = data['y']

        #: The width of the icon
        self.width = data['w']

        #: The height of the icon
        self.height = data['h']

        #: The index of the icon in an imaginary array of icon images counting from
        #: left to right, top to bottom on the linked compound image.
        self.offset = data['offset']

        #: The of the compound image the icon is contained in.
        self.url = data['url']


class Reward(object):
    """Represents a Battle.net reward."""
    def __init__(self, data, factory):
        #: The title of this award
        self.title = data['title']

        #: The unique id for this reward
        self.id = data['id']

        #: A reference to the :class:`Icon` for this award.
        self.icon = Icon(self.title, data['icon'], factory)

        #: The unique id of the achievement that unlocks this reward
        self.achievement_id = data['achievementId']

        #: A reference to the :class:`Achievement` that unlocks this reward. None if none needed.
        self.achievement = None
        if data['achievementId'] != 0:
            if data['achievementId'] not in factory.achievement:
                pass  # print("{0} not found".format(data['achievementId']))
            else:
                self.achievement = factory.achievement[data['achievementId']]


class PlayerProfile(object):
    """
        :param region: The player's region: us, eu, kr, tw, cn, or sea
        :param bnet_id: The player's unique battle.net id
        :param realm: The realm within the region the player is registered to. Generally a 1 or 2
        :param name: The player's current Battle.net name
        :param factory: A reference to the :class:`SC2BnetFactory` to use when constructing resources.

        This class should not be manually constructed, use :meth:`SC2BnetFactory.load_profile`.

        Create a new PlayerProfile with basic data. No web API calls are made by default. The
        :meth:`load_details`, :meth:`load_ladders`, and :meth:`load_matches` methods can be
        used to pull additional information from the Battle.net API.
    """

    def __init__(self, region, bnet_id, realm, name, factory):
        self._factory = factory

        #: The region of Battle.net this character belongs to
        self.region = region

        #: The character's unique Battle.net id.
        self.id = bnet_id

        #: The id for the character's home realm in the region
        self.realm = realm

        #: The character's current name
        self.name = name

        #: The html profile page on Battle.net
        self.link = "http://{host}/sc2/profile/{id}/{realm}/{name}/".format(host=HOST_BY_REGION[region], **self.__dict__)

        #: The name of the clan the player belongs to.
        self.clan_name = str()

        #: The tag of the clan the player belongs to.
        self.clan_tag = str()

        #: A reference to the :class:`Icon` object the player is currently using as a portrait
        self.portrait = None

        #: One of ZERG, PROTOSS, TERRAN, or RANDOM
        self.primary_race = str()

        #: Total career Terran wins.
        self.terran_wins = int()

        #: Total career Protoss wins.
        self.protoss_wins = int()

        #: Total career Zerg wins.
        self.zerg_wins = int()

        #: Total career games played.
        self.total_games = int()

        #: The current season number
        self.current_season_number = int()

        #: The number of games played this season
        self.current_season_game_count = int()

        #: The difficulty level used to complete the WoL campaign: CASUAL, NORMAL, HARD, or BRUTAL
        self.wol_campaign_completion = str()

        #: The difficulty level used to complete the HotS campaign: CASUAL, NORMAL, HARD, or BRUTAL
        self.hots_campaign_completion = str()

        #: The player's overall character level.
        self.combined_levels = int()

        #: The player's Terran character level.
        self.terran_level = int()

        #: The player's total Terran XP
        self.terran_total_xp = int()

        #: The player's current XP progress to the next Terran level. -1 if at max level.
        self.terran_level_xp = int()

        #: The player's Zerg character level.
        self.zerg_level = int()

        #: The player's total Zerg XP
        self.zerg_total_xp = int()

        #: The player's current XP progress to the next Zerg level. -1 if at max level.
        self.zerg_level_xp = int()

        #: The player's Protoss character level.
        self.protoss_level = int()

        #: The player's total Protoss XP
        self.protoss_total_xp = int()

        #: The player's current XP progress to the next Protoss level. -1 if at max level.
        self.protoss_level_xp = int()

        #: A dict of achivement -> completion date for achivements completed by this player.
        self.achievements = dict()

        #: The total point value of all achievements completed by this player.
        self.total_achievement_points = 0

        #: A dict category -> points that breaks the total achievement points down by category.
        self.achievement_points_by_category = dict()

        #: A list of rewards this player has earned
        self.rewards_earned = list()

        #: A list of the earned rewards selected to be showcased.
        self.rewards_selected = list()

        #: A list of recent matches played by the player
        self.recent_matches = list()

        #: The reference to the `Season` object for the current season
        self.current_season = None

        #: The reference to the `Season` object for the previous season
        self.previous_season = None

    def load_details(self):
        """
        Loads the majority of the player profile data. Everything except for
        :attr:`current_season`, :attr:`previous_season`, and :attr:`recent_matches`.
        """
        api_path = "/api/sc2/profile/{id}/{realm}/{name}/".format(**self.__dict__)
        data = self._factory.load_data(HOST_BY_REGION[self.region], api_path)
        self.clan_name = data['clanName']
        self.clan_tag = data['clanTag']
        self.portrait = self._factory.icon[data['portrait']['url']][data['portrait']['offset']]

        self.primary_race = data['career']['primaryRace']
        self.terran_wins = data['career']['terranWins']
        self.protoss_wins = data['career']['protossWins']
        self.zerg_wins = data['career']['zergWins']
        self.total_games = data['career']['careerTotalGames']

        self.current_season_number = data['season']['seasonId']
        self.current_season_game_count = data['season']['totalGamesThisSeason']

        self.wol_campaign_completion = data['campaign']['wol']
        self.hots_campaign_completion = data['campaign']['hots']

        self.combined_levels = data['swarmLevels']['level']
        self.terran_level = data['swarmLevels']['terran']['level']
        self.terran_total_xp = data['swarmLevels']['terran']['totalLevelXP']
        self.terran_level_xp = data['swarmLevels']['terran']['currentLevelXP']
        self.zerg_level = data['swarmLevels']['zerg']['level']
        self.zerg_total_xp = data['swarmLevels']['zerg']['totalLevelXP']
        self.zerg_level_xp = data['swarmLevels']['zerg']['currentLevelXP']
        self.protoss_level = data['swarmLevels']['protoss']['level']
        self.protoss_total_xp = data['swarmLevels']['protoss']['totalLevelXP']
        self.protoss_level_xp = data['swarmLevels']['protoss']['currentLevelXP']

        self.achievement_points_by_category = dict()
        self.total_achievement_points = data['achievements']['points']['totalPoints']
        for category_id, points in data['achievements']['points']['categoryPoints'].items():
            self.achievement_points_by_category[category_id] = points

        self.achievements = dict()
        for achievement_data in data['achievements']['achievements']:
            achievement = self._factory.achievement[achievement_data['achievementId']]
            self.achievements[achievement] = achievement_data['completionDate']

        self.rewards_earned = list()
        for reward_id in data['rewards']['earned']:
            reward = self._factory.reward[reward_id]
            self.rewards_earned.append(reward)

        self.rewards_selected = list()
        for reward_id in data['rewards']['selected']:
            reward = self._factory.reward[reward_id]
            self.rewards_selected.append(reward)

    def load_matches(self):
        """Loads recent matches into the :attr:`recent_matches` attribute."""
        api_path = "/api/sc2/profile/{id}/{realm}/{name}/matches".format(**self.__dict__)
        data = self._factory.load_data(HOST_BY_REGION[self.region], api_path)
        self.recent_matches = list()
        for match_data in data['matches']:
            self.recent_matches.append(Match(match_data, self._factory))

    def load_ladders(self):
        """
        Loads the current and previous season ladder data into
        :attr:`current_season` and :attr:`previous_season` respectively.
        """
        api_path = "/api/sc2/profile/{id}/{realm}/{name}/ladders".format(**self.__dict__)
        data = self._factory.load_data(HOST_BY_REGION[self.region], api_path)
        self.current_season = Season(data['currentSeason'], self, self.current_season_number, last=False)
        self.previous_season = Season(data['previousSeason'], self, self.current_season_number-1, last=True)


class Match(object):
    """Represents a single match played by a player."""
    def __init__(self, data, factory):
        #: The map the match was played on
        self.map = data['map']

        #: The type of match that was played. One of:
        #:
        #:  * CUSTOM - Arcade map
        #:  * CO_OP - VS AI
        #:  * THREES - 3v3 (can it tell between HotS and WoL?)
        #:  * ???
        self.type = data['type']

        #: The result of the match for the player. One of: WIN, LOSS, ??.
        self.result = data['decision']

        #: The effective game speed during the match. Generally FASTER.
        self.speed = data['speed']

        #: The date the match was played (in UTC?)
        self.end_time = datetime.fromtimestamp(data['date'])


class Season(object):
    """Represents the ranked ladder activity for a single person in one season on one region."""
    def __init__(self, data, profile, number, last=False):
        #: A backreference to the :class:`PlayerProfile` this season is for
        self.profile = profile

        #: Region this season is active on
        self.region = profile.region

        #: The season number
        self.number = number

        #: A list of :class:`Team` references for teams this player has played on this season.
        self.teams = [Team(item, self, profile._factory, last=last) for item in data]

        #: A list of :class:`TeamRanking` references for ladder rankings this season
        self.rankings = sum([team.rankings for team in self.teams], [])


class Team(object):
    """Represents a collection of players playing on a ranked ladder in one season."""
    def __init__(self, data, season, factory, last=False):
        #: The region this team is active in
        self.region = season.region

        #: A list of :class:`TeamPlacement` references for ladders the team is not yet placed into.
        self.placements = [TeamPlacement(item, self, factory) for item in data['nonRanked']]

        #: A back reference to the :class:`Season` this team is a part of.
        self.season = season

        #: A list of :class:`PlayerProfile` references for members of the team
        self.members = list()

        #: A list of :class:`TeamRanking` references for ranks achieved by this team in this season.
        self.rankings = [TeamRanking(item, self, factory, last=last) for item in data['ladder']]

        for item in data['characters']:
            character = PlayerProfile(self.region, item['id'], item['realm'], item['displayName'], factory)
            character.clan_name = item['clanName']
            character.clan_tag = item['clanTag']
            self.members.append(character)


class TeamPlacement(object):
    """Represents a team's placement matches from the profile/ladders view."""
    def __init__(self, data, team, factory):
        #: The region the team placement matches are on.
        self.region

        #: A reference to the :class:`Team` the ranking is for.
        self.team = team

        #: The queue this ladder draws opponents from.
        self.ladder_queue = data['mmq']

        info = LADDER_TYPES.get(self.ladder.queue, (None, None))

        #: The expansion the ladder is linked to. Only available when loaded through a profile.
        self.ladder_expansion = info[0]

        #: The type of teams for the ladder; 1v1, 2v2, 3v3, 4v4 (FFA is unranked).
        self.ladder_type = info[1]

        #: The number of placement matches currently completed
        self.games_played = data['gamesPlayed']


class TeamRanking(object):
    """Represents a team's ladder ranking from the profile/ladders view."""
    def __init__(self, data, team, factory, last=False):
        #: The region the team ranking is on.
        self.region = team.region

        #: A link to the corresponding :class:`Ladder`.
        self.ladder = Ladder(self.region, data['ladderId'], factory, last=last)
        self.ladder.name = data['ladderName']
        self.ladder.division = data['division']
        self.ladder.league = data['league']
        self.ladder.queue = data['matchMakingQueue']
        info = LADDER_TYPES.get(self.ladder.queue, (None, None))
        self.ladder.expansion = info[0]
        self.ladder.type = info[1]

        #: A reference to the :class:`Team` the ranking is for.
        self.team = team

        #: The current win total.
        self.wins = data['wins']

        #: The current loss total.
        self.losses = data['losses']

        #: The current rank of the team.
        self.rank = data['rank']

        #: True if this ranking is showcased in the player profile.
        self.showcase = data['showcase']


class Ladder(object):
    """Represents a single ladder in a single season."""
    def __init__(self, region, ladder_id, factory, last=False):
        #: The unique integer id for the ladder
        self.id = ladder_id

        #: The region the ladder is active on
        self.region = region

        #: The name of the ladder
        self.name = str()

        #: The division id of the ladder
        self.division = int()

        #: The league of the ladder: BRONZE, SILVER, GOLD, PLATINUM, DIAMOND, MASTER, GRANDMASTER
        self.league = str()

        #: The queue this ladder draws opponents from. Only available when loaded through a profile.
        self.queue = str()

        #: The expansion the ladder is linked to. Only available when loaded through a profile.
        self.expansion = None

        #: The type of teams for the ladder; 1v1, 2v2, 3v3, 4v4 (FFA is unranked).
        self.type = None

        #: A list of :class:`LadderRanking` on the ladder.
        self.rankings = list()

        #: A dict mapping rank -> :class:`LadderRanking`
        self.rank = dict()

        #: A boolean flag that is true of the team is arranged team.
        #: False if the team was partially random. None if not known
        self.arranged_team = None

        self._factory = factory

    def load_details(self):
        """Load additional ladder details from the Web API."""
        api_path = "/api/sc2/ladder/{0}".format(self.id)
        data = self._factory.load_data(HOST_BY_REGION[self.region], api_path)

        self.rankings = [LadderRanking(item, self, self._factory) for item in data['ladderMembers']]

         # TODO: Is this how their sorting really works? How are ties broken?
        self.rankings.sort(key=lambda r: r.points, reverse=True)
        for r, ranking in enumerate(self.rankings):
            self.rank[r+1] = ranking
            ranking.rank = r+1


class LadderRanking(object):
    """
    Represents a ladder ranking for a team. Depending on how the ladder ranking
    was loaded, different attributes are available.
    """
    def __init__(self, data, ladder, factory):
        #: The region this ladder ranking is on.
        self.region = ladder.region

        #: A reference to the :class:`Ladder` object this ranking is for.
        self.ladder = ladder

        item = data['character']
        character = PlayerProfile(self.region, item['id'], item['realm'], item['displayName'], factory)
        character.clan_name = item['clanName']
        character.clan_tag = item['clanTag']

        #: The players on the team for this ranking. Because of a bug in the WebAPI, there will only
        #: be one player here no matter how big the team. Hopefully a future update will fix this.
        self.players = [character]

        #: The current team rank.
        self.rank = None

        #: The previous team rank.
        self.previous_rank = data['previousRank']

        #: The highest team rank.
        self.highest_rank = data['highestRank']

        #: The current win total.
        self.wins = data['wins']

        #: The current loss total.
        self.losses = data['losses']

        #: The team's current point total.
        self.points = data['points']

        #: The time the team joined the ladder.
        self.join_time = datetime.fromtimestamp(data['joinTimestamp'])

        #: A list of the favored races for each player while playing in this ladder. One of TERRAN
        #: ZERG, PROTOSS; not sure if RANDOM is a valid race here.
        self.favorite_races = list()
        for pid in range(1, 9):
            key = "favoriteRaceP{0}".format(pid)
            if key in data:
                self.favorite_races.append(data[key])


def main(args=None):
    import argparse
    parser = argparse.ArgumentParser(description="Client for querying the battle.net API")
    parser.add_argument("region")
    parser.add_argument('--locale', default=None)
    parser.add_argument("--cache-path", default=None)
    parser.add_argument("--cache-types", default=None)
    parser.add_argument("--public-key", default=None)
    parser.add_argument("--private-key", default=None)
    parser.add_argument("--raw", action="store_true", default=False)

    subparsers = parser.add_subparsers(title="subcommands", help='sub-command help')

    profile_command = subparsers.add_parser('profile', help='PlayerProfile Arguments')
    profile_command.set_defaults(func=get_profile)
    profile_command.set_defaults(command="profile")
    profile_command.add_argument("id")
    profile_command.add_argument("realm")
    profile_command.add_argument("name")
    profile_command.add_argument("--details", action="store_true", default=False)
    profile_command.add_argument("--ladders", action="store_true", default=False)
    profile_command.add_argument("--matches", action="store_true", default=False)

    ladders_command = subparsers.add_parser('ladder', help='Ladder Arguments')
    ladders_command.set_defaults(func=get_ladder)
    ladders_command.set_defaults(command="ladder")
    ladders_command.add_argument("id")
    ladders_command.add_argument("--last", action="store_true", default=False, help="Only valid for grandmaster ladder rankings")

    args = parser.parse_args(args)

    if args.cache_path is not None:
        types = args.cache_types.lower().split(",") if args.cache_types else None
        cache = FileCache(args.cache_path, types)
    else:
        cache = NoCache()

    factory = SC2BnetFactory(args.locale, args.public_key, args.private_key, cache)
    args.func(args, factory)


def get_profile(args, factory):
    profile = factory.load_profile(args.region, args.id, args.realm, args.name)


def get_ladder(args, factory):
    ladder = factory.load_ladder(args.region, args.id)


def set_factory(factory):
    module = sys.modules[__name__]
    module.achievement = factory.achievement
    module.reward = factory.reward
    module.icon = factory.icon
    module.configure = factory.configure
    module.load_data = factory.load_data
    module.load_ladder = factory.load_ladder
    module.load_profile = factory.load_profile


locale = os.getenv('SC2BNET_LOCALE', None)
public_key = os.getenv('SC2BNET_PUBLIC_KEY', None)
private_key = os.getenv('SC2BNET_PRIVATE_KEY', None)
cache_dir = os.getenv('SC2BNET_CACHE_DIR', None)
cache_types = os.getenv('SC2BNET_CACHE_TYPES', None)
if cache_types is not None:
    cache_types = cache_types.split(",")
cache = FileCache(cache_dir, cache_types=cache_types) if cache_dir else NoCache()
set_factory(SC2BnetFactory(locale, public_key, private_key, cache))

"""ESPN's replaceable, unofficial fantasy/scoreboard adapter.

Validate appliedTotal against explicit full-PPR weights before using it:
custom leagues can change scoring. Raw-stat normalization is the fallback.
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.core.time import EASTERN, utcnow, weekly_window
from app.providers.base import GameData, PlayerData, ProjectionData, ProviderError, ResultData

TEAMS = {
    1: "ATL",
    2: "BUF",
    3: "CHI",
    4: "CIN",
    5: "CLE",
    6: "DAL",
    7: "DEN",
    8: "DET",
    9: "GB",
    10: "TEN",
    11: "IND",
    12: "KC",
    13: "LV",
    14: "LAR",
    15: "MIA",
    16: "MIN",
    17: "NE",
    18: "NO",
    19: "NYG",
    20: "NYJ",
    21: "PHI",
    22: "ARI",
    23: "PIT",
    24: "LAC",
    25: "SF",
    26: "SEA",
    27: "TB",
    28: "WSH",
    29: "CAR",
    30: "JAX",
    33: "BAL",
    34: "HOU",
}
POSITIONS = {2: "RB", 3: "WR", 4: "TE"}
# Passing, rushing, receiving, fumbles lost, 2-point conversions and return TDs.
PPR_WEIGHTS = {
    "3": Decimal("0.04"),
    "4": Decimal(4),
    "20": Decimal(-2),
    "24": Decimal("0.1"),
    "25": Decimal(6),
    "42": Decimal("0.1"),
    "43": Decimal(6),
    "53": Decimal(1),
    "72": Decimal(-2),
    "19": Decimal(2),
    "26": Decimal(2),
    "44": Decimal(2),
    "63": Decimal(6),
    "101": Decimal(6),
    "102": Decimal(6),
}


def full_ppr(stats: dict) -> Decimal:
    return sum(
        (Decimal(str(stats.get(key, 0))) * weight for key, weight in PPR_WEIGHTS.items()),
        Decimal(0),
    )


def record_ppr(record: dict) -> Decimal:
    normalized = full_ppr(record.get("stats", {}))
    supplied = record.get("appliedTotal")
    if supplied is not None:
        total = Decimal(str(supplied))
        if total.is_finite() and abs(total - normalized) <= Decimal("0.000001"):
            return total
    return normalized


def parse_player(item: dict) -> PlayerData | None:
    data = item.get("player", item)
    position = POSITIONS.get(data.get("defaultPositionId"))
    team = TEAMS.get(data.get("proTeamId"))
    if not position or not team:
        return None
    return PlayerData(
        str(data["id"]),
        data["fullName"],
        team,
        position,
        data.get("active", True),
        {"injury_status": data.get("injuryStatus")},
    )


def stat_record(item, season, week, source):
    data = item.get("player", item)
    return next(
        (
            s
            for s in data.get("stats", [])
            if s.get("seasonId") == season
            and s.get("scoringPeriodId") == week
            and s.get("statSourceId") == source
            and s.get("statSplitTypeId") == 1
        ),
        None,
    )


class ESPNProvider:
    name = "espn"

    def __init__(self, client=None):
        settings = get_settings()
        self.league = settings.espn_league_id
        self.client = client or httpx.Client(
            timeout=30,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Referer": "https://fantasy.espn.com/",
            },
            cookies={
                k: v
                for k, v in {"SWID": settings.espn_swid, "espn_s2": settings.espn_s2}.items()
                if v
            },
        )
        self.cache: dict = {}

    def _get(self, url, *, params=None, headers=None, ttl=120):
        key = json.dumps([url, params, headers], sort_keys=True)
        cached = self.cache.get(key)
        if cached and time.monotonic() - cached[0] < ttl:
            return cached[1]
        for attempt in range(3):
            try:
                response = self.client.get(url, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()
                self.cache[key] = (time.monotonic(), data)
                return data
            except (httpx.HTTPError, ValueError) as error:
                if isinstance(error, httpx.HTTPStatusError) and error.response.status_code < 500:
                    raise ProviderError(
                        f"ESPN returned HTTP {error.response.status_code}."
                    ) from None
                if attempt == 2:
                    raise ProviderError(
                        "ESPN is temporarily unavailable or returned invalid data."
                    ) from None
                time.sleep(0.5 * (attempt + 1))

    def _scoreboard(self, season=None, week=None):
        params = {"limit": 1000}
        if season is not None:
            params.update({"dates": season, "seasontype": 2, "week": week})
        data = self._get(
            "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard", params=params
        )
        if not isinstance(data, dict) or "events" not in data:
            raise ProviderError("ESPN scoreboard format changed.")
        return data

    def get_nfl_state(self):
        data = self._get("https://sports.core.api.espn.com/v2/sports/football/leagues/nfl", ttl=300)
        season_data = data.get("season", {})
        period = season_data.get("type", {})
        if period.get("type") != 2:
            raise ProviderError("The current ESPN period is outside the NFL regular season.")
        season, week = int(season_data["year"]), int(period["week"]["number"])
        # ESPN may keep showing the just-finished week through Tuesday. Advance
        # based on our Tuesday opening rule, never from a guessed calendar week.
        start = (
            datetime.fromisoformat(period["week"]["startDate"].replace("Z", "+00:00"))
            .astimezone(EASTERN)
            .date()
        )
        sunday = start + timedelta(days=(6 - start.weekday()) % 7)
        if week < 18:
            next_opens, _ = weekly_window(sunday + timedelta(days=7))
            if utcnow() >= next_opens:
                week += 1
        return season, week

    def get_schedule(self, season, week):
        # Core API remains available when the site scoreboard CDN rejects a request.
        try:
            return self._core_schedule(season, week)
        except ProviderError:
            return self._site_schedule(season, week)

    def _ref(self, reference, ttl=120):
        url = reference["$ref"]
        parsed = urlparse(url)
        if parsed.hostname != "sports.core.api.espn.com" or parsed.port not in {None, 80, 443}:
            raise ProviderError("Unexpected ESPN resource host.")
        return self._get(url.replace("http://", "https://", 1), ttl=ttl)

    def _core_schedule(self, season, week):
        listing = self._get(
            f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/{season}/types/2/weeks/{week}/events",
            params={"limit": 1000},
        )
        items = listing.get("items", [])
        if not items or listing.get("pageCount", 1) != 1:
            raise ProviderError("ESPN returned an empty or incomplete schedule.")

        def load(reference):
            event = self._ref(reference)
            competition = event["competitions"][0]
            teams = {c["homeAway"]: TEAMS[int(c["id"])] for c in competition["competitors"]}
            status = competition.get("status", {})
            if "$ref" in status:
                status = self._ref(status)
            status = status.get("type", {})
            if not status:
                raise ProviderError("ESPN did not supply a game status.")
            return GameData(
                str(event["id"]),
                teams["home"],
                teams["away"],
                datetime.fromisoformat(event["date"].replace("Z", "+00:00")),
                "FINAL"
                if status.get("completed")
                else "LIVE"
                if status.get("state") == "in"
                else "NOT_STARTED",
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            return list(pool.map(load, items))

    def _site_schedule(self, season, week):
        data = self._scoreboard(season, week)
        games = []
        for event in data["events"]:
            competition = event["competitions"][0]
            teams = {
                c["homeAway"]: TEAMS.get(int(c["team"]["id"]), c["team"]["abbreviation"])
                for c in competition["competitors"]
            }
            status = event["status"]["type"]
            games.append(
                GameData(
                    str(event["id"]),
                    teams["home"],
                    teams["away"],
                    datetime.fromisoformat(event["date"].replace("Z", "+00:00")),
                    "FINAL"
                    if status.get("completed")
                    else "LIVE"
                    if status.get("state") == "in"
                    else "NOT_STARTED",
                )
            )
        if not games:
            raise ProviderError("ESPN returned an empty NFL schedule.")
        return games

    def _players(self, season, week, ttl=120, source=0):
        filters = {
            "players": {
                "limit": 500,
                "offset": 0,
                "sortPercOwned": {"sortPriority": 1, "sortAsc": False},
                "filterSlotIds": {"value": [2, 4, 6]},
                "filterStatsForSourceIds": {"value": [source]},
                "filterStatsForTopScoringPeriodIds": {
                    "value": 18,
                    "additionalValue": [f"00{season}", f"10{season}"],
                },
            }
        }
        if source == 1:
            del filters["players"]["filterStatsForTopScoringPeriodIds"]
            filters["players"]["filterStatsForExternalIds"] = {"value": [int(f"{season}{week}")]}
        url = (
            f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}/segments/0/"
        )
        url += f"leagues/{self.league}" if self.league else "leaguedefaults/3"
        players, seen = [], set()
        for offset in range(0, 10000, 500):
            filters["players"]["offset"] = offset
            data = self._get(
                url,
                params={"view": "kona_player_info", "scoringPeriodId": week},
                headers={"x-fantasy-filter": json.dumps(filters)},
                ttl=ttl,
            )
            if not isinstance(data, dict) or not isinstance(data.get("players"), list):
                raise ProviderError("ESPN fantasy player format changed.")
            if data.get("seasonId", season) != season:
                raise ProviderError("ESPN returned a different season than requested.")
            batch = data["players"]
            for item in batch:
                pid = item.get("player", item)["id"]
                if pid in seen:
                    raise ProviderError(
                        "ESPN pagination repeated a player; refusing a partial snapshot."
                    )
                seen.add(pid)
            players.extend(batch)
            if len(batch) < 500:
                break
        else:
            raise ProviderError("ESPN player pool exceeded the supported import size.")
        if not players:
            raise ProviderError("ESPN returned an empty player pool.")
        return players

    def get_players(self, season):
        return [p for item in self._players(season, 1, ttl=86400) if (p := parse_player(item))]

    def get_week_projections(self, season, week):
        rows = []
        for item in self._players(season, week, source=1):
            player, record = parse_player(item), stat_record(item, season, week, 1)
            if player and record and record.get("stats"):
                rows.append(ProjectionData(player, record_ppr(record), record))
        if not rows:
            raise ProviderError("ESPN has no weekly projections for the requested week.")
        return rows

    def get_week_results(self, season, week):
        rows = []
        for item in self._players(season, week):
            player, record = parse_player(item), stat_record(item, season, week, 0)
            if player and record is not None:
                rows.append(ResultData(player.id, record_ppr(record), record))
        if not rows:
            raise ProviderError("ESPN has not published results for the requested week.")
        return rows

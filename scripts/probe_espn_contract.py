"""Read-only, compact diagnostics for ESPN request contracts."""
import json
import httpx

with httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Referer": "https://fantasy.espn.com/"}) as client:
    url = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026/segments/0/leaguedefaults/3"
    for variant in ("external", "period", "all"):
        f = {"players": {"limit": 2, "sortPercOwned": {"sortPriority": 1, "sortAsc": False}, "filterSlotIds": {"value": [2, 4, 6]}}}
        if variant == "external":
            f["players"]["filterStatsForExternalIds"] = {"value": [2026, 20263]}
        if variant == "period":
            f["players"]["filterStatsForTopScoringPeriodIds"] = {"value": 18, "additionalValue": ["002026", "102026"]}
        response = client.get(url, params={"view": "kona_player_info", "scoringPeriodId": 3}, headers={"x-fantasy-filter": json.dumps(f)})
        print(variant, response.status_code)
        if response.is_success:
            p = response.json()["players"][0]["player"]
            print(p["fullName"], [(s["seasonId"], s["scoringPeriodId"], s["statSourceId"], s["externalId"]) for s in p.get("stats", [])])
    scoreboard = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
    for headers in (None, {"x-fantasy-filter": json.dumps({"players": {"limit": 2, "sortPercOwned": {"sortPriority": 1, "sortAsc": False}}})}):
        for params in ({"limit": 1000}, {"limit": 1000, "dates": 2026, "seasontype": 2, "week": 3}):
            response = client.get(scoreboard, params=params, headers=headers)
            print("scoreboard", bool(headers), str(response.url), response.status_code)
    for url in ["https://sports.core.api.espn.com/v2/sports/football/leagues/nfl", "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events/401872948?lang=en&region=us"]:
        response = client.get(url)
        print("core", response.status_code)
        if response.is_success:
            data = response.json()
            print("keys", list(data))
            print(json.dumps({k: data[k] for k in ("season", "week", "date", "competitions") if k in data})[:4000])

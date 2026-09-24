"""Read-only provider diagnostic; never prints cookies or credentials."""
import json
import httpx

headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Referer": "https://fantasy.espn.com/"}
with httpx.Client(headers=headers, timeout=20, follow_redirects=True) as client:
    urls = [
        "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
        "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=2026&seasontype=2&week=3",
        "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026/segments/0/leaguedefaults/3?view=kona_player_info&scoringPeriodId=3",
        "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2025/segments/0/leaguedefaults/3?view=kona_player_info&scoringPeriodId=3",
        "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2026/players?view=kona_player_info&scoringPeriodId=3",
        "https://fantasy.espn.com/apis/v3/games/ffl/seasons/2026/segments/0/leaguedefaults/3?view=kona_player_info&scoringPeriodId=3",
        "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?limit=1000",
        "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2026/types/2/weeks/3/events?limit=1000",
    ]
    for url in urls:
        try:
            response = client.get(url, headers={"x-fantasy-filter": json.dumps({"players": {"limit": 2, "sortPercOwned": {"sortPriority": 1, "sortAsc": False}}})})
            print(url, response.status_code)
            if not response.is_success:
                print(response.text[:400])
            if response.is_success:
                data = response.json()
                print("shape", type(data).__name__, "count", len(data))
                if isinstance(data, list):
                    sample = next((p for p in data if p.get("defaultPositionId") == 2 and p.get("active")), data[0])
                    print("sample", sample.get("fullName"), "stats", len(sample.get("stats", [])))
                elif "players" in data:
                    print("players", len(data["players"]))
                else:
                    print(json.dumps({k: data[k] for k in ["season", "week"] if k in data}))
                    print("event count", len(data.get("events", [])))
                    print("sample", json.dumps(data.get("items", [])[:1]))
        except (httpx.HTTPError, ValueError) as e:
            print(type(e).__name__)

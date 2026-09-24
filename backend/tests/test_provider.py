from decimal import Decimal

import httpx
import pytest

from app.providers.base import ProviderError
from app.providers.csv_provider import CSVProvider
from app.providers.espn import ESPNProvider, full_ppr, record_ppr, stat_record


def test_ppr_not_league_applied_total():
    stats = {"24": 85, "25": 1, "42": 42, "43": 1, "53": 5, "72": 1}
    assert full_ppr(stats) == Decimal("27.7")


def test_return_touchdowns_and_no_yardage_or_long_td_bonus():
    assert full_ppr({"101": 1, "102": 1, "63": 1, "46": 1, "47": 20}) == Decimal(18)


def test_supplied_total_used_only_when_it_is_full_ppr():
    assert record_ppr({"stats": {"53": 5, "42": 50}, "appliedTotal": 10.0000001}) == Decimal(
        "10.0000001"
    )
    assert record_ppr({"stats": {"53": 5, "42": 50}, "appliedTotal": 5}) == Decimal(10)


def test_projection_filter_requests_exact_week():
    import json

    def handle(request):
        filters = json.loads(request.headers["x-fantasy-filter"])["players"]
        assert filters["filterStatsForExternalIds"]["value"] == [20263]
        assert "sortPercOwned" in filters
        return httpx.Response(
            200,
            json={
                "players": [
                    {
                        "player": {
                            "id": 1,
                            "fullName": "Test Runner",
                            "defaultPositionId": 2,
                            "proTeamId": 33,
                            "stats": [
                                {
                                    "seasonId": 2026,
                                    "scoringPeriodId": 3,
                                    "statSourceId": 1,
                                    "statSplitTypeId": 1,
                                    "stats": {"24": 100},
                                }
                            ],
                        }
                    }
                ]
            },
        )

    assert (
        ESPNProvider(httpx.Client(transport=httpx.MockTransport(handle)))
        .get_week_projections(2026, 3)[0]
        .projected_ppr
        == 10
    )


def test_week_and_source_isolation():
    records = [
        {
            "seasonId": 2026,
            "scoringPeriodId": 3,
            "statSourceId": source,
            "statSplitTypeId": 1,
            "stats": {"53": source + 1},
        }
        for source in [0, 1]
    ]
    assert stat_record({"player": {"stats": records}}, 2026, 3, 0)["stats"]["53"] == 1
    assert stat_record({"stats": records}, 2026, 4, 1) is None


def test_provider_contract_projection_vs_actual():
    def handle(request):
        return httpx.Response(
            200,
            json={
                "seasonId": 2026,
                "players": [
                    {
                        "player": {
                            "id": 1,
                            "fullName": "Test Runner",
                            "defaultPositionId": 2,
                            "proTeamId": 33,
                            "stats": [
                                {
                                    "seasonId": 2026,
                                    "scoringPeriodId": 3,
                                    "statSourceId": s,
                                    "statSplitTypeId": 1,
                                    "stats": {"24": 100 * (s + 1)},
                                    "appliedTotal": 999,
                                }
                                for s in [0, 1]
                            ],
                        }
                    }
                ],
            },
        )

    provider = ESPNProvider(httpx.Client(transport=httpx.MockTransport(handle)))
    assert provider.get_week_projections(2026, 3)[0].projected_ppr == 20
    assert provider.get_week_results(2026, 3)[0].actual_ppr == 10


def test_provider_failure_is_explicit():
    provider = ESPNProvider(
        httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(403)))
    )
    with pytest.raises(ProviderError, match="403"):
        provider.get_week_projections(2026, 3)


def test_csv_timezone_and_duplicate_validation():
    header = (
        "provider_player_id,player_name,team,position,opponent,kickoff_at,projected_ppr_points\n"
    )
    row = "1,Player,BAL,RB,CIN,2026-09-27T17:00:00Z,12.5\n"
    csv = CSVProvider(header + row, 2026, 3)
    assert csv.get_week_projections(2026, 3)[0].projected_ppr == Decimal("12.5")
    with pytest.raises(ProviderError):
        CSVProvider(header + row + row, 2026, 3)
    with pytest.raises(ProviderError):
        CSVProvider(header + row.replace("17:00:00Z", "17:00:00"), 2026, 3)

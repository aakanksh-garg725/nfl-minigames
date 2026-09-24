from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.auth import current_user
from app.core.db import get_db
from app.core.time import aware
from app.main import app
from app.models import LineupSlot, NFLWeek, Player, PlayerResult, Profile, WeeklyEntry
from app.services import scoring
from app.services.rules import SLOTS


@pytest.fixture
def shared(db):
    week = db.scalar(select(NFLWeek))
    db.add(Profile(user_id="other-player", username="other_fan", favorite_team="BAL"))
    entry = WeeklyEntry(
        user_id="other-player",
        season=week.season,
        week=week.week,
        status="COMPLETE",
        completed_at=aware(week.opens_at) + timedelta(minutes=1),
    )
    db.add(entry)
    db.flush()
    players = list(db.scalars(select(Player).limit(6)))
    for index, (slot, player) in enumerate(zip(SLOTS, players)):
        db.add(
            LineupSlot(
                entry_id=entry.id,
                slot=slot,
                player_id=player.id,
                projection_when_acquired=15,
                acquisition_method="DEAL",
            )
        )
        db.add(
            PlayerResult(
                player_id=player.id,
                season=week.season,
                week=week.week,
                actual_ppr=Decimal(index - 1),
                game_status="LIVE",
                provider="test",
            )
        )
    db.flush()
    scoring.recompute(db, week.season, week.week)
    db.commit()
    return week, entry


@pytest.fixture
def client(db, user):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[current_user] = lambda: user
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def lineup_url(week, user_id="other-player"):
    return f"/api/v1/leaderboards/weekly/{week.season}/{week.week}/lineups/{user_id}"


def test_current_leaderboard_lineup_read_only_and_live_scores(client, db, shared):
    week, entry = shared
    response = client.get(lineup_url(week))
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "other_fan"
    assert data["score"] == 9
    assert [s["slot"] for s in data["slots"]] == list(SLOTS)
    assert all(set(s) == {"slot", "player", "actual_ppr", "game_status"} for s in data["slots"])
    assert not {"email", "entry", "entry_id", "user_id"}.intersection(data)
    assert all(s["player"]["opponent"] for s in data["slots"])
    assert all(isinstance(s["player"]["is_home"], bool) for s in data["slots"])
    result = db.scalar(
        select(PlayerResult).where(PlayerResult.player_id == data["slots"][0]["player"]["id"])
    )
    result.actual_ppr = 10
    db.commit()
    # Totals and player rows use the same latest results, even before rank recalculation.
    updated = client.get(lineup_url(week)).json()
    assert updated["score"] == 20
    assert updated["slots"][0]["actual_ppr"] == 10
    assert client.post(lineup_url(week), json={}).status_code == 405
    assert client.get(lineup_url(week, "missing")).status_code == 404


@pytest.mark.parametrize("invalid", ["incomplete", "missing_slot", "late", "wrong_game"])
def test_non_leaderboard_entries_are_not_shared(client, db, shared, invalid):
    week, entry = shared
    if invalid == "incomplete":
        entry.status = "IN_PROGRESS"
    elif invalid == "missing_slot":
        db.scalar(select(LineupSlot).where(LineupSlot.entry_id == entry.id)).player_id = None
    elif invalid == "late":
        entry.completed_at = week.closes_at
    else:
        entry.game_type = "OTHER"
    db.commit()
    assert client.get(lineup_url(week)).status_code == 404


def test_historical_and_future_lineups_are_not_shared(client, shared):
    week, _ = shared
    for year, number in [
        (week.season - 1, week.week),
        (week.season, week.week - 1),
        (week.season, week.week + 1),
    ]:
        assert (
            client.get(
                f"/api/v1/leaderboards/weekly/{year}/{number}/lineups/other-player"
            ).status_code
            == 404
        )


def test_lineup_view_requires_signin(client, shared):
    def unauthenticated():
        raise HTTPException(401, "Sign in required")

    app.dependency_overrides[current_user] = unauthenticated
    assert client.get(lineup_url(shared[0])).status_code == 401


def test_weekly_leaderboard_totals_acquired_projections_separately(client, db, shared):
    week, entry = shared
    url = f"/api/v1/leaderboards/weekly?season={week.season}&week={week.week}"
    row = client.get(url).json()["rows"][0]
    assert row["projected_score"] == 90
    assert row["score"] == 9
    slots = list(db.scalars(select(LineupSlot).where(LineupSlot.entry_id == entry.id)))
    slots[0].projection_when_acquired = Decimal("15.125")
    slots[1].projection_when_acquired = None
    db.commit()
    updated = client.get(url).json()["rows"][0]
    assert updated["projected_score"] == 75.125
    assert updated["score"] == row["score"]
    assert updated["rank"] == row["rank"]
    # Historical weeks keep their own acquired projections, not current ESPN values.
    entry.status = "FINAL"
    db.commit()
    assert client.get(url).json()["rows"][0]["projected_score"] == 75.125
    season = scoring.season_leaderboard(db, week.season)
    assert "projected_score" not in season["rows"][0]

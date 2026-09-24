from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.auth import current_user
from app.core.db import get_db
from app.core.time import aware
from app.main import app, limited_user
from app.models import (
    LineupSlot,
    NFLWeek,
    Player,
    PlayerResult,
    Profile,
    RivalryMatchup,
    WeeklyEntry,
)
from app.services import rivalries, scoring
from app.services.rules import RuleError


@pytest.fixture
def rivals(db, user):
    for name in ["opponent", "second", "outsider"]:
        db.add(Profile(user_id=name, username=name, favorite_team="SEA"))
    db.commit()
    week = db.scalar(select(NFLWeek))
    now = aware(week.opens_at) + timedelta(days=1)
    return user, "opponent", now


def accepted(db, rivals, opponent="opponent"):
    user, _, now = rivals
    invite = rivalries.invite(db, user, opponent, now)
    rivalries.respond(db, opponent, invite.id, "ACCEPT", now)
    return invite


def test_current_unlocked_week_acceptance_and_all_remaining_history(db, rivals):
    rivalry = accepted(db, rivals)
    assert rivalry.start_week == 3
    assert db.scalar(select(func.count()).select_from(RivalryMatchup)) == 16
    assert rivalries.public_rivalry(db, rivalry, rivals[0])["record"] == {
        "wins": 0,
        "losses": 0,
        "ties": 0,
    }


def test_matchup_lineups_are_viewer_relative_private_and_week_scoped(db, rivals):
    rivalry = accepted(db, rivals)
    _, players = setup_scores(db, rivals, own=12, opponent=-1)
    scoring.recompute(db, 2026, 4)
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[current_user] = lambda: rivals[0]
    try:
        client = TestClient(app)
        url = f"/api/v1/rivalries/{rivalry.id}/matchups/4"
        response = client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "FINAL"
        assert data["you"]["score"] == 12
        assert data["opponent"]["score"] == -1
        assert data["you"]["slots"][0]["player"]["id"] == players[0].id
        assert data["opponent"]["slots"][0]["player"]["id"] == players[1].id
        assert "deal_game_id" not in data["opponent"]["slots"][0]
        assert "email" not in data["opponent"]
        assert data["weeks"] == list(range(3, 19))
        empty = client.get(url.replace("/4", "/3")).json()
        assert empty["you"]["slots"] == []
        assert empty["you"]["score"] == 0
        assert client.get(url.replace("/4", "/2")).status_code == 404
        app.dependency_overrides[current_user] = lambda: "opponent"
        inverse = client.get(url).json()
        assert inverse["you"] == data["opponent"]
        assert inverse["opponent"] == data["you"]
        app.dependency_overrides[current_user] = lambda: "outsider"
        assert client.get(url).status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_pending_invitation_cannot_expose_lineups(db, rivals):
    invitation = rivalries.invite(db, rivals[0], "opponent", rivals[2])
    with pytest.raises(RuleError, match="Matchup not found"):
        rivalries.matchup_detail(db, rivals[0], invitation.id, 3)


def test_acceptance_date_not_invitation_date_controls_start(db, rivals):
    user, opponent, now = rivals
    invitation = rivalries.invite(db, user, opponent, now)
    rivalries.respond(db, opponent, invitation.id, "ACCEPT", now + timedelta(days=7))
    assert invitation.start_week == 4


def test_multiple_opponents_and_reversed_duplicate(db, rivals):
    first = accepted(db, rivals)
    second = accepted(db, rivals, "second")
    assert first.id != second.id
    with pytest.raises(RuleError, match="already exists"):
        rivalries.invite(db, "opponent", "local_player", rivals[2])


@pytest.mark.parametrize("username", ["local_player", "missing"])
def test_no_self_or_missing_user_invitation(db, rivals, username):
    with pytest.raises(RuleError):
        rivalries.invite(db, rivals[0], username, rivals[2])


def test_only_recipient_accepts_and_only_sender_cancels(db, rivals):
    user, opponent, now = rivals
    invitation = rivalries.invite(db, user, opponent, now)
    for actor, decision in [
        (user, "ACCEPT"),
        (user, "DECLINE"),
        (opponent, "CANCEL"),
        ("outsider", "ACCEPT"),
    ]:
        with pytest.raises(RuleError):
            rivalries.respond(db, actor, invitation.id, decision, now)
    rivalries.respond(db, opponent, invitation.id, "DECLINE", now)
    assert invitation.status == "DECLINED"
    renewed = rivalries.invite(db, user, opponent, now)
    rivalries.respond(db, user, renewed.id, "CANCEL", now)
    assert renewed.status == "CANCELED"


def test_repeated_acceptance_creates_no_duplicate_weeks(db, rivals):
    rivalry = accepted(db, rivals)
    with pytest.raises(RuleError):
        rivalries.respond(db, "opponent", rivalry.id, "ACCEPT", rivals[2])
    assert db.scalar(select(func.count()).select_from(RivalryMatchup)) == 16


def test_private_api_history_and_rename(db, rivals):
    rivalry = accepted(db, rivals)
    db.get(Profile, "opponent").username = "renamed"
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[current_user] = lambda: "outsider"
    app.dependency_overrides[limited_user] = lambda: "outsider"
    try:
        client = TestClient(app)
        assert client.get(f"/api/v1/rivalries/{rivalry.id}").status_code == 404
        assert client.get("/api/v1/rivalries?season=2026").json()["rivalries"] == []
        assert (
            client.post(
                f"/api/v1/rivalries/{rivalry.id}/decision", json={"decision": "ACCEPT"}
            ).status_code
            == 404
        )
        app.dependency_overrides[current_user] = lambda: rivals[0]
        response = client.get(f"/api/v1/rivalries/{rivalry.id}").json()
        assert response["opponent"]["username"] == "renamed"
        assert "email" not in response["opponent"]
    finally:
        app.dependency_overrides.clear()


def test_invitation_api_accepts_only_for_recipient(db, rivals):
    actor = [rivals[0]]
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[current_user] = lambda: actor[0]
    app.dependency_overrides[limited_user] = lambda: actor[0]
    try:
        client = TestClient(app)
        response = client.post("/api/v1/rivalries", json={"username": "OPPONENT"})
        assert response.status_code == 200
        invitation = response.json()
        assert invitation["status"] == "PENDING"
        url = f"/api/v1/rivalries/{invitation['id']}/decision"
        assert client.post(url, json={"decision": "ACCEPT"}).status_code == 403
        actor[0] = "opponent"
        response = client.post(url, json={"decision": "ACCEPT"})
        assert response.status_code == 200
        assert response.json()["status"] == "ACCEPTED"
        assert len(response.json()["history"]) == 16
    finally:
        app.dependency_overrides.clear()


def setup_scores(db, rivals, own=10, opponent=5, result_status="FINAL"):
    current = db.scalar(select(NFLWeek))
    week = NFLWeek(
        season=2026,
        week=4,
        opens_at=aware(current.opens_at) + timedelta(days=7),
        closes_at=aware(current.closes_at) + timedelta(days=7),
        scoring_status="FINAL",
    )
    db.add(week)
    players = list(db.scalars(select(Player).limit(2)))
    for user, player, score in zip([rivals[0], "opponent"], players, [own, opponent]):
        entry = WeeklyEntry(user_id=user, season=2026, week=4, status="IN_PROGRESS")
        db.add(entry)
        db.flush()
        # Intentionally only one filled slot. Other slots contribute zero.
        db.add(LineupSlot(entry_id=entry.id, slot="RB1", player_id=player.id))
        db.add(
            PlayerResult(
                player_id=player.id,
                season=2026,
                week=4,
                actual_ppr=Decimal(score),
                provider="test",
                game_status=result_status,
            )
        )
    db.flush()
    return week, players


@pytest.mark.parametrize(
    "own,theirs,outcome", [(10, 5, "WIN"), (5, 10, "LOSS"), (10, 10, "TIE"), (-1, 0, "LOSS")]
)
def test_weekly_scores_partial_lineups_ties_and_negative_scores(db, rivals, own, theirs, outcome):
    rivalry = accepted(db, rivals)
    setup_scores(db, rivals, own, theirs)
    scoring.recompute(db, 2026, 4)
    scoring.recompute(db, 2026, 4)
    result = rivalries.public_rivalry(db, rivalry, rivals[0])
    assert result["history"][1]["outcome"] == outcome
    assert result["your_total"] == own
    assert sum(result["record"].values()) == 1
    inverse = rivalries.public_rivalry(db, rivalry, "opponent")
    assert inverse["your_total"] == theirs
    assert inverse["record"]["wins"] == result["record"]["losses"]


def test_no_lineup_is_zero_and_zero_zero_is_tie(db, rivals):
    rivalry = accepted(db, rivals)
    current = db.scalar(select(NFLWeek))
    db.add(
        NFLWeek(
            season=2026,
            week=4,
            opens_at=current.opens_at,
            closes_at=current.closes_at,
            scoring_status="FINAL",
        )
    )
    db.flush()
    rivalries.sync_matchups(db, 2026, 4)
    result = rivalries.public_rivalry(db, rivalry, rivals[0])
    assert result["history"][1]["outcome"] == "TIE"
    assert result["your_total"] == 0


def test_final_missing_results_not_awarded_and_stat_corrections_recalculate(db, rivals):
    rivalry = accepted(db, rivals)
    week, players = setup_scores(db, rivals, 10, 5, "LIVE")
    scoring.recompute(db, 2026, 4)
    assert rivalries.public_rivalry(db, rivalry, rivals[0])["record"]["wins"] == 0
    for result in db.scalars(select(PlayerResult).where(PlayerResult.week == 4)):
        result.game_status = "CORRECTED"
        if result.player_id == players[1].id:
            result.actual_ppr = Decimal(20)
    db.flush()
    scoring.recompute(db, 2026, 4)
    assert rivalries.public_rivalry(db, rivalry, rivals[0])["record"]["losses"] == 1
    week.scoring_status = "LIVE"
    db.flush()
    scoring.recompute(db, 2026, 4)
    assert rivalries.public_rivalry(db, rivalry, rivals[0])["your_total"] == 0


def test_multiple_opponents_do_not_double_season_points(db, rivals):
    accepted(db, rivals)
    accepted(db, rivals, "second")
    setup_scores(db, rivals)
    scoring.recompute(db, 2026, 4)
    response = rivalries.list_rivalries(db, rivals[0], 2026)
    assert response["total_points"] == 10
    assert response["weeks_scored"] == 1
    assert response["record"]["wins"] == 2
    assert len(response["rivalries"]) == 2
    assert all(
        item["record"] == {"wins": 1, "losses": 0, "ties": 0} for item in response["rivalries"]
    )
    assert all(
        item["opponent_record"] == {"wins": 0, "losses": 1, "ties": 0}
        for item in response["rivalries"]
    )


def test_season_end_and_boundary(db, rivals):
    current = db.scalar(select(NFLWeek))
    assert rivalries.matchup_start_week(db, aware(current.closes_at) - timedelta(seconds=1)) == (
        2026,
        3,
    )
    assert rivalries.matchup_start_week(db, aware(current.closes_at)) == (2026, 4)
    assert rivalries.matchup_start_week(db, aware(current.closes_at) + timedelta(seconds=1)) == (
        2026,
        4,
    )
    current.week = 18
    db.flush()
    assert rivalries.matchup_start_week(db, rivals[2]) == (2026, 18)
    with pytest.raises(RuleError, match="No unlocked weeks"):
        rivalries.matchup_start_week(db, aware(current.closes_at))

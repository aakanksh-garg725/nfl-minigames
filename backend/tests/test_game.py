import json
from collections import Counter
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.time import aware, utcnow
from app.models import (
    DealEvent,
    NFLGame,
    NFLWeek,
    PlayerResult,
    Profile,
    Projection,
    ProjectionSnapshot,
    WeeklyEntry,
)
from app.services import game, scoring
from app.services.rules import (
    ALGORITHM_VERSION,
    DEALER_ALGORITHM_VERSION,
    ROUND_QUOTAS,
    SLOTS,
    RuleError,
    calculate_dealer_target,
    dealer_random_factor,
    find_closest_offer_player,
)


def advance(db, user, g, action, value):
    result = game.act(db, user, g.id, action, value, g.version)
    db.commit()
    return result


def round_to_offer(db, user, g):
    quota = ROUND_QUOTAS[g.current_round - 1]
    for _ in range(quota):
        case = next(
            c
            for c in game.game_cases(db, g)
            if c.status == "CLOSED" and c.case_number != g.selected_case_number
        )
        advance(db, user, g, "open", case.case_number)


@pytest.mark.parametrize("accept_round", [1, 2, 3, 4])
def test_accept_each_round_and_no_replay(db, user, accept_round):
    g = game.start_game(db, user, SLOTS[0])
    db.commit()
    advance(db, user, g, "select", 1)
    for round_number in range(1, accept_round + 1):
        round_to_offer(db, user, g)
        advance(
            db,
            user,
            g,
            "decision",
            (round_number, "DEAL" if round_number == accept_round else "NO_DEAL"),
        )
    assert g.status == "COMPLETE"
    assert game.entry_slots(db, db.get(WeeklyEntry, g.entry_id))[0].player_id == g.awarded_player_id
    with pytest.raises(RuleError):
        game.start_game(db, user, SLOTS[0])


@pytest.mark.parametrize("choice", ["KEEP", "SWAP"])
def test_final_choice_and_refresh(db, user, choice):
    g = game.start_game(db, user, SLOTS[0])
    db.commit()
    game_id = g.id
    advance(db, user, g, "select", 4)
    for round_number in range(1, 5):
        round_to_offer(db, user, g)
        advance(db, user, g, "decision", (round_number, "NO_DEAL"))
        db.expire_all()
        g = game.owned_game(db, user, game_id)
    assert g.status == "FINAL_CHOICE"
    remaining = [c for c in game.game_cases(db, g) if c.status == "CLOSED"]
    expected = next(c for c in remaining if (c.case_number == 4) == (choice == "KEEP")).player_id
    advance(db, user, g, "final", choice)
    assert g.awarded_player_id == expected
    assert sum("player" in c for c in game.public_game(db, g)["cases"]) == 12


def test_six_slots_unique_and_leaderboard_actual_only(db, user):
    acquired = set()
    for slot in SLOTS:
        g = game.start_game(db, user, slot)
        db.commit()
        assert not acquired.intersection(g.candidate_ids)
        advance(db, user, g, "select", 1)
        round_to_offer(db, user, g)
        advance(db, user, g, "decision", (1, "DEAL"))
        acquired.add(g.awarded_player_id)
    entry = db.get(WeeklyEntry, g.entry_id)
    assert entry.status == "COMPLETE" and len(acquired) == 6
    assert scoring.weekly_leaderboard(db, entry.season, entry.week)["rows"][0]["score"] == 0
    for player_id in acquired:
        db.add(
            PlayerResult(
                player_id=player_id,
                season=entry.season,
                week=entry.week,
                actual_ppr=Decimal("10.5"),
                provider="test",
                game_status="FINAL",
            )
        )
    for nfl_game in db.scalars(select(NFLGame)):
        nfl_game.status = "FINAL"
    db.flush()
    scoring.finalize(db, entry.season, entry.week)
    db.commit()
    assert entry.actual_score == Decimal(63)
    assert entry.final_rank == 1
    assert scoring.season_leaderboard(db, entry.season)["rows"][0]["score"] == 63


def test_hidden_state_and_other_user(db, user):
    g = game.start_game(db, user, SLOTS[0])
    db.commit()
    public = game.public_game(db, g)
    assert len(public["board"]) == 12
    assert all(set(c) == {"case_number", "status", "is_user_case"} for c in public["cases"])
    serialized = json.dumps(public, default=str)
    for hidden in [
        g.seed,
        "candidate_ids",
        "expected_value",
        "ev_multiplier",
        "target_projection",
        "standard_deviation",
        "risk_weight",
        "random_factor",
        "base_target",
        "seed_hash",
    ]:
        assert hidden not in serialized
    with pytest.raises(RuleError, match="not found"):
        game.owned_game(db, "another-user", g.id)


def test_versions_extra_click_and_final_skip(db, user):
    g = game.start_game(db, user, SLOTS[0])
    db.commit()
    with pytest.raises(RuleError):
        game.act(db, user, g.id, "open", 2, 0)
    advance(db, user, g, "select", 1)
    with pytest.raises(RuleError):
        game.act(db, user, g.id, "open", 2, 0)
    with pytest.raises(RuleError):
        game.act(db, user, g.id, "final", "SWAP", g.version)
    round_to_offer(db, user, g)
    with pytest.raises(RuleError):
        game.act(db, user, g.id, "open", 8, g.version)


def test_risk_offers_are_audited_include_my_case_and_do_not_reroll(db, user):
    g = game.start_game(db, user, SLOTS[0])
    db.commit()
    advance(db, user, g, "select", 1)
    prior = set()
    for number in range(1, 5):
        round_to_offer(db, user, g)
        remaining = [c for c in game.game_cases(db, g) if c.status == "CLOSED"]
        assert any(c.case_number == g.selected_case_number for c in remaining)
        factor = dealer_random_factor(g.seed, number)
        expected = calculate_dealer_target([c.projection for c in remaining], factor)
        offer = game.game_offers(db, g)[-1]
        assert offer.cases_remaining == len(remaining)
        assert abs(offer.target_projection - expected.target_projection) < Decimal("0.000001")
        pool = [
            p for p in game.candidate_pool(db, g.projection_snapshot_id) if p.id in g.candidate_ids
        ]
        assert (
            offer.offered_player_id
            == find_closest_offer_player(pool, expected.target_projection, prior).id
        )
        prior.add(offer.offered_player_id)
        audits = db.scalars(
            select(DealEvent).where(
                DealEvent.deal_game_id == g.id,
                DealEvent.event_type == "OFFER_CREATED",
            )
        ).all()
        assert len(audits) == number
        payload = next(e.payload for e in audits if e.payload["round"] == number)
        assert payload["dealer_algorithm"] == DEALER_ALGORITHM_VERSION
        assert Decimal(payload["random_factor"]) == factor
        assert Decimal(payload["standard_deviation"]) == expected.standard_deviation
        assert Decimal(payload["base_target"]) == expected.base_target
        before = game.public_game(db, g)
        for hidden in [
            "random_factor",
            "risk_weight",
            "standard_deviation",
            "base_target",
            "target_projection",
        ]:
            assert hidden not in json.dumps(before, default=str)
        with pytest.raises(RuleError):
            game.act(db, user, g.id, "open", 12, g.version)
        db.expire_all()
        assert game.public_game(db, g) == before
        advance(db, user, g, "decision", (number, "NO_DEAL"))


def test_expiration_and_restart(db, user):
    g = game.start_game(db, user, SLOTS[0])
    db.commit()
    g.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()
    with pytest.raises(RuleError) as error:
        game.act(db, user, g.id, "select", 1, g.version)
    assert error.value.status == 410
    assert g.status == "EXPIRED"
    replacement = game.start_game(db, user, SLOTS[0])
    db.commit()
    assert replacement.id != g.id


def test_earlier_rescheduled_kickoff_expires(db, user):
    g = game.start_game(db, user, SLOTS[0])
    db.commit()
    projection = db.scalar(select(Projection).where(Projection.player_id.in_(g.candidate_ids)))
    nfl_game = db.get(NFLGame, projection.nfl_game_id)
    nfl_game.kickoff_at = utcnow() - timedelta(seconds=1)
    db.commit()
    assert game.expire_if_needed(db, g, user, utcnow())


def test_snapshot_switch_does_not_change_game(db, user):
    g = game.start_game(db, user, SLOTS[0])
    db.commit()
    before = game.public_game(db, g)
    week = db.scalar(select(NFLWeek))
    week.projection_snapshot_id = None
    db.commit()
    assert game.public_game(db, g) == before
    advance(db, user, g, "select", 1)
    round_to_offer(db, user, g)
    assert len(game.game_offers(db, g)) == 1


def test_new_games_filter_below_three_points_for_cases_and_offers(db, user):
    rows = db.scalars(select(Projection).where(Projection.position == "RB")).all()
    rows[0].projected_ppr = Decimal("0")
    rows[1].projected_ppr = Decimal("2.999")
    excluded = {rows[0].player_id, rows[1].player_id}
    db.commit()
    g = game.start_game(db, user, SLOTS[0])
    db.commit()
    assert g.algorithm_version == ALGORITHM_VERSION
    assert not excluded.intersection(g.candidate_ids)
    cases = game.game_cases(db, g)
    assert len(cases) == 12
    assert Counter(c.tier_number for c in cases) == {
        tier: 2 if tier in {2, 4} else 1 for tier in range(1, 11)
    }
    assert len({c.player_id for c in cases}) == 12
    assert all(c.projection >= Decimal("3.0") for c in cases)
    advance(db, user, g, "select", 1)
    for number in range(1, 5):
        round_to_offer(db, user, g)
        offer = game.game_offers(db, g)[-1]
        assert offer.offered_player_id not in excluded
        assert offer.offered_player_projection >= Decimal("3.0")
        advance(db, user, g, "decision", (number, "NO_DEAL"))


@pytest.mark.parametrize("invalid_source", ["case", "pending_offer"])
def test_legacy_below_minimum_games_expire_without_awarding(db, user, invalid_source):
    g = game.start_game(db, user, SLOTS[0])
    db.commit()
    advance(db, user, g, "select", 1)
    if invalid_source == "case":
        game.game_cases(db, g)[0].projection = Decimal("2.999")
    else:
        round_to_offer(db, user, g)
        game.game_offers(db, g)[0].offered_player_projection = Decimal("2.9")
    db.commit()
    with pytest.raises(RuleError) as error:
        game.act(db, user, g.id, "decision", (1, "DEAL"), g.version)
    assert error.value.status == 410
    assert g.status == "EXPIRED"
    assert g.awarded_player_id is None
    replacement = game.start_game(db, user, SLOTS[0])
    db.commit()
    assert replacement.id != g.id


def test_completed_game_is_not_changed_by_new_projection_policy(db, user):
    g = game.start_game(db, user, SLOTS[0])
    db.commit()
    advance(db, user, g, "select", 1)
    round_to_offer(db, user, g)
    advance(db, user, g, "decision", (1, "DEAL"))
    game.game_cases(db, g)[0].projection = Decimal("0")
    db.commit()
    assert not game.expire_if_needed(db, g, user, utcnow())
    assert g.status == "COMPLETE"


def test_lineup_uses_acquisition_snapshot(db, user):
    g = game.start_game(db, user, SLOTS[0])
    db.commit()
    advance(db, user, g, "select", 1)
    round_to_offer(db, user, g)
    advance(db, user, g, "decision", (1, "DEAL"))
    original = db.scalar(
        select(Projection).where(
            Projection.player_id == g.awarded_player_id,
            Projection.snapshot_id == g.projection_snapshot_id,
        )
    )
    other = ProjectionSnapshot(provider="test", season=original.season, week=original.week)
    db.add(other)
    db.flush()
    # Move the older row to another snapshot, so an unordered first-row query is wrong.
    acquired_snapshot = original.snapshot_id
    original.snapshot_id = other.id
    original.opponent = "OLD"
    db.add(
        Projection(
            snapshot_id=acquired_snapshot,
            player_id=original.player_id,
            season=original.season,
            week=original.week,
            position=original.position,
            team=original.team,
            opponent="NEW",
            nfl_game_id=original.nfl_game_id,
            kickoff_at=original.kickoff_at,
            projected_ppr=original.projected_ppr,
        )
    )
    db.commit()
    result = scoring.lineup(db, db.get(WeeklyEntry, g.entry_id))
    assert result["slots"][0]["opponent"] == "NEW"


def test_no_incomplete_entry_on_leaderboard(db, user):
    entry = game.start_entry(db, user)
    db.commit()
    assert scoring.weekly_leaderboard(db, entry.season, entry.week)["rows"] == []


@pytest.mark.parametrize("is_home", [True, False])
def test_matchups_on_board_reveals_offers_and_lineup(db, user, is_home):
    if not is_home:
        for nfl_game in db.scalars(select(NFLGame)):
            nfl_game.home_team, nfl_game.away_team = nfl_game.away_team, nfl_game.home_team
        db.commit()
    g = game.start_game(db, user, SLOTS[0])
    db.commit()
    initial = game.public_game(db, g)
    assert all(p["opponent"] == "NFL" and p["is_home"] is is_home for p in initial["board"])
    assert all(set(c) == {"case_number", "status", "is_user_case"} for c in initial["cases"])
    advance(db, user, g, "select", 1)
    round_to_offer(db, user, g)
    offered = game.public_game(db, g)
    assert offered["offers"][0]["player"]["opponent"] == "NFL"
    assert offered["offers"][0]["player"]["is_home"] is is_home
    revealed = [c["player"] for c in offered["cases"] if "player" in c]
    assert len(revealed) == 4
    assert all(p["opponent"] == "NFL" and p["is_home"] is is_home for p in revealed)
    advance(db, user, g, "decision", (1, "DEAL"))
    assert game.public_game(db, g)["awarded_player"]["is_home"] is is_home
    slot = scoring.lineup(db, db.get(WeeklyEntry, g.entry_id))["slots"][0]
    assert slot["opponent"] == slot["player"]["opponent"] == "NFL"
    assert slot["is_home"] is slot["player"]["is_home"] is is_home


def test_matchup_uses_snapshot_team_and_does_not_guess_unknown_venue(db, user):
    g = game.start_game(db, user, SLOTS[0])
    db.commit()
    case = game.game_cases(db, g)[0]
    projection = db.scalar(
        select(Projection).where(
            Projection.snapshot_id == g.projection_snapshot_id,
            Projection.player_id == case.player_id,
        )
    )
    from app.models import Player

    db.get(Player, case.player_id).team = "TRADED"
    db.commit()
    row = next(p for p in game.public_game(db, g)["board"] if p["id"] == case.player_id)
    assert row["team"] == projection.team
    assert row["is_home"] is True
    assert game.player_matchup(None, None) == {"opponent": None, "is_home": None}
    assert game.player_matchup(projection, None)["is_home"] is None
    assert (
        game.player_matchup(projection, NFLGame(home_team="UNKNOWN", away_team="OTHER"))["is_home"]
        is None
    )


def test_global_deadline(db, user):
    g = game.start_game(db, user, SLOTS[0])
    db.commit()
    week = db.scalar(select(NFLWeek))
    with pytest.raises(RuleError):
        game.act(db, user, g.id, "select", 1, 0, now=aware(week.closes_at))


def test_shared_rank_and_season_only_final(db, user):
    week = db.scalar(select(NFLWeek))
    for idx, score in enumerate([30, 30, 20]):
        uid = f"user-{idx}"
        db.add(Profile(user_id=uid, username=f"person_{idx}", display_name="", favorite_team="BAL"))
        db.flush()
        entry = game.start_entry(db, uid)
        players = db.scalars(select(Projection).limit(6)).all()
        for slot, projection in zip(game.entry_slots(db, entry), players, strict=True):
            slot.player_id = projection.player_id
        entry.status, entry.completed_at, entry.actual_score = "COMPLETE", utcnow(), score
    db.commit()
    assert [r["rank"] for r in scoring.weekly_leaderboard(db, week.season, week.week)["rows"]] == [
        1,
        1,
        3,
    ]
    assert scoring.season_leaderboard(db, week.season)["rows"] == []

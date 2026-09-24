from decimal import Decimal

from sqlalchemy import select

from app.core.time import aware
from app.models import (
    DealGame,
    NFLGame,
    NFLWeek,
    Player,
    PlayerResult,
    Profile,
    Projection,
    WeeklyEntry,
)
from app.services.game import entry_slots, player_matchup, public_player
from app.services.rules import RuleError


def eligible_entries(db, season, week=None):
    query = select(WeeklyEntry).where(
        WeeklyEntry.season == season,
        WeeklyEntry.game_type == "DEAL",
        WeeklyEntry.status.in_(["COMPLETE", "FINAL"]),
    )
    if week is not None:
        query = query.where(WeeklyEntry.week == week)
    entries = db.scalars(query).all()
    valid = []
    for entry in entries:
        nfl_week = db.scalar(
            select(NFLWeek).where(NFLWeek.season == season, NFLWeek.week == entry.week)
        )
        if (
            nfl_week
            and entry.completed_at
            and aware(entry.completed_at) < aware(nfl_week.closes_at)
            and len([s for s in entry_slots(db, entry) if s.player_id]) == 6
        ):
            valid.append(entry)
    return valid


def recompute(db, season, week):
    results = {
        r.player_id: r.actual_ppr
        for r in db.scalars(
            select(PlayerResult).where(
                PlayerResult.season == season,
                PlayerResult.week == week,
            )
        )
    }
    entries = eligible_entries(db, season, week)
    for entry in entries:
        entry.actual_score = sum(
            (results.get(s.player_id, Decimal(0)) for s in entry_slots(db, entry)), Decimal(0)
        )
    entries.sort(key=lambda e: -e.actual_score)
    prior, rank = None, 0
    for index, entry in enumerate(entries, 1):
        if entry.actual_score != prior:
            rank = index
        entry.final_rank = rank if entry.status == "FINAL" else None
        prior = entry.actual_score
    db.flush()

    from app.services.rivalries import sync_matchups

    sync_matchups(db, season, week)


def finalize(db, season, week, final=True):
    nfl_week = db.scalar(
        select(NFLWeek).where(NFLWeek.season == season, NFLWeek.week == week).with_for_update()
    )
    if not nfl_week:
        raise RuleError("Week not found.", 404)
    games = db.scalars(select(NFLGame).where(NFLGame.season == season, NFLGame.week == week)).all()
    if final and (not games or any(g.status != "FINAL" for g in games)):
        raise RuleError("All NFL games must be final before the week can be finalized.")
    entries = eligible_entries(db, season, week)
    if final:
        results = {
            r.player_id: r
            for r in db.scalars(
                select(PlayerResult).where(
                    PlayerResult.season == season,
                    PlayerResult.week == week,
                )
            )
        }
        if any(
            s.player_id not in results
            or results[s.player_id].game_status not in {"FINAL", "CORRECTED"}
            for e in entries
            for s in entry_slots(db, e)
        ):
            raise RuleError(
                "Some rostered players are missing final results. Import results before finalizing."
            )
    nfl_week.scoring_status = "FINAL" if final else "LIVE"
    for entry in entries:
        entry.status = "FINAL" if final else "COMPLETE"
        entry.final_rank = None
    recompute(db, season, week)


def weekly_leaderboard(db, season, week):
    nfl_week = db.scalar(select(NFLWeek).where(NFLWeek.season == season, NFLWeek.week == week))
    entries = sorted(eligible_entries(db, season, week), key=lambda e: (-e.actual_score, e.user_id))
    rows, rank, previous = [], 0, None
    for index, entry in enumerate(entries, 1):
        if entry.actual_score != previous:
            rank = index
        profile = db.get(Profile, entry.user_id)
        rows.append(
            {
                "rank": rank,
                "username": profile.username,
                "display_name": profile.display_name,
                "score": float(entry.actual_score),
                "user_id": entry.user_id,
                "weeks_played": 1,
            }
        )
        previous = entry.actual_score
    return {
        "season": season,
        "week": week,
        "status": "FINAL" if nfl_week and nfl_week.scoring_status == "FINAL" else "LIVE",
        "rows": rows,
    }


def season_leaderboard(db, season):
    users = {}
    for entry in eligible_entries(db, season):
        if entry.status != "FINAL":
            continue
        record = users.setdefault(entry.user_id, {"total": Decimal(0), "weeks": 0})
        record["total"] += entry.actual_score
        record["weeks"] += 1
    rows, rank, previous = [], 0, None
    for index, (user, data) in enumerate(
        sorted(users.items(), key=lambda p: (-p[1]["total"], p[0])), 1
    ):
        if data["total"] != previous:
            rank = index
        profile = db.get(Profile, user)
        rows.append(
            {
                "user_id": user,
                "rank": rank,
                "username": profile.username,
                "display_name": profile.display_name,
                "score": float(data["total"]),
                "weeks_played": data["weeks"],
                "average": float(data["total"] / data["weeks"]),
            }
        )
        previous = data["total"]
    return {"season": season, "status": "FINAL", "rows": rows}


def lineup(db, entry):
    if not entry:
        return {"entry": None, "slots": []}
    results = {
        r.player_id: r
        for r in db.scalars(
            select(PlayerResult).where(
                PlayerResult.season == entry.season,
                PlayerResult.week == entry.week,
            )
        )
    }
    slots = []
    for slot in entry_slots(db, entry):
        item = {
            "slot": slot.slot,
            "player": None,
            "actual_ppr": 0,
            "game_status": "NOT_STARTED",
            "acquisition_method": slot.acquisition_method,
            "deal_game_id": slot.deal_game_id,
        }
        if slot.player_id:
            player = db.get(Player, slot.player_id)
            acquired_game = db.get(DealGame, slot.deal_game_id) if slot.deal_game_id else None
            projection = db.scalar(
                select(Projection)
                .where(
                    Projection.player_id == slot.player_id,
                    Projection.season == entry.season,
                    Projection.week == entry.week,
                    Projection.snapshot_id == acquired_game.projection_snapshot_id
                    if acquired_game
                    else True,
                )
                .limit(1)
            )
            result = results.get(slot.player_id)
            matchup = player_matchup(
                projection, db.get(NFLGame, projection.nfl_game_id) if projection else None
            )
            item.update(
                {
                    "player": public_player(player, slot.projection_when_acquired, **matchup),
                    "actual_ppr": float(result.actual_ppr) if result else 0,
                    "game_status": result.game_status if result else "NOT_STARTED",
                    "opponent": projection.opponent if projection else None,
                    "is_home": matchup["is_home"],
                    "kickoff_at": aware(projection.kickoff_at) if projection else None,
                }
            )
        slots.append(item)
    return {
        "entry": {
            "id": entry.id,
            "season": entry.season,
            "week": entry.week,
            "status": entry.status,
            "score": float(
                sum(
                    results[s.player_id].actual_ppr
                    for s in entry_slots(db, entry)
                    if s.player_id in results
                )
            ),
            "final_rank": entry.final_rank,
        },
        "slots": slots,
    }

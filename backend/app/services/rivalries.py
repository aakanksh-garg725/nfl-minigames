"""Season-long, opt-in head-to-head using each user's existing weekly lineup."""

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import or_, select

from app.core.time import EASTERN, aware, utcnow
from app.models import (
    LineupSlot,
    NFLWeek,
    PlayerResult,
    Profile,
    Rivalry,
    RivalryMatchup,
    WeeklyEntry,
)
from app.services.game import begin_write, current_week
from app.services.rules import RuleError
from app.services.scoring import lineup, lineup_points


def matchup_start_week(db, now):
    current = current_week(db, now)
    # Accept until Sunday's 1 PM Eastern lock, including the current week.
    # Local calendar arithmetic keeps the deadline correct across DST changes.
    closing = aware(current.closes_at).astimezone(EASTERN)
    number = current.week
    while closing <= now.astimezone(EASTERN):
        closing += timedelta(days=7)
        number += 1
    if number > 18:
        raise RuleError(
            "No unlocked weeks remain in this regular season. Invite again next season.", 409
        )
    return current.season, number


def require_profile(db, user):
    profile = db.get(Profile, user)
    if not profile or not profile.favorite_team:
        raise RuleError("Complete your username and favorite team in Profile first.", 428)
    return profile


def invite(db, user, username, now=None):
    now = now or utcnow()
    begin_write(db)
    require_profile(db, user)
    season, _ = matchup_start_week(db, now)
    opponent = db.scalar(select(Profile).where(Profile.username == username.lower()))
    if not opponent:
        raise RuleError("No user has that username. Check the spelling and try again.", 404)
    if opponent.user_id == user:
        raise RuleError("Choose another user, not yourself.", 422)
    require_profile(db, opponent.user_id)
    low, high = sorted([user, opponent.user_id])
    rivalry = db.scalar(
        select(Rivalry)
        .where(Rivalry.season == season, Rivalry.user_low == low, Rivalry.user_high == high)
        .with_for_update()
    )
    if rivalry and rivalry.status in {"PENDING", "ACCEPTED"}:
        raise RuleError(
            "An invitation or active rivalry with that user already exists this season.", 409
        )
    if not rivalry:
        rivalry = Rivalry(season=season, user_low=low, user_high=high)
        db.add(rivalry)
    rivalry.invited_by = user
    rivalry.status = "PENDING"
    rivalry.created_at = now
    db.flush()
    return rivalry


def owned_rivalry(db, user, rivalry_id, lock=False):
    query = select(Rivalry).where(
        Rivalry.id == rivalry_id, or_(Rivalry.user_low == user, Rivalry.user_high == user)
    )
    rivalry = db.scalar(query.with_for_update() if lock else query)
    if not rivalry:
        raise RuleError("Matchup not found.", 404)
    return rivalry


def respond(db, user, rivalry_id, decision, now=None):
    now = now or utcnow()
    begin_write(db)
    rivalry = owned_rivalry(db, user, rivalry_id, lock=True)
    if rivalry.status != "PENDING":
        raise RuleError("This invitation has already been handled. Refresh to see its status.", 409)
    if decision == "CANCEL":
        if user != rivalry.invited_by:
            raise RuleError("Only the sender can cancel an invitation.", 403)
        rivalry.status = "CANCELED"
    else:
        if user == rivalry.invited_by:
            raise RuleError("Only the invited user can accept or decline.", 403)
        if decision == "ACCEPT":
            require_profile(db, user)
            season, start_week = matchup_start_week(db, now)
            if season != rivalry.season:
                raise RuleError("This invitation is for a previous season. Request a new one.", 409)
            rivalry.status = "ACCEPTED"
            rivalry.start_week = start_week
            rivalry.accepted_at = now
            db.add_all(
                RivalryMatchup(rivalry_id=rivalry.id, week=week) for week in range(start_week, 19)
            )
        elif decision == "DECLINE":
            rivalry.status = "DECLINED"
        else:
            raise RuleError("Invalid invitation decision.", 422)
    db.flush()
    return rivalry


def sync_matchups(db, season, week):
    """Idempotent recalculation, including partial lineups and stat corrections."""
    nfl_week = db.scalar(select(NFLWeek).where(NFLWeek.season == season, NFLWeek.week == week))
    if not nfl_week:
        return
    results = {
        r.player_id: r
        for r in db.scalars(
            select(PlayerResult).where(PlayerResult.season == season, PlayerResult.week == week)
        )
    }
    entries = list(
        db.scalars(
            select(WeeklyEntry).where(
                WeeklyEntry.season == season,
                WeeklyEntry.week == week,
                WeeklyEntry.game_type == "DEAL",
            )
        )
    )
    scores, missing_final = {}, set()
    for entry in entries:
        slots = list(db.scalars(select(LineupSlot).where(LineupSlot.entry_id == entry.id)))
        scores[entry.user_id] = lineup_points(db, entry, results)
        if any(
            s.player_id
            and (
                s.player_id not in results
                or results[s.player_id].game_status not in {"FINAL", "CORRECTED"}
            )
            for s in slots
        ):
            missing_final.add(entry.user_id)
    rows = db.execute(
        select(RivalryMatchup, Rivalry)
        .join(Rivalry)
        .where(Rivalry.season == season, Rivalry.status == "ACCEPTED", RivalryMatchup.week == week)
        .with_for_update()
    ).all()
    for match, rivalry in rows:
        match.low_score = scores.get(rivalry.user_low, Decimal(0))
        match.high_score = scores.get(rivalry.user_high, Decimal(0))
        can_finalize = nfl_week.scoring_status == "FINAL" and not {
            rivalry.user_low,
            rivalry.user_high,
        }.intersection(missing_final)
        match.status = (
            "FINAL"
            if can_finalize
            else "LIVE"
            if results or utcnow() >= aware(nfl_week.closes_at)
            else "UPCOMING"
        )
        match.winner_id = None
        if can_finalize and match.low_score != match.high_score:
            match.winner_id = (
                rivalry.user_low if match.low_score > match.high_score else rivalry.user_high
            )
        match.updated_at = utcnow()
    db.flush()


def public_rivalry(db, rivalry, user):
    opponent_id = rivalry.user_high if rivalry.user_low == user else rivalry.user_low
    opponent = db.get(Profile, opponent_id)
    matches = list(
        db.scalars(
            select(RivalryMatchup)
            .where(RivalryMatchup.rivalry_id == rivalry.id)
            .order_by(RivalryMatchup.week)
        )
    )
    record = {"wins": 0, "losses": 0, "ties": 0}
    your_total, their_total = Decimal(0), Decimal(0)
    history = []
    for match in matches:
        yours, theirs = (
            (match.low_score, match.high_score)
            if user == rivalry.user_low
            else (match.high_score, match.low_score)
        )
        outcome = None
        if match.status == "FINAL":
            outcome = "TIE" if not match.winner_id else "WIN" if match.winner_id == user else "LOSS"
            record[{"WIN": "wins", "LOSS": "losses", "TIE": "ties"}[outcome]] += 1
            your_total += yours
            their_total += theirs
        history.append(
            {
                "week": match.week,
                "status": match.status,
                "your_score": float(yours),
                "opponent_score": float(theirs),
                "outcome": outcome,
                "updated_at": aware(match.updated_at),
            }
        )
    return {
        "id": rivalry.id,
        "season": rivalry.season,
        "status": rivalry.status,
        "direction": "SENT" if user == rivalry.invited_by else "RECEIVED",
        "start_week": rivalry.start_week,
        "opponent": {"username": opponent.username, "favorite_team": opponent.favorite_team},
        "record": record,
        "opponent_record": {
            "wins": record["losses"],
            "losses": record["wins"],
            "ties": record["ties"],
        },
        "your_total": float(your_total),
        "opponent_total": float(their_total),
        "history": history,
    }


def list_rivalries(db, user, season):
    rows = list(
        db.scalars(
            select(Rivalry)
            .where(
                Rivalry.season == season, or_(Rivalry.user_low == user, Rivalry.user_high == user)
            )
            .order_by(Rivalry.created_at.desc())
        )
    )
    items = [public_rivalry(db, rivalry, user) for rivalry in rows]
    # Each weekly lineup counts once in the season total, even with multiple opponents.
    week_scores = {}
    record = {"wins": 0, "losses": 0, "ties": 0}
    for item in items:
        for key in record:
            record[key] += item["record"][key]
        for match in item["history"]:
            if match["status"] == "FINAL":
                week_scores[match["week"]] = Decimal(str(match["your_score"]))
    return {
        "season": season,
        "rivalries": items,
        "record": record,
        "total_points": float(sum(week_scores.values(), Decimal(0))),
        "weeks_scored": len(week_scores),
    }


def matchup_detail(db, user, rivalry_id, week):
    rivalry = owned_rivalry(db, user, rivalry_id)
    match = db.scalar(
        select(RivalryMatchup).where(
            RivalryMatchup.rivalry_id == rivalry.id, RivalryMatchup.week == week
        )
    )
    if rivalry.status != "ACCEPTED" or not match:
        raise RuleError("Matchup not found.", 404)
    opponent_id = rivalry.user_high if user == rivalry.user_low else rivalry.user_low

    def team(user_id):
        profile = db.get(Profile, user_id)
        entry = db.scalar(
            select(WeeklyEntry).where(
                WeeklyEntry.user_id == user_id,
                WeeklyEntry.season == rivalry.season,
                WeeklyEntry.week == week,
                WeeklyEntry.game_type == "DEAL",
            )
        )
        data = lineup(db, entry)
        # Only acquired players: never expose an opponent's game IDs or hidden cases.
        slots = [
            {key: slot[key] for key in ("slot", "player", "actual_ppr", "game_status")}
            for slot in data["slots"]
        ]
        return {
            "username": profile.username,
            "favorite_team": profile.favorite_team,
            "score": data["entry"]["score"] if data["entry"] else 0,
            "slots": slots,
        }

    return {
        "rivalry_id": rivalry.id,
        "season": rivalry.season,
        "week": week,
        "status": match.status,
        "you": team(user),
        "opponent": team(opponent_id),
        "weeks": list(
            db.scalars(
                select(RivalryMatchup.week)
                .where(RivalryMatchup.rivalry_id == rivalry.id)
                .order_by(RivalryMatchup.week)
            )
        ),
    }

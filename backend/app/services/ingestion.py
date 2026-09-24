import logging
from collections import Counter
from datetime import timedelta

from sqlalchemy import select

from app.core.time import EASTERN, utcnow, weekly_window
from app.models import (
    NFLGame,
    NFLWeek,
    Player,
    PlayerResult,
    Projection,
    ProjectionSnapshot,
    ProviderRun,
)
from app.providers.base import ProviderError
from app.services.rules import MIN_POOL_SIZE, is_playable_projection
from app.services.scoring import recompute

log = logging.getLogger(__name__)


def sync_schedule(db, provider, season, week):
    schedule = provider.get_schedule(season, week)
    sunday_dates = [
        g.kickoff_at.astimezone(EASTERN).date()
        for g in schedule
        if g.kickoff_at.astimezone(EASTERN).weekday() == 6
    ]
    if not sunday_dates:
        day = min(g.kickoff_at for g in schedule).astimezone(EASTERN).date()
        sunday_dates = [day + timedelta(days=(6 - day.weekday()) % 7)]
    sunday = Counter(sunday_dates).most_common(1)[0][0]
    opens, closes = weekly_window(sunday)
    nfl_week = db.scalar(select(NFLWeek).where(NFLWeek.season == season, NFLWeek.week == week))
    if not nfl_week:
        nfl_week = NFLWeek(season=season, week=week, opens_at=opens, closes_at=closes)
        db.add(nfl_week)
        db.flush()
    game_map = {}
    for source in schedule:
        game = db.scalar(
            select(NFLGame).where(
                NFLGame.provider == provider.name, NFLGame.provider_game_id == source.id
            )
        )
        # CSV fallback reconciles by teams instead of creating duplicate schedule rows.
        if not game:
            game = db.scalar(
                select(NFLGame).where(
                    NFLGame.season == season,
                    NFLGame.week == week,
                    NFLGame.home_team.in_([source.home, source.away]),
                    NFLGame.away_team.in_([source.home, source.away]),
                )
            )
        if not game:
            game = NFLGame(
                provider=provider.name,
                provider_game_id=source.id,
                season=season,
                week=week,
                home_team=source.home,
                away_team=source.away,
            )
            db.add(game)
        game.kickoff_at, game.status = source.kickoff_at, source.status
        game_map[source.home] = game_map[source.away] = game
    db.flush()
    if nfl_week.scoring_status != "FINAL":
        now = utcnow()
        nfl_week.scoring_status = "UPCOMING" if now < opens else "OPEN" if now < closes else "LIVE"
    return nfl_week, game_map


def upsert_player(db, provider, source):
    player = db.scalar(
        select(Player).where(Player.provider == provider, Player.provider_player_id == source.id)
    )
    if not player:
        player = Player(provider=provider, provider_player_id=source.id)
        db.add(player)
    player.full_name, player.team, player.position = source.name, source.team, source.position
    player.first_name, _, player.last_name = source.name.partition(" ")
    player.fantasy_positions = [source.position]
    player.active, player.provider_metadata = source.active, source.metadata
    db.flush()
    return player


def sync_projections(db, provider, season, week):
    # Fetch and validate before publishing any snapshot. The previous snapshot remains usable on failure.
    data = provider.get_week_projections(season, week)
    if not data:
        raise ProviderError("Provider returned no projections.")
    nfl_week, games = sync_schedule(db, provider, season, week)
    valid = [r for r in data if r.player.team in games and r.projected_ppr.is_finite()]
    counts = Counter(
        r.player.position
        for r in valid
        if is_playable_projection(r.projected_ppr) and r.player.active
    )
    if any(counts[p] < MIN_POOL_SIZE for p in ("RB", "WR", "TE")):
        raise ProviderError(
            "Projection snapshot needs at least 14 RBs, WRs and TEs projected for at least 3.0 PPR points."
        )
    snapshot = ProjectionSnapshot(provider=provider.name, season=season, week=week)
    db.add(snapshot)
    db.flush()
    for row in valid:
        player = upsert_player(db, provider.name, row.player)
        game = games[player.team]
        db.add(
            Projection(
                snapshot_id=snapshot.id,
                player_id=player.id,
                season=season,
                week=week,
                position=player.position,
                team=player.team,
                opponent=game.away_team if game.home_team == player.team else game.home_team,
                nfl_game_id=game.id,
                kickoff_at=game.kickoff_at,
                projected_ppr=row.projected_ppr,
                raw_payload=row.raw,
            )
        )
    nfl_week.projection_snapshot_id = snapshot.id
    db.flush()
    return {"snapshot_id": snapshot.id, "players": len(valid)}


def sync_results(db, provider, season, week):
    data = provider.get_week_results(season, week)
    if not data:
        raise ProviderError("No results were returned. Existing scores have been preserved.")
    _, games = sync_schedule(db, provider, season, week)
    count = 0
    for row in data:
        player = db.scalar(
            select(Player).where(
                Player.provider == provider.name, Player.provider_player_id == row.player_id
            )
        )
        if not player or player.team not in games:
            continue
        result = db.scalar(
            select(PlayerResult).where(
                PlayerResult.player_id == player.id,
                PlayerResult.season == season,
                PlayerResult.week == week,
            )
        )
        if not result:
            result = PlayerResult(player_id=player.id, season=season, week=week)
            db.add(result)
        result.actual_ppr, result.provider = row.actual_ppr, provider.name
        result.game_status = games[player.team].status
        result.raw_payload, result.fetched_at = row.raw, utcnow()
        count += 1
    db.flush()
    recompute(db, season, week)
    return {"results": count}


def run_sync(db, provider, operation, season, week):
    try:
        result = (sync_projections if operation == "projections" else sync_results)(
            db, provider, season, week
        )
        db.add(
            ProviderRun(
                provider=provider.name, operation=operation, status="SUCCESS", message=str(result)
            )
        )
        db.commit()
        log.info("provider_sync_success", extra={"provider": provider.name, "operation": operation})
        return result
    except Exception as error:
        db.rollback()
        # Avoid printing connection strings or provider cookies in exception messages.
        message = str(error) if isinstance(error, ProviderError) else type(error).__name__
        db.add(
            ProviderRun(
                provider=provider.name, operation=operation, status="FAILED", message=message
            )
        )
        db.commit()
        log.error(
            "provider_sync_failed",
            extra={"provider": provider.name, "operation": operation, "reason": message},
        )
        raise ProviderError(message) from None

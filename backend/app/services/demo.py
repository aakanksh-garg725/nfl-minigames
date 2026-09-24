"""Synthetic local practice data. Never imported into Supabase or a production database."""

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.auth import DEMO_USER
from app.core.time import EASTERN, utcnow, weekly_window
from app.models import NFLGame, NFLWeek, Player, Profile, Projection, ProjectionSnapshot

DEMO_PLAYERS = {
    "RB": [
        ("Bijan Robinson", "ATL"),
        ("Saquon Barkley", "PHI"),
        ("Jahmyr Gibbs", "DET"),
        ("Derrick Henry", "BAL"),
        ("De'Von Achane", "MIA"),
        ("Jonathan Taylor", "IND"),
        ("Josh Jacobs", "GB"),
        ("Breece Hall", "NYJ"),
        ("James Cook", "BUF"),
        ("Kyren Williams", "LAR"),
        ("Kenneth Walker III", "SEA"),
        ("Chase Brown", "CIN"),
        ("James Conner", "ARI"),
        ("Aaron Jones", "MIN"),
        ("Tony Pollard", "TEN"),
        ("Rachaad White", "TB"),
    ],
    "WR": [
        ("Ja'Marr Chase", "CIN"),
        ("Justin Jefferson", "MIN"),
        ("CeeDee Lamb", "DAL"),
        ("Amon-Ra St. Brown", "DET"),
        ("Puka Nacua", "LAR"),
        ("A.J. Brown", "PHI"),
        ("Nico Collins", "HOU"),
        ("Malik Nabers", "NYG"),
        ("Drake London", "ATL"),
        ("Brian Thomas Jr.", "JAX"),
        ("Garrett Wilson", "NYJ"),
        ("Terry McLaurin", "WSH"),
        ("Mike Evans", "TB"),
        ("Tee Higgins", "CIN"),
        ("DeVonta Smith", "PHI"),
        ("Zay Flowers", "BAL"),
    ],
    "TE": [
        ("Brock Bowers", "LV"),
        ("Trey McBride", "ARI"),
        ("George Kittle", "SF"),
        ("Sam LaPorta", "DET"),
        ("Travis Kelce", "KC"),
        ("Mark Andrews", "BAL"),
        ("T.J. Hockenson", "MIN"),
        ("David Njoku", "CLE"),
        ("Evan Engram", "DEN"),
        ("Dalton Kincaid", "BUF"),
        ("Kyle Pitts", "ATL"),
        ("Jake Ferguson", "DAL"),
        ("Dallas Goedert", "PHI"),
        ("Pat Freiermuth", "PIT"),
        ("Cole Kmet", "CHI"),
        ("Hunter Henry", "NE"),
    ],
}


def seed_demo(db):
    if db.bind.dialect.name != "sqlite":
        raise ValueError("Practice data is restricted to local SQLite")
    if db.scalar(select(NFLWeek).limit(1)):
        return
    now = utcnow()
    local = now.astimezone(EASTERN)
    sunday = local.date() + timedelta(days=(6 - local.weekday()) % 7)
    opens, closes = weekly_window(sunday)
    # Practice is always playable; its deliberately different clock is disclosed in the UI.
    if closes <= now:
        closes += timedelta(days=7)
    opens = min(opens, now - timedelta(hours=1))
    snapshot = ProjectionSnapshot(provider="practice", season=local.year, week=3)
    db.add(snapshot)
    db.flush()
    db.add(
        NFLWeek(
            season=local.year,
            week=3,
            opens_at=opens,
            closes_at=closes,
            scoring_status="OPEN",
            projection_snapshot_id=snapshot.id,
        )
    )
    db.add(
        Profile(
            user_id=DEMO_USER,
            username="local_player",
            display_name="Local Player",
            favorite_team="BAL",
        )
    )
    games = {}
    for position, names in DEMO_PLAYERS.items():
        for index, (name, team) in enumerate(names):
            if team not in games:
                game = NFLGame(
                    provider="practice",
                    provider_game_id=f"demo-{team}",
                    season=local.year,
                    week=3,
                    home_team=team,
                    away_team="NFL",
                    kickoff_at=closes + timedelta(hours=3),
                    status="NOT_STARTED",
                )
                db.add(game)
                db.flush()
                games[team] = game
            player = Player(
                provider="practice",
                provider_player_id=f"{position}-{index}",
                full_name=name,
                position=position,
                fantasy_positions=[position],
                team=team,
                active=True,
            )
            db.add(player)
            db.flush()
            projection = Decimal("24.8" if position != "TE" else "19.6") - Decimal(index) * Decimal(
                "1.1"
            )
            db.add(
                Projection(
                    snapshot_id=snapshot.id,
                    player_id=player.id,
                    season=local.year,
                    week=3,
                    position=position,
                    team=team,
                    opponent="NFL",
                    nfl_game_id=games[team].id,
                    kickoff_at=games[team].kickoff_at,
                    projected_ppr=projection,
                )
            )
    db.commit()

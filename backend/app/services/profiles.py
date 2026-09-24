"""Public profile validation; identities remain bound to immutable auth user IDs."""

import re

from sqlalchemy import select

from app.models import Profile

NFL_TEAMS = {
    "ARI": "Arizona Cardinals",
    "ATL": "Atlanta Falcons",
    "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers",
    "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals",
    "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos",
    "DET": "Detroit Lions",
    "GB": "Green Bay Packers",
    "HOU": "Houston Texans",
    "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars",
    "KC": "Kansas City Chiefs",
    "LV": "Las Vegas Raiders",
    "LAC": "Los Angeles Chargers",
    "LAR": "Los Angeles Rams",
    "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings",
    "NE": "New England Patriots",
    "NO": "New Orleans Saints",
    "NYG": "New York Giants",
    "NYJ": "New York Jets",
    "PHI": "Philadelphia Eagles",
    "PIT": "Pittsburgh Steelers",
    "SF": "San Francisco 49ers",
    "SEA": "Seattle Seahawks",
    "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans",
    "WAS": "Washington Commanders",
}


def profile_complete(profile):
    return bool(
        profile
        and re.fullmatch(r"[a-zA-Z0-9_]{3,24}", profile.username or "")
        and profile.favorite_team in NFL_TEAMS
    )


def username_available(db, username, user):
    return (
        db.scalar(
            select(Profile.user_id).where(
                Profile.username == username.lower(), Profile.user_id != user
            )
        )
        is None
    )


def username_suggestions(db, username, user):
    base = re.sub(r"[^a-z0-9_]", "", username.lower())[:18] or "player"
    candidates = [f"{base}_{suffix}" for suffix in ["nfl", "fan", "ppr", *range(1, 101)]]
    taken = set(
        db.scalars(
            select(Profile.username).where(
                Profile.username.in_(candidates), Profile.user_id != user
            )
        )
    )
    return [candidate for candidate in candidates if candidate not in taken][:3]

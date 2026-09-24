import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.providers.base import GameData, PlayerData, ProjectionData, ProviderError, ResultData


class CSVProvider:
    """Import uses the chosen identity namespace, so CSV can repair an ESPN outage."""

    def __init__(self, content: str, season: int, week: int, identity_provider="espn"):
        self.name = identity_provider
        self.season, self.week = season, week
        self.rows = list(csv.DictReader(io.StringIO(content.lstrip("\ufeff"))))
        required = {
            "provider_player_id",
            "player_name",
            "team",
            "position",
            "opponent",
            "kickoff_at",
        }
        if not self.rows or not required <= self.rows[0].keys():
            raise ProviderError("CSV is empty or is missing required identity/schedule columns.")
        seen = set()
        for row in self.rows:
            if row["provider_player_id"] in seen:
                raise ProviderError("CSV contains duplicate player IDs.")
            seen.add(row["provider_player_id"])
            if row["position"] not in {"RB", "WR", "TE"}:
                raise ProviderError("CSV positions must be RB, WR, or TE.")
            if row.get("game_status") and row["game_status"] not in {
                "NOT_STARTED",
                "LIVE",
                "FINAL",
                "CORRECTED",
            }:
                raise ProviderError(
                    "CSV game_status must be NOT_STARTED, LIVE, FINAL or CORRECTED."
                )
            try:
                kickoff = datetime.fromisoformat(row["kickoff_at"].replace("Z", "+00:00"))
                if kickoff.tzinfo is None:
                    raise ValueError()
                for key in ("projected_ppr_points", "actual_ppr_points"):
                    if row.get(key) and not Decimal(row[key]).is_finite():
                        raise ValueError()
            except (ValueError, InvalidOperation):
                raise ProviderError(
                    "CSV requires timezone-aware kickoff_at and finite numeric points."
                ) from None

    def get_nfl_state(self):
        return self.season, self.week

    def get_schedule(self, season, week):
        games = {}
        for row in self.rows:
            pair = sorted([row["team"], row["opponent"]])
            key = f"{season}-{week}-{'-'.join(pair)}"
            game = GameData(
                key,
                pair[0],
                pair[1],
                datetime.fromisoformat(row["kickoff_at"].replace("Z", "+00:00")),
                row.get("game_status") or "NOT_STARTED",
            )
            if key in games and games[key].kickoff_at != game.kickoff_at:
                raise ProviderError("CSV has inconsistent kickoff times for the same game.")
            games[key] = game
        return list(games.values())

    def get_players(self, season):
        return [
            PlayerData(r["provider_player_id"], r["player_name"], r["team"], r["position"])
            for r in self.rows
        ]

    def get_week_projections(self, season, week):
        return [
            ProjectionData(p, Decimal(r["projected_ppr_points"]), r)
            for p, r in zip(self.get_players(season), self.rows, strict=True)
            if r.get("projected_ppr_points")
        ]

    def get_week_results(self, season, week):
        return [
            ResultData(r["provider_player_id"], Decimal(r["actual_ppr_points"]), r)
            for r in self.rows
            if r.get("actual_ppr_points")
        ]

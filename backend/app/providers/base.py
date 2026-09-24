from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Protocol


class ProviderError(Exception):
    pass


@dataclass
class GameData:
    id: str
    home: str
    away: str
    kickoff_at: datetime
    status: str


@dataclass
class PlayerData:
    id: str
    name: str
    team: str
    position: str
    active: bool = True
    metadata: dict = field(default_factory=dict)


@dataclass
class ProjectionData:
    player: PlayerData
    projected_ppr: Decimal
    raw: dict = field(default_factory=dict)


@dataclass
class ResultData:
    player_id: str
    actual_ppr: Decimal
    raw: dict = field(default_factory=dict)


class FantasyDataProvider(Protocol):
    name: str

    def get_nfl_state(self) -> tuple[int, int]: ...
    def get_schedule(self, season: int, week: int) -> list[GameData]: ...
    def get_players(self, season: int) -> list[PlayerData]: ...
    def get_week_projections(self, season: int, week: int) -> list[ProjectionData]: ...
    def get_week_results(self, season: int, week: int) -> list[ResultData]: ...

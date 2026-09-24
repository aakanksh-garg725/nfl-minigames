from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.time import utcnow


def new_id() -> str:
    return str(uuid4())


class Profile(Base):
    __tablename__ = "profiles"
    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(24), unique=True)
    display_name: Mapped[str] = mapped_column(String(60), default="")
    favorite_team: Mapped[str | None] = mapped_column(String(3))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class NFLWeek(Base):
    __tablename__ = "nfl_weeks"
    __table_args__ = (UniqueConstraint("season", "week"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    opens_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    scoring_status: Mapped[str] = mapped_column(String(16), default="UPCOMING")
    projection_snapshot_id: Mapped[str | None] = mapped_column(String(36))


class NFLGame(Base):
    __tablename__ = "nfl_games"
    __table_args__ = (UniqueConstraint("provider", "provider_game_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(24))
    provider_game_id: Mapped[str] = mapped_column(String(40))
    season: Mapped[int] = mapped_column(Integer, index=True)
    week: Mapped[int] = mapped_column(Integer)
    home_team: Mapped[str] = mapped_column(String(8))
    away_team: Mapped[str] = mapped_column(String(8))
    kickoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="NOT_STARTED")


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (UniqueConstraint("provider", "provider_player_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(24))
    provider_player_id: Mapped[str] = mapped_column(String(40))
    full_name: Mapped[str] = mapped_column(String(100))
    first_name: Mapped[str] = mapped_column(String(60), default="")
    last_name: Mapped[str] = mapped_column(String(60), default="")
    position: Mapped[str] = mapped_column(String(8))
    fantasy_positions: Mapped[list] = mapped_column(JSON, default=list)
    team: Mapped[str] = mapped_column(String(8))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    jersey_number: Mapped[int | None] = mapped_column(Integer)
    provider_metadata: Mapped[dict] = mapped_column(JSON, default=dict)


class ProjectionSnapshot(Base):
    __tablename__ = "projection_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(24))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="SUCCESS")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source_version: Mapped[str] = mapped_column(String(40), default="1")


class Projection(Base):
    __tablename__ = "player_week_projections"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "player_id"),
        Index("projection_pool_idx", "snapshot_id", "position", "projected_ppr"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("projection_snapshots.id"))
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    position: Mapped[str] = mapped_column(String(8))
    team: Mapped[str] = mapped_column(String(8))
    opponent: Mapped[str] = mapped_column(String(8))
    nfl_game_id: Mapped[str] = mapped_column(ForeignKey("nfl_games.id"))
    kickoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    projected_ppr: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)


class PlayerResult(Base):
    __tablename__ = "player_week_results"
    __table_args__ = (UniqueConstraint("player_id", "season", "week"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"))
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    actual_ppr: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=0)
    game_status: Mapped[str] = mapped_column(String(24), default="NOT_STARTED")
    provider: Mapped[str] = mapped_column(String(24))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)


class WeeklyEntry(Base):
    __tablename__ = "weekly_entries"
    __table_args__ = (UniqueConstraint("user_id", "season", "week", "game_type"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("profiles.user_id"), index=True)
    game_type: Mapped[str] = mapped_column(String(24), default="DEAL")
    season: Mapped[int] = mapped_column(Integer)
    week: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="IN_PROGRESS")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_score: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=0)
    final_rank: Mapped[int | None] = mapped_column(Integer)


class LineupSlot(Base):
    __tablename__ = "lineup_slots"
    __table_args__ = (
        UniqueConstraint("entry_id", "slot"),
        UniqueConstraint("entry_id", "player_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    entry_id: Mapped[str] = mapped_column(ForeignKey("weekly_entries.id"), index=True)
    slot: Mapped[str] = mapped_column(String(8))
    player_id: Mapped[str | None] = mapped_column(ForeignKey("players.id"))
    projection_when_acquired: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    acquisition_method: Mapped[str | None] = mapped_column(String(16))
    deal_game_id: Mapped[str | None] = mapped_column(String(36))


class DealGame(Base):
    __tablename__ = "deal_games"
    __table_args__ = (Index("game_entry_slot_idx", "entry_id", "slot"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    entry_id: Mapped[str] = mapped_column(ForeignKey("weekly_entries.id"))
    slot: Mapped[str] = mapped_column(String(8))
    projection_snapshot_id: Mapped[str] = mapped_column(ForeignKey("projection_snapshots.id"))
    status: Mapped[str] = mapped_column(String(32), default="AWAITING_CASE_SELECTION")
    selected_case_number: Mapped[int | None] = mapped_column(Integer)
    current_round: Mapped[int] = mapped_column(Integer, default=0)
    round_open_count: Mapped[int] = mapped_column(Integer, default=0)
    outcome: Mapped[str | None] = mapped_column(String(16))
    awarded_player_id: Mapped[str | None] = mapped_column(ForeignKey("players.id"))
    seed: Mapped[str] = mapped_column(String(128))
    seed_hash: Mapped[str] = mapped_column(String(64))
    algorithm_version: Mapped[str] = mapped_column(String(30), default="us-ev-v1")
    # Frozen eligible IDs include the dealer pool; hidden and backend-only.
    candidate_ids: Mapped[list] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DealCase(Base):
    __tablename__ = "deal_game_cases"
    __table_args__ = (
        UniqueConstraint("deal_game_id", "case_number"),
        UniqueConstraint("deal_game_id", "player_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    deal_game_id: Mapped[str] = mapped_column(ForeignKey("deal_games.id"), index=True)
    case_number: Mapped[int] = mapped_column(Integer)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"))
    tier_number: Mapped[int] = mapped_column(Integer)
    full_pool_rank: Mapped[int] = mapped_column(Integer)
    board_rank: Mapped[int] = mapped_column(Integer)
    projection: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    status: Mapped[str] = mapped_column(String(24), default="CLOSED")
    opened_order: Mapped[int | None] = mapped_column(Integer)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DealOffer(Base):
    __tablename__ = "deal_game_offers"
    __table_args__ = (UniqueConstraint("deal_game_id", "offer_number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    deal_game_id: Mapped[str] = mapped_column(ForeignKey("deal_games.id"), index=True)
    offer_number: Mapped[int] = mapped_column(Integer)
    cases_remaining: Mapped[int] = mapped_column(Integer)
    expected_value: Mapped[Decimal] = mapped_column(Numeric(14, 6))
    ev_multiplier: Mapped[Decimal] = mapped_column(Numeric(8, 5))
    target_projection: Mapped[Decimal] = mapped_column(Numeric(14, 6))
    offered_player_id: Mapped[str] = mapped_column(ForeignKey("players.id"))
    offered_player_projection: Mapped[Decimal] = mapped_column(Numeric(10, 3))
    decision: Mapped[str] = mapped_column(String(16), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DealEvent(Base):
    __tablename__ = "deal_game_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    deal_game_id: Mapped[str] = mapped_column(ForeignKey("deal_games.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(36))
    event_type: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProviderRun(Base):
    __tablename__ = "provider_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(24))
    operation: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RateBucket(Base):
    __tablename__ = "rate_buckets"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    window: Mapped[int] = mapped_column(Integer)
    count: Mapped[int] = mapped_column(Integer, default=1)


class Rivalry(Base):
    __tablename__ = "rivalries"
    __table_args__ = (
        UniqueConstraint("season", "user_low", "user_high"),
        CheckConstraint("user_low < user_high"),
        CheckConstraint("status IN ('PENDING','ACCEPTED','DECLINED','CANCELED')"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    season: Mapped[int] = mapped_column(Integer, index=True)
    user_low: Mapped[str] = mapped_column(ForeignKey("profiles.user_id"), index=True)
    user_high: Mapped[str] = mapped_column(ForeignKey("profiles.user_id"), index=True)
    invited_by: Mapped[str] = mapped_column(ForeignKey("profiles.user_id"))
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    start_week: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RivalryMatchup(Base):
    __tablename__ = "rivalry_matchups"
    __table_args__ = (
        UniqueConstraint("rivalry_id", "week"),
        CheckConstraint("week BETWEEN 1 AND 18"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    rivalry_id: Mapped[str] = mapped_column(ForeignKey("rivalries.id"), index=True)
    week: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="UPCOMING")
    low_score: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0)
    high_score: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0)
    winner_id: Mapped[str | None] = mapped_column(ForeignKey("profiles.user_id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

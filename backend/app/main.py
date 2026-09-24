import asyncio
import logging
import re
import time
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import admin_user, current_user
from app.core.config import get_settings
from app.core.db import Base, SessionLocal, engine, get_db
from app.core.logging import configure_logging
from app.core.time import aware, utcnow
from app.models import (
    DealEvent,
    DealGame,
    Profile,
    ProjectionSnapshot,
    ProviderRun,
    RateBucket,
    WeeklyEntry,
)
from app.providers.base import ProviderError
from app.providers.csv_provider import CSVProvider
from app.providers.espn import ESPNProvider
from app.services import game, rivalries, scoring
from app.services.ingestion import run_sync
from app.services.profiles import (
    NFL_TEAMS,
    profile_complete,
    username_available,
    username_suggestions,
)
from app.services.rules import RuleError, Slot

settings = get_settings()
configure_logging()


@asynccontextmanager
async def lifespan(app):
    if settings.demo:
        from app.services.demo import seed_demo

        Base.metadata.create_all(engine)
        from app.core.local_schema import upgrade_practice_schema

        upgrade_practice_schema(engine)
        with SessionLocal() as db:
            seed_demo(db)
    task = None
    if settings.auto_sync and not settings.demo:
        from app.worker import worker_loop

        task = asyncio.create_task(worker_loop())
    yield
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Sunday Vault API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
    allow_credentials=False,
)


@app.exception_handler(RuleError)
async def rule_error(request, error):
    logging.getLogger(__name__).info("state_transition_rejected: %s", error.message)
    return JSONResponse(status_code=error.status, content={"detail": error.message})


@app.exception_handler(ProviderError)
async def provider_error(request, error):
    return JSONResponse(status_code=503, content={"detail": str(error)})


@app.exception_handler(IntegrityError)
async def conflict(request, error):
    return JSONResponse(
        status_code=409,
        content={"detail": "That username or action already exists. Refresh and try again."},
    )


@app.middleware("http")
async def cache_control(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def limited_user(user=Depends(current_user)):
    # Atomic DB upsert works across multiple API workers. No proxy/IP trust required.
    with SessionLocal() as db:
        dialect = db.bind.dialect.name
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        window = int(time.time()) // 60
        stmt = insert(RateBucket).values(key=user, window=window, count=1)
        from sqlalchemy import case

        stmt = stmt.on_conflict_do_update(
            index_elements=[RateBucket.key],
            set_={
                "window": window,
                "count": case((RateBucket.window == window, RateBucket.count + 1), else_=1),
            },
        ).returning(RateBucket.count)
        count = db.scalar(stmt)
        db.commit()
    if count > 120:
        raise HTTPException(429, "Too many actions. Please wait a minute.")
    return user


class StartGame(BaseModel):
    slot: Slot


class Versioned(BaseModel):
    version: int = Field(ge=0)


class CaseSelection(Versioned):
    case_number: int = Field(ge=1, le=12)


class Decision(Versioned):
    decision: Literal["DEAL", "NO_DEAL"]


class FinalChoice(Versioned):
    choice: Literal["KEEP", "SWAP"]


class ProfileInput(BaseModel):
    username: str = Field(min_length=3, max_length=24, pattern=r"^[a-zA-Z0-9_]+$")
    display_name: str = Field(default="", max_length=60)
    favorite_team: str = Field(min_length=2, max_length=3)


class RivalryInvite(BaseModel):
    username: str = Field(min_length=3, max_length=24, pattern=r"^[a-zA-Z0-9_]+$")


class RivalryDecision(BaseModel):
    decision: Literal["ACCEPT", "DECLINE", "CANCEL"]


@app.get("/api/v1/rivalries")
def rivalry_list(
    season: int | None = None, user=Depends(current_user), db: Session = Depends(get_db)
):
    return rivalries.list_rivalries(db, user, season or game.current_week(db).season)


@app.post("/api/v1/rivalries")
def rivalry_invite(body: RivalryInvite, user=Depends(limited_user), db: Session = Depends(get_db)):
    result = rivalries.invite(db, user, body.username)
    db.commit()
    return rivalries.public_rivalry(db, result, user)


@app.post("/api/v1/rivalries/{rivalry_id}/decision")
def rivalry_decision(
    rivalry_id: str,
    body: RivalryDecision,
    user=Depends(limited_user),
    db: Session = Depends(get_db),
):
    result = rivalries.respond(db, user, rivalry_id, body.decision)
    db.commit()
    return rivalries.public_rivalry(db, result, user)


@app.get("/api/v1/rivalries/{rivalry_id}")
def rivalry_detail(rivalry_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    return rivalries.public_rivalry(db, rivalries.owned_rivalry(db, user, rivalry_id), user)


@app.get("/api/v1/rivalries/{rivalry_id}/matchups/{week}")
def rivalry_matchup(
    rivalry_id: str, week: int, user=Depends(current_user), db: Session = Depends(get_db)
):
    return rivalries.matchup_detail(db, user, rivalry_id, week)


@app.get("/api/v1/health")
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "mode": "practice" if settings.demo else "live", "provider": "espn"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "database_unavailable"})


@app.get("/api/v1/config")
def public_config():
    return {"mode": "practice" if settings.demo else "live", "provider": "espn"}


def week_payload(db, week, user=None):
    now = utcnow()
    entry = game.get_entry(db, user, week) if user else None
    summary = scoring.lineup(db, entry)
    active = None
    if entry:
        active = db.scalar(
            select(DealGame)
            .where(DealGame.entry_id == entry.id, DealGame.status.not_in(["COMPLETE", "EXPIRED"]))
            .order_by(DealGame.started_at.desc())
            .limit(1)
        )
    return {
        "season": week.season,
        "week": week.week,
        "opens_at": aware(week.opens_at),
        "closes_at": aware(week.closes_at),
        "status": week.scoring_status,
        "is_open": aware(week.opens_at) <= now < aware(week.closes_at),
        "data_ready": bool(week.projection_snapshot_id),
        "entry": summary["entry"],
        "slots": summary["slots"],
        "next_slot": game.next_slot(db, entry) if entry else "RB1",
        "active_game_id": active.id if active else None,
        "mode": "practice" if settings.demo else "live",
    }


@app.get("/api/v1/week/public")
def public_week(db: Session = Depends(get_db)):
    return week_payload(db, game.current_week(db))


@app.get("/api/v1/week/current")
def week_current(user=Depends(current_user), db: Session = Depends(get_db)):
    return week_payload(db, game.current_week(db), user)


@app.post("/api/v1/entry/start")
def entry_start(user=Depends(limited_user), db: Session = Depends(get_db)):
    entry = game.start_entry(db, user)
    db.commit()
    return scoring.lineup(db, entry)


@app.post("/api/v1/deal-games")
def deal_start(body: StartGame, user=Depends(limited_user), db: Session = Depends(get_db)):
    result = game.start_game(db, user, body.slot)
    db.commit()
    return game.public_game(db, result)


@app.get("/api/v1/deal-games/{game_id}")
def deal_get(game_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    game.begin_write(db)
    result = game.owned_game(db, user, game_id, lock=True)
    game.expire_if_needed(db, result, user, utcnow())
    db.commit()
    return game.public_game(db, result)


def perform(db, user, game_id, action, value, version):
    result = game.act(db, user, game_id, action, value, version)
    db.commit()
    return game.public_game(db, result)


@app.post("/api/v1/deal-games/{game_id}/select-case")
def select_case(
    game_id: str, body: CaseSelection, user=Depends(limited_user), db: Session = Depends(get_db)
):
    return perform(db, user, game_id, "select", body.case_number, body.version)


@app.post("/api/v1/deal-games/{game_id}/cases/{number}/open")
def open_case(
    game_id: str,
    number: int,
    body: Versioned,
    user=Depends(limited_user),
    db: Session = Depends(get_db),
):
    return perform(db, user, game_id, "open", number, body.version)


@app.post("/api/v1/deal-games/{game_id}/offers/{number}/decision")
def decide(
    game_id: str,
    number: int,
    body: Decision,
    user=Depends(limited_user),
    db: Session = Depends(get_db),
):
    return perform(db, user, game_id, "decision", (number, body.decision), body.version)


@app.post("/api/v1/deal-games/{game_id}/final-choice")
def final_choice(
    game_id: str, body: FinalChoice, user=Depends(limited_user), db: Session = Depends(get_db)
):
    return perform(db, user, game_id, "final", body.choice, body.version)


@app.get("/api/v1/profile")
def get_profile(user=Depends(current_user), db: Session = Depends(get_db)):
    profile = db.get(Profile, user)
    return {
        "user_id": user,
        "username": profile.username if profile else "",
        "display_name": profile.display_name if profile else "",
        "favorite_team": profile.favorite_team if profile else None,
        "profile_complete": profile_complete(profile),
        "teams": [{"code": code, "name": name} for code, name in NFL_TEAMS.items()],
        "is_admin": user in settings.admin_user_ids.split(","),
    }


@app.get("/api/v1/profile/username-availability")
def check_username(username: str, user=Depends(limited_user), db: Session = Depends(get_db)):
    if not re.fullmatch(r"[a-zA-Z0-9_]{3,24}", username):
        raise HTTPException(422, "Use 3–24 letters, numbers or underscores.")
    available = username_available(db, username, user)
    return {
        "available": available,
        "suggestions": [] if available else username_suggestions(db, username, user),
    }


def username_conflict(db, username, user):
    return JSONResponse(
        status_code=409,
        content={
            "detail": "That username is already taken. Please choose a different one.",
            "suggestions": username_suggestions(db, username, user),
        },
    )


@app.patch("/api/v1/profile")
def update_profile(body: ProfileInput, user=Depends(limited_user), db: Session = Depends(get_db)):
    if not settings.demo and not db.scalar(
        text(
            "SELECT email_confirmed_at IS NOT NULL FROM auth.users WHERE id = CAST(:user AS uuid)"
        ),
        {"user": user},
    ):
        raise HTTPException(403, "Verify your email before setting up your profile.")
    username = body.username.lower()
    if not re.fullmatch(r"[a-z0-9_]{3,24}", username):
        raise HTTPException(422, "Use 3–24 letters, numbers or underscores.")
    if body.favorite_team not in NFL_TEAMS:
        raise HTTPException(422, "Choose a valid NFL team.")
    if not username_available(db, username, user):
        return username_conflict(db, username, user)
    profile = db.get(Profile, user)
    if not profile:
        profile = Profile(user_id=user)
        db.add(profile)
    profile.username, profile.display_name = username, body.display_name.strip()
    profile.favorite_team = body.favorite_team
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if not username_available(db, username, user):
            return username_conflict(db, username, user)
        raise
    return get_profile(user, db)


@app.get("/api/v1/lineup/current")
def current_lineup(user=Depends(current_user), db: Session = Depends(get_db)):
    week = game.current_week(db)
    data = scoring.lineup(db, game.get_entry(db, user, week))
    data["rank"] = next(
        (
            r["rank"]
            for r in scoring.weekly_leaderboard(db, week.season, week.week)["rows"]
            if r["user_id"] == user
        ),
        None,
    )
    return data


@app.get("/api/v1/lineup/{season}/{week}")
@app.get("/api/v1/history/{season}/{week}")
def past_lineup(season: int, week: int, user=Depends(current_user), db: Session = Depends(get_db)):
    entry = db.scalar(
        select(WeeklyEntry).where(
            WeeklyEntry.user_id == user, WeeklyEntry.season == season, WeeklyEntry.week == week
        )
    )
    if not entry:
        raise HTTPException(404, "No entry exists for that week.")
    return scoring.lineup(db, entry)


@app.get("/api/v1/history")
def history(user=Depends(current_user), db: Session = Depends(get_db)):
    entries = db.scalars(
        select(WeeklyEntry)
        .where(WeeklyEntry.user_id == user)
        .order_by(WeeklyEntry.season.desc(), WeeklyEntry.week.desc())
    ).all()
    return [scoring.lineup(db, entry) for entry in entries]


@app.get("/api/v1/leaderboards/weekly")
def weekly_board(season: int, week: int, db: Session = Depends(get_db)):
    return scoring.weekly_leaderboard(db, season, week)


@app.get("/api/v1/leaderboards/season")
def season_board(season: int, db: Session = Depends(get_db)):
    return scoring.season_leaderboard(db, season)


@app.get("/api/v1/leaderboards/weekly/{season}/{week}/lineups/{user_id}")
def leaderboard_player_lineup(
    season: int,
    week: int,
    user_id: str,
    viewer=Depends(current_user),
    db: Session = Depends(get_db),
):
    return scoring.leaderboard_lineup(db, season, week, user_id)


@app.get("/api/v1/admin/health")
def admin_health(user=Depends(admin_user), db: Session = Depends(get_db)):
    runs = db.scalars(select(ProviderRun).order_by(ProviderRun.created_at.desc()).limit(30)).all()
    snapshots = db.scalars(
        select(ProjectionSnapshot).order_by(ProjectionSnapshot.fetched_at.desc()).limit(5)
    ).all()
    return {
        "runs": [
            {
                "id": r.id,
                "status": r.status,
                "operation": r.operation,
                "message": r.message,
                "created_at": aware(r.created_at),
            }
            for r in runs
        ],
        "snapshots": [
            {"id": s.id, "season": s.season, "week": s.week, "fetched_at": aware(s.fetched_at)}
            for s in snapshots
        ],
    }


@app.post("/api/v1/admin/sync/{operation}")
def admin_sync(
    operation: Literal["projections", "results"],
    season: int,
    week: int,
    user=Depends(admin_user),
    db: Session = Depends(get_db),
):
    return run_sync(db, ESPNProvider(), operation, season, week)


@app.post("/api/v1/admin/import")
def import_csv(
    file: UploadFile = File(...),
    season: int = Form(...),
    week: int = Form(...),
    operation: Literal["projections", "results"] = Form(...),
    user=Depends(admin_user),
    db: Session = Depends(get_db),
):
    data = file.file.read(5_000_001)
    if len(data) > 5_000_000:
        raise HTTPException(413, "CSV must be smaller than 5 MB.")
    try:
        content = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(422, "CSV must be UTF-8 encoded.") from None
    return run_sync(db, CSVProvider(content, season, week), operation, season, week)


@app.post("/api/v1/admin/weeks/{season}/{week}/{operation}")
def admin_week(
    season: int,
    week: int,
    operation: Literal["recompute", "finalize", "unfinalize"],
    user=Depends(admin_user),
    db: Session = Depends(get_db),
):
    if operation == "recompute":
        scoring.recompute(db, season, week)
    else:
        scoring.finalize(db, season, week, operation == "finalize")
    db.commit()
    return {"status": "ok"}


@app.get("/api/v1/admin/games/{game_id}/audit")
def admin_audit(game_id: str, user=Depends(admin_user), db: Session = Depends(get_db)):
    events = db.scalars(
        select(DealEvent).where(DealEvent.deal_game_id == game_id).order_by(DealEvent.created_at)
    ).all()
    return [
        {"event_type": e.event_type, "payload": e.payload, "created_at": aware(e.created_at)}
        for e in events
    ]


@app.post("/api/v1/admin/games/{game_id}/expire")
def admin_expire(game_id: str, user=Depends(admin_user), db: Session = Depends(get_db)):
    result = db.scalar(select(DealGame).where(DealGame.id == game_id).with_for_update())
    if not result or result.status == "COMPLETE":
        raise HTTPException(409, "Only unfinished games can be expired.")
    result.status, result.version = "EXPIRED", result.version + 1
    game.event(db, result, user, "ADMIN_EXPIRED")
    db.commit()
    return {"status": "EXPIRED"}

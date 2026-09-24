import logging
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.time import aware, utcnow
from app.models import (
    DealCase,
    DealEvent,
    DealGame,
    DealOffer,
    LineupSlot,
    NFLGame,
    NFLWeek,
    Player,
    Profile,
    Projection,
    ProjectionSnapshot,
    WeeklyEntry,
)
from app.services.rules import (
    ALGORITHM_VERSION,
    DEALER_ALGORITHM_VERSION,
    ROUND_QUOTAS,
    SLOTS,
    Candidate,
    RuleError,
    Slot,
    Status,
    assert_window,
    build_eligible_pool,
    calculate_dealer_target,
    create_board,
    dealer_random_factor,
    find_closest_offer_player,
    is_playable_projection,
    next_round_state,
    validate_case_open,
)

log = logging.getLogger(__name__)


def begin_write(db: Session):
    if db.bind.dialect.name == "sqlite" and not db.in_transaction():
        db.execute(text("BEGIN IMMEDIATE"))


def current_week(db: Session, now: datetime | None = None) -> NFLWeek:
    now = now or utcnow()
    week = db.scalar(
        select(NFLWeek).where(NFLWeek.opens_at <= now).order_by(NFLWeek.opens_at.desc()).limit(1)
    )
    if week is None:
        week = db.scalar(select(NFLWeek).order_by(NFLWeek.opens_at).limit(1))
    if week is None:
        raise RuleError(
            "Weekly player data is temporarily unavailable. Please check back soon.", 503
        )
    return week


def get_entry(db: Session, user: str, week: NFLWeek):
    return db.scalar(
        select(WeeklyEntry).where(
            WeeklyEntry.user_id == user,
            WeeklyEntry.season == week.season,
            WeeklyEntry.week == week.week,
            WeeklyEntry.game_type == "DEAL",
        )
    )


def entry_slots(db: Session, entry: WeeklyEntry):
    slots = db.scalars(select(LineupSlot).where(LineupSlot.entry_id == entry.id)).all()
    return sorted(slots, key=lambda s: SLOTS.index(Slot(s.slot)))


def next_slot(db: Session, entry: WeeklyEntry):
    return next((s.slot for s in entry_slots(db, entry) if not s.player_id), None)


def start_entry(db: Session, user: str, now: datetime | None = None):
    now = now or utcnow()
    begin_write(db)
    # Serializes initial entry creation across processes and duplicate requests.
    profile = db.scalar(select(Profile).where(Profile.user_id == user).with_for_update())
    if not profile or not profile.favorite_team:
        raise RuleError(
            "Choose a username and favorite NFL team in your profile before playing.", 428
        )
    week = current_week(db, now)
    assert_window(now, aware(week.opens_at), aware(week.closes_at))
    entry = get_entry(db, user, week)
    if entry:
        return entry
    entry = WeeklyEntry(user_id=user, season=week.season, week=week.week)
    db.add(entry)
    db.flush()
    db.add_all(LineupSlot(entry_id=entry.id, slot=s) for s in SLOTS)
    db.flush()
    return entry


def candidate_pool(db: Session, snapshot_id: str):
    rows = db.execute(
        select(Projection, Player, NFLGame)
        .join(
            Player,
            Player.id == Projection.player_id,
        )
        .join(NFLGame, NFLGame.id == Projection.nfl_game_id)
        .where(Projection.snapshot_id == snapshot_id)
    ).all()
    return [
        Candidate(
            p.id,
            projection.projected_ppr,
            projection.position,
            aware(nfl_game.kickoff_at),
            p.active,
        )
        for projection, p, nfl_game in rows
    ]


def event(db: Session, game: DealGame, user: str, kind: str, payload: dict | None = None):
    db.add(DealEvent(deal_game_id=game.id, user_id=user, event_type=kind, payload=payload or {}))
    log.info("game_event", extra={"event": kind, "game_id": game.id, "user_id": user})


def expire_if_needed(db: Session, game: DealGame, user: str, now: datetime) -> bool:
    if game.status in {Status.COMPLETE, Status.EXPIRED}:
        return game.status == Status.EXPIRED
    # Preserve completed picks, but never award a legacy case/offer below the current minimum.
    invalid_case = any(not is_playable_projection(c.projection) for c in game_cases(db, game))
    invalid_offer = any(
        o.decision == "PENDING" and not is_playable_projection(o.offered_player_projection)
        for o in game_offers(db, game)
    )
    if invalid_case or invalid_offer:
        game.status = Status.EXPIRED
        game.version += 1
        event(db, game, user, "GAME_EXPIRED", {"reason": "PROJECTION_ELIGIBILITY_UPDATED"})
        return True
    # An earlier rescheduled kickoff must also close an already-created game.
    kickoffs = db.scalars(
        select(NFLGame.kickoff_at)
        .join(
            Projection,
            Projection.nfl_game_id == NFLGame.id,
        )
        .where(
            Projection.snapshot_id == game.projection_snapshot_id,
            Projection.player_id.in_(game.candidate_ids),
        )
    ).all()
    expiry = min([aware(game.expires_at)] + [aware(k) for k in kickoffs])
    if now >= expiry:
        game.status = Status.EXPIRED
        game.version += 1
        event(db, game, user, "GAME_EXPIRED")
        return True
    return False


def start_game(db: Session, user: str, slot: Slot, now: datetime | None = None):
    now = now or utcnow()
    entry = start_entry(db, user, now)
    entry = db.scalar(select(WeeklyEntry).where(WeeklyEntry.id == entry.id).with_for_update())
    if next_slot(db, entry) != slot:
        raise RuleError("Complete the lineup slots in order. Completed slots cannot be replayed.")
    existing = db.scalars(
        select(DealGame)
        .where(
            DealGame.entry_id == entry.id,
            DealGame.slot == slot,
            DealGame.status.not_in([Status.EXPIRED, Status.COMPLETE]),
        )
        .with_for_update()
    ).all()
    for game in existing:
        if not expire_if_needed(db, game, user, now):
            return game
    week = current_week(db, now)
    snapshot = (
        db.get(ProjectionSnapshot, week.projection_snapshot_id)
        if week.projection_snapshot_id
        else None
    )
    if not snapshot or snapshot.status != "SUCCESS":
        raise RuleError("Weekly player data is temporarily unavailable.", 503)
    rostered = {s.player_id for s in entry_slots(db, entry) if s.player_id}
    pool = build_eligible_pool(candidate_pool(db, snapshot.id), slot, rostered, now)
    board, seed, seed_hash = create_board(pool)
    game = DealGame(
        entry_id=entry.id,
        slot=slot,
        projection_snapshot_id=snapshot.id,
        algorithm_version=ALGORITHM_VERSION,
        seed=seed,
        seed_hash=seed_hash,
        candidate_ids=[p.id for p in pool],
        expires_at=min(aware(week.closes_at), *(p.kickoff_at for p in pool)),
        started_at=now,
    )
    db.add(game)
    db.flush()
    db.add_all(
        DealCase(
            deal_game_id=game.id,
            case_number=p.case_number,
            player_id=p.player.id,
            tier_number=p.tier_number,
            full_pool_rank=p.full_pool_rank,
            board_rank=p.board_rank,
            projection=p.player.projection,
        )
        for p in board
    )
    event(
        db,
        game,
        user,
        "GAME_CREATED",
        {"snapshot_id": snapshot.id, "algorithm": game.algorithm_version},
    )
    db.flush()
    return game


def owned_game(db: Session, user: str, game_id: str, lock=False):
    lookup = db.execute(
        select(DealGame.id, DealGame.entry_id)
        .join(
            WeeklyEntry,
            WeeklyEntry.id == DealGame.entry_id,
        )
        .where(DealGame.id == game_id, WeeklyEntry.user_id == user)
    ).first()
    if not lookup:
        raise RuleError("Game not found.", 404)
    if lock:
        db.execute(select(WeeklyEntry).where(WeeklyEntry.id == lookup.entry_id).with_for_update())
    stmt = select(DealGame).where(DealGame.id == game_id).execution_options(populate_existing=True)
    return db.scalar(stmt.with_for_update() if lock else stmt)


def game_cases(db: Session, game: DealGame):
    return list(
        db.scalars(
            select(DealCase).where(DealCase.deal_game_id == game.id).order_by(DealCase.case_number)
        )
    )


def game_offers(db: Session, game: DealGame):
    return list(
        db.scalars(
            select(DealOffer)
            .where(DealOffer.deal_game_id == game.id)
            .order_by(DealOffer.offer_number)
        )
    )


def make_offer(db: Session, game: DealGame, user: str, cases):
    remaining = [c.projection for c in cases if c.status == "CLOSED"]
    calculation = calculate_dealer_target(
        remaining, dealer_random_factor(game.seed, game.current_round)
    )
    audit = {
        "dealer_algorithm": DEALER_ALGORITHM_VERSION,
        "expected_value": str(calculation.expected_value),
        "standard_deviation": str(calculation.standard_deviation),
        "ev_multiplier": str(calculation.ev_multiplier),
        "risk_weight": str(calculation.risk_weight),
        "base_target": str(calculation.base_target),
        "random_factor": str(calculation.random_factor),
        "target_projection": str(calculation.target_projection),
    }
    log.info(
        "dealer_calculation",
        extra={
            "game_id": game.id,
            **audit,
        },
    )
    # Eligibility was frozen at creation; expiry covers the entire candidate pool.
    pool = [
        p for p in candidate_pool(db, game.projection_snapshot_id) if p.id in game.candidate_ids
    ]
    prior = {o.offered_player_id for o in game_offers(db, game)}
    player = find_closest_offer_player(pool, calculation.target_projection, prior)
    db.add(
        DealOffer(
            deal_game_id=game.id,
            offer_number=game.current_round,
            cases_remaining=len(remaining),
            expected_value=calculation.expected_value,
            ev_multiplier=calculation.ev_multiplier,
            target_projection=calculation.target_projection,
            offered_player_id=player.id,
            offered_player_projection=player.projection,
        )
    )
    # Persist the exact inputs, SD and random draw in the server-only audit event.
    event(db, game, user, "OFFER_CREATED", {"round": game.current_round, **audit})


def award(db: Session, game: DealGame, user: str, player_id: str, projection, outcome: str, now):
    entry = db.get(WeeklyEntry, game.entry_id)
    slots = entry_slots(db, entry)
    slot = next(s for s in slots if s.slot == game.slot)
    if slot.player_id or any(s.player_id == player_id for s in slots):
        raise RuleError("This slot or player is already locked into your lineup.")
    slot.player_id = player_id
    slot.projection_when_acquired = projection
    slot.acquisition_method = outcome
    slot.deal_game_id = game.id
    game.status = Status.COMPLETE
    game.outcome = outcome
    game.awarded_player_id = player_id
    game.completed_at = now
    if all(s.player_id for s in slots):
        entry.status = "COMPLETE"
        entry.completed_at = now
    event(db, game, user, "GAME_COMPLETED", {"outcome": outcome, "player_id": player_id})


def act(db: Session, user: str, game_id: str, action: str, value, version: int, now=None):
    now = now or utcnow()
    begin_write(db)
    game = owned_game(db, user, game_id, lock=True)
    if expire_if_needed(db, game, user, now):
        db.commit()  # Persist expiry even though the requested action is rejected.
        raise RuleError(
            "This game is no longer eligible to continue. Restart this slot while the week is open.",
            410,
        )
    entry = db.get(WeeklyEntry, game.entry_id)
    week = db.scalar(
        select(NFLWeek).where(NFLWeek.season == entry.season, NFLWeek.week == entry.week)
    )
    assert_window(now, aware(week.opens_at), aware(week.closes_at))
    if game.version != version:
        raise RuleError("The game changed in another request. Refresh and try again.")
    if game.status == Status.COMPLETE:
        raise RuleError("This lineup slot is already complete.")
    cases = game_cases(db, game)
    if action == "select":
        if game.status != Status.SELECT:
            raise RuleError("Your case has already been selected.")
        if value not in range(1, 13):
            raise RuleError("Choose a case numbered 1 through 12.", 422)
        game.selected_case_number = value
        game.current_round = 1
        game.status = Status.ROUND_1
        event(db, game, user, "CASE_SELECTED", {"case_number": value})
    elif action == "open":
        case = next((c for c in cases if c.case_number == value), None)
        if not case:
            raise RuleError("Case not found.", 404)
        validate_case_open(game.status, game.selected_case_number, value, case.status == "CLOSED")
        case.status = "ELIMINATED"
        case.opened_at = now
        case.opened_order = sum(c.status == "ELIMINATED" for c in cases)
        game.round_open_count += 1
        game.status = next_round_state(game.current_round, game.round_open_count)
        event(db, game, user, "CASE_OPENED", {"case_number": value, "player_id": case.player_id})
        if game.status.startswith("OFFER_"):
            make_offer(db, game, user, cases)
    elif action == "decision":
        offer_number, decision = value
        if game.status != f"OFFER_{offer_number}" or decision not in {"DEAL", "NO_DEAL"}:
            raise RuleError("This offer is not awaiting a decision.")
        offer = next(o for o in game_offers(db, game) if o.offer_number == offer_number)
        if offer.decision != "PENDING":
            raise RuleError("This offer has already been decided.")
        offer.decision, offer.decided_at = decision, now
        event(
            db,
            game,
            user,
            "OFFER_ACCEPTED" if decision == "DEAL" else "OFFER_DECLINED",
            {"round": offer_number},
        )
        if decision == "DEAL":
            award(
                db,
                game,
                user,
                offer.offered_player_id,
                offer.offered_player_projection,
                "DEAL",
                now,
            )
        elif game.current_round == 4:
            game.status = Status.FINAL
        else:
            game.current_round += 1
            game.round_open_count = 0
            game.status = f"ROUND_{game.current_round}"
    elif action == "final":
        if game.status != Status.FINAL or value not in {"KEEP", "SWAP"}:
            raise RuleError("The final choice is not available.")
        remaining = [c for c in cases if c.status == "CLOSED"]
        chosen = next(
            c
            for c in remaining
            if (c.case_number == game.selected_case_number) == (value == "KEEP")
        )
        for case in remaining:
            case.status = "FINAL_SELECTED" if case == chosen else "FINAL_OTHER"
        event(db, game, user, f"FINAL_{value}")
        award(db, game, user, chosen.player_id, chosen.projection, f"FINAL_{value}", now)
    else:
        raise RuleError("Unknown game action.", 422)
    game.version += 1
    db.flush()
    return game


def player_matchup(projection: Projection | None, nfl_game: NFLGame | None):
    if not projection:
        return {"opponent": None, "is_home": None}
    is_home = None
    if nfl_game and projection.team in {nfl_game.home_team, nfl_game.away_team}:
        is_home = projection.team == nfl_game.home_team
    return {
        "team": projection.team,
        "opponent": projection.opponent or None,
        "is_home": is_home,
    }


def public_player(player: Player, projection=None, **extra):
    return {
        "id": player.id,
        "name": player.full_name,
        "team": player.team,
        "position": player.position,
        "projection": float(projection) if projection is not None else None,
        "opponent": None,
        "is_home": None,
        **extra,
    }


def public_game(db: Session, game: DealGame):
    cases, offers = game_cases(db, game), game_offers(db, game)
    ids = {c.player_id for c in cases} | {o.offered_player_id for o in offers}
    players = {p.id: p for p in db.scalars(select(Player).where(Player.id.in_(ids)))}
    matchups = {
        projection.player_id: player_matchup(projection, nfl_game)
        for projection, nfl_game in db.execute(
            select(Projection, NFLGame)
            .outerjoin(NFLGame, NFLGame.id == Projection.nfl_game_id)
            .where(
                Projection.snapshot_id == game.projection_snapshot_id,
                Projection.player_id.in_(ids),
            )
        )
    }
    board = [
        public_player(
            players[c.player_id],
            c.projection,
            board_rank=c.board_rank,
            eliminated=c.status == "ELIMINATED",
            **matchups.get(c.player_id, {}),
        )
        for c in sorted(cases, key=lambda c: c.board_rank)
    ]
    public_cases = []
    for case in cases:
        item = {
            "case_number": case.case_number,
            "status": case.status,
            "is_user_case": case.case_number == game.selected_case_number,
        }
        # Only reveal the original user case after an accepted deal; other closed cases remain hidden.
        reveal = case.status != "CLOSED" or (
            game.status == Status.COMPLETE and item["is_user_case"]
        )
        if reveal:
            item["player"] = public_player(
                players[case.player_id],
                case.projection,
                board_rank=case.board_rank,
                **matchups.get(case.player_id, {}),
            )
        public_cases.append(item)
    offer_rows = [
        {
            "offer_number": o.offer_number,
            "decision": o.decision,
            "player": public_player(
                players[o.offered_player_id],
                o.offered_player_projection,
                **matchups.get(o.offered_player_id, {}),
            ),
        }
        for o in offers
    ]
    instruction = "Choose your case"
    if game.status.startswith("ROUND_"):
        instruction = (
            f"Open {ROUND_QUOTAS[game.current_round - 1] - game.round_open_count} more cases"
        )
    elif game.status.startswith("OFFER_"):
        instruction = "The Dealer is calling"
    elif game.status == Status.FINAL:
        instruction = "Two cases remain. Keep or swap?"
    elif game.status == Status.COMPLETE:
        instruction = f"{game.slot} locked in"
    elif game.status == Status.EXPIRED:
        instruction = "This game has expired"
    awarded = next((p for p in board if p["id"] == game.awarded_player_id), None)
    if not awarded:
        awarded = next((o["player"] for o in offer_rows if o["decision"] == "DEAL"), None)
    return {
        "id": game.id,
        "slot": game.slot,
        "status": game.status,
        "version": game.version,
        "expires_at": aware(game.expires_at),
        "current_round": game.current_round,
        "round_open_count": game.round_open_count,
        "selected_case_number": game.selected_case_number,
        "board": board,
        "cases": public_cases,
        "offers": offer_rows,
        "instruction": instruction,
        "outcome": game.outcome,
        "awarded_player": awarded,
    }

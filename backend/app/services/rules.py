"""Pure, deterministic domain rules. No provider, HTTP, or database dependencies."""

import hashlib
import random
import secrets
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class Slot(StrEnum):
    RB1 = "RB1"
    RB2 = "RB2"
    WR1 = "WR1"
    WR2 = "WR2"
    TE = "TE"
    FLEX = "FLEX"


class Status(StrEnum):
    SELECT = "AWAITING_CASE_SELECTION"
    ROUND_1 = "ROUND_1"
    OFFER_1 = "OFFER_1"
    ROUND_2 = "ROUND_2"
    OFFER_2 = "OFFER_2"
    ROUND_3 = "ROUND_3"
    OFFER_3 = "OFFER_3"
    ROUND_4 = "ROUND_4"
    OFFER_4 = "OFFER_4"
    FINAL = "FINAL_CHOICE"
    COMPLETE = "COMPLETE"
    EXPIRED = "EXPIRED"


SLOTS = tuple(Slot)
POOL_TIER_COUNT = 10
CASE_COUNT = 12
EXTRA_PLAYER_TIERS = {2, 4}
# Larger tiers come first, so 14 players give tiers 2 and 4 two members each.
MIN_POOL_SIZE = POOL_TIER_COUNT + max(EXTRA_PLAYER_TIERS)
ALGORITHM_VERSION = "risk-v4-10tiers-extra2and4"
DEALER_ALGORITHM_VERSION = "ev-sd-jitter-v1"
MIN_GAME_PROJECTION = Decimal("3.0")
ROUND_QUOTAS = (4, 3, 2, 1)
DEALER_EV_MULTIPLIER = {
    8: Decimal("0.88"),
    5: Decimal("0.95"),
    3: Decimal("1.00"),
    2: Decimal("1.05"),
}
DEALER_RISK_WEIGHT = {
    8: Decimal("0.10"),
    5: Decimal("0.15"),
    3: Decimal("0.20"),
    2: Decimal("0.25"),
}


class RuleError(Exception):
    def __init__(self, message: str, status: int = 409):
        self.message = message
        self.status = status
        super().__init__(message)


@dataclass(frozen=True)
class Candidate:
    id: str
    projection: Decimal
    position: str
    kickoff_at: datetime
    active: bool = True


@dataclass(frozen=True)
class SelectedPlayer:
    player: Candidate
    tier_number: int
    full_pool_rank: int
    board_rank: int
    case_number: int


def is_playable_projection(projection: Decimal) -> bool:
    return projection.is_finite() and projection >= MIN_GAME_PROJECTION


def build_eligible_pool(players, slot: Slot, rostered: set[str], now: datetime):
    allowed = {"RB", "WR", "TE"} if slot == Slot.FLEX else {slot.value.rstrip("12")}
    return sorted(
        (
            p
            for p in players
            if p.active
            and p.position in allowed
            and is_playable_projection(p.projection)
            and p.id not in rostered
            and p.kickoff_at > now
        ),
        key=lambda p: (-p.projection, p.id),
    )


def split_into_10_tiers(players):
    if len(players) < POOL_TIER_COUNT:
        raise RuleError("Fewer than 10 eligible players are available for this position.", 503)
    size, remainder = divmod(len(players), POOL_TIER_COUNT)
    start, tiers = 0, []
    for i in range(POOL_TIER_COUNT):
        end = start + size + (i < remainder)
        tiers.append(players[start:end])
        start = end
    return tiers


def create_board(pool, seed: str | None = None):
    # Defend this boundary as well as the shared case/Dealer eligibility filter.
    pool = sorted(
        (p for p in pool if is_playable_projection(p.projection)),
        key=lambda p: (-p.projection, p.id),
    )
    seed = seed or secrets.token_hex(32)
    rng = random.Random(seed)
    ranks = {p.id: i + 1 for i, p in enumerate(pool)}
    tiers = split_into_10_tiers(pool)
    selected = []
    for number, tier in enumerate(tiers, 1):
        count = 2 if number in EXTRA_PLAYER_TIERS else 1
        if len(tier) < count:
            raise RuleError(
                "At least 14 eligible players are required so tiers 2 and 4 each have two players.",
                503,
            )
        selected.extend((p, number) for p in rng.sample(tier, count))
    selected.sort(key=lambda p: (-p[0].projection, p[0].id))
    numbers = list(range(1, CASE_COUNT + 1))
    rng.shuffle(numbers)
    board = [
        SelectedPlayer(p, tier, ranks[p.id], rank + 1, numbers[rank])
        for rank, (p, tier) in enumerate(selected)
    ]
    return board, seed, hashlib.sha256(seed.encode()).hexdigest()


def calculate_remaining_ev(projections) -> Decimal:
    if not projections:
        raise RuleError("Cannot calculate an empty board")
    return sum(projections, Decimal(0)) / len(projections)


@dataclass(frozen=True)
class DealerTarget:
    expected_value: Decimal
    standard_deviation: Decimal
    ev_multiplier: Decimal
    risk_weight: Decimal
    base_target: Decimal
    random_factor: Decimal
    target_projection: Decimal


def dealer_random_factor(seed: str, offer_number: int) -> Decimal:
    if offer_number not in range(1, 5):
        raise RuleError("Invalid Dealer offer number.")
    # Independent of the case shuffle. Retries produce the same draw, even after rollback.
    rng = random.Random(f"{DEALER_ALGORITHM_VERSION}:{seed}:offer:{offer_number}")
    return Decimal(rng.randint(9700, 10300)) / Decimal(10000)


def calculate_dealer_target(projections, random_factor: Decimal = Decimal("1")) -> DealerTarget:
    if len(projections) not in DEALER_EV_MULTIPLIER:
        raise RuleError("Dealer offers require 8, 5, 3, or 2 unopened cases.")
    if any(not p.is_finite() for p in projections):
        raise RuleError("Dealer projections must be finite.")
    if not random_factor.is_finite() or not Decimal("0.97") <= random_factor <= Decimal("1.03"):
        raise RuleError("Dealer random factor must be between 0.97 and 1.03.")
    ev = calculate_remaining_ev(projections)
    # The unopened cases are the whole population, including the user's sealed case.
    variance = sum(((p - ev) ** 2 for p in projections), Decimal(0)) / len(projections)
    sd = variance.sqrt()
    multiplier = DEALER_EV_MULTIPLIER[len(projections)]
    risk_weight = DEALER_RISK_WEIGHT[len(projections)]
    base_target = ev * multiplier + sd * risk_weight
    return DealerTarget(
        ev, sd, multiplier, risk_weight, base_target, random_factor, base_target * random_factor
    )


def find_closest_offer_player(candidates, target: Decimal, excluded: set[str]):
    candidates = [
        p for p in candidates if p.id not in excluded and is_playable_projection(p.projection)
    ]
    if not candidates:
        raise RuleError("No eligible Dealer candidates remain", 503)
    return min(
        candidates,
        key=lambda p: (
            abs(p.projection - target),
            0 if p.projection <= target else 1,
            p.projection,
            p.id,
        ),
    )


def assert_window(now: datetime, opens: datetime, closes: datetime):
    if not opens <= now < closes:
        raise RuleError("This week's lineup window is closed.")


def validate_case_open(status: str, selected: int | None, number: int, is_closed: bool):
    if status not in {f"ROUND_{i}" for i in range(1, 5)}:
        raise RuleError("Cases cannot be opened in the current game state.")
    if number == selected:
        raise RuleError("Your case must stay sealed until the final choice.")
    if not is_closed:
        raise RuleError("This case has already been opened.")


def next_round_state(round_number: int, opened: int) -> str:
    quota = ROUND_QUOTAS[round_number - 1]
    if opened > quota:
        raise RuleError("The round's opening quota has already been reached.")
    return f"OFFER_{round_number}" if opened == quota else f"ROUND_{round_number}"

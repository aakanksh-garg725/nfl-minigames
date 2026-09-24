from collections import Counter
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from app.core.time import EASTERN, weekly_window
from app.services.rules import (
    DEALER_EV_MULTIPLIER,
    DEALER_RISK_WEIGHT,
    Candidate,
    RuleError,
    Slot,
    assert_window,
    build_eligible_pool,
    calculate_dealer_target,
    calculate_remaining_ev,
    create_board,
    dealer_random_factor,
    find_closest_offer_player,
    split_into_10_tiers,
    validate_case_open,
)

NOW = datetime(2026, 9, 22, 14, tzinfo=UTC)


def player(i, points=None, **kwargs):
    return Candidate(
        str(i).zfill(4),
        Decimal(str(points if points is not None else 100 - i)),
        kwargs.get("position", "RB"),
        kwargs.get("kickoff_at", NOW + timedelta(days=2)),
        kwargs.get("active", True),
    )


@pytest.mark.parametrize("count", [14, 15, 28, 77, 151])
def test_tiers_cover_entire_pool(count):
    pool = [player(i, count + 2 - i) for i in range(count)]
    tiers = split_into_10_tiers(pool)
    assert len(tiers) == 10
    assert [p for tier in tiers for p in tier] == pool
    sizes = [len(t) for t in tiers]
    assert max(sizes) - min(sizes) <= 1
    assert sizes == sorted(sizes, reverse=True)
    board, _, _ = create_board(pool, "fixed")
    assert len({p.player.id for p in board}) == 12
    assert Counter(p.tier_number for p in board) == {
        tier: 2 if tier in {2, 4} else 1 for tier in range(1, 11)
    }
    assert {p.case_number for p in board} == set(range(1, 13))
    for item in board:
        assert item.player in tiers[item.tier_number - 1]


@pytest.mark.parametrize("count", [0, 1, 9])
def test_insufficient_pool(count):
    with pytest.raises(RuleError):
        split_into_10_tiers([player(i) for i in range(count)])


@pytest.mark.parametrize("count", [10, 11, 12, 13])
def test_bonus_tiers_must_have_two_unique_players(count):
    with pytest.raises(RuleError, match="tiers 2 and 4"):
        create_board([player(i) for i in range(count)])


@pytest.mark.parametrize(
    "points", ["-1", "0", "0.001", "0.049", "0.05", "2.9", "2.999", "NaN", "Infinity", "-Infinity"]
)
def test_below_minimum_and_nonfinite_projections_never_enter_game(points):
    bad = player(1000, points)
    good = [player(i, 20 - i) for i in range(14)]
    pool = build_eligible_pool([bad, *good], Slot.RB1, set(), NOW)
    assert bad.id not in {p.id for p in pool}
    board, _, _ = create_board([bad, *good], "zero-regression")
    assert bad.id not in {p.player.id for p in board}
    assert find_closest_offer_player([bad, *good], Decimal(0), set()).id != bad.id
    with pytest.raises(RuleError):
        find_closest_offer_player([bad], Decimal(0), set())


def test_exact_three_points_is_playable_but_below_minimum_cannot_fill_tiers():
    valid = player(100, "3.0")
    assert build_eligible_pool([valid], Slot.RB1, set(), NOW) == [valid]
    assert find_closest_offer_player([valid], Decimal(0), set()) == valid
    with pytest.raises(RuleError, match="14 eligible"):
        create_board([player(i) for i in range(13)] + [player(99, "2.999")])
    board, _, _ = create_board([player(i) for i in range(13)] + [valid], "boundary")
    assert valid.id in {p.player.id for p in board}


def test_all_tiers_contribute_with_unique_bonus_picks_across_seeds():
    pool = [player(i, 142 - i) for i in range(140)]
    tiers = split_into_10_tiers(pool)
    for seed in range(25):
        board, _, _ = create_board(pool, str(seed))
        assert len({p.player.id for p in board}) == 12
        assert Counter(p.tier_number for p in board) == {
            tier: 2 if tier in {2, 4} else 1 for tier in range(1, 11)
        }
        assert [p.board_rank for p in board] == list(range(1, 13))
        for item in board:
            assert item.player in tiers[item.tier_number - 1]
    assert find_closest_offer_player(pool, Decimal(1), set()).projection == Decimal(3)


def test_eligibility_ties_and_roster():
    pool = [
        player(2, 10),
        player(1, 10),
        player(3, 0),
        player(4, 5, kickoff_at=NOW),
        player(5, 9, active=False),
        player(6, 8),
        player(7, 12, position="WR"),
    ]
    assert [p.id for p in build_eligible_pool(pool, Slot.RB1, {"0006"}, NOW)] == ["0001", "0002"]
    assert build_eligible_pool(pool, Slot.FLEX, set(), NOW)[0].position == "WR"


def test_reproducible_secure_board():
    pool = [player(i) for i in range(77)]
    assert create_board(pool, "seed") == create_board(pool, "seed")
    assert create_board(pool)[1] != create_board(pool)[1]


def test_exact_ev_and_coefficients():
    values = [Decimal(x) for x in ["22.4", "19.1", "16.7", "14.9", "12.2"]]
    assert calculate_remaining_ev(values) == Decimal("17.06")
    assert calculate_dealer_target(values).expected_value == Decimal("17.06")
    assert DEALER_EV_MULTIPLIER == {
        8: Decimal("0.88"),
        5: Decimal("0.95"),
        3: Decimal("1.00"),
        2: Decimal("1.05"),
    }
    assert DEALER_RISK_WEIGHT == {
        8: Decimal("0.10"),
        5: Decimal("0.15"),
        3: Decimal("0.20"),
        2: Decimal("0.25"),
    }


def test_requested_second_offer_example_uses_population_sd():
    calculation = calculate_dealer_target([Decimal(n) for n in [21, 18, 14, 9, 4]])
    assert calculation.expected_value == Decimal("13.2")
    assert calculation.standard_deviation == Decimal("37.36").sqrt()
    assert calculation.base_target.quantize(Decimal("0.01")) == Decimal("13.46")
    assert calculation.target_projection == calculation.base_target
    offer = find_closest_offer_player(
        [player(1, "9"), player(2, "13.5"), player(3, "15")],
        calculation.target_projection,
        set(),
    )
    assert offer.id == "0002"


@pytest.mark.parametrize(
    "count,multiplier,risk",
    [(8, "0.88", "0.10"), (5, "0.95", "0.15"), (3, "1.00", "0.20"), (2, "1.05", "0.25")],
)
def test_uniform_board_has_no_risk_premium(count, multiplier, risk):
    calculation = calculate_dealer_target([Decimal(10)] * count)
    assert calculation.standard_deviation == 0
    assert calculation.ev_multiplier == Decimal(multiplier)
    assert calculation.risk_weight == Decimal(risk)
    assert calculation.base_target == Decimal(10) * Decimal(multiplier)


def test_volatile_board_gets_higher_offer_for_same_ev():
    tight = calculate_dealer_target([Decimal(n) for n in [13, 14, 14]])
    volatile = calculate_dealer_target([Decimal(n) for n in [23, 15, 3]])
    assert tight.expected_value == volatile.expected_value
    assert volatile.standard_deviation > tight.standard_deviation
    assert volatile.target_projection > tight.target_projection


@pytest.mark.parametrize("factor", ["0.97", "1", "1.03"])
def test_random_factor_multiplies_the_entire_risk_adjusted_target(factor):
    calculation = calculate_dealer_target([Decimal(23), Decimal(15), Decimal(3)], Decimal(factor))
    assert calculation.target_projection == calculation.base_target * Decimal(factor)


def test_random_factor_is_repeatable_private_seed_and_round_specific():
    draws = {dealer_random_factor(str(seed), offer) for seed in range(100) for offer in range(1, 5)}
    assert all(Decimal("0.97") <= draw <= Decimal("1.03") for draw in draws)
    assert min(draws) < Decimal("0.99") and max(draws) > Decimal("1.01")
    assert dealer_random_factor("secret", 2) == dealer_random_factor("secret", 2)
    assert len({dealer_random_factor("secret", offer) for offer in range(1, 5)}) > 1


@pytest.mark.parametrize("factor", ["0.9699", "1.0301", "NaN", "Infinity"])
def test_invalid_random_factor_rejected(factor):
    with pytest.raises(RuleError):
        calculate_dealer_target([Decimal(10)] * 5, Decimal(factor))


@pytest.mark.parametrize("count", [0, 1, 4, 6, 12])
def test_invalid_offer_case_count_rejected(count):
    with pytest.raises(RuleError):
        calculate_dealer_target([Decimal(10)] * count)


@pytest.mark.parametrize(
    "target,expected", [(10, "0002"), (9, "0001"), (1, "0001"), (50, "0003"), (11, "0002")]
)
def test_offer_mapping(target, expected):
    assert (
        find_closest_offer_player(
            [player(1, 8), player(2, 10), player(3, 12)], Decimal(target), set()
        ).id
        == expected
    )


def test_offer_previous_exclusion():
    assert (
        find_closest_offer_player([player(1, 10), player(2, 10)], Decimal(10), {"0001"}).id
        == "0002"
    )


@pytest.mark.parametrize("sunday", [date(2026, 9, 27), date(2026, 11, 1), date(2026, 3, 8)])
def test_timezone_windows_and_exact_boundaries(sunday):
    opens, closes = weekly_window(sunday)
    assert opens.astimezone(EASTERN).hour == 9
    assert closes.astimezone(EASTERN).hour == 13
    assert_window(opens, opens, closes)
    assert_window(closes - timedelta(seconds=1), opens, closes)
    for invalid in [opens - timedelta(seconds=1), closes]:
        with pytest.raises(RuleError):
            assert_window(invalid, opens, closes)


@pytest.mark.parametrize(
    "status,selected,number,closed",
    [
        ("AWAITING_CASE_SELECTION", None, 2, True),
        ("ROUND_1", 2, 2, True),
        ("OFFER_1", 1, 2, True),
        ("COMPLETE", 1, 2, True),
        ("ROUND_2", 1, 2, False),
    ],
)
def test_invalid_case_open(status, selected, number, closed):
    with pytest.raises(RuleError):
        validate_case_open(status, selected, number, closed)

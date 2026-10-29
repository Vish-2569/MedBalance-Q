"""FEFO math unit tests — pure computation, no DB."""
from datetime import date

from medbal_common.fefo import compute_position


def test_worked_example_insulin():
    """50 vials, rate 2/day, expiry in 14 days -> 28 effective, 22 at-risk."""
    today = date(2026, 11, 1)
    lots = [{"batch_no": "B-001", "expiry": date(2026, 11, 15), "qty": 50}]
    result = compute_position("H4", "INSULIN", lots, rate=2.0, today=today,
                              min_reserve_days=7, target_days=21, lead_time_days=3)
    assert result.effective_stock == 28
    assert result.at_risk == 22
    assert result.shortage == 14  # ceil(2*21) - 28
    assert result.reserve == 14   # max(ceil(2*7), ceil(2*3*1.2)) = max(14, 8)
    assert len(result.lots) == 1
    assert result.lots[0].effective == 28
    assert result.lots[0].at_risk == 22


def test_multi_lot_fefo():
    """Two lots, earlier one consumed first."""
    today = date(2026, 11, 1)
    lots = [
        {"batch_no": "B-001", "expiry": date(2026, 11, 11), "qty": 30},
        {"batch_no": "B-002", "expiry": date(2026, 12, 1), "qty": 40},
    ]
    result = compute_position("H1", "PCM", lots, rate=2.0, today=today,
                              min_reserve_days=7, target_days=21, lead_time_days=3)
    assert result.effective_stock == 60
    assert result.at_risk == 10
    assert result.lots[0].effective == 20
    assert result.lots[0].at_risk == 10
    assert result.lots[1].effective == 40
    assert result.lots[1].at_risk == 0


def test_reserve_protected_from_longest():
    """Reserve is taken from longest-dated lots."""
    today = date(2026, 11, 1)
    lots = [
        {"batch_no": "B-001", "expiry": date(2026, 11, 11), "qty": 20},
        {"batch_no": "B-002", "expiry": date(2027, 6, 1), "qty": 100},
    ]
    result = compute_position("H1", "PCM", lots, rate=2.0, today=today,
                              min_reserve_days=7, target_days=21, lead_time_days=3)
    assert result.reserve == 14
    assert result.lots[1].reserved == 14
    assert result.lots[0].reserved == 0
    assert result.lots[0].transferable == 20
    assert result.lots[1].transferable == 86


def test_zero_rate():
    """Zero rate -> effective=0, everything at-risk, reserve=0."""
    today = date(2026, 11, 1)
    lots = [{"batch_no": "B-001", "expiry": date(2027, 1, 1), "qty": 100}]
    result = compute_position("H1", "PCM", lots, rate=0.0, today=today)
    assert result.effective_stock == 0
    assert result.at_risk == 100
    assert result.reserve == 0
    assert result.shortage == 0


def test_expired_lot():
    """Expired lot contributes 0 effective."""
    today = date(2026, 11, 15)
    lots = [{"batch_no": "B-001", "expiry": date(2026, 11, 10), "qty": 50}]
    result = compute_position("H1", "PCM", lots, rate=2.0, today=today)
    assert result.effective_stock == 0
    assert result.at_risk == 50


def test_no_lots():
    """No lots -> shortage = ceil(rate * target_days)."""
    today = date(2026, 11, 1)
    result = compute_position("H1", "PCM", [], rate=5.0, today=today,
                              target_days=21)
    assert result.effective_stock == 0
    assert result.at_risk == 0
    assert result.reserve == 0
    assert result.shortage == 105


def test_lots_returned_in_fefo_order():
    """Regardless of input order, output lots are sorted by expiry."""
    today = date(2026, 11, 1)
    lots = [
        {"batch_no": "B-LATE", "expiry": date(2027, 6, 1), "qty": 50},
        {"batch_no": "B-EARLY", "expiry": date(2026, 12, 1), "qty": 30},
    ]
    result = compute_position("H1", "PCM", lots, rate=1.0, today=today)
    assert result.lots[0].batch_no == "B-EARLY"
    assert result.lots[1].batch_no == "B-LATE"


def test_reserve_exceeds_stock():
    """Reserve larger than total stock -> all reserved, transferable=0."""
    today = date(2026, 11, 1)
    lots = [{"batch_no": "B-001", "expiry": date(2027, 6, 1), "qty": 5}]
    result = compute_position("H1", "PCM", lots, rate=3.0, today=today,
                              min_reserve_days=7, target_days=21, lead_time_days=3)
    # R = max(ceil(3*7), ceil(3*3*1.2)) = max(21, 11) = 21
    assert result.reserve == 21
    assert result.lots[0].reserved == 5  # can only reserve what exists
    assert result.lots[0].transferable == 0

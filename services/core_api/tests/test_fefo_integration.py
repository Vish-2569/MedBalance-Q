"""Integration test: FEFO positions from seed data."""
from __future__ import annotations

from datetime import date

from medbal_common.db import session_scope

from app.queries import get_lots_for_position, get_consumption_rate, get_policy
from medbal_common.fefo import compute_position


def test_h4_insulin_position(seed_data):
    """H4 has 50 insulin vials expiring 2026-11-19, rate ~0 (PHC, no usage)."""
    today = date(2026, 11, 1)
    with session_scope() as s:
        lots = get_lots_for_position(s, "H4", "INSULIN")
        rate = get_consumption_rate(s, "H4", "INSULIN", today)
        policy = get_policy(s, "H4", "INSULIN")

    pos = compute_position("H4", "INSULIN", lots, rate, today,
                           policy["min_reserve_days"], policy["target_days"],
                           policy["lead_time_days"])
    assert len(pos.lots) == 1
    assert pos.lots[0].qty == 50
    # With rate ~0, effective stock should be 0 and all 50 at risk
    if rate < 0.1:
        assert pos.effective_stock == 0
        assert pos.at_risk == 50


def test_h1_insulin_shortage(seed_data):
    """H1 has only 5 insulin vials — should show shortage."""
    today = date(2026, 11, 1)
    with session_scope() as s:
        lots = get_lots_for_position(s, "H1", "INSULIN")
        rate = get_consumption_rate(s, "H1", "INSULIN", today)

    pos = compute_position("H1", "INSULIN", lots, rate, today,
                           min_reserve_days=7, target_days=21, lead_time_days=3)
    assert len(pos.lots) == 1
    assert pos.lots[0].qty == 5
    # Even with moderate rate, 5 vials is a shortage
    if rate > 0:
        assert pos.shortage > 0


def test_positions_count(seed_data):
    """All facility×drug groups with lots should produce positions."""
    from app.queries import facility_drug_groups
    with session_scope() as s:
        groups = facility_drug_groups(s)
    assert len(groups) >= 3  # H4:INSULIN, H1:INSULIN, H1:PCM

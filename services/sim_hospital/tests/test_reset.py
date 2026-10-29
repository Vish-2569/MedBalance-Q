"""Reset restores initial state."""
from __future__ import annotations

from app import stock_db


def test_reset_restores_state():
    initial_stock = stock_db.get_total_stock()
    initial_count = stock_db.get_lot_count()
    assert initial_stock > 0

    # Consume some stock
    stock_db.decrement_lot("PCM", "B-PCM-H1-001", 100)
    stock_db.insert_consumption("2026-11-01", "PCM", 100, 100, 0)

    assert stock_db.get_total_stock() < initial_stock
    assert len(stock_db.get_consumption_log()) == 1

    # Reset
    stock_db.reset("h1")

    assert stock_db.get_total_stock() == initial_stock
    assert stock_db.get_lot_count() == initial_count
    assert len(stock_db.get_consumption_log()) == 0

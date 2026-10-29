"""FEFO dispensing tests."""
from __future__ import annotations

from app import stock_db
from app.consumption import dispense_fefo


def test_fefo_order():
    """Earlier-expiry lot consumed first."""
    conn = stock_db.get_conn()
    conn.execute("DELETE FROM lots")
    conn.execute(
        "INSERT INTO lots VALUES ('PCM','B1','2026-12-01',100,'active')"
    )
    conn.execute(
        "INSERT INTO lots VALUES ('PCM','B2','2026-11-15',50,'active')"
    )
    conn.commit()

    dispensed, stockout = dispense_fefo("PCM", 30)
    assert dispensed == 30
    assert stockout == 0

    lots = stock_db.get_active_lots("PCM")
    b2 = next(l for l in lots if l["batch_no"] == "B2")
    b1 = next(l for l in lots if l["batch_no"] == "B1")
    assert b2["qty"] == 20  # earlier lot consumed first
    assert b1["qty"] == 100  # later lot untouched


def test_expiry_zeros_lot():
    """Lot with expiry <= today gets zeroed."""
    conn = stock_db.get_conn()
    conn.execute("DELETE FROM lots")
    conn.execute(
        "INSERT INTO lots VALUES ('PCM','B1','2026-11-01',100,'active')"
    )
    conn.execute(
        "INSERT INTO lots VALUES ('PCM','B2','2026-12-01',200,'active')"
    )
    conn.commit()

    stock_db.expire_lots("2026-11-01")

    lots = stock_db.get_all_lots()
    b1 = next(l for l in lots if l["batch_no"] == "B1")
    b2 = next(l for l in lots if l["batch_no"] == "B2")
    assert b1["qty"] == 0
    assert b1["status"] == "expired"
    assert b2["qty"] == 200
    assert b2["status"] == "active"


def test_partial_dispensing():
    """First lot depleted, second partially consumed."""
    conn = stock_db.get_conn()
    conn.execute("DELETE FROM lots")
    conn.execute(
        "INSERT INTO lots VALUES ('PCM','B1','2026-11-15',20,'active')"
    )
    conn.execute(
        "INSERT INTO lots VALUES ('PCM','B2','2026-12-01',100,'active')"
    )
    conn.commit()

    dispensed, stockout = dispense_fefo("PCM", 50)
    assert dispensed == 50
    assert stockout == 0

    lots = stock_db.get_active_lots("PCM")
    assert len(lots) == 1  # B1 fully depleted (qty=0, not returned by active)
    assert lots[0]["batch_no"] == "B2"
    assert lots[0]["qty"] == 70


def test_stockout():
    """Demand exceeds all stock."""
    conn = stock_db.get_conn()
    conn.execute("DELETE FROM lots")
    conn.execute(
        "INSERT INTO lots VALUES ('PCM','B1','2026-12-01',30,'active')"
    )
    conn.commit()

    dispensed, stockout = dispense_fefo("PCM", 50)
    assert dispensed == 30
    assert stockout == 20

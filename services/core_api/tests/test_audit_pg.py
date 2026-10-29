"""Audit chain tests using SQLite (same logic, just verifying the adapter works)."""
from __future__ import annotations

from sqlalchemy import text

from medbal_common.db import session_scope
from medbal_common import audit


def test_audit_chain_ok(db_engine):
    with session_scope() as s:
        s.execute(text("DELETE FROM audit_log"))
        audit.append(s, "user1", "create", "order", "ORD-001", {"qty": 50})
        audit.append(s, "user1", "approve", "order", "ORD-001", {"status": "approved"})
        audit.append(s, "user2", "create", "order", "ORD-002", {"qty": 30})

    with session_scope() as s:
        result = audit.verify(s)
    assert result["ok"] is True
    assert result["entries"] == 3


def test_audit_tamper_detected(db_engine):
    with session_scope() as s:
        s.execute(text("DELETE FROM audit_log"))
        seq1 = audit.append(s, "user1", "create", "order", "ORD-001", {"qty": 50})
        audit.append(s, "user1", "approve", "order", "ORD-001", {"status": "approved"})

    with session_scope() as s:
        s.execute(
            text("UPDATE audit_log SET payload = :payload WHERE seq = :seq"),
            {"payload": '{"qty":999}', "seq": seq1},
        )
        s.commit()

    with session_scope() as s:
        result = audit.verify(s)
    assert result["ok"] is False
    assert result["first_bad_seq"] == seq1


def test_audit_empty_chain(db_engine):
    with session_scope() as s:
        s.execute(text("DELETE FROM audit_log"))
    with session_scope() as s:
        result = audit.verify(s)
    assert result["ok"] is True
    assert result["entries"] == 0

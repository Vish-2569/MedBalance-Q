from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

CREATE_AUDIT_TABLE = """
CREATE TABLE IF NOT EXISTS audit_log (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    entity TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

CREATE_AUDIT_TABLE_PG = """
CREATE TABLE IF NOT EXISTS audit_log (
    seq SERIAL PRIMARY KEY,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    entity TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    payload JSONB NOT NULL,
    hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def _canonical(data: dict) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def _compute_hash(prev_hash: str, entry: dict) -> str:
    raw = prev_hash + _canonical(entry)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _dialect(session: Session) -> str:
    try:
        return session.bind.dialect.name  # type: ignore[union-attr]
    except AttributeError:
        return "sqlite"


def append(
    session: Session,
    actor: str,
    action: str,
    entity: str,
    entity_id: str,
    payload: dict,
) -> int:
    row = session.execute(
        text("SELECT hash FROM audit_log ORDER BY seq DESC LIMIT 1")
    ).fetchone()
    prev_hash = row[0] if row else "0" * 64

    canonical_payload = _canonical(payload)
    entry = {
        "actor": actor,
        "action": action,
        "entity": entity,
        "entity_id": entity_id,
        "payload": canonical_payload,
    }
    new_hash = _compute_hash(prev_hash, entry)
    created_at = datetime.now(timezone.utc).isoformat()

    dialect = _dialect(session)

    if dialect == "postgresql":
        result = session.execute(
            text(
                "INSERT INTO audit_log (actor, action, entity, entity_id, payload, hash, created_at) "
                "VALUES (:actor, :action, :entity, :entity_id, CAST(:payload AS JSONB), :hash, :created_at) "
                "RETURNING seq"
            ),
            {
                "actor": actor,
                "action": action,
                "entity": entity,
                "entity_id": entity_id,
                "payload": canonical_payload,
                "hash": new_hash,
                "created_at": created_at,
            },
        )
        seq = result.scalar()
    else:
        session.execute(
            text(
                "INSERT INTO audit_log (actor, action, entity, entity_id, payload, hash, created_at) "
                "VALUES (:actor, :action, :entity, :entity_id, :payload, :hash, :created_at)"
            ),
            {
                "actor": actor,
                "action": action,
                "entity": entity,
                "entity_id": entity_id,
                "payload": canonical_payload,
                "hash": new_hash,
                "created_at": created_at,
            },
        )
        seq = session.execute(text("SELECT last_insert_rowid()")).scalar()

    return seq


def _payload_str(raw) -> str:
    """Normalise payload from DB: JSONB comes back as dict, SQLite as str."""
    if isinstance(raw, dict):
        return _canonical(raw)
    return raw


def verify(session: Session) -> dict:
    rows = session.execute(
        text("SELECT seq, actor, action, entity, entity_id, payload, hash FROM audit_log ORDER BY seq")
    ).fetchall()

    if not rows:
        return {"ok": True, "entries": 0, "first_bad_seq": None}

    prev_hash = "0" * 64
    for row in rows:
        seq, actor, action, entity, entity_id, payload, stored_hash = row
        entry = {
            "actor": actor,
            "action": action,
            "entity": entity,
            "entity_id": entity_id,
            "payload": _payload_str(payload),
        }
        expected = _compute_hash(prev_hash, entry)
        if expected != stored_hash:
            return {"ok": False, "entries": len(rows), "first_bad_seq": seq}
        prev_hash = stored_hash

    return {"ok": True, "entries": len(rows), "first_bad_seq": None}

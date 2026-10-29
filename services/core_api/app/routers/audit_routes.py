"""Audit endpoints: verify chain, query entries, tamper/restore demo."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from medbal_common.db import session_scope
from medbal_common import audit

from ..queries import get_audit_entries, tamper_audit_row, restore_audit_row

router = APIRouter()

_tamper_stash: dict[int, str] = {}


@router.get("/audit/verify")
async def verify_audit():
    with session_scope() as s:
        result = audit.verify(s)
    return JSONResponse(result)


@router.get("/audit")
async def query_audit(entity: str | None = None, id: str | None = None):
    with session_scope() as s:
        entries = get_audit_entries(s, entity, id)
    return JSONResponse(entries)


class TamperRequest(BaseModel):
    seq: int | None = None


@router.post("/admin/tamper-demo")
async def tamper_demo(body: TamperRequest | None = None):
    """Tamper with an audit row for demonstration purposes.
    Modifies the payload of an audit entry to break the hash chain."""
    with session_scope() as s:
        if body and body.seq:
            target_seq = body.seq
        else:
            from sqlalchemy import text
            row = s.execute(text("SELECT seq FROM audit_log ORDER BY seq LIMIT 1")).fetchone()
            if not row:
                raise HTTPException(404, "No audit entries to tamper")
            target_seq = row.seq

        result = tamper_audit_row(s, target_seq)
        if "error" in result:
            raise HTTPException(404, result["error"])
        _tamper_stash[target_seq] = result["original_payload"]

    return JSONResponse({
        "tampered_seq": target_seq,
        "message": "Audit row tampered. GET /audit/verify will now fail.",
    })


class RestoreRequest(BaseModel):
    seq: int | None = None


@router.post("/admin/restore-demo")
async def restore_demo(body: RestoreRequest | None = None):
    """Restore a previously tampered audit row."""
    target_seq = body.seq if body and body.seq else None

    if target_seq is None:
        if not _tamper_stash:
            raise HTTPException(404, "No tampered rows to restore")
        target_seq = next(iter(_tamper_stash))

    original = _tamper_stash.pop(target_seq, None)
    if original is None:
        raise HTTPException(404, f"No stashed original for seq {target_seq}")

    with session_scope() as s:
        result = restore_audit_row(s, target_seq, original)

    return JSONResponse({
        "restored_seq": target_seq,
        "message": "Audit row restored. GET /audit/verify should now pass.",
    })

"""Audit endpoints: verify chain and query entries."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from medbal_common.db import session_scope
from medbal_common import audit

from ..queries import get_audit_entries

router = APIRouter()


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

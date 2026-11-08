"""Authentication endpoints: login, me, users list."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from medbal_common.auth import (
    authenticate,
    create_token,
    get_current_user,
    CurrentUser,
    DEMO_USERS,
    TokenResponse,
)
from medbal_common.settings import settings

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
async def login(body: LoginRequest):
    if not settings.JWT_SECRET:
        raise HTTPException(503, "JWT_SECRET is not configured")
    user = authenticate(body.username, body.password)
    if not user:
        raise HTTPException(401, "Invalid username or password")
    token = create_token(user.user_id, user.role, user.name)
    return JSONResponse(token.model_dump())


@router.get("/auth/me")
async def me(user: CurrentUser = Depends(get_current_user)):
    return JSONResponse(user.model_dump())


@router.get("/auth/users")
async def list_users():
    return JSONResponse([
        {"username": uid, "role": u["role"], "name": u["name"]}
        for uid, u in DEMO_USERS.items()
    ])

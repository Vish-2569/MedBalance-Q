"""JWT authentication and role-based access control."""
from __future__ import annotations

import hmac as hmac_mod
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from medbal_common.settings import settings

_bearer = HTTPBearer(auto_error=False)

_SERVICE_USER = None

ALGORITHM = "HS256"

DEMO_USERS: dict[str, dict] = {
    "district_officer": {
        "password": "district123",
        "role": "district_officer",
        "name": "Dr. Ramesh Kumar",
    },
    "pharmacist": {
        "password": "pharma123",
        "role": "pharmacist",
        "name": "Smt. Kavitha N.",
    },
    "admin": {
        "password": "admin123",
        "role": "admin",
        "name": "System Admin",
    },
    "operator": {
        "password": "operator123",
        "role": "operator",
        "name": "Sim Operator",
    },
}


class TokenPayload(BaseModel):
    sub: str
    role: str
    name: str
    exp: int


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str
    expires_in: int


class CurrentUser(BaseModel):
    user_id: str
    role: str
    name: str


def create_token(user_id: str, role: str, name: str) -> TokenResponse:
    secret = settings.require_jwt_secret()
    expire_minutes = settings.JWT_EXPIRE_MINUTES
    exp = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    payload = {
        "sub": user_id,
        "role": role,
        "name": name,
        "exp": exp,
    }
    token = jwt.encode(payload, secret, algorithm=ALGORITHM)
    return TokenResponse(
        access_token=token,
        role=role,
        name=name,
        expires_in=expire_minutes * 60,
    )


def verify_token(token: str) -> TokenPayload:
    secret = settings.require_jwt_secret()
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        return TokenPayload(**payload)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")


async def get_current_user(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> CurrentUser:
    if not settings.JWT_SECRET:
        return CurrentUser(user_id="anonymous", role="admin", name="Anonymous (no JWT_SECRET)")

    service_token = request.headers.get("X-Service-Token")
    if service_token and hmac_mod.compare_digest(service_token, settings.JWT_SECRET):
        return CurrentUser(user_id="service", role="admin", name="Internal Service")

    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    payload = verify_token(creds.credentials)
    return CurrentUser(user_id=payload.sub, role=payload.role, name=payload.name)


def require_role(*roles: str):
    async def _check(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Role '{user.role}' cannot perform this action. Required: {', '.join(roles)}",
            )
        return user
    return _check


def authenticate(username: str, password: str) -> CurrentUser | None:
    user = DEMO_USERS.get(username)
    if not user or user["password"] != password:
        return None
    return CurrentUser(user_id=username, role=user["role"], name=user["name"])

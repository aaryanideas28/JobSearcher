# File: src/api/routes/auth.py
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config.settings import get_settings
from database.models import User
from src.api.dependencies import get_db

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


class LoginRequest(BaseModel):
    """Minimal login payload for local scaffold authentication."""

    email: str = Field(..., min_length=3)
    full_name: str = Field(default="Candidate", min_length=1)


class TokenResponse(BaseModel):
    """Bearer token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    user_id: int


class AuthenticatedUser(BaseModel):
    """Authenticated user details exposed to route dependencies."""

    id: int
    email: str
    full_name: str


def _urlsafe_json(data: dict[str, Any]) -> str:
    encoded = json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("utf-8").rstrip("=")


def _sign(message: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


def create_access_token(user: User, expires_in: int = 3600) -> str:
    """Create a signed compact bearer token for local development."""

    settings = get_settings()
    now = int(time.time())
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.full_name,
        "iat": now,
        "exp": now + expires_in,
        "jti": secrets.token_urlsafe(8),
    }
    body = _urlsafe_json(payload)
    signature = _sign(body, settings.auth_token_secret)
    return f"{body}.{signature}"


def decode_access_token(token: str) -> dict[str, Any]:
    """Verify and decode a local development bearer token."""

    settings = get_settings()
    try:
        body, signature = token.split(".", maxsplit=1)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token") from exc

    expected = _sign(body, settings.auth_token_secret)
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token signature")

    padded_body = body + "=" * (-len(body) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded_body.encode("utf-8")))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    return payload


def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> AuthenticatedUser:
    """Resolve the current user from a bearer token."""

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    payload = decode_access_token(token)
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return AuthenticatedUser(id=user.id, email=user.email, full_name=user.full_name)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> TokenResponse:
    """Create or fetch a user and return a signed access token."""

    user = db.query(User).filter(User.email == str(payload.email)).one_or_none()
    if user is None:
        user = User(email=str(payload.email), full_name=payload.full_name)
        db.add(user)
        db.commit()
        db.refresh(user)

    return TokenResponse(access_token=create_access_token(user), user_id=user.id)


@router.get("/me", response_model=AuthenticatedUser)
async def me(current_user: Annotated[AuthenticatedUser, Depends(get_current_user)]) -> AuthenticatedUser:
    """Return the currently authenticated user."""

    return current_user


@router.get("/google/callback")
async def google_oauth_callback(code: str | None = None, state: str | None = None) -> dict[str, str | None]:
    """Placeholder callback for the Gmail/OAuth consent flow."""

    return {"status": "received", "code": code, "state": state}

"""Authentication: invite-code-gated signup, password login, session cookie."""
from __future__ import annotations

import os
import re
from typing import Annotated

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from db import get_session
from models.db_models import User

router = APIRouter()

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{2,32}$")
_BCRYPT_ROUNDS = 12


def _hash_password(password: str) -> str:
    # bcrypt has a 72-byte input limit. Truncate to keep parity with verify.
    pw_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pw_bytes, bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode("utf-8")


def _verify_password(password: str, hashed: str) -> bool:
    pw_bytes = password.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(pw_bytes, hashed.encode("utf-8"))
    except ValueError:
        return False


def _invite_code() -> str:
    code = os.getenv("SIGNUP_INVITE_CODE", "").strip()
    if not code:
        # Fail loud so it's never silently disabled.
        raise HTTPException(503, "Signups are not configured (missing SIGNUP_INVITE_CODE)")
    return code


class SignupRequest(BaseModel):
    invite_code: str
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UserPublic(BaseModel):
    id: str
    username: str


_AUTH_DISABLED = os.getenv("AUTH_DISABLED", "").strip() in ("1", "true", "yes")
_LOCAL_USER_ID = "local-dev-user"
_LOCAL_USERNAME = "local"


def _get_local_user(db: Session) -> User:
    user = db.get(User, _LOCAL_USER_ID)
    if not user:
        user = User(id=_LOCAL_USER_ID, username=_LOCAL_USERNAME, password_hash="")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def current_user(request: Request, db: Annotated[Session, Depends(get_session)]) -> User:
    if _AUTH_DISABLED:
        return _get_local_user(db)
    user_id = request.session.get("user_id") if hasattr(request, "session") else None
    if not user_id:
        raise HTTPException(401, "Not authenticated")
    user = db.get(User, user_id)
    if not user:
        request.session.clear()
        raise HTTPException(401, "Session user no longer exists")
    return user


def optional_user(request: Request, db: Annotated[Session, Depends(get_session)]) -> User | None:
    if _AUTH_DISABLED:
        return _get_local_user(db)
    user_id = request.session.get("user_id") if hasattr(request, "session") else None
    if not user_id:
        return None
    return db.get(User, user_id)


@router.post("/auth/signup", response_model=UserPublic)
def signup(req: SignupRequest, request: Request, db: Annotated[Session, Depends(get_session)]):
    if req.invite_code.strip() != _invite_code():
        raise HTTPException(400, "Invalid invite code")
    if not _USERNAME_RE.match(req.username):
        raise HTTPException(400, "Username must be 2–32 chars: letters, digits, _ . -")
    if len(req.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    existing = db.exec(select(User).where(User.username == req.username)).first()
    if existing:
        raise HTTPException(409, "Username already taken")

    user = User(username=req.username, password_hash=_hash_password(req.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    request.session["user_id"] = user.id
    return UserPublic(id=user.id, username=user.username)


@router.post("/auth/login", response_model=UserPublic)
def login(req: LoginRequest, request: Request, db: Annotated[Session, Depends(get_session)]):
    user = db.exec(select(User).where(User.username == req.username)).first()
    if not user or not _verify_password(req.password, user.password_hash):
        raise HTTPException(401, "Invalid username or password")
    request.session["user_id"] = user.id
    return UserPublic(id=user.id, username=user.username)


@router.post("/auth/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/auth/me", response_model=UserPublic)
def me(user: Annotated[User, Depends(current_user)]):
    return UserPublic(id=user.id, username=user.username)

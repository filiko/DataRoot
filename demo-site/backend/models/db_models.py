"""SQLModel tables for users, projects, membership, and invites."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    # Naive UTC — SQLite drops tzinfo on read, so storing naive keeps comparisons consistent.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(default_factory=_uuid, primary_key=True)
    username: str = Field(index=True, unique=True)
    password_hash: str
    created_at: datetime = Field(default_factory=_now)


class Project(SQLModel, table=True):
    __tablename__ = "projects"

    id: str = Field(primary_key=True)
    owner_id: str = Field(foreign_key="users.id", index=True)
    name: str
    pen_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    revision: int = Field(default=0)
    updated_at: datetime = Field(default_factory=_now)


class ProjectMember(SQLModel, table=True):
    __tablename__ = "project_members"

    project_id: str = Field(foreign_key="projects.id", primary_key=True)
    user_id: str = Field(foreign_key="users.id", primary_key=True)
    role: str = Field(default="editor")  # 'owner' | 'editor'
    added_at: datetime = Field(default_factory=_now)


class Invite(SQLModel, table=True):
    __tablename__ = "invites"

    token: str = Field(primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True)
    created_by: str = Field(foreign_key="users.id")
    created_at: datetime = Field(default_factory=_now)
    expires_at: Optional[datetime] = None
    max_uses: int = Field(default=20)
    uses: int = Field(default=0)


class WaitlistSubmission(SQLModel, table=True):
    __tablename__ = "waitlist"

    id: str = Field(default_factory=_uuid, primary_key=True)
    name: str
    email: str
    project_url: str = Field(default="")
    message: str = Field(default="")
    submitted_at: datetime = Field(default_factory=_now)

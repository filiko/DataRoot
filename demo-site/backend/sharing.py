"""Project sharing: invite-link generation and membership enforcement."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from auth import current_user
from db import get_session
from models.db_models import Invite, Project, ProjectMember, User

router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def require_member(
    project_id: str,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_session)],
) -> User:
    """Dependency: 403 unless user is a member of project_id."""
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, f"Project '{project_id}' not found")
    member = db.get(ProjectMember, (project_id, user.id))
    if not member:
        raise HTTPException(403, "You don't have access to this project")
    return user


def require_owner(
    project_id: str,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_session)],
) -> User:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, f"Project '{project_id}' not found")
    if project.owner_id != user.id:
        raise HTTPException(403, "Only the project owner can do that")
    return user


class InviteResponse(BaseModel):
    token: str
    project_id: str
    expires_at: datetime | None
    max_uses: int
    uses: int


class InviteAcceptResponse(BaseModel):
    project_id: str
    role: str


@router.post("/projects/{project_id}/invites", response_model=InviteResponse)
def create_invite(
    project_id: str,
    user: Annotated[User, Depends(require_owner)],
    db: Annotated[Session, Depends(get_session)],
):
    invite = Invite(
        token=secrets.token_urlsafe(24),
        project_id=project_id,
        created_by=user.id,
        expires_at=_now() + timedelta(days=7),
        max_uses=20,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return InviteResponse(
        token=invite.token,
        project_id=invite.project_id,
        expires_at=invite.expires_at,
        max_uses=invite.max_uses,
        uses=invite.uses,
    )


@router.post("/invites/{token}/accept", response_model=InviteAcceptResponse)
def accept_invite(
    token: str,
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_session)],
):
    invite = db.get(Invite, token)
    if not invite:
        raise HTTPException(404, "Invite not found")
    if invite.expires_at and invite.expires_at < _now():
        raise HTTPException(410, "Invite has expired")
    if invite.uses >= invite.max_uses:
        raise HTTPException(410, "Invite has been used up")

    project = db.get(Project, invite.project_id)
    if not project:
        raise HTTPException(404, "Project no longer exists")

    existing = db.get(ProjectMember, (project.id, user.id))
    role = existing.role if existing else "editor"
    if not existing:
        db.add(ProjectMember(project_id=project.id, user_id=user.id, role="editor"))
        invite.uses += 1
        db.add(invite)
    db.commit()
    return InviteAcceptResponse(project_id=project.id, role=role)


@router.get("/invites/{token}")
def peek_invite(token: str, db: Annotated[Session, Depends(get_session)]):
    """Return basic info about an invite (no auth) so the frontend can show project name on the accept page."""
    invite = db.get(Invite, token)
    if not invite:
        raise HTTPException(404, "Invite not found")
    project = db.get(Project, invite.project_id)
    return {
        "project_id": invite.project_id,
        "project_name": project.name if project else None,
        "expired": bool(invite.expires_at and invite.expires_at < _now()),
        "exhausted": invite.uses >= invite.max_uses,
    }

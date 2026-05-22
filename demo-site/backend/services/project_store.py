"""Database-backed project storage. Replaces the in-memory dict + ephemeral filesystem."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from models.db_models import Project, ProjectMember, User
from models.pen import PenFile


def _to_jsonable(pen: PenFile) -> dict:
    return json.loads(pen.model_dump_json(by_alias=True))


class ProjectStore:
    @staticmethod
    def load(project_id: str, db: Session) -> PenFile:
        row = db.get(Project, project_id)
        if not row:
            raise HTTPException(404, f"Project '{project_id}' not found")
        return PenFile.model_validate(row.pen_json)

    @staticmethod
    def save(pen: PenFile, db: Session) -> PenFile:
        """UPSERT — assumes the Project row already exists (created via .create())."""
        row = db.get(Project, pen.project.id)
        if not row:
            raise HTTPException(404, f"Project '{pen.project.id}' not found")
        row.pen_json = _to_jsonable(pen)
        row.revision = pen.project.revision
        row.name = pen.project.name
        row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.add(row)
        db.commit()
        return pen

    @staticmethod
    def create(pen: PenFile, owner: User, db: Session) -> PenFile:
        """Insert a Project + owner ProjectMember row for a freshly-built PenFile."""
        existing = db.get(Project, pen.project.id)
        if existing:
            # Defensive: collisions on a UUID are astronomically rare, but keep idempotent.
            raise HTTPException(409, "Project id already exists")
        row = Project(
            id=pen.project.id,
            owner_id=owner.id,
            name=pen.project.name,
            pen_json=_to_jsonable(pen),
            revision=pen.project.revision,
        )
        db.add(row)
        db.add(ProjectMember(project_id=row.id, user_id=owner.id, role="owner"))
        db.commit()
        return pen

    @staticmethod
    def delete(project_id: str, db: Session) -> None:
        # Delete members + invites first to satisfy FKs.
        from models.db_models import Invite

        for m in db.exec(select(ProjectMember).where(ProjectMember.project_id == project_id)).all():
            db.delete(m)
        for inv in db.exec(select(Invite).where(Invite.project_id == project_id)).all():
            db.delete(inv)
        row = db.get(Project, project_id)
        if row:
            db.delete(row)
        db.commit()

    @staticmethod
    def list_for_user(user: User, db: Session) -> list[dict]:
        stmt = (
            select(Project, ProjectMember.role)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(ProjectMember.user_id == user.id)
            .order_by(Project.updated_at.desc())
        )
        out: list[dict] = []
        for project, role in db.exec(stmt).all():
            out.append({
                "id": project.id,
                "name": project.name,
                "role": role,
                "revision": project.revision,
                "updated_at": project.updated_at.isoformat(),
                "owner_id": project.owner_id,
            })
        return out

    @staticmethod
    def get_revision(project_id: str, db: Session) -> dict:
        row = db.get(Project, project_id)
        if not row:
            raise HTTPException(404, f"Project '{project_id}' not found")
        return {"revision": row.revision, "updated_at": row.updated_at.isoformat()}

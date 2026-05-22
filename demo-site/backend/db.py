"""Database engine and session helpers for DFDMaker."""
from __future__ import annotations

import os
import sys
import time
from typing import Iterator

from sqlalchemy.exc import OperationalError
from sqlmodel import Session, SQLModel, create_engine

DEFAULT_SQLITE_URL = "sqlite:///./dfdmaker.db"


def _normalize_url(url: str) -> str:
    # Railway Postgres often gives postgres:// — SQLAlchemy 2.x wants postgresql+psycopg://
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://") and "+psycopg" not in url and "+asyncpg" not in url:
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = _normalize_url(os.getenv("DATABASE_URL", DEFAULT_SQLITE_URL))

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args, pool_pre_ping=True)


def init_db(max_attempts: int = 10, delay_seconds: float = 2.0) -> None:
    """Create tables. Retries on OperationalError so the app can start before
    Railway's Postgres is fully reachable."""
    from models import db_models  # noqa: F401  -- registers table classes

    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            SQLModel.metadata.create_all(engine)
            return
        except OperationalError as e:
            last_err = e
            print(
                f"[dfdmaker] DB not ready (attempt {attempt}/{max_attempts}): {e}",
                file=sys.stderr,
            )
            time.sleep(delay_seconds)
    # Out of retries — let the failure bubble up so Railway restarts us.
    raise RuntimeError(f"Database unreachable after {max_attempts} attempts: {last_err}")


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session

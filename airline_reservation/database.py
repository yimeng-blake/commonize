"""Database helpers for the airline reservation system."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Dict, Iterator, Tuple

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .models import Base


def create_session_factory(
    db_url: str = "sqlite+pysqlite:///airline.db",
    *,
    echo: bool = False,
    connect_args: Dict[str, object] | None = None,
) -> Tuple[Engine, sessionmaker[Session]]:
    """Return an engine/session factory pair configured for SQLite by default."""

    if db_url.startswith("sqlite"):
        final_connect_args = {"check_same_thread": False}
        if connect_args:
            final_connect_args.update(connect_args)
    else:
        final_connect_args = connect_args or {}

    if db_url.endswith(":memory:"):
        engine = create_engine(
            db_url,
            echo=echo,
            future=True,
            connect_args=final_connect_args,
            poolclass=StaticPool,
        )
    else:
        engine = create_engine(
            db_url,
            echo=echo,
            future=True,
            connect_args=final_connect_args,
        )
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    return engine, session_factory


def init_db(db_url: str = "sqlite+pysqlite:///airline.db", *, echo: bool = False) -> sessionmaker[Session]:
    """Create all tables and return a session factory."""

    engine, session_factory = create_session_factory(db_url, echo=echo)
    Base.metadata.create_all(engine)
    return session_factory


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Provide a transactional scope around a series of operations."""

    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

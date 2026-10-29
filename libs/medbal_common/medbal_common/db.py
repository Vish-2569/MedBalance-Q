from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text, Engine
from sqlalchemy.orm import Session, sessionmaker

from medbal_common.settings import settings

_log = logging.getLogger("medbal.db")

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None

MAX_CONNECT_RETRIES = 10
RETRY_BACKOFF_BASE = 1.5


def get_engine(url: str | None = None) -> Engine:
    global _engine
    if _engine is None or url is not None:
        _engine = create_engine(
            url or settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_timeout=10,
            connect_args={"connect_timeout": 5},
        )
    return _engine


def wait_for_db(url: str | None = None, retries: int = MAX_CONNECT_RETRIES) -> Engine:
    """Get engine with startup retry/backoff. Returns engine once DB is reachable."""
    engine = get_engine(url)
    for attempt in range(1, retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            _log.info("Postgres ready (attempt %d)", attempt)
            return engine
        except Exception as exc:
            delay = min(RETRY_BACKOFF_BASE ** attempt, 15)
            _log.warning("Postgres not ready (attempt %d/%d): %s — retrying in %.1fs",
                         attempt, retries, exc, delay)
            if attempt < retries:
                time.sleep(delay)
    _log.error("Postgres unreachable after %d attempts", retries)
    return engine


def get_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None or engine is not None:
        _session_factory = sessionmaker(bind=engine or get_engine(), expire_on_commit=False)
    return _session_factory


@contextmanager
def session_scope(engine: Engine | None = None) -> Generator[Session, None, None]:
    factory = get_session_factory(engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

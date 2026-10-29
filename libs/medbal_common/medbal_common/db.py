from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session, sessionmaker

from medbal_common.settings import settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine(url: str | None = None) -> Engine:
    global _engine
    if _engine is None or url is not None:
        _engine = create_engine(url or settings.DATABASE_URL, pool_pre_ping=True)
    return _engine


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

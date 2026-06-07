from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from clients.config import settings


@lru_cache(maxsize=1)
def _get_engine():
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


@lru_cache(maxsize=1)
def _get_session_factory() -> sessionmaker:
    return sessionmaker(bind=_get_engine(), autocommit=False, autoflush=False)


@contextmanager
def get_db_session() -> Session:
    session = _get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    from models.db import Base
    Base.metadata.create_all(bind=_get_engine())

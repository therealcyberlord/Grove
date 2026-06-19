"""Shared fixtures for DB tests. Uses PostgreSQL with per-test transaction rollback for isolation."""
import uuid
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from clients.config import settings
from models.db import Base, Filing, PageIndexRecord

SAMPLE_STRUCTURE = [{"title": "Item 1", "node_id": "0001", "start_index": 1, "end_index": 10, "nodes": []}]


@pytest.fixture(scope="session")
def db_engine():
    url = settings.test_database_url
    if not url:
        pytest.skip("TEST_DATABASE_URL is not configured - skipping DB integration tests")
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    """Each test runs inside a transaction that is rolled back on teardown — no data leaks."""
    conn = db_engine.connect()
    trans = conn.begin()
    session = Session(conn, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    trans.rollback()
    conn.close()


@pytest.fixture()
def patch_db(db_session, monkeypatch):
    """Patch clients.database.get_db_session to yield the test db_session."""
    @contextmanager
    def fake_get_db_session():
        yield db_session
        db_session.flush()

    monkeypatch.setattr("clients.database.get_db_session", fake_get_db_session)
    return db_session


@pytest.fixture()
def sample_filing(db_session):
    period = date.today() - timedelta(days=30)
    filing = Filing(
        ticker="AAPL",
        form_type="10-K",
        period=period,
        fiscal_year=period.year,
        fiscal_quarter=4,
        doc_name=f"AAPL_10-K_{period}.md",
        content_s3_key=f"filings/AAPL/AAPL_10-K_{period}.md",
    )
    db_session.add(filing)
    db_session.flush()
    return filing


@pytest.fixture()
def stale_filing(db_session):
    period = date.today() - timedelta(days=500)
    filing = Filing(
        ticker="AAPL",
        form_type="10-K",
        period=period,
        fiscal_year=period.year,
        fiscal_quarter=4,
        doc_name=f"AAPL_10-K_{period}.md",
        content_s3_key=f"filings/AAPL/AAPL_10-K_{period}.md",
    )
    db_session.add(filing)
    db_session.flush()
    return filing


@pytest.fixture()
def sample_page_index(db_session, sample_filing):
    doc_id = str(uuid.uuid4())
    record = PageIndexRecord(
        doc_id=doc_id,
        filing_id=sample_filing.id,
        doc_name=sample_filing.doc_name,
        doc_description="Apple 10-K index.",
        line_count=100,
        structure_s3_key=f"indexes/{doc_id}.json",
    )
    db_session.add(record)
    db_session.flush()
    return record


@pytest.fixture()
def workspace_dir(tmp_path) -> Path:
    d = tmp_path / "workspace"
    d.mkdir()
    return d

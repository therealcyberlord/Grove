"""Tests for scripts/seed_db.py seeding logic."""
import json
import uuid
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

from models.db import Filing, PageIndexRecord

_STRUCTURE = [{"title": "Risk Factors", "node_id": "0001", "start_index": 1, "end_index": 5, "nodes": []}]
_FAKE_S3_KEY = "filings/AAPL/AAPL_10-K_2025-09-27.md"
_FAKE_STRUCTURE_KEY = "indexes/fake-doc-id.json"


def _fake_get_db_session(session):
    """Build a get_db_session replacement that yields the given test session (mirrors patch_db)."""
    @contextmanager
    def fake():
        yield session
        session.flush()
    return fake


def _write_workspace(workspace_dir: Path, doc_id: str, doc_name: str, doc_type: str = "md"):
    meta_path = workspace_dir / "_meta.json"
    meta = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
    meta[doc_id] = {"type": doc_type, "doc_name": doc_name, "doc_description": "desc", "path": "/tmp/doc.md", "line_count": 50}
    meta_path.write_text(json.dumps(meta))

    full = {
        "id": doc_id,
        "type": doc_type,
        "path": "/tmp/doc.md",
        "doc_name": doc_name,
        "doc_description": "desc",
        "line_count": 50,
        "structure": _STRUCTURE,
    }
    (workspace_dir / f"{doc_id}.json").write_text(json.dumps(full))


def test_seed_filings_inserts_rows(db_session, tmp_path, monkeypatch):
    docs_dir = tmp_path / "documents"
    docs_dir.mkdir()
    period = date(2025, 9, 27)
    md_file = docs_dir / "AAPL_10-K_2025-09-27.md"
    md_file.write_text("# Apple 10-K\nContent here.")

    from scripts.seed_db import seed_filings

    monkeypatch.setattr("scripts.seed_db._DOCUMENTS_DIR", docs_dir)
    monkeypatch.setattr("scripts.seed_db.get_db_session", _fake_get_db_session(db_session))
    monkeypatch.setattr("scripts.seed_db.upload_filing", MagicMock(return_value=_FAKE_S3_KEY))
    n = seed_filings()

    assert n == 1
    row = db_session.query(Filing).filter_by(doc_name="AAPL_10-K_2025-09-27.md").first()
    assert row is not None
    assert row.ticker == "AAPL"
    assert row.form_type == "10-K"
    assert row.period == period
    assert row.fiscal_year == 2025
    assert row.fiscal_quarter == 4
    assert row.content_s3_key == _FAKE_S3_KEY


def test_seed_filings_skips_unrecognized_filenames(db_session, tmp_path, monkeypatch):
    docs_dir = tmp_path / "documents"
    docs_dir.mkdir()
    (docs_dir / "random_file.md").write_text("junk")

    from scripts.seed_db import seed_filings

    monkeypatch.setattr("scripts.seed_db._DOCUMENTS_DIR", docs_dir)
    monkeypatch.setattr("scripts.seed_db.get_db_session", _fake_get_db_session(db_session))
    monkeypatch.setattr("scripts.seed_db.upload_filing", MagicMock(return_value=_FAKE_S3_KEY))
    n = seed_filings()

    assert n == 0


def test_seed_page_indexes_resolves_filing_id(db_session, sample_filing, tmp_path, monkeypatch):
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    doc_id = str(uuid.uuid4())
    _write_workspace(workspace_dir, doc_id, sample_filing.doc_name)

    from scripts.seed_db import seed_page_indexes

    monkeypatch.setattr("scripts.seed_db._WORKSPACE_DIR", workspace_dir)
    monkeypatch.setattr("scripts.seed_db.get_db_session", _fake_get_db_session(db_session))
    monkeypatch.setattr("scripts.seed_db.upload_structure", MagicMock(return_value=_FAKE_STRUCTURE_KEY))
    n = seed_page_indexes()

    assert n == 1
    row = db_session.query(PageIndexRecord).filter_by(doc_id=doc_id).first()
    assert row is not None
    assert row.filing_id == sample_filing.id
    assert row.structure_s3_key == _FAKE_STRUCTURE_KEY


def test_seed_page_indexes_skips_missing_workspace_json(db_session, tmp_path, monkeypatch):
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    doc_id = str(uuid.uuid4())
    # Write meta but NOT the full doc JSON
    meta = {doc_id: {"type": "md", "doc_name": "MISSING_10-K_2025-01-01.md", "doc_description": "", "path": "", "line_count": 0}}
    (workspace_dir / "_meta.json").write_text(json.dumps(meta))

    from scripts.seed_db import seed_page_indexes

    monkeypatch.setattr("scripts.seed_db._WORKSPACE_DIR", workspace_dir)
    monkeypatch.setattr("scripts.seed_db.get_db_session", _fake_get_db_session(db_session))
    monkeypatch.setattr("scripts.seed_db.upload_structure", MagicMock(return_value=_FAKE_STRUCTURE_KEY))
    n = seed_page_indexes()

    assert n == 0

"""Tests for DBBackedPageIndexClient DB persistence and hydration."""
import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock

from clients.pageindex import DBBackedPageIndexClient
from models.db import PageIndexRecord
from tests.db.conftest import SAMPLE_STRUCTURE

_FAKE_STRUCTURE_KEY = "indexes/fake-doc-id.json"


def _make_client(workspace_dir: Path) -> DBBackedPageIndexClient:
    """Build a DBBackedPageIndexClient with a fresh in-memory state (no real index() calls)."""
    client = DBBackedPageIndexClient.__new__(DBBackedPageIndexClient)
    client.workspace = workspace_dir
    client.documents = {}
    client.model = "test-model"
    client.retrieve_model = "test-model"
    return client


def test_persist_index_to_db_inserts_record(patch_db, workspace_dir, sample_filing, monkeypatch):
    db_session = patch_db
    client = _make_client(workspace_dir)
    doc_id = str(uuid.uuid4())
    full_doc = {
        "id": doc_id,
        "type": "md",
        "path": str(workspace_dir / sample_filing.doc_name),
        "doc_name": sample_filing.doc_name,
        "doc_description": "Apple 10-K",
        "line_count": 200,
        "structure": SAMPLE_STRUCTURE,
    }

    monkeypatch.setattr("clients.storage.upload_structure", MagicMock(return_value=_FAKE_STRUCTURE_KEY))
    client._persist_index_to_db(doc_id, full_doc, filing_id=sample_filing.id)

    row = db_session.query(PageIndexRecord).filter_by(doc_id=doc_id).first()
    assert row is not None
    assert row.doc_name == sample_filing.doc_name
    assert row.filing_id == sample_filing.id
    assert row.structure_s3_key == _FAKE_STRUCTURE_KEY
    assert row.line_count == 200


def test_persist_index_to_db_resolves_filing_id_by_doc_name(patch_db, workspace_dir, sample_filing, monkeypatch):
    """When filing_id isn't passed explicitly, it must be resolved by matching doc_name
    against Filing.doc_name (with/without the .md suffix). Regression: indexing a temp file
    with a random basename produced a doc_name like 'tmpXXXXXX' that matched no Filing row,
    leaving filing_id null."""
    db_session = patch_db
    client = _make_client(workspace_dir)
    doc_id = str(uuid.uuid4())
    full_doc = {
        "id": doc_id,
        "type": "md",
        "path": str(workspace_dir / sample_filing.doc_name),
        "doc_name": Path(sample_filing.doc_name).stem,  # what PageIndex derives from the basename
        "doc_description": "Apple 10-K",
        "line_count": 200,
        "structure": SAMPLE_STRUCTURE,
    }

    monkeypatch.setattr("clients.storage.upload_structure", MagicMock(return_value=_FAKE_STRUCTURE_KEY))
    client._persist_index_to_db(doc_id, full_doc)

    row = db_session.query(PageIndexRecord).filter_by(doc_id=doc_id).first()
    assert row is not None
    assert row.filing_id == sample_filing.id


def test_persist_index_to_db_leaves_filing_id_null_on_no_match(patch_db, workspace_dir, sample_filing, monkeypatch):
    """A doc_name that doesn't correspond to any Filing.doc_name resolves to a null filing_id
    (this is the broken state a mismatched doc_name produces - documented so a future doc_name
    derivation change that breaks the match is caught by the test above, not silently accepted)."""
    db_session = patch_db
    client = _make_client(workspace_dir)
    doc_id = str(uuid.uuid4())
    full_doc = {
        "id": doc_id,
        "type": "md",
        "path": "/tmp/tmpRANDOM123.md",
        "doc_name": "tmpRANDOM123",
        "doc_description": "",
        "line_count": 1,
        "structure": [],
    }

    monkeypatch.setattr("clients.storage.upload_structure", MagicMock(return_value="indexes/orphan.json"))
    client._persist_index_to_db(doc_id, full_doc)

    row = db_session.query(PageIndexRecord).filter_by(doc_id=doc_id).first()
    assert row is not None
    assert row.filing_id is None


def test_persist_index_to_db_skips_duplicate(patch_db, workspace_dir, sample_filing, sample_page_index, monkeypatch):
    db_session = patch_db
    client = _make_client(workspace_dir)
    full_doc = {
        "id": sample_page_index.doc_id,
        "path": "",
        "doc_name": sample_page_index.doc_name,
        "doc_description": "dup",
        "line_count": 1,
        "structure": [],
    }

    monkeypatch.setattr("clients.storage.upload_structure", MagicMock(return_value="indexes/should-not-be-used.json"))
    client._persist_index_to_db(sample_page_index.doc_id, full_doc, filing_id=sample_filing.id)

    row = db_session.query(PageIndexRecord).filter_by(doc_id=sample_page_index.doc_id).first()
    assert row.structure_s3_key == sample_page_index.structure_s3_key  # original unchanged


def test_hydrate_single_from_db_writes_workspace_json(patch_db, workspace_dir, sample_page_index, monkeypatch):
    client = _make_client(workspace_dir)

    monkeypatch.setattr("clients.storage.download_structure", MagicMock(return_value=SAMPLE_STRUCTURE))
    client._hydrate_single_from_db(sample_page_index.doc_id)

    ws_file = workspace_dir / f"{sample_page_index.doc_id}.json"
    assert ws_file.exists()
    data = json.loads(ws_file.read_text())
    assert data["structure"] == SAMPLE_STRUCTURE

    assert sample_page_index.doc_id in client.documents
    assert client.documents[sample_page_index.doc_id]["doc_name"] == sample_page_index.doc_name


def test_cold_start_syncs_db_records(patch_db, workspace_dir, sample_page_index, monkeypatch):
    """On init with empty workspace, _sync_db_to_workspace populates client.documents."""
    client = _make_client(workspace_dir)

    monkeypatch.setattr("clients.storage.download_structure", MagicMock(return_value=SAMPLE_STRUCTURE))
    client._sync_db_to_workspace()

    assert sample_page_index.doc_id in client.documents


def test_sync_db_to_workspace_hydrates_only_missing_docs(patch_db, workspace_dir, sample_filing, sample_page_index, monkeypatch):
    """Mixed cold start: a doc already loaded (e.g. from local workspace JSON) must be left
    untouched, while a doc only present in the DB gets hydrated."""
    db_session = patch_db
    other_doc_id = str(uuid.uuid4())
    db_session.add(PageIndexRecord(
        doc_id=other_doc_id,
        filing_id=sample_filing.id,
        doc_name="OTHER_10-K.md",
        doc_description="Other filing index.",
        line_count=50,
        structure_s3_key=f"indexes/{other_doc_id}.json",
    ))
    db_session.flush()

    client = _make_client(workspace_dir)
    loaded_entry = {"id": sample_page_index.doc_id, "doc_name": sample_page_index.doc_name, "type": "md", "structure": SAMPLE_STRUCTURE}
    client.documents[sample_page_index.doc_id] = loaded_entry

    download_mock = MagicMock(return_value=SAMPLE_STRUCTURE)
    monkeypatch.setattr("clients.storage.download_structure", download_mock)
    client._sync_db_to_workspace()

    assert client.documents[sample_page_index.doc_id] is loaded_entry  # untouched, not re-hydrated
    assert other_doc_id in client.documents
    download_mock.assert_called_once()  # only the missing doc triggered a download


def test_ensure_doc_loaded_hydrates_on_workspace_miss(patch_db, workspace_dir, sample_page_index, monkeypatch):
    """_ensure_doc_loaded triggers DB hydration when workspace JSON is absent."""
    client = _make_client(workspace_dir)
    client.documents[sample_page_index.doc_id] = {
        "id": sample_page_index.doc_id,
        "doc_name": sample_page_index.doc_name,
        "type": "md",
    }

    ws_file = workspace_dir / f"{sample_page_index.doc_id}.json"
    assert not ws_file.exists()

    monkeypatch.setattr("clients.storage.download_structure", MagicMock(return_value=SAMPLE_STRUCTURE))
    client._ensure_doc_loaded(sample_page_index.doc_id)

    assert ws_file.exists()

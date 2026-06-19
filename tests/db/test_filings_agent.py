"""Tests for _do_fetch_and_index: DB cache hit/stale logic and content persistence."""
import uuid
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock
from models.db import Filing

_S3_KEY = "filings/AAPL/AAPL_10-K_test.md"


def _make_edgar_mocks(period_str: str, md_content: str = "# Fake 10-K"):
    mock_filing = MagicMock()
    mock_filing.period_of_report = period_str
    mock_filing.markdown.return_value = md_content

    mock_filings = MagicMock()
    mock_filings.latest.return_value = mock_filing

    mock_company = MagicMock()
    mock_company.get_filings.return_value = mock_filings

    return mock_company, mock_filing


def test_db_cache_hit_skips_edgar(patch_db, sample_filing, sample_page_index, monkeypatch):
    """Fresh DB record (age <= 365 days) should return immediately without EDGAR call."""
    mock_company, mock_filing = _make_edgar_mocks(str(sample_filing.period))

    mock_pi_client = MagicMock()
    mock_pi_client.documents = {sample_page_index.doc_id: {}}

    monkeypatch.setattr("edgar.Company", MagicMock(return_value=mock_company))
    monkeypatch.setattr("edgar.set_identity", MagicMock())
    monkeypatch.setattr("agents.subagents.filings.agent.get_pageindex_client", MagicMock(return_value=mock_pi_client))

    from agents.subagents.filings.agent import _do_fetch_and_index
    doc_id, period = _do_fetch_and_index("AAPL")

    assert doc_id == sample_page_index.doc_id
    mock_filing.markdown.assert_not_called()


def test_db_cache_hit_returns_correct_metadata(patch_db, sample_filing, sample_page_index, monkeypatch):
    mock_company, mock_filing = _make_edgar_mocks(str(sample_filing.period))
    mock_pi_client = MagicMock()
    mock_pi_client.documents = {sample_page_index.doc_id: {}}

    monkeypatch.setattr("edgar.Company", MagicMock(return_value=mock_company))
    monkeypatch.setattr("edgar.set_identity", MagicMock())
    monkeypatch.setattr("agents.subagents.filings.agent.get_pageindex_client", MagicMock(return_value=mock_pi_client))

    from agents.subagents.filings.agent import _do_fetch_and_index
    _, period = _do_fetch_and_index("AAPL")

    assert period == str(sample_filing.period)
    assert sample_filing.fiscal_year == sample_filing.period.year
    assert sample_filing.fiscal_quarter == 4


def test_fresh_filing_without_page_index_reindexes_and_updates_in_place(patch_db, sample_filing, monkeypatch):
    """A fresh Filing row with no matching PageIndexRecord (e.g. a prior run uploaded to S3
    and inserted the Filing but failed before indexing completed) must re-index rather than
    crash. Regression: session.merge() on a brand new transient Filing has id=None, so it
    INSERTs and collides with uq_filing_ticker_form_period instead of updating the existing
    row - this must update in place."""
    db_session = patch_db
    period_str = str(sample_filing.period)
    md_content = "# Re-indexed 10-K content"
    mock_company, mock_filing = _make_edgar_mocks(period_str, md_content=md_content)

    mock_pi_client = MagicMock()
    mock_pi_client.index.return_value = str(uuid.uuid4())
    mock_pi_client.documents = {}

    monkeypatch.setattr("edgar.Company", MagicMock(return_value=mock_company))
    monkeypatch.setattr("edgar.set_identity", MagicMock())
    monkeypatch.setattr("agents.subagents.filings.agent.get_pageindex_client", MagicMock(return_value=mock_pi_client))
    monkeypatch.setattr("clients.storage.get_s3_client", MagicMock())
    monkeypatch.setattr("clients.storage.ensure_bucket", MagicMock())
    monkeypatch.setattr("clients.storage.upload_filing", MagicMock(return_value=_S3_KEY))

    from agents.subagents.filings.agent import _do_fetch_and_index
    _do_fetch_and_index("AAPL")  # must not raise IntegrityError

    rows = db_session.query(Filing).filter_by(ticker="AAPL", form_type="10-K", period=sample_filing.period).all()
    assert len(rows) == 1
    assert rows[0].id == sample_filing.id
    assert rows[0].content_s3_key == _S3_KEY
    mock_pi_client.index.assert_called_once()


def test_db_cache_stale_refetches_from_edgar(patch_db, stale_filing, monkeypatch):
    """Stale DB record (age > 365 days) should trigger a fresh EDGAR fetch."""
    new_period = str(date.today() - timedelta(days=10))
    mock_company, mock_filing = _make_edgar_mocks(new_period, md_content="# Fresh 10-K content")

    mock_pi_client = MagicMock()
    mock_pi_client.index.return_value = str(uuid.uuid4())
    mock_pi_client.documents = {}

    monkeypatch.setattr("edgar.Company", MagicMock(return_value=mock_company))
    monkeypatch.setattr("edgar.set_identity", MagicMock())
    monkeypatch.setattr("agents.subagents.filings.agent.get_pageindex_client", MagicMock(return_value=mock_pi_client))
    monkeypatch.setattr("clients.storage.get_s3_client", MagicMock())
    monkeypatch.setattr("clients.storage.ensure_bucket", MagicMock())
    monkeypatch.setattr("clients.storage.upload_filing", MagicMock(return_value=_S3_KEY))

    from agents.subagents.filings.agent import _do_fetch_and_index
    _do_fetch_and_index("AAPL")

    mock_filing.markdown.assert_called_once()
    mock_pi_client.index.assert_called_once()


def test_index_called_with_canonical_filename(patch_db, monkeypatch):
    """The file handed to client.index() must be named {ticker}_10-K_{period}.md, since
    PageIndex derives doc_name from its basename and _persist_index_to_db matches that
    against Filing.doc_name to resolve the filing_id FK. Regression: a prior version wrote
    to a tempfile.NamedTemporaryFile with a random name (e.g. 'tmpXXXXXX.md'), producing a
    doc_name that matched no Filing row and left filing_id null."""
    period_str = str(date.today() - timedelta(days=5))
    md_content = "# New Apple 10-K\n\nContent here."
    mock_company, mock_filing = _make_edgar_mocks(period_str, md_content=md_content)

    captured = {}

    def _capture_index(path, *args, **kwargs):
        captured["name"] = Path(path).name
        captured["content"] = Path(path).read_text(encoding="utf-8")
        return str(uuid.uuid4())

    mock_pi_client = MagicMock()
    mock_pi_client.index.side_effect = _capture_index
    mock_pi_client.documents = {}

    monkeypatch.setattr("edgar.Company", MagicMock(return_value=mock_company))
    monkeypatch.setattr("edgar.set_identity", MagicMock())
    monkeypatch.setattr("agents.subagents.filings.agent.get_pageindex_client", MagicMock(return_value=mock_pi_client))
    monkeypatch.setattr("clients.storage.get_s3_client", MagicMock())
    monkeypatch.setattr("clients.storage.ensure_bucket", MagicMock())
    monkeypatch.setattr("clients.storage.upload_filing", MagicMock(return_value=_S3_KEY))

    from agents.subagents.filings.agent import _do_fetch_and_index
    _do_fetch_and_index("AAPL")

    assert captured["name"] == f"AAPL_10-K_{period_str}.md"
    assert captured["content"] == md_content


def test_filing_s3_key_persisted_to_db(patch_db, monkeypatch):
    """A fresh fetch should insert a Filing row with correct s3_key and metadata."""
    db_session = patch_db
    period_str = str(date.today() - timedelta(days=5))
    md_content = "# New Apple 10-K\n\nContent here."
    mock_company, mock_filing = _make_edgar_mocks(period_str, md_content=md_content)

    mock_pi_client = MagicMock()
    mock_pi_client.index.return_value = str(uuid.uuid4())
    mock_pi_client.documents = {}

    expected_s3_key = f"filings/AAPL/AAPL_10-K_{period_str}.md"

    monkeypatch.setattr("edgar.Company", MagicMock(return_value=mock_company))
    monkeypatch.setattr("edgar.set_identity", MagicMock())
    monkeypatch.setattr("agents.subagents.filings.agent.get_pageindex_client", MagicMock(return_value=mock_pi_client))
    monkeypatch.setattr("clients.storage.get_s3_client", MagicMock())
    monkeypatch.setattr("clients.storage.ensure_bucket", MagicMock())
    monkeypatch.setattr("clients.storage.upload_filing", MagicMock(return_value=expected_s3_key))

    from agents.subagents.filings.agent import _do_fetch_and_index
    _do_fetch_and_index("AAPL")

    period_date = date.fromisoformat(period_str)
    filename = f"AAPL_10-K_{period_str}.md"
    row = db_session.query(Filing).filter_by(doc_name=filename).first()
    assert row is not None
    assert row.content_s3_key == expected_s3_key
    assert row.fiscal_year == period_date.year
    assert row.fiscal_quarter == 4

"""One-time migration: seed PostgreSQL + S3 from existing workspace/ and documents/ directories."""
import json
import logging
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from clients.database import get_db_session, init_db  # noqa: E402
from clients.storage import ensure_bucket, upload_filing, upload_structure  # noqa: E402
from models.db import Filing, PageIndexRecord  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

_DOCUMENTS_DIR = ROOT / "documents"
_WORKSPACE_DIR = ROOT / "workspace"

_FILENAME_RE = re.compile(r"^(?P<ticker>[A-Z]+)_(?P<form>10-[A-Z]+)_(?P<period>\d{4}-\d{2}-\d{2})\.md$")


def seed_filings() -> int:
    seeded = 0
    for md_file in sorted(_DOCUMENTS_DIR.glob("*.md")):
        m = _FILENAME_RE.match(md_file.name)
        if not m:
            logger.info("  skip (unrecognized filename): %s", md_file.name)
            continue
        ticker = m.group("ticker")
        form_type = m.group("form")
        period_str = m.group("period")
        period_date = date.fromisoformat(period_str)
        content = md_file.read_text(encoding="utf-8")

        with get_db_session() as session:
            existing = session.query(Filing).filter_by(doc_name=md_file.name).first()
            if existing:
                if existing.content_s3_key:
                    logger.info("  already seeded: %s", md_file.name)
                    continue
                # Row exists but S3 key missing — upload and patch
                s3_key = upload_filing(ticker, md_file.name, content)
                existing.content_s3_key = s3_key
                logger.info("  patched s3_key: %s", md_file.name)
                continue

            s3_key = upload_filing(ticker, md_file.name, content)
            session.add(Filing(
                ticker=ticker,
                form_type=form_type,
                period=period_date,
                fiscal_year=period_date.year,
                fiscal_quarter=4,
                doc_name=md_file.name,
                content_s3_key=s3_key,
            ))
        seeded += 1
        logger.info("  seeded filing: %s -> %s", md_file.name, s3_key)
    return seeded


def seed_page_indexes() -> int:
    meta_path = _WORKSPACE_DIR / "_meta.json"
    if not meta_path.exists():
        logger.info("  no _meta.json found, skipping page_indexes seeding")
        return 0

    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    seeded = 0
    for doc_id, entry in meta.items():
        if entry.get("type") == "pdf":
            logger.info("  skip %s: PDF not supported", doc_id)
            continue

        doc_path = _WORKSPACE_DIR / f"{doc_id}.json"
        if not doc_path.exists():
            logger.info("  skip %s: workspace JSON not found", doc_id)
            continue

        with open(doc_path, encoding="utf-8") as f:
            full_doc = json.load(f)

        doc_name = entry.get("doc_name", "")

        with get_db_session() as session:
            existing = session.query(PageIndexRecord).filter_by(doc_id=doc_id).first()
            if existing:
                logger.info("  already seeded: %s (%s)", doc_id, doc_name)
                continue

            doc_name_md = doc_name if doc_name.endswith(".md") else f"{doc_name}.md"
            filing_row = session.query(Filing).filter(
                Filing.doc_name.in_([doc_name, doc_name_md])
            ).first()
            filing_id = filing_row.id if filing_row else None

            structure_s3_key = upload_structure(doc_id, full_doc.get("structure", []))
            session.add(PageIndexRecord(
                doc_id=doc_id,
                filing_id=filing_id,
                doc_name=doc_name,
                doc_description=full_doc.get("doc_description"),
                line_count=full_doc.get("line_count"),
                structure_s3_key=structure_s3_key,
            ))
        seeded += 1
        logger.info("  seeded page_index: %s (%s)", doc_id, doc_name)
    return seeded


def main():
    logger.info("Initializing DB schema...")
    init_db()

    logger.info("Ensuring S3 bucket exists...")
    ensure_bucket()

    logger.info("\nSeeding filings from %s...", _DOCUMENTS_DIR)
    n_filings = seed_filings()

    logger.info("\nSeeding page_indexes from %s...", _WORKSPACE_DIR)
    n_indexes = seed_page_indexes()

    logger.info("\nDone. Seeded %d filing(s) and %d page_index record(s).", n_filings, n_indexes)


if __name__ == "__main__":
    main()

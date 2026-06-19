import json
import logging
from functools import lru_cache
from pathlib import Path

from lib.PageIndex.pageindex import PageIndexClient

logger = logging.getLogger(__name__)

_WORKSPACE = Path(__file__).parent.parent / "workspace"


class DBBackedPageIndexClient(PageIndexClient):
    """PageIndexClient that persists index data to PostgreSQL after each index() call
    and hydrates the local workspace from DB on cold start or cache miss."""

    def _save_doc(self, doc_id: str):
        full_doc = self.documents[doc_id].copy()
        super()._save_doc(doc_id)
        self._persist_index_to_db(doc_id, full_doc)

    def _persist_index_to_db(self, doc_id: str, full_doc: dict, filing_id=None):
        from clients.database import get_db_session
        from clients.storage import upload_structure
        from models.db import Filing, PageIndexRecord

        doc_name = full_doc.get("doc_name", "")

        with get_db_session() as session:
            if session.query(PageIndexRecord).filter_by(doc_id=doc_id).first():
                return
            if filing_id is None:
                doc_name_md = doc_name if doc_name.endswith(".md") else f"{doc_name}.md"
                row = session.query(Filing).filter(
                    Filing.doc_name.in_([doc_name, doc_name_md])
                ).first()
                filing_id = row.id if row else None
            structure_s3_key = upload_structure(doc_id, full_doc.get("structure", []))
            record = PageIndexRecord(
                doc_id=doc_id,
                filing_id=filing_id,
                doc_name=doc_name,
                doc_description=full_doc.get("doc_description"),
                line_count=full_doc.get("line_count"),
                structure_s3_key=structure_s3_key,
            )
            session.add(record)
        logger.info("pageindex: persisted %s (%s) to DB", doc_id, doc_name)

    def _hydrate_single_from_db(self, doc_id: str):
        from clients.database import get_db_session
        from clients.storage import download_structure
        from models.db import PageIndexRecord

        with get_db_session() as session:
            record = session.query(PageIndexRecord).filter_by(doc_id=doc_id).first()
            if not record:
                return
            # Copy scalar fields before session closes (expire_on_commit=True would
            # otherwise expire them, causing DetachedInstanceError on access outside).
            structure_s3_key = record.structure_s3_key
            doc_name = record.doc_name
            doc_description = record.doc_description or ""
            line_count = record.line_count

        structure = download_structure(structure_s3_key)
        full_doc = {
            "id": doc_id,
            "type": "md",
            "doc_name": doc_name,
            "doc_description": doc_description,
            "structure": structure,
        }
        if line_count is not None:
            full_doc["line_count"] = line_count

        if self.workspace:
            path = self.workspace / f"{doc_id}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(full_doc, f, ensure_ascii=False, indent=2)
            self._save_meta(doc_id, self._make_meta_entry(full_doc))

        self.documents[doc_id] = self._make_meta_entry(full_doc)
        self.documents[doc_id]["id"] = doc_id
        logger.info("pageindex: hydrated %s (%s) from DB", doc_id, doc_name)

    def _load_workspace(self):
        super()._load_workspace()
        self._sync_db_to_workspace()

    def _sync_db_to_workspace(self):
        from clients.database import get_db_session
        from models.db import PageIndexRecord

        with get_db_session() as session:
            records = session.query(PageIndexRecord).all()
            missing = [(r.doc_id, r.doc_name) for r in records if r.doc_id not in self.documents]

        for doc_id, doc_name in missing:
            logger.info("pageindex: syncing %s (%s) from DB to workspace", doc_id, doc_name)
            self._hydrate_single_from_db(doc_id)

    def _ensure_doc_loaded(self, doc_id: str):
        if self.workspace and not (self.workspace / f"{doc_id}.json").exists():
            self._hydrate_single_from_db(doc_id)
        super()._ensure_doc_loaded(doc_id)


@lru_cache(maxsize=1)
def get_pageindex_client() -> DBBackedPageIndexClient:
    _WORKSPACE.mkdir(exist_ok=True)
    return DBBackedPageIndexClient(workspace=_WORKSPACE)

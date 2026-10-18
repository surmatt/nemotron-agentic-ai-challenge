"""A small replaceable store for artifact provenance."""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path
import re
from typing import Iterable, Protocol

from .contracts import ArtifactRecord


class ArtifactStore(Protocol):
    def put(self, record: ArtifactRecord) -> None: ...
    def replace_stage(self, stage: str, records: Iterable[ArtifactRecord]) -> dict[str, int]:
        """Delete every record of one stage, then write the new ones. Old runs leave no stale records."""
        if not re.fullmatch(r"[a-z]+", stage):
            raise ValueError("stage must be a lower-case word")
        rows = [{"record_id": r.record_id, "record_json": r.model_dump_json()} for r in records]
        if any(not row["record_id"].startswith(f"{stage}:") for row in rows):
            raise ValueError(f"record IDs must start with '{stage}:'")
        before = self.table.count_rows()
        self.table.delete(f"record_id LIKE '{stage}:%'")
        removed = before - self.table.count_rows()
        if rows:
            self.table.add(rows)
        return {"removed": removed, "written": len(rows)}

    def get(self, record_id: str) -> ArtifactRecord | None: ...


DEFAULT_WORK_DIR = "artifacts"


def table_name(base: str, work_dir: str | Path | None = None) -> str:
    """One table per work dir, so a test run in another folder never replaces the main records."""
    name = Path(work_dir).name if work_dir is not None else DEFAULT_WORK_DIR
    if name == DEFAULT_WORK_DIR:
        return base
    return f"{base}__{re.sub(r'[^A-Za-z0-9_]+', '_', name)}"


def existing_tables(db: object) -> set[str]:
    listing = db.list_tables()  # type: ignore[attr-defined]
    return set(getattr(listing, "tables", listing))


class LanceArtifactStore:
    """Persist artifact records. Teams define their retrieval tables and indexes."""

    def __init__(self, path: str | Path, work_dir: str | Path | None = None):
        import lancedb
        import pyarrow as pa

        self.db = lancedb.connect(str(path))
        self.table = self.db.create_table(
            table_name("artifact_provenance", work_dir),
            schema=pa.schema([("record_id", pa.string()), ("record_json", pa.string())]),
            exist_ok=True,
        )

    def put(self, record: ArtifactRecord) -> None:
        self.table.merge_insert("record_id").when_matched_update_all().when_not_matched_insert_all().execute([
            {"record_id": record.record_id, "record_json": record.model_dump_json()}
        ])

    def replace_stage(self, stage: str, records: Iterable[ArtifactRecord]) -> dict[str, int]:
        """Delete every record of one stage, then write the new ones. Old runs leave no stale records."""
        if not re.fullmatch(r"[a-z]+", stage):
            raise ValueError("stage must be a lower-case word")
        rows = [{"record_id": r.record_id, "record_json": r.model_dump_json()} for r in records]
        if any(not row["record_id"].startswith(f"{stage}:") for row in rows):
            raise ValueError(f"record IDs must start with '{stage}:'")
        before = self.table.count_rows()
        self.table.delete(f"record_id LIKE '{stage}:%'")
        removed = before - self.table.count_rows()
        if rows:
            self.table.add(rows)
        return {"removed": removed, "written": len(rows)}

    def get(self, record_id: str) -> ArtifactRecord | None:
        if not record_id or len(record_id) > 200:
            raise ValueError("record_id must contain 1 to 200 characters")
        escaped = record_id.replace("'", "''")
        rows = self.table.search().where(f"record_id = '{escaped}'").select(["record_json"]).limit(2).to_list(
            timeout=timedelta(seconds=10))
        if len(rows) > 1:
            raise ValueError("provenance record ID is not unique")
        return ArtifactRecord.model_validate_json(rows[0]["record_json"]) if rows else None

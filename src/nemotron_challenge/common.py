"""Shared helpers for the team stages: files, hashes, retries, and source references."""
from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Callable, Iterable, TypeVar

from .clients import ProtocolError, ServiceError
from .contracts import SourceReference

T = TypeVar("T")
RETRY_STATUS = {429, 500, 502, 503, 504}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_text(path: Path, text: str) -> None:
    """Write a file in one step so that a failed run leaves no partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=".tmp-", delete=False) as stream:
        stream.write(text)
        temporary = Path(stream.name)
    os.replace(temporary, path)


def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    write_text(path, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"{path} is missing. Run the earlier stage first.")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def with_retry(call: Callable[[], T], *, attempts: int = 4, base_delay: float = 2.0) -> T:
    """Retry transient service errors with a bounded number of attempts."""
    for attempt in range(1, attempts + 1):
        try:
            return call()
        except ProtocolError:
            raise
        except ServiceError as exc:
            transient = exc.status_code in RETRY_STATUS or exc.status_code is None
            if not transient or attempt == attempts:
                raise
            delay = float(exc.retry_after) if (exc.retry_after or "").isdigit() else base_delay * attempt
            time.sleep(min(delay, 30))
    raise AssertionError("unreachable")


def text_dir(work_dir: Path) -> Path:
    """The stage folder with the entry text to use: the Super VL correction when it exists, else Parse."""
    corrected = work_dir / "correct"
    return corrected if (corrected / "entries.jsonl").is_file() else work_dir / "extract"


def scan_reference(page: dict[str, Any], manifest: dict[str, Any]) -> SourceReference:
    return SourceReference(
        dataset=manifest["dataset"], dataset_revision=manifest["revision"], source_id=page["page_id"],
        source_url=manifest["source_url"], content_sha256=page["image_sha256"], license=manifest["license"]["spdx"],
    )


def wiki_reference(article: dict[str, Any]) -> SourceReference:
    return SourceReference(
        dataset="wikimedia/structured-wikipedia", dataset_revision=article["dataset_revision"],
        source_id=f"enwiki:{article['page_id']}:{article['revision_id']}", source_url=article["revision_url"],
        content_sha256=article["text_sha256"], license="CC-BY-SA-4.0",
    )


WORD_LIST = Path("/usr/share/dict/words")


@lru_cache(maxsize=1)
def system_words() -> frozenset[str]:
    """The system word list in lower case, or an empty set when the system has none."""
    if not WORD_LIST.is_file():
        return frozenset()
    return frozenset(w.lower() for w in WORD_LIST.read_text(encoding="utf-8", errors="ignore").split())

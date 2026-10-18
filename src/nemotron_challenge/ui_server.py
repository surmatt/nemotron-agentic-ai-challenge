"""HTTP API and static files for the visual pipeline workbench. Start it with `nemotron-challenge ui`.

The API binds to 127.0.0.1 by default. It has no authentication: do not expose it on a shared network.
"""
from __future__ import annotations

from io import BytesIO
import mimetypes
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import workbench
from .common import sha256_text
from .config import ConfigurationError, Settings
from .ocr_eval import crop_block

REPO = Path(__file__).resolve().parents[2]
DIST = REPO / "ui" / "dist"
MEDIA = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


class RunRequest(BaseModel):
    steps: list[str] = []
    all: bool = False


class RerunRequest(BaseModel):
    step: str


def create_app(work_dir: Path = Path("artifacts"), raw_scans: Path = Path("data/raw/britannica"),
               settings_loader: Callable[[], Settings] = Settings.from_env) -> FastAPI:
    api = FastAPI(title="Nemotron pipeline workbench", version="1.0.0")

    def guard(call: Callable[[], Any]) -> Any:
        try:
            return call()
        except FileNotFoundError as exc:
            raise HTTPException(404, str(exc)) from None
        except workbench.StepError as exc:
            raise HTTPException(409, str(exc)) from None
        except ConfigurationError as exc:
            raise HTTPException(500, f"configuration: {exc}") from None

    def image(path: Path, width: int | None) -> Response:
        if not path.is_file():
            raise HTTPException(404, "image file is missing")
        if not width:
            return FileResponse(path, media_type=MEDIA.get(path.suffix.lower(), "application/octet-stream"))
        thumb = work_dir / "ui" / "thumbs" / f"{sha256_text(f'{path.resolve()}:{path.stat().st_mtime}')[:16]}-{width}.jpg"
        if not thumb.is_file():
            from PIL import Image

            with Image.open(path) as source:
                small = source.convert("RGB")
                small.thumbnail((width, width * 2), Image.Resampling.LANCZOS)
                buffer = BytesIO()
                small.save(buffer, format="JPEG", quality=82)
            thumb.parent.mkdir(parents=True, exist_ok=True)
            thumb.write_bytes(buffer.getvalue())
        return FileResponse(thumb, media_type="image/jpeg", headers={"Cache-Control": "max-age=3600"})

    def crop(found: tuple[Path, list[float]]) -> Response:
        path, bbox = found
        return Response(crop_block(path, bbox), media_type="image/jpeg")

    @api.get("/api/services")
    def services(live: bool = False) -> dict[str, Any]:
        return guard(lambda: workbench.services(settings_loader(), live))

    @api.get("/api/uploads")
    def uploads() -> list[dict[str, Any]]:
        return workbench.list_uploads(work_dir)

    @api.post("/api/uploads")
    async def upload(file: UploadFile = File(...)) -> dict[str, Any]:
        data = await file.read(workbench.MAX_UPLOAD_BYTES + 1)
        upload_id = guard(lambda: workbench.create_upload(work_dir, data, file.filename or "scan"))
        return {"id": upload_id}

    @api.post("/api/uploads/from-corpus/{row_index}")
    def from_corpus(row_index: int) -> dict[str, Any]:
        return {"id": guard(lambda: workbench.create_from_corpus(work_dir, raw_scans, row_index))}

    @api.get("/api/uploads/{upload_id}")
    def upload_view(upload_id: str) -> dict[str, Any]:
        return guard(lambda: workbench.upload_view(work_dir, upload_id))

    @api.post("/api/uploads/{upload_id}/run")
    def run(upload_id: str, body: RunRequest) -> dict[str, Any]:
        def go() -> list[str]:
            steps = workbench.remaining_steps(work_dir, upload_id) if body.all else body.steps
            if not steps:
                raise workbench.StepError("name at least one step")
            return workbench.start(work_dir, upload_id, steps, settings_loader)

        return {"started": guard(go)}

    @api.post("/api/uploads/{upload_id}/rerun")
    def rerun(upload_id: str, body: RerunRequest) -> dict[str, Any]:
        return {"started": guard(lambda: workbench.rerun(work_dir, upload_id, body.step, settings_loader))}

    @api.get("/api/uploads/{upload_id}/image")
    def upload_image(upload_id: str, w: int | None = Query(None, ge=64, le=1600)) -> Response:
        folder = guard(lambda: workbench.upload_dir(work_dir, upload_id))
        meta = workbench.read_json(folder / "meta.json")
        return image(folder / meta["scan_file"], w)

    @api.get("/api/uploads/{upload_id}/blocks/{index}/crop")
    def upload_crop(upload_id: str, index: int) -> Response:
        return crop(guard(lambda: workbench.upload_block(work_dir, upload_id, index)))

    @api.get("/api/uploads/{upload_id}/raw/{step}")
    def upload_raw(upload_id: str, step: str) -> Any:
        return guard(lambda: workbench.upload_raw(work_dir, upload_id, step))

    @api.get("/api/corpus")
    def corpus() -> dict[str, Any]:
        return guard(lambda: workbench.corpus_index(work_dir))

    @api.get("/api/corpus/{row_index}")
    def corpus_page(row_index: int) -> dict[str, Any]:
        return guard(lambda: workbench.corpus_page(work_dir, row_index, raw_scans))

    @api.post("/api/corpus/{row_index}/rerun")
    def corpus_rerun(row_index: int, body: RerunRequest) -> dict[str, Any]:
        return guard(lambda: workbench.rerun_from_corpus(work_dir, raw_scans, row_index, body.step, settings_loader))

    @api.get("/api/corpus/{row_index}/image")
    def corpus_image(row_index: int, w: int | None = Query(None, ge=64, le=1600)) -> Response:
        return image(guard(lambda: workbench.corpus_scan(raw_scans, row_index)), w)

    @api.get("/api/corpus/{row_index}/blocks/{index}/crop")
    def corpus_crop(row_index: int, index: int) -> Response:
        return crop(guard(lambda: workbench.corpus_block(work_dir, raw_scans, row_index, index)))

    @api.get("/api/corpus/{row_index}/raw/{step}")
    def corpus_raw(row_index: int, step: str) -> Any:
        return guard(lambda: workbench.corpus_raw(work_dir, row_index, step))

    def document(kind: str, ident: str, ext: str) -> Response:
        path = guard(lambda: workbench.document_file(work_dir, kind, ident, ext))
        return FileResponse(path, media_type="application/pdf" if ext == "pdf" else "text/plain; charset=utf-8")

    @api.get("/api/uploads/{upload_id}/document/{ext}")
    def upload_document(upload_id: str, ext: str) -> Response:
        return document("upload", upload_id, ext)

    @api.get("/api/corpus/{row_index}/document/{ext}")
    def corpus_document(row_index: int, ext: str) -> Response:
        return document("corpus", str(row_index), ext)

    @api.get("/api/site")
    def site_status() -> dict[str, Any]:
        return workbench.site_status(work_dir)

    @api.post("/api/site/build")
    def site_build() -> dict[str, Any]:
        return guard(lambda: workbench.build_site(work_dir, raw_scans, settings_loader))

    @api.get("/site/{path:path}")
    def site_file(path: str) -> Response:
        target = guard(lambda: workbench.site_file(work_dir, path))
        media = {".tex": "text/plain; charset=utf-8", ".json": "application/json"}.get(target.suffix)
        return FileResponse(target, media_type=media or mimetypes.guess_type(target.name)[0] or "application/octet-stream")

    if (DIST / "index.html").is_file():
        api.mount("/", StaticFiles(directory=DIST, html=True), name="ui")
    else:
        @api.get("/", response_class=HTMLResponse)
        def missing_build() -> str:
            return ("<p>The UI is not built. Run <code>npm install &amp;&amp; npm run build</code> in <code>ui/</code>, "
                    "or start the dev server with <code>npm run dev</code>.</p>")
    return api


def serve(host: str, port: int, work_dir: Path) -> None:
    import uvicorn

    uvicorn.run(create_app(work_dir), host=host, port=port, log_level="info")

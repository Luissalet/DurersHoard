from __future__ import annotations

import asyncio
import json
import mimetypes
import re
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import ROOT, settings
from .native import catalog, dispatch, executable, launch_gui, failed_results
from .history import execute as history_execute
from .sessions import sessions
from . import store

try:
    from hoard_link import family as hoard_family
    from hoard_link import guard as hoard_guard
    HOARDLINK_AVAILABLE = True
except ImportError:
    hoard_family = None
    hoard_guard = None
    HOARDLINK_AVAILABLE = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings().data_dir.mkdir(parents=True, exist_ok=True)
    if hoard_family:
        from hoard_link.tokens import read_or_create_token
        read_or_create_token(settings().data_dir / "mcp-token")
        hoard_family.configure("durer", str(settings().data_dir))
    yield
    sessions.close()


app = FastAPI(title="Dürer's Hoard", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "durer_hoard" / "static"), name="static")
if hoard_family:
    hoard_family.install_fastapi(app, "durer", str(settings().data_dir), contract=True,
                                  instructions="Persistent local VectorCraft illustration projects. Native tools and commands are fully discoverable.")
if hoard_guard:
    hoard_guard.install_guard(app, port_getter=lambda: settings().port)


class CreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)


class ActionsRequest(BaseModel):
    actions: list[dict[str, Any]] = Field(min_length=1, max_length=80)


class ExportRequest(BaseModel):
    format: str
    arguments: dict[str, Any] = Field(default_factory=dict)


def _project(project_id: str):
    try:
        item = store.read(project_id)
        root = store.project_root(project_id)
        return item, root
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/", response_class=HTMLResponse)
def index():
    return (ROOT / "durer_hoard" / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/health")
def health():
    configured = settings().vectorcraft_cli
    gui = settings().vectorcraft_gui
    return {"ok": True, "service": "durers-hoard", "hoard_link": HOARDLINK_AVAILABLE,
            "engine_configured": bool(configured and configured.is_file()),
            "gui_configured": bool(gui and gui.is_file()),
            "engine_path": str(configured) if configured else None, "data_dir": str(settings().data_dir),
            **(hoard_family.health_block() if hoard_family else {})}


@app.get("/api/catalog")
def get_catalog():
    try:
        return catalog()
    except Exception as exc:
        raise HTTPException(503, f"Native engine discovery failed: {exc}") from exc


@app.get("/api/operations/{operation_id}")
def operation(operation_id: str):
    record = sessions.operation(operation_id)
    if not record:
        raise HTTPException(404, "Operation receipt not found in this service lifetime")
    return record


@app.get("/api/illustrations")
def illustrations():
    return store.list_projects()


@app.post("/api/illustrations")
def new_illustration(payload: CreateRequest):
    try:
        item = store.create(payload.title)
        project, root = _project(item["id"])
        results = sessions.execute(item["id"], root / "project.vectorcraft", [])
        return {**project, "results": results}
    except Exception as exc:
        raise HTTPException(503, str(exc)) from exc


@app.post("/api/illustrations/import")
async def import_illustration(title: str, file: UploadFile = File(...)):
    filename = Path(file.filename or "source").name
    suffix = Path(filename).suffix.lower()
    if suffix not in {".svg", ".png", ".jpg", ".jpeg", ".webp", ".pdf"}:
        raise HTTPException(415, "Import supports SVG, PNG, JPEG, WebP, and PDF files")
    data_dir = settings().data_dir / "staging"
    data_dir.mkdir(parents=True, exist_ok=True)
    staged = data_dir / f"{uuid.uuid4().hex}{suffix}"
    contents = await file.read(50 * 1024 * 1024 + 1)
    if not contents or len(contents) > 50 * 1024 * 1024:
        raise HTTPException(413, "File must be between 1 byte and 50 MB")
    staged.write_bytes(contents)
    try:
        item = store.create(title, source=staged, source_name=filename)
        project, root = _project(item["id"])
        source_path = item["source"]["path"]
        results = await asyncio.to_thread(
            sessions.execute, item["id"], root / "project.vectorcraft",
            [{"name": "open_file", "arguments": {"path": source_path}}])
        return {**project, "results": results}
    except Exception as exc:
        raise HTTPException(503, f"Import was copied but native open failed: {exc}") from exc
    finally:
        staged.unlink(missing_ok=True)


@app.get("/api/illustrations/{project_id}")
def illustration(project_id: str):
    item, _ = _project(project_id)
    return item


@app.post("/api/illustrations/{project_id}/actions")
def actions(project_id: str, payload: ActionsRequest):
    item, root = _project(project_id)
    try:
        results = history_execute(project_id, root / "project.vectorcraft", payload.actions)
        result = {"illustration": store.read(project_id), "results": results}
        return JSONResponse(result, status_code=502) if failed_results(results) else result
    except Exception as exc:
        raise HTTPException(502, f"VectorCraft action failed: {exc}") from exc


@app.post("/api/illustrations/{project_id}/export")
def export(project_id: str, payload: ExportRequest):
    _, root = _project(project_id)
    fmt = payload.format.lower().lstrip(".")
    if fmt not in {"svg", "png", "pdf", "jpg", "webp", "gif", "tiff", "bmp", "dxf", "eps", "emf", "wmf", "psd", "vectorcraft"}:
        raise HTTPException(415, "Format is not in the native export schema")
    path = root / "exports" / f"{project_id}-{uuid.uuid4().hex}.{fmt}"
    args = {**payload.arguments, "format": fmt, "path": str(path)}
    try:
        results = sessions.execute(project_id, root / "project.vectorcraft",
                                   [{"name": "export", "arguments": args}])
        if any(row.get("name") == "export" and row.get("is_error") for row in results):
            raise RuntimeError("VectorCraft reported an export error")
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError("Native export reported success but produced no file")
        return {"format": fmt, "path": str(path), "url": f"/api/illustrations/{project_id}/files/exports/{path.name}",
                "bytes": path.stat().st_size, "results": results}
    except Exception as exc:
        raise HTTPException(502, f"Native export failed: {exc}") from exc


@app.get("/api/illustrations/{project_id}/files/{area}/{filename}")
def file(project_id: str, area: str, filename: str):
    _, root = _project(project_id)
    if area not in {"exports", "sources"} or Path(filename).name != filename:
        raise HTTPException(404, "File not found")
    target = (root / area / filename).resolve()
    if not target.is_relative_to((root / area).resolve()) or not target.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(target, filename=target.name)


@app.get("/api/illustrations/{project_id}/preview")
def preview(project_id: str):
    _, root = _project(project_id)
    path = root / "exports" / f"preview-{uuid.uuid4().hex}.png"
    try:
        results = sessions.execute(project_id, root / "project.vectorcraft",
                                   [{"name": "export", "arguments": {"format": "png", "path": str(path), "scale": 1}}])
        if any(row.get("name") == "export" and row.get("is_error") for row in results):
            raise RuntimeError("VectorCraft reported a preview export error")
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError("Native preview export returned no PNG")
        return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})
    except Exception as exc:
        raise HTTPException(502, f"Preview render failed: {exc}") from exc


@app.get("/api/illustrations/{project_id}/native")
def native_file(project_id: str):
    _, root = _project(project_id)
    path = root / "project.vectorcraft"
    if not path.is_file():
        raise HTTPException(404, "Native project is not saved")
    return FileResponse(path, filename=f"{project_id}.vectorcraft")


@app.post("/api/illustrations/{project_id}/open-gui")
def open_gui(project_id: str):
    _, root = _project(project_id)
    try:
        gui = launch_gui(project_id)
        sessions.connect(project_id, gui["address"])
        results = sessions.execute(project_id, root / "project.vectorcraft", [])
        if any(row.get("is_error") for row in results):
            raise RuntimeError("VectorCraft GUI did not open the native project")
        return {**gui, "project_file": str(root / "project.vectorcraft"), "results": results}
    except Exception as exc:
        raise HTTPException(502, f"Could not open VectorCraft desktop: {exc}") from exc


@app.post("/api/native/dispatch")
def raw_dispatch(payload: ActionsRequest):
    """One-shot full native bridge; persistent editing should use the project endpoint."""
    try:
        return dispatch(payload.actions)
    except Exception as exc:
        raise HTTPException(502, str(exc)) from exc


from . import agent_tools
for _tool_name in ("illustration_list", "illustration_create", "illustration_inspect",
                   "illustration_native_call", "illustration_export", "vectorcraft_catalog"):
    app.add_api_route("/api/agent/" + _tool_name, getattr(agent_tools, _tool_name), methods=["POST"])

"""Thin HoardLink HTTP tool routes; all editing remains native VectorCraft MCP."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import store
from .config import settings
from .history import execute as history_execute
from .native import catalog
from .sessions import sessions

router = APIRouter(prefix="/api/agent")


class ProjectId(BaseModel):
    project_id: str


class Create(BaseModel):
    title: str = Field(min_length=1, max_length=160)


class NativeCall(BaseModel):
    project_id: str
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ProjectExport(BaseModel):
    project_id: str
    format: str = Field(pattern=r"^(svg|png|pdf|jpg|webp)$")


def _get(project_id: str):
    try:
        item = store.read(project_id)
        return item, store.project_root(project_id)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/illustration_list")
def illustration_list():
    """List saved vector projects and their hoard:// references."""
    return store.list_projects()


@router.post("/illustration_create")
def illustration_create(payload: Create):
    """Create an editable native VectorCraft illustration project."""
    item = store.create(payload.title)
    root = store.project_root(item["id"])
    results = sessions.execute(item["id"], root / "project.vectorcraft", [])
    return {"illustration": store.read(item["id"]), "results": results}


@router.post("/illustration_inspect")
def illustration_inspect(payload: ProjectId):
    """Inspect a saved native document using VectorCraft."""
    item, root = _get(payload.project_id)
    results = sessions.execute(item["id"], root / "project.vectorcraft", [{"name": "inspect_document", "arguments": {}}])
    return {"illustration": item, "results": results}


@router.post("/illustration_native_call")
def illustration_native_call(payload: NativeCall):
    """Dispatch a verified native VectorCraft MCP tool in a persistent project session."""
    item, root = _get(payload.project_id)
    names = {tool["name"] for tool in catalog()["tools"]}
    if payload.tool not in names:
        raise HTTPException(400, "Tool name is absent from the current native catalog")
    results = history_execute(item["id"], root / "project.vectorcraft", [{"name": payload.tool, "arguments": payload.arguments}])
    return {"illustration": store.read(item["id"]), "results": results}


@router.post("/illustration_export")
def illustration_export(payload: ProjectExport):
    """Export a native SVG, PNG, PDF, JPEG, or WebP file."""
    item, root = _get(payload.project_id)
    target = root / "exports" / (payload.project_id + "-" + uuid.uuid4().hex + "." + payload.format)
    results = sessions.execute(item["id"], root / "project.vectorcraft", [{
        "name": "export", "arguments": {"format": payload.format, "path": str(target)}}])
    if any(row.get("name") == "export" and row.get("is_error") for row in results):
        raise HTTPException(502, "Native export reported an error")
    if not target.is_file() or target.stat().st_size == 0:
        raise HTTPException(502, "Native export did not produce a file")
    return {"format": payload.format, "path": str(target),
            "url": f"/api/illustrations/{payload.project_id}/files/exports/{target.name}", "results": results}


@router.post("/vectorcraft_catalog")
def vectorcraft_catalog():
    """Return every native MCP tool schema, CLI help, and discovered command."""
    return catalog()

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import settings


CANVAS_UNITS = {"Pixels", "Points", "Picas", "Inches", "Millimeters", "Centimeters", "Feet", "Yards", "Meters", "Feet & Inches"}
POINTS_PER_UNIT = {
    "Pixels": 1.0, "Points": 1.0, "Picas": 12.0, "Inches": 72.0,
    "Millimeters": 72.0 / 25.4, "Centimeters": 72.0 / 2.54,
    "Feet": 864.0, "Yards": 2592.0, "Meters": 72.0 / 0.0254,
    "Feet & Inches": 864.0,
}


def canvas_settings(width: float | None, height: float | None, units: str | None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Convert requested dimensions to points; units selects VectorCraft's ruler display."""
    if units is not None and units not in CANVAS_UNITS:
        raise ValueError("Unsupported canvas units; use VectorCraft's documented units")
    params: dict[str, Any] = {}
    manifest: dict[str, Any] = {}
    for name, value in (("width", width), ("height", height)):
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                  or not math.isfinite(value) or value <= 0 or value > 100000):
            raise ValueError(f"Canvas {name} must be a finite number greater than 0 and at most 100000")
    requested_units = units or ("Points" if width is not None or height is not None else None)
    factor = POINTS_PER_UNIT.get(requested_units or "Points", 1.0)
    if requested_units is not None:
        manifest["units"] = requested_units
    for name, value in (("width", width), ("height", height)):
        if value is not None:
            native_points = round(value * factor, 6)
            params[name] = native_points
            manifest[name] = value
            manifest[f"{name}_points"] = native_points
    if units is not None or requested_units is not None:
        params["units"] = units or requested_units
        manifest["units"] = units or requested_units
    return manifest, params


def project_root(project_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}", project_id):
        raise ValueError("Invalid illustration ID")
    root = settings().data_dir / "illustrations" / project_id
    if not root.resolve().is_relative_to((settings().data_dir / "illustrations").resolve()):
        raise ValueError("Invalid project path")
    return root


def manifest_path(project_id: str) -> Path:
    return project_root(project_id) / "illustration.json"


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    """Replace a manifest only after its complete UTF-8 JSON is on disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
        temp.replace(path)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def read(project_id: str) -> dict[str, Any]:
    path = manifest_path(project_id)
    if not path.is_file():
        raise FileNotFoundError("Illustration not found")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["project_file"] = str(project_root(project_id) / "project.vectorcraft")
    data["reference"] = f"hoard://durer/illustration/{project_id}"
    return data


def list_projects() -> list[dict[str, Any]]:
    root = settings().data_dir / "illustrations"
    root.mkdir(parents=True, exist_ok=True)
    items = []
    for path in root.glob("*/illustration.json"):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            item["reference"] = f"hoard://durer/illustration/{item['id']}"
            items.append(item)
        except (ValueError, KeyError, OSError):
            continue
    return sorted(items, key=lambda item: item.get("updated_at", ""), reverse=True)


def create(title: str, *, source: Path | None = None, source_name: str | None = None, canvas: dict[str, Any] | None = None) -> dict[str, Any]:
    title = " ".join(title.split()).strip()[:160]
    if not title:
        raise ValueError("Title is required")
    project_id = uuid.uuid4().hex
    root = project_root(project_id)
    (root / "exports").mkdir(parents=True)
    (root / "sources").mkdir()
    manifest = {"id": project_id, "title": title, "created_at": _now(), "updated_at": _now(),
                "source": None, "native_format": ".vectorcraft", "engine": "VectorCraft 0.3.1"}
    if canvas:
        manifest["canvas"] = dict(canvas)
    if source:
        suffix = source.suffix.lower()
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", source_name or source.name)[:180] or "source" + suffix
        copied = root / "sources" / safe_name
        shutil.copyfile(source, copied)
        manifest["source"] = {"name": safe_name, "path": str(copied),
                               "sha256": hashlib.sha256(copied.read_bytes()).hexdigest(),
                               "bytes": copied.stat().st_size}
    write_json_atomic(manifest_path(project_id), manifest)
    return read(project_id)


def touch(project_id: str) -> None:
    path = manifest_path(project_id)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["updated_at"] = _now()
    write_json_atomic(path, data)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

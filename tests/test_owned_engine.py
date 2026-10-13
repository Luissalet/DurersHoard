"""Actual owned-engine effects, historical preservation and native workflow."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess

from fastapi.testclient import TestClient
import pytest

from durer_hoard import store
from durer_hoard.native import catalog, executable, gui_executable
from durer_hoard.sessions import sessions


@pytest.fixture
def owned(monkeypatch, tmp_path):
    monkeypatch.setenv("DURER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DURER_CONFIG", str(tmp_path / "absent.json"))
    monkeypatch.setenv("DURER_VECTORCRAFT_CLI", str(tmp_path / "not-an-engine.exe"))
    monkeypatch.setenv("DURER_VECTORCRAFT_GUI", str(tmp_path / "not-an-editor.exe"))
    monkeypatch.setenv("HOARD_COPILOT", "0")
    monkeypatch.setenv("HOARD_AUTO_REGISTER", "0")
    yield tmp_path
    sessions.close()


def test_catalog_and_api_health_use_owned_binaries_with_invalid_legacy_config(owned):
    from durer_hoard.api import app
    assert executable().name == ("durer-cli.exe" if os.name == "nt" else "durer-cli")
    assert gui_executable().is_file()
    data = catalog()
    assert len(data["tools"]) == 25 and len(data["commands"]) == 659
    assert "durer-cli" in data["cli"]["help"]
    assert all("vectorcraft" not in item["uri"] for item in data["resources"])
    with TestClient(app, base_url="http://127.0.0.1:5222") as client:
        health = client.get("/api/health").json()
        assert health["engine_configured"] and health["gui_configured"]
        assert Path(health["engine_path"]) == executable()
        assert client.get("/api/engine/catalog").status_code == 200


def test_historical_document_is_copied_and_undo_survives_restart(owned):
    from durer_hoard.history import execute
    source = (Path(__file__).parent / "fixtures/historical.vectorcraft")
    item = store.create("Historical document")
    root = store.project_root(item["id"])
    legacy = root / "project.vectorcraft"
    legacy.write_bytes(source.read_bytes())
    original = legacy.read_bytes()
    original_manifest = store.manifest_path(item["id"]).read_bytes()
    original_doc = json.loads(original)["document"]
    path = root / "project.durer"
    results = sessions.execute(item["id"], path, [])
    assert not any(r["is_error"] for r in results)
    copy = json.loads(path.read_text(encoding="utf-8"))
    assert copy["format"] == "durer"
    assert copy["document"]["layers"] == original_doc["layers"]
    assert copy["document"]["artboards"] == original_doc["artboards"]
    assert legacy.read_bytes() == original
    assert store.manifest_path(item["id"]).read_bytes() == original_manifest
    before = path.read_bytes()
    result = execute(item["id"], path, [{"name": "draw_shape", "arguments": {"shape": "ellipse", "x": 12, "y": 23, "width": 45, "height": 56, "fill": "#114488"}}])
    assert not any(r["is_error"] for r in result)
    after = path.read_bytes()
    assert after != before
    sessions.close()
    assert not any(r["is_error"] for r in execute(item["id"], path, [{"name": "undo", "arguments": {}}]))
    assert path.read_bytes() == before
    sessions.close()
    assert not any(r["is_error"] for r in execute(item["id"], path, [{"name": "redo", "arguments": {}}]))
    assert path.read_bytes() == after and legacy.read_bytes() == original


def test_owned_mcp_names_and_legacy_aliases_reach_same_project(owned):
    from durer_hoard.mcp_server import call_tool, list_tools
    async def exercise():
        tools = await list_tools()
        names = {t.name for t in tools}
        assert {"durer_catalog", "durer_draw_shape", "vectorcraft_draw_shape"}.issubset(names)
        created = await call_tool("illustration_create", {"title": "Owned MCP", "width": 120, "height": 80, "units": "Points"})
        assert not created.isError
        project = created.structuredContent["illustration"]["id"]
        for name in ("durer_draw_shape", "vectorcraft_draw_shape"):
            response = await call_tool(name, {"project_id": project, "shape": "rectangle", "x": 10, "y": 10, "width": 20, "height": 20})
            assert not response.isError
        read = await call_tool("illustration_inspect", {"project_id": project})
        text = next(r for r in read.structuredContent["results"] if r["name"] == "inspect_document")["result"]["content"][0]["text"]
        assert json.loads(text)["objects"] >= 2
    asyncio.run(exercise())


def test_http_import_retains_historical_original_and_exports_real_files(owned):
    from durer_hoard.api import app
    from PIL import Image
    import io
    original = (Path(__file__).parent / "fixtures/historical.vectorcraft").read_bytes()
    with TestClient(app, base_url="http://127.0.0.1:5222") as client:
        response = client.post("/api/illustrations/import?title=Historical", files={"file": ("old.vectorcraft", original, "application/json")})
        assert response.status_code == 200, response.text
        item = response.json()
        assert Path(item["source"]["path"]).read_bytes() == original
        path = Path(item["project_file"])
        assert path.suffix == ".durer" and json.loads(path.read_text())["format"] == "durer"
        for fmt in ("svg", "png", "pdf"):
            export = client.post(f"/api/illustrations/{item['id']}/export", json={"format": fmt})
            assert export.status_code == 200, export.text
            data = client.get(export.json()["url"]).content
            if fmt == "png":
                with Image.open(io.BytesIO(data)) as image:
                    image.load()
                    assert image.width > 0 and image.height > 0
            elif fmt == "pdf":
                assert data.startswith(b"%PDF-")
            else:
                assert b"<svg" in data
        assert Path(item["source"]["path"]).read_bytes() == original

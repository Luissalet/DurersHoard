from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import asyncio
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient


def _find_verified_cli() -> Path | None:
    candidates = [os.environ.get("DURER_VECTORCRAFT_CLI")]
    try:
        from durer_hoard.config import settings
        configured = settings().vectorcraft_cli
        candidates.append(str(configured) if configured else None)
    except Exception:
        pass
    candidates.extend([shutil.which("vectorcraft-cli.exe"), shutil.which("vectorcraft-cli")])
    return next((Path(path).expanduser().resolve() for path in candidates
                 if path and Path(path).expanduser().is_file()), None)


CLI = _find_verified_cli()


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    if not CLI or not CLI.is_file():
        pytest.skip("Verified VectorCraft 0.3.1 bundle is unavailable")
    monkeypatch.setenv("DURER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DURER_VECTORCRAFT_CLI", str(CLI))
    yield tmp_path / "data"
    from durer_hoard.sessions import sessions
    sessions.close()


def _tool_text(result):
    return result["content"][0]["text"]


def test_native_create_edit_undo_reopen_and_export(isolated):
    from durer_hoard import store
    from durer_hoard.sessions import sessions

    item = store.create("Native illustration")
    root = store.project_root(item["id"])
    project = root / "project.vectorcraft"
    source = root / "sources" / "reference.svg"
    source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80"><circle cx="40" cy="40" r="20"/></svg>', encoding="utf-8")
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()

    created = sessions.execute(item["id"], project, [{"name": "draw_shape", "arguments": {
        "shape": "rectangle", "x": 50, "y": 60, "width": 180, "height": 120,
        "fill": "#e07146", "stroke": "#24261f", "strokeWidth": 3}}])
    assert not created[0]["is_error"]
    assert project.is_file() and project.stat().st_size > 1000
    object_id = json.loads(_tool_text(created[0]["result"]))["id"]
    assert object_id > 1
    transformed = sessions.execute(item["id"], project, [{"name": "transform", "arguments": {
        "ids": [object_id], "dx": 20, "dy": 15, "scale": 0.75, "rotate": 12}}])
    assert not transformed[0]["is_error"]

    undone = sessions.execute(item["id"], project, [{"name": "undo", "arguments": {}}])
    assert not undone[0]["is_error"]
    redone = sessions.execute(item["id"], project, [{"name": "redo", "arguments": {}}])
    assert not redone[0]["is_error"]

    for fmt in ("svg", "png", "pdf"):
        target = root / "exports" / ("roundtrip." + fmt)
        results = sessions.execute(item["id"], project, [{"name": "export", "arguments": {"format": fmt, "path": str(target)}}])
        assert not results[0]["is_error"]
        assert target.is_file() and target.stat().st_size > 100

    sessions.close()
    reopened = sessions.execute(item["id"], project, [{"name": "inspect_document", "arguments": {}}])
    assert not reopened[-1]["is_error"]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
    assert store.read(item["id"])["reference"] == f"hoard://durer/illustration/{item['id']}"


def test_file_snapshots_restore_undo_and_redo_after_engine_restart(isolated):
    from durer_hoard import store
    from durer_hoard.history import execute
    from durer_hoard.sessions import sessions

    item = store.create("Restart recovery")
    project = store.project_root(item["id"]) / "project.vectorcraft"
    sessions.execute(item["id"], project, [])
    original = hashlib.sha256(project.read_bytes()).hexdigest()
    changed = execute(item["id"], project, [{"name": "draw_shape", "arguments": {
        "shape": "ellipse", "x": 90, "y": 90, "width": 120, "height": 65, "fill": "#ce744c"}}])
    assert not changed[0]["is_error"]
    after_edit = hashlib.sha256(project.read_bytes()).hexdigest()
    assert after_edit != original

    sessions.close()
    undo = execute(item["id"], project, [{"name": "undo", "arguments": {}}])
    assert not undo[0]["is_error"]
    assert hashlib.sha256(project.read_bytes()).hexdigest() == original
    assert undo[-1]["name"] == "inspect_document"
    assert not undo[-1]["is_error"]

    sessions.close()
    redo = execute(item["id"], project, [{"name": "redo", "arguments": {}}])
    assert not redo[0]["is_error"]
    assert hashlib.sha256(project.read_bytes()).hexdigest() == after_edit


def test_concurrent_first_calls_share_one_native_session_and_keep_both_edits(isolated):
    from durer_hoard import store
    from durer_hoard.sessions import sessions

    item = store.create("Concurrent native session")
    project = store.project_root(item["id"]) / "project.vectorcraft"
    actions = [
        {"name": "draw_shape", "arguments": {"shape": "rectangle", "x": 10, "y": 12,
         "width": 70, "height": 40, "fill": "#cf6749"}},
        {"name": "draw_shape", "arguments": {"shape": "ellipse", "x": 95, "y": 20,
         "width": 55, "height": 55, "fill": "#536d49"}},
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(sessions.execute, item["id"], project, [action]) for action in actions]
        results = [future.result(timeout=90) for future in futures]
    assert all(not result[0]["is_error"] for result in results)
    assert len([session for sid, session in sessions.sessions.items() if sid == item["id"]]) == 1
    inspect = sessions.execute(item["id"], project, [{"name": "inspect_document", "arguments": {}}])
    assert not inspect[-1]["is_error"]
    assert project.is_file() and project.stat().st_size > 1000


def test_timeout_returns_reconcilable_receipt_without_cancelling_work(isolated, monkeypatch):
    from durer_hoard.sessions import sessions

    async def delayed(project_id, path, actions):
        await asyncio.sleep(0.12)
        return [{"name": "inspect_document", "is_error": False, "result": {"done": True}}]

    monkeypatch.setattr(sessions, "_execute", delayed)
    with pytest.raises(TimeoutError, match="may still complete") as error:
        sessions.execute("a" * 32, isolated / "unused.vectorcraft", [], timeout=0.01)
    receipt = error.value.args[0].split("operation ", 1)[1].split(" exceeded", 1)[0]
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        status = sessions.operation(receipt)
        if status and status["state"] != "pending":
            break
        time.sleep(0.01)
    assert status["state"] == "completed"
    assert status["result"][0]["result"] == {"done": True}


def test_external_native_edit_survives_reopen_and_app_undo(isolated):
    from durer_hoard import store
    from durer_hoard.history import execute
    from durer_hoard.sessions import sessions

    external = store.create("External source document")
    external_path = store.project_root(external["id"]) / "project.vectorcraft"
    external_edit = sessions.execute(external["id"], external_path, [{"name": "draw_shape", "arguments": {
        "shape": "ellipse", "x": 20, "y": 25, "width": 75, "height": 50, "fill": "#123456"}}])
    external_fills = [layer["fill"] for layer in json.loads(
        external_edit[-1]["result"]["content"][0]["text"])["layers"][0]["children"]]
    target = store.create("Externally updated document")
    target_path = store.project_root(target["id"]) / "project.vectorcraft"
    sessions.execute(target["id"], target_path, [])
    sessions.close()

    shutil.copyfile(external_path, target_path)  # external editor replacement while Dürer is closed
    reopened = sessions.execute(target["id"], target_path, [{"name": "inspect_document", "arguments": {}}])
    external_fills = [layer["fill"] for layer in json.loads(
        reopened[-1]["result"]["content"][0]["text"])["layers"][0]["children"]]
    external_hash = hashlib.sha256(target_path.read_bytes()).hexdigest()
    changed = execute(target["id"], target_path, [{"name": "draw_shape", "arguments": {
        "shape": "rectangle", "x": 120, "y": 35, "width": 45, "height": 30, "fill": "#cf6749"}}])
    assert not changed[0]["is_error"]
    after_edit = sessions.execute(target["id"], target_path, [{"name": "inspect_document", "arguments": {}}])
    text = after_edit[-1]["result"]["content"][0]["text"]
    fills = [layer["fill"] for layer in json.loads(text)["layers"][0]["children"]]
    assert "#123456" in fills and "#cf6749" in fills

    undone = execute(target["id"], target_path, [{"name": "undo", "arguments": {}}])
    assert not any(row.get("is_error") for row in undone)
    assert undone[-1]["name"] == "inspect_document"
    layers = json.loads(undone[-1]["result"]["content"][0]["text"])["layers"][0]["children"]
    assert [layer["fill"] for layer in layers] == external_fills
    assert hashlib.sha256(target_path.read_bytes()).hexdigest() == external_hash
    sessions.close()


def test_api_import_copies_source_and_keeps_project_editable(isolated):
    from durer_hoard.api import app
    from durer_hoard.sessions import sessions

    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="120" height="80"><rect x="10" y="10" width="90" height="55" fill="#566d48"/></svg>'
    before = hashlib.sha256(svg).hexdigest()
    with TestClient(app, base_url="http://127.0.0.1:5222") as client:
        assert client.get("/api/health", headers={"host": "evil.example"}).status_code == 403
        tools = client.get("/api/agent/tools")
        assert tools.status_code == 200
        assert {"illustration_create", "illustration_native_call", "vectorcraft_catalog"}.issubset(
            {tool["name"] for tool in tools.json()["tools"]})
        token_path = isolated / "mcp-token"
        token = token_path.read_text(encoding="utf-8").strip()
        hub_create = client.post("/api/agent/call", headers={"Authorization": "Bearer " + token}, json={
            "name": "illustration_create", "arguments": {"title": "HoardLink contract"}})
        assert hub_create.status_code == 200, hub_create.text
        assert hub_create.json()["illustration"]["reference"].startswith("hoard://durer/illustration/")
        imported = client.post("/api/illustrations/import?title=Source%20preserved", files={
            "file": ("source.svg", svg, "image/svg+xml")})
        assert imported.status_code == 200, imported.text
        item = imported.json()
        source_file = Path(item["source"]["path"])
        assert source_file.read_bytes() == svg
        assert item["source"]["sha256"] == before
        assert item["reference"].startswith("hoard://durer/illustration/")
        project_file = Path(item["project_file"])
        assert project_file.is_file() and project_file.stat().st_size > 1000
        action = client.post(f"/api/illustrations/{item['id']}/actions", json={"actions": [
            {"name": "draw_shape", "arguments": {"shape": "ellipse", "x": 80, "y": 80, "width": 100, "height": 70, "fill": "#ce744c"}}]})
        assert action.status_code == 200, action.text
        exported = client.post(f"/api/illustrations/{item['id']}/export", json={"format": "png", "arguments": {}})
        assert exported.status_code == 200, exported.text
        download = client.get(exported.json()["url"])
        assert download.status_code == 200 and download.content.startswith(b"\x89PNG")
        assert hashlib.sha256(source_file.read_bytes()).hexdigest() == before
        assert client.get("/api/health").json()["hoard_link"] is True
    sessions.close()


def test_failed_export_cannot_return_a_previous_file(isolated, monkeypatch):
    from durer_hoard.api import app
    from durer_hoard import store
    from durer_hoard.sessions import sessions

    item = store.create("Export failure")
    root = store.project_root(item["id"])
    stale = root / "exports" / f"{item['id']}.png"
    stale.write_bytes(b"older export")
    monkeypatch.setattr(sessions, "execute", lambda *args, **kwargs: [
        {"name": "export", "is_error": True, "result": {"error": "synthetic failure"}}])
    with TestClient(app, base_url="http://127.0.0.1:5222") as client:
        response = client.post(f"/api/illustrations/{item['id']}/export", json={"format": "png"})
        assert response.status_code == 502
        assert "reported an export error" in response.json()["detail"]
        assert stale.read_bytes() == b"older export"


def test_import_waits_in_worker_thread_without_blocking_health(isolated, monkeypatch):
    import httpx
    from durer_hoard.api import app
    from durer_hoard.sessions import sessions

    def slow_open(*args, **kwargs):
        time.sleep(0.4)
        return []

    monkeypatch.setattr(sessions, "execute", slow_open)

    async def exercise():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:5222") as client:
            pending = asyncio.create_task(client.post("/api/illustrations/import?title=Responsive", files={
                "file": ("tiny.svg", b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>', "image/svg+xml")}))
            await asyncio.sleep(0.05)
            started = time.monotonic()
            health = await client.get("/api/health")
            elapsed = time.monotonic() - started
            result = await pending
            return health, elapsed, result

    health, elapsed, imported = asyncio.run(exercise())
    assert health.status_code == 200 and health.json()["ok"]
    assert elapsed < 0.25
    assert imported.status_code == 200, imported.text


def test_faustus_stdio_mcp_lists_and_dispatches_complete_native_tools(isolated):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def exercise():
        env = dict(os.environ)
        env["DURER_DATA_DIR"] = str(isolated)
        env["DURER_VECTORCRAFT_CLI"] = str(CLI)
        params = StdioServerParameters(command=sys.executable, args=["-m", "durer_hoard.mcp_server"], env=env)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                tools = (await client.list_tools()).tools
                names = {tool.name for tool in tools}
                assert "vectorcraft_run_command" in names
                assert "vectorcraft_draw_shape" in names
                assert "vectorcraft_transform" in names
                assert "vectorcraft_pathfinder" in names
                assert "vectorcraft_catalog" in names
                created = await client.call_tool("illustration_create", {"title": "MCP drawing"})
                payload = json.loads(created.content[0].text)
                project_id = payload["illustration"]["id"]
                drawn = await client.call_tool("vectorcraft_draw_shape", {
                    "project_id": project_id,
                    "shape": "rectangle", "x": 15, "y": 25, "width": 85, "height": 65,
                    "fill": "#566d48"})
                assert not drawn.isError
                inspection = await client.call_tool("illustration_inspect", {"project_id": project_id})
                assert not inspection.isError
                catalog_result = await client.call_tool("vectorcraft_catalog", {})
                full = json.loads(catalog_result.content[0].text)
                assert len(full["tools"]) == 25 and len(full["commands"]) == 659

    asyncio.run(exercise())

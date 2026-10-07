from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
import asyncio
import shutil
import subprocess
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


def _own_native_processes():
    if os.name != "nt":
        return None
    import subprocess
    query = f"Get-CimInstance Win32_Process -Filter \"Name='vectorcraft-cli.exe' AND ParentProcessId={os.getpid()}\" | Select-Object ProcessId,ParentProcessId | ConvertTo-Json -Compress"
    result = subprocess.check_output(["powershell", "-NoProfile", "-Command", query], text=True).strip()
    rows = json.loads(result) if result else []
    return rows if isinstance(rows, list) else [rows]


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


@pytest.mark.parametrize(("unit", "points_per_unit"), [
    ("Pixels", 1), ("Points", 1), ("Picas", 12), ("Inches", 72),
    ("Millimeters", 72 / 25.4), ("Centimeters", 72 / 2.54),
    ("Feet", 864), ("Yards", 2592), ("Meters", 72 / 0.0254),
    ("Feet & Inches", 864),
])
def test_canvas_input_units_convert_to_native_points(unit, points_per_unit):
    from durer_hoard.store import canvas_settings

    manifest, params = canvas_settings(2, 3, unit)
    assert manifest["units"] == unit
    assert params["units"] == unit
    assert params["width"] == pytest.approx(2 * points_per_unit)
    assert params["height"] == pytest.approx(3 * points_per_unit)


def test_custom_canvas_size_units_and_artwork_export_are_native(isolated):
    from durer_hoard.api import app
    from durer_hoard.sessions import sessions

    cli_info = lambda path: json.loads(subprocess.check_output([str(CLI), "info", str(path)], text=True))
    with TestClient(app, base_url="http://127.0.0.1:5222") as client:
        custom = client.post("/api/illustrations", json={
            "title": "400 by 300 points", "width": 400, "height": 300, "units": "Points"})
        assert custom.status_code == 200, custom.text
        item = custom.json()
        assert item["canvas"] == {"width": 400.0, "height": 300.0, "width_points": 400.0, "height_points": 300.0, "units": "Points"}
        native = Path(item["project_file"])
        info = cli_info(native)
        assert info["info"]["units"] == "Points"
        assert info["artboards"][0]["rect"] == [0.0, 0.0, 400.0, 300.0]

        drawn = client.post(f"/api/illustrations/{item['id']}/actions", json={"actions": [{
            "name": "draw_shape", "arguments": {"shape": "rectangle", "x": 17, "y": 23,
                "width": 80, "height": 50, "fill": "#ce744c", "stroke": "#24261f", "strokeWidth": 0}}]})
        assert drawn.status_code == 200, drawn.text
        exported = client.post(f"/api/illustrations/{item['id']}/export", json={"format": "svg"})
        assert exported.status_code == 200, exported.text
        svg = client.get(exported.json()["url"]).text
        assert 'viewBox="0 0 400 300"' in svg
        assert 'd="M17 23 L97 23 L97 73 L17 73 Z"' in svg
        assert svg.count('fill="#ce744c"') == 1

        millimeters = client.post("/api/illustrations", json={
            "title": "210 by 297 millimeters", "width": 210, "height": 297, "units": "Millimeters"})
        assert millimeters.status_code == 200, millimeters.text
        second = millimeters.json()
        other = cli_info(Path(second["project_file"]))
        assert other["info"]["units"] == "Millimeters"
        assert (other["artboards"][0]["rect"][2], other["artboards"][0]["rect"][3]) == pytest.approx((210 * 72 / 25.4, 297 * 72 / 25.4), rel=1e-6)
        physical_pdf = client.post(f"/api/illustrations/{second['id']}/export", json={"format": "pdf"})
        assert physical_pdf.status_code == 200, physical_pdf.text
        pdf_bytes = client.get(physical_pdf.json()["url"]).content
        media_box = re.search(rb"MediaBox\s*\[\s*0\s+0\s+([0-9.]+)\s+([0-9.]+)", pdf_bytes)
        assert media_box, pdf_bytes[:500]
        assert float(media_box.group(1)) == pytest.approx(210 * 72 / 25.4, abs=0.01)
        assert float(media_box.group(2)) == pytest.approx(297 * 72 / 25.4, abs=0.01)

        default = client.post("/api/illustrations", json={"title": "Native defaults"})
        assert default.status_code == 200, default.text
        fallback = cli_info(Path(default.json()["project_file"]))
        assert fallback["artboards"][0]["rect"] == [0.0, 0.0, 612.0, 792.0]
        assert len(client.get("/api/illustrations").json()) == 3
    sessions.close()


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

    async def delayed(project_id, path, actions, new_document=None):
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
            "name": "illustration_create", "arguments": {"title": "HoardLink contract", "width": 400, "height": 300, "units": "Points"}})
        assert hub_create.status_code == 200, hub_create.text
        assert hub_create.json()["illustration"]["reference"].startswith("hoard://durer/illustration/")
        assert hub_create.json()["illustration"]["canvas"] == {"width": 400.0, "height": 300.0, "width_points": 400.0, "height_points": 300.0, "units": "Points"}
        hub_doc = json.loads(subprocess.check_output([str(CLI), "info", hub_create.json()["illustration"]["project_file"]], text=True))
        assert hub_doc["artboards"][0]["rect"] == [0.0, 0.0, 400.0, 300.0]
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
                create_tool = next(tool for tool in tools if tool.name == "illustration_create")
                assert {"width", "height", "units"}.issubset(create_tool.inputSchema["properties"])
                created = await client.call_tool("illustration_create", {"title": "MCP drawing", "width": 400, "height": 300, "units": "Points"})
                payload = json.loads(created.content[0].text)
                project_id = payload["illustration"]["id"]
                from durer_hoard.store import project_root
                assert payload["illustration"]["canvas"] == {"width": 400, "height": 300, "width_points": 400.0, "height_points": 300.0, "units": "Points"}
                assert json.loads(subprocess.check_output([str(CLI), "info", str(project_root(project_id) / "project.vectorcraft")], text=True))["artboards"][0]["rect"] == [0.0, 0.0, 400.0, 300.0]
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


def test_real_stdio_marks_failures_and_preserves_native_details(isolated):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def exercise():
        env = dict(os.environ)
        env["DURER_DATA_DIR"] = str(isolated)
        env["DURER_VECTORCRAFT_CLI"] = str(CLI)
        params = StdioServerParameters(command=sys.executable, args=["-m", "durer_hoard.mcp_server"], env=env)
        evidence = []
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                created = await client.call_tool("illustration_create", {"title": "MCP failure and recovery verification"})
                assert created.isError is False
                payload = json.loads(created.content[0].text)
                assert created.structuredContent == payload
                project_id = payload["illustration"]["id"]
                cases = [
                    ("unknown_project", "illustration_inspect", {"project_id": "f" * 32}, True),
                    ("unknown_native_tool", "illustration_native_call", {"project_id": project_id, "tool": "does_not_exist", "arguments": {}}, True),
                    ("bad_native_arguments", "illustration_native_call", {"project_id": project_id, "tool": "draw_shape", "arguments": {}}, True),
                    ("undo_without_changes", "vectorcraft_undo", {"project_id": project_id}, True),
                    ("native_success", "illustration_native_call", {"project_id": project_id, "tool": "draw_shape", "arguments": {
                        "shape": "rectangle", "x": 10, "y": 20, "width": 50, "height": 30, "fill": "#123456"}}, False),
                    ("inspect_success", "illustration_inspect", {"project_id": project_id}, False),
                    ("export_success", "illustration_export", {"project_id": project_id, "format": "svg"}, False),
                ]
                for case, tool, arguments, expected in cases:
                    result = await client.call_tool(tool, arguments)
                    body = json.loads(result.content[0].text)
                    assert result.isError is expected, (case, body)
                    assert result.structuredContent == body
                    if case == "bad_native_arguments":
                        assert body["results"][0]["name"] == "draw_shape"
                        assert body["results"][0]["is_error"] is True
                        assert body["results"][0]["result"]["isError"] is True
                        assert body["results"][0]["result"]["content"][0]["text"]
                        assert body["results"][-1]["name"] == "inspect_document"
                    if case == "export_success":
                        assert Path(body["path"]).is_file()
                    evidence.append({"case": case, "outer_is_error": result.isError, "payload": body})
        output = os.environ.get("DURER_MCP_ERROR_EVIDENCE")
        if output:
            directory = Path(output)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "mcp-fixed.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")

    asyncio.run(exercise())


def test_http_and_hoard_wrapper_mark_native_failure_and_recover(isolated):
    from durer_hoard.api import app
    with TestClient(app, base_url="http://127.0.0.1:5222") as client:
        token = (isolated / "mcp-token").read_text(encoding="utf-8").strip()
        headers = {"Authorization": "Bearer " + token}
        created = client.post("/api/agent/call", headers=headers, json={
            "name": "illustration_create", "arguments": {"title": "HTTP error recovery"}})
        assert created.status_code == 200
        project_id = created.json()["illustration"]["id"]
        evidence = []
        for case, url, body in [
            ("ui_actions", f"/api/illustrations/{project_id}/actions", {"actions": [{"name": "draw_shape", "arguments": {}}]}),
            ("agent_native", "/api/agent/illustration_native_call", {"project_id": project_id, "tool": "draw_shape", "arguments": {}}),
            ("hoard_wrapper", "/api/agent/call", {"name": "illustration_native_call", "arguments": {"project_id": project_id, "tool": "draw_shape", "arguments": {}}}),
        ]:
            failed = client.post(url, headers=headers, json=body)
            assert failed.status_code == 502, failed.text
            assert failed.json()["results"][0]["is_error"] is True
            assert failed.json()["results"][0]["result"]["content"][0]["text"]
            evidence.append({"case": case, "http_status": failed.status_code, "payload": failed.json()})
        recovered = client.post("/api/agent/call", headers=headers, json={
            "name": "illustration_native_call", "arguments": {"project_id": project_id, "tool": "draw_shape", "arguments": {
                "shape": "ellipse", "x": 15, "y": 25, "width": 80, "height": 60, "fill": "#345678"}}})
        assert recovered.status_code == 200 and not recovered.json()["results"][0]["is_error"]
        evidence.append({"case": "hoard_recovered", "http_status": recovered.status_code, "payload": recovered.json()})
        output = os.environ.get("DURER_MCP_ERROR_EVIDENCE")
        if output:
            directory = Path(output)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "http-fixed.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")


def test_mcp_export_details_and_timeout_operation_receipt_are_retained(isolated, monkeypatch):
    from durer_hoard import store
    from durer_hoard.mcp_server import call_tool
    from durer_hoard.sessions import sessions
    item = store.create("Failure payload retention")
    native = [{"name": "export", "is_error": True, "result": {"isError": True, "content": [{"type": "text", "text": "native export validation failure"}]}}]
    monkeypatch.setattr(sessions, "execute", lambda *args: native)
    failed = asyncio.run(call_tool("illustration_export", {"project_id": item["id"], "format": "png"}))
    assert failed.isError is True
    assert failed.structuredContent["results"] == native
    message = "VectorCraft operation abcdef exceeded 1s; it may still complete. Check /api/operations/abcdef before retrying."
    def timeout(*args):
        raise TimeoutError(message)
    monkeypatch.setattr(sessions, "execute", timeout)
    pending = asyncio.run(call_tool("illustration_inspect", {"project_id": item["id"]}))
    assert pending.isError is True
    assert pending.structuredContent["error"] == message


def test_real_gallery_cache_does_not_create_editor_processes_and_invalidates(isolated, monkeypatch):
    import io
    from PIL import Image
    from durer_hoard.api import app
    from durer_hoard import store, thumbnails
    from durer_hoard.sessions import sessions
    from durer_hoard.history import execute

    source = isolated.parent / "original.svg"
    source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20"><circle cx="10" cy="10" r="8"/></svg>', encoding="utf-8")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    projects = []
    for index, color in enumerate(("#e02010", "#1050e0", "#10a020")):
        item = store.create(f"Gallery cache fixture {index}", source=source)
        root = store.project_root(item["id"])
        path = root / "project.vectorcraft"
        results = sessions.execute(item["id"], path, [{"name": "draw_shape", "arguments": {
            "shape": "rectangle", "x": 30, "y": 40, "width": 120, "height": 90, "fill": color}}],
            new_document={"width": 720, "height": 480})
        assert not any(row["is_error"] for row in results)
        projects.append((item, path, hashlib.sha256(path.read_bytes()).hexdigest()))
    sessions.close()
    assert _own_native_processes() in ([], None)
    renders = []
    convert = thumbnails._convert
    def observed(snapshot, output):
        # Relative links retain their original document directory.
        assert snapshot.parent == output.parents[2]
        renders.append(str(snapshot))
        convert(snapshot, output)
    monkeypatch.setattr(thumbnails, "_convert", observed)
    evidence = {"projects": 3, "native_processes_before": _own_native_processes()}
    with TestClient(app, base_url="http://127.0.0.1:5222") as client:
        first = []
        for item, path, original_hash in projects:
            response = client.get(f"/api/illustrations/{item['id']}/thumbnail")
            assert response.status_code == 200, response.text
            assert response.headers["x-durer-thumbnail-cache"] == "miss"
            with Image.open(io.BytesIO(response.content)) as image:
                assert max(image.size) == 512
            first.append(response.content)
            assert hashlib.sha256(path.read_bytes()).hexdigest() == original_hash
        assert len(renders) == 3 and len(sessions.sessions) == 0
        evidence["native_processes_after_first"] = _own_native_processes()
        assert evidence["native_processes_after_first"] in ([], None)
        for index, (item, path, original_hash) in enumerate(projects):
            response = client.get(f"/api/illustrations/{item['id']}/thumbnail?t=another-gallery-load")
            assert response.headers["x-durer-thumbnail-cache"] == "hit"
            assert response.content == first[index]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == original_hash
            assert not list(path.parent.glob(".thumbnail-source-*"))
            assert not list((path.parent / "cache").glob("render-*"))
            assert len(list((path.parent / "cache").glob("thumbnail-*.png"))) == 1
            assert Path(item["source"]["path"]).read_bytes() == source.read_bytes()
        assert len(renders) == 3 and len(sessions.sessions) == 0
        evidence["second_gallery_new_renders"] = 0
        evidence["native_processes_after_repeat"] = _own_native_processes()
        item, path, original_hash = projects[0]
        changed = execute(item["id"], path, [{"name": "draw_shape", "arguments": {
            "shape": "ellipse", "x": 250, "y": 100, "width": 100, "height": 100, "fill": "#7d2fc0"}}])
        assert not any(row["is_error"] for row in changed)
        edited_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        response = client.get(f"/api/illustrations/{item['id']}/thumbnail")
        assert response.headers["x-durer-thumbnail-cache"] == "miss" and response.content != first[0]
        assert len(sessions.sessions) == 1 and len(renders) == 4
        assert hashlib.sha256(path.read_bytes()).hexdigest() == edited_hash
        undone = execute(item["id"], path, [{"name": "undo", "arguments": {}}])
        assert not any(row["is_error"] for row in undone)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == original_hash
        undo_thumbnail = client.get(f"/api/illustrations/{item['id']}/thumbnail")
        assert undo_thumbnail.content == first[0]
        evidence["edit_invalidates_and_undo_retained"] = True
        refreshed = client.get(f"/api/illustrations/{item['id']}/thumbnail?refresh=true")
        assert refreshed.headers["x-durer-thumbnail-cache"] == "miss"
        assert refreshed.content == first[0]
        evidence["explicit_refresh"] = True
        # Simulate an external saved-file replacement, without touching metadata.
        shutil.copyfile(projects[1][1], path)
        external_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        external = client.get(f"/api/illustrations/{item['id']}/thumbnail")
        assert external.headers["x-durer-thumbnail-cache"] == "miss"
        assert external.content == first[1]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == external_hash
        evidence["external_saved_file_invalidates"] = True
        assert len(list((path.parent / "cache").glob("thumbnail-*.png"))) <= 2
        assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
        evidence["source_hash_unchanged"] = source_hash
        evidence["first_thumbnail_sha256"] = [hashlib.sha256(data).hexdigest() for data in first]
    evidence["native_processes_after_close"] = _own_native_processes()
    assert evidence["native_processes_after_close"] in ([], None)
    output = os.environ.get("DURER_GALLERY_EVIDENCE")
    if output:
        destination = Path(output)
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "gallery-fixed.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")


def test_transient_thumbnail_converters_are_bounded_and_failures_clean_up(isolated, monkeypatch):
    from durer_hoard import thumbnails
    from PIL import Image
    import threading
    active, peak = 0, 0
    lock = threading.Lock()
    def fake_run(args, **kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.08)
        Image.new("RGB", (30, 20), "red").save(args[-1])
        with lock:
            active -= 1
        return type("Result", (), {"returncode": 0})()
    monkeypatch.setattr(thumbnails.subprocess, "run", fake_run)
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = [pool.submit(thumbnails._convert, isolated / "source", isolated.parent / f"render-{i}.png") for i in range(4)]
        for job in jobs:
            job.result()
    assert peak == 2 and active == 0
    project = isolated.parent / "project.vectorcraft"
    project.write_bytes(b"synthetic native failure fixture")
    def fail(*args):
        raise RuntimeError("Native converter failed")
    monkeypatch.setattr(thumbnails, "_convert", fail)
    with pytest.raises(RuntimeError, match="converter failed"):
        thumbnails.thumbnail(project)
    assert project.read_bytes() == b"synthetic native failure fixture"
    assert not list(project.parent.glob(".thumbnail-source-*"))
    assert not list((project.parent / "cache").glob("render-*"))


def test_real_thumbnail_snapshot_retains_relative_linked_image_context(isolated):
    import io
    from PIL import Image
    from durer_hoard import store
    from durer_hoard.api import app
    from durer_hoard.sessions import sessions
    item = store.create("Relative linked thumbnail")
    root = store.project_root(item["id"])
    asset = root / "sources" / "linked.png"
    Image.new("RGB", (24, 24), (64, 176, 128)).save(asset)
    source = root / "sources" / "source.svg"
    source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><image href="linked.png" x="10" y="10" width="60" height="60"/></svg>', encoding="utf-8")
    project = root / "project.vectorcraft"
    results = sessions.execute(item["id"], project, [{"name": "open_file", "arguments": {"path": str(source)}}])
    assert not any(row["is_error"] for row in results)
    sessions.close()
    saved = json.loads(project.read_text(encoding="utf-8"))
    links = []
    def collect(value):
        if isinstance(value, dict):
            if isinstance(value.get("link"), dict):
                links.append(value["link"])
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)
    collect(saved)
    assert any(link.get("relative") == "sources/linked.png" for link in links)
    before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (project, asset, source)}
    with TestClient(app, base_url="http://127.0.0.1:5222") as client:
        response = client.get(f"/api/illustrations/{item['id']}/thumbnail")
        assert response.status_code == 200, response.text
        with Image.open(io.BytesIO(response.content)) as image:
            assert image.convert("RGB").getpixel((30, 30)) == (64, 176, 128)
        assert not sessions.sessions
    assert before == {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (project, asset, source)}
    assert not list(root.glob(".thumbnail-source-*"))
    assert _own_native_processes() in ([], None)

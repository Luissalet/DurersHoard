import asyncio
import json

import httpx

from durer_hoard import mcp_server, store


def test_running_app_scope_and_uncertain_post_never_reexecute_locally(tmp_path, monkeypatch):
    monkeypatch.setenv("DURER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DURER_URL", "http://127.0.0.1:1")
    (tmp_path / "mcp-token").write_text("private-test-token", encoding="utf8")
    real_client = httpx.AsyncClient
    posts = []
    scope = {"data_dir": str(tmp_path / "other")}

    async def respond(request):
        if request.method == "GET":
            return httpx.Response(200, json={"service": "durers-hoard", **scope})
        posts.append(request)
        assert request.headers["Authorization"] == "Bearer private-test-token"
        raise httpx.ReadTimeout("The sent mutation may have completed", request=request)

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(respond), **kw))
    assert asyncio.run(mcp_server._running_app_call("illustration_list", {})) is None
    assert not posts
    scope["data_dir"] = str(tmp_path)
    monkeypatch.setattr(store, "list_projects", lambda: (_ for _ in ()).throw(AssertionError("Must not retry after POST")))
    result = asyncio.run(mcp_server.call_tool("illustration_list", {}))
    assert result.isError and result.structuredContent["outcome_unknown"]
    assert len(posts) == 1


def test_running_app_native_failure_preserves_result_and_maps_full_tool_name(tmp_path, monkeypatch):
    monkeypatch.setenv("DURER_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DURER_URL", "http://127.0.0.1:1")
    (tmp_path / "mcp-token").write_text("private-test-token", encoding="utf8")
    real_client = httpx.AsyncClient
    failure = {"results": [{"name": "draw_shape", "is_error": True, "result": {"isError": True, "content": [{"type": "text", "text": "Native shape arguments missing"}]}}]}

    async def respond(request):
        if request.method == "GET":
            return httpx.Response(200, json={"service": "durers-hoard", "data_dir": str(tmp_path)})
        assert json.loads(request.content) == {"name": "illustration_native_call", "arguments": {
            "project_id": "a", "tool": "draw_shape", "arguments": {"shape": "ellipse"}}}
        return httpx.Response(502, json=failure)

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(respond), **kw))
    result = asyncio.run(mcp_server.call_tool("vectorcraft_draw_shape", {"project_id": "a", "shape": "ellipse"}))
    assert result.isError and result.structuredContent == failure

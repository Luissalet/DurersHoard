"""The Faustus copilot in Dürer's Hoard: Hoard Link's install_copilot on the FastAPI app, the launcher on its page, the manifest."""
from __future__ import annotations

import importlib
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
PORT = 5222


class FakeFaustus:
    """Capabilities, the panel element and a POST that records what it was sent."""

    def __init__(self):
        self.posts = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def _send(self, body, kind="application/json"):
                self.send_response(200)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/api/hoard-copilot/capabilities":
                    self._send(b'{"contract_version": "1.0"}')
                elif self.path == "/api/hoard-copilot/panel.js":
                    self._send(b"customElements.define('faustus-chat', class extends HTMLElement {});", "application/javascript")
                else:
                    self.send_error(404)

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                owner.posts.append((self.path, self.headers.get("Authorization"), json.loads(body or b"null")))
                self._send(b'{"ok": true}')

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()


@pytest.fixture()
def faustus():
    fake = FakeFaustus()
    yield fake
    fake.close()


def load_api(monkeypatch, tmp_path, faustus, **env):
    monkeypatch.setenv("DURER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DURER_CONFIG", str(tmp_path / "no-config.json"))
    monkeypatch.setenv("DURER_PORT", str(PORT))
    monkeypatch.setenv("HOARD_FAUSTUS_URL", faustus.url)
    monkeypatch.setenv("HOARD_FAUSTUS_TOKEN", "secret-token")
    monkeypatch.delenv("HOARD_COPILOT", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    import durer_hoard.api as api
    return importlib.reload(api)


@pytest.fixture()
def client(monkeypatch, tmp_path, faustus):
    pytest.importorskip("hoard_link.copilot", reason="needs a Hoard Link with the copilot (install_copilot)")
    api = load_api(monkeypatch, tmp_path, faustus)
    assert api.COPILOT_INSTALLED
    with TestClient(api.app, base_url=f"http://127.0.0.1:{PORT}") as test_client:
        yield test_client
    importlib.reload(api)   # leave the module as the environment builds it


def test_info_names_the_app(client, faustus):
    info = client.get("/api/copilot/info").json()
    assert info["app_id"] == "durer" and info["app_name"] == "Dürer's Hoard"
    assert info["panel_url"] == "/api/copilot/panel.js" and info["data_space_id"]
    assert info["settings_url"] == faustus.url + "/studio/settings"


def test_the_page_carries_the_launcher_once_and_the_script_is_served(client):
    page = client.get("/").text
    assert page.count("/api/copilot/launcher.js") == 1
    assert '<script src="/static/copilot.js" defer></script>' in page
    launcher = client.get("/api/copilot/launcher.js")
    assert launcher.status_code == 200 and "hoardCopilot" in launcher.text
    assert client.get("/static/copilot.js").status_code == 200


def test_panel_comes_through_the_relay_and_the_token_stays_on_the_server(client, faustus):
    panel = client.get("/api/copilot/panel.js")
    assert panel.status_code == 200 and "faustus-chat" in panel.text
    assert "secret-token" not in panel.text and "secret-token" not in client.get("/api/copilot/info").text


def test_proxy_forces_the_origin_and_only_reaches_the_copilot_surface(client, faustus):
    envelope = {"path": "/api/hoard-copilot/turn", "method": "POST",
                "body": {"context": {"origin": {"app_id": "someone-else", "data_space_id": "stolen"}}}}
    assert client.post("/api/copilot/proxy", json=envelope).status_code == 200
    path, auth, body = faustus.posts[-1]
    assert (path, auth) == ("/api/hoard-copilot/turn", "Bearer secret-token")
    assert body["context"]["origin"]["app_id"] == "durer"
    assert body["context"]["origin"]["data_space_id"] == client.get("/api/copilot/info").json()["data_space_id"]
    assert client.post("/api/copilot/proxy", json={"path": "/api/admin/keys", "method": "GET"}).status_code == 400


def test_health_says_the_copilot_is_on(client):
    assert client.get("/api/health").json()["copilot"] is True


def test_copilot_off_switch(monkeypatch, tmp_path, faustus):
    pytest.importorskip("hoard_link.copilot")
    api = load_api(monkeypatch, tmp_path, faustus, HOARD_COPILOT="0")
    try:
        with TestClient(api.app, base_url=f"http://127.0.0.1:{PORT}") as test_client:
            assert api.COPILOT_INSTALLED is False
            assert test_client.get("/api/copilot/info").status_code == 404
            assert "copilot/launcher.js" not in test_client.get("/").text
            assert test_client.get("/api/health").json()["copilot"] is False
    finally:
        importlib.reload(api)


def test_app_starts_with_a_hoard_link_that_has_no_copilot(monkeypatch, tmp_path, faustus):
    monkeypatch.setitem(sys.modules, "hoard_link.copilot", None)   # `from hoard_link.copilot import ...` raises ImportError
    api = load_api(monkeypatch, tmp_path, faustus)
    try:
        with TestClient(api.app, base_url=f"http://127.0.0.1:{PORT}") as test_client:
            assert api.COPILOT_INSTALLED is False
            assert test_client.get("/").status_code == 200
            assert test_client.get("/api/copilot/info").status_code == 404
    finally:
        monkeypatch.undo()
        importlib.reload(api)


def test_manifest_declares_the_copilot():
    manifest = json.loads((ROOT / "faustus-plugin.json").read_text(encoding="utf-8"))
    copilot = manifest["x-family"]["copilot"]
    assert copilot["provider"] == "faustus" and copilot["contract"] == "1.0" and copilot["panel"] == "/api/copilot/panel.js"
    assert "active_objects" in copilot["context"]


def test_the_client_script_is_loaded_by_the_page_and_defines_the_hook():
    html = (ROOT / "durer_hoard" / "static" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "durer_hoard" / "static" / "copilot.js").read_text(encoding="utf-8")
    app_js = (ROOT / "durer_hoard" / "static" / "app.js").read_text(encoding="utf-8")
    assert html.index('src="/static/app.js"') < html.index('src="/static/copilot.js"')
    assert "root.hoardCopilot = {" in script and "onTurnEnd" in script
    assert "globalThis.__durerCopilot=" in app_js

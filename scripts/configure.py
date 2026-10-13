from __future__ import annotations

import json
import os
import shutil
import socket
import sys
import tempfile
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def _existing_service(port: int) -> bool:
    try:
        from hoard_link.net import already_running
        return bool(already_running("durers-hoard", port))
    except ImportError:
        try:
            with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.5) as response:
                return json.loads(response.read(65536)).get("service") == "durers-hoard"
        except Exception:
            return False


def _can_bind(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            if sys.platform == "win32" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            probe.bind(("127.0.0.1", port))
            return True
    except OSError:
        return False


def _find_cli(config: dict, explicit: str | None) -> Path:
    # Historical config/arguments are retained, but never select an external engine.
    path = ROOT / "native/bin" / ("durer-cli.exe" if os.name == "nt" else "durer-cli")
    if not path.is_file():
        raise SystemExit("Build the Dürer engine with python scripts/build_engine.py first.")
    return path


def configure(explicit_cli: str | None = None) -> dict:
    config_path = Path(os.environ.get("DURER_CONFIG", ROOT / "local-config.json")).expanduser().resolve()
    try:
        config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not read local config {config_path}: {exc}") from exc
    if not isinstance(config, dict):
        raise SystemExit(f"Local config must contain a JSON object: {config_path}")

    cli = _find_cli(config, explicit_cli)
    configured_port = config.get("port", 5222)
    try:
        configured_port = int(configured_port)
        if not 1 <= configured_port <= 65535:
            raise ValueError
    except (TypeError, ValueError):
        configured_port = 5222
    if _can_bind(configured_port) or _existing_service(configured_port):
        selected = configured_port
    else:
        selected = next((port for port in range(configured_port, min(65536, configured_port + 21)) if _can_bind(port)), None)
        if selected is None:
            raise SystemExit(f"No free loopback port in {configured_port}â€“{min(65535, configured_port + 20)}")

    config["engine"] = "durer"
    config["host"] = "127.0.0.1"
    config["port"] = selected
    if not config.get("data_dir"):
        config["data_dir"] = str(Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local")) / "DurerHoard")

    config_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=config_path.name + ".", suffix=".tmp", dir=config_path.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(config, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
        temp.replace(config_path)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise
    return config


if __name__ == "__main__":
    configured = configure(sys.argv[1] if len(sys.argv) > 1 else None)
    print(json.dumps(configured, ensure_ascii=False, indent=2))

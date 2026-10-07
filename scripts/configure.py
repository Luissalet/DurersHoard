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
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit).expanduser())
    configured = os.environ.get("DURER_VECTORCRAFT_CLI") or config.get("vectorcraft_cli")
    if configured:
        candidates.append(Path(configured).expanduser())
    path_cli = shutil.which("vectorcraft-cli.exe") or shutil.which("vectorcraft-cli")
    if path_cli:
        candidates.append(Path(path_cli))
    bundle_root = os.environ.get("DURER_NATIVE_BUNDLE_DIR")
    search_roots = [Path(bundle_root).expanduser()] if bundle_root else []
    search_roots.extend([ROOT / "native-craft-bundles", ROOT.parent / "native-craft-bundles"])
    for base in search_roots:
        if base.is_dir():
            candidates.append(base / "vectorcraft-cli.exe")
            candidates.extend(base.glob("vectorcraft-*-windows-x64-portable/vectorcraft-cli.exe"))
            candidates.extend(base.glob("*/vectorcraft-cli.exe"))
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved
    raise SystemExit(
        "VectorCraft CLI not found. Pass its path as an argument or set "
        "DURER_VECTORCRAFT_CLI / DURER_NATIVE_BUNDLE_DIR, or add vectorcraft-cli.exe to PATH."
    )


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
            raise SystemExit(f"No free loopback port in {configured_port}–{min(65535, configured_port + 20)}")

    config["vectorcraft_cli"] = str(cli)
    config["host"] = "127.0.0.1"
    config["port"] = selected
    if not config.get("data_dir"):
        config["data_dir"] = str(Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local")) / "DurerHoard")
    configured_gui = config.get("vectorcraft_gui")
    gui = Path(configured_gui).expanduser() if configured_gui else cli.with_name("vectorcraft.exe")
    if gui.resolve().is_file():
        config["vectorcraft_gui"] = str(gui.resolve())
    else:
        config.pop("vectorcraft_gui", None)

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

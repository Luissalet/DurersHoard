"""Direct, lossless bridge to VectorCraft's complete native MCP surface."""
from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import McpError

from .config import settings

_gui_processes: dict[str, tuple[subprocess.Popen, str]] = {}


def failed_results(results: list[dict[str, Any]]) -> bool:
    """Keep native failure flags visible across the outer MCP/HTTP response."""
    return any(row.get("is_error") is True or
               (isinstance(row.get("result"), dict) and row["result"].get("isError") is True)
               for row in results)


def executable() -> Path:
    path = settings().vectorcraft_cli
    if path is None or not path.is_file():
        raise RuntimeError("Configure vectorcraft_cli in local-config.json or DURER_VECTORCRAFT_CLI.")
    return path


def environment() -> dict[str, str]:
    root = settings().data_dir / "native-runtime"
    appdata, localappdata = root / "appdata", root / "localappdata"
    appdata.mkdir(parents=True, exist_ok=True)
    localappdata.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update({"APPDATA": str(appdata), "LOCALAPPDATA": str(localappdata)})
    return env


def serial(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (tuple, list)):
        return [serial(item) for item in value]
    if isinstance(value, dict):
        return {str(key): serial(item) for key, item in value.items()}
    if hasattr(value, "model_dump"):
        return serial(value.model_dump(mode="json"))
    if hasattr(value, "__dict__"):
        return serial(vars(value))
    return str(value)


async def _connect():
    params = StdioServerParameters(command=str(executable()), args=["mcp", "--headless"], env=environment())
    return stdio_client(params)


async def catalog_async() -> dict[str, Any]:
    async with await _connect() as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            tools = serial((await client.list_tools()).tools)
            optional = {}
            for method, key, attr in ((client.list_prompts, "prompts", "prompts"),
                                      (client.list_resources, "resources", "resources"),
                                      (client.list_resource_templates, "resource_templates", "resourceTemplates")):
                try:
                    optional[key] = serial(getattr(await method(), attr, []) or [])
                except McpError as exc:
                    if exc.error.code != -32601:
                        raise
                    optional[key] = []
            return {"executable": str(executable()), "tools": tools, **optional,
                    "commands": command_catalog(), "cli": cli_help()}


def catalog() -> dict[str, Any]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(catalog_async())
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, catalog_async()).result(timeout=180)


async def dispatch_async(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    async with await _connect() as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            for action in actions:
                kind, name = action.get("kind", "tool"), str(action.get("name", ""))
                args = action.get("arguments", {})
                if not name or not isinstance(args, dict):
                    raise ValueError("Each action needs a name and arguments object.")
                if kind == "tool":
                    result = await client.call_tool(name, args)
                    results.append({"kind": kind, "name": name, "is_error": bool(result.isError), "result": serial(result)})
                elif kind == "prompt":
                    results.append({"kind": kind, "name": name, "result": serial(await client.get_prompt(name, args))})
                elif kind == "resource":
                    results.append({"kind": kind, "name": str(args.get("uri", name)),
                                    "result": serial(await client.read_resource(str(args.get("uri", name))))})
                else:
                    raise ValueError("kind must be tool, prompt, or resource")
    return results


def dispatch(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return asyncio.run(dispatch_async(actions))


def launch_gui(project_id: str) -> dict[str, Any]:
    """Start the verified VectorCraft GUI control server and return its MCP address."""
    configured = settings().vectorcraft_gui
    if configured is None or not configured.is_file():
        raise RuntimeError("The sibling vectorcraft.exe GUI is not configured or not present")
    existing = _gui_processes.get(project_id)
    if existing and existing[0].poll() is None:
        return {"executable": str(configured), "pid": existing[0].pid, "address": existing[1], "reused": True}
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = int(probe.getsockname()[1])
    root = settings().data_dir / "native-runtime" / ("gui-" + project_id)
    appdata, localappdata = root / "appdata", root / "localappdata"
    appdata.mkdir(parents=True, exist_ok=True)
    localappdata.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, APPDATA=str(appdata), LOCALAPPDATA=str(localappdata))
    log_path = root / "vectorcraft-gui.log"
    log = log_path.open("ab")
    try:
        process = subprocess.Popen([str(configured), "--control", str(port)], cwd=str(configured.parent),
                                   env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, close_fds=True)
    finally:
        log.close()
    address = f"127.0.0.1:{port}"
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and process.poll() is None:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.25):
                _gui_processes[project_id] = (process, address)
                return {"executable": str(configured), "pid": process.pid, "address": address,
                        "log": str(log_path), "reused": False}
        except OSError:
            time.sleep(0.2)
    if process.poll() is None:
        process.terminate()
    raise RuntimeError(f"VectorCraft GUI control channel did not start. See {log_path}")


def command_catalog() -> list[dict[str, Any]]:
    proc = subprocess.run([str(executable()), "commands"], capture_output=True, timeout=60,
                          env=environment(), check=False)
    if proc.returncode:
        raise RuntimeError(f"VectorCraft command discovery failed: {proc.stderr.decode('utf-8', 'replace')[-1200:]}")
    data = json.loads(proc.stdout.decode("utf-8", "replace"))
    if not isinstance(data, list):
        raise RuntimeError("VectorCraft command catalogue is not an array")
    return data


def cli_help() -> dict[str, Any]:
    proc = subprocess.run([str(executable()), "--help"], capture_output=True, timeout=30,
                          env=environment(), check=False)
    output = "\n".join(part.decode("utf-8", "replace") for part in (proc.stdout, proc.stderr) if part)
    if "vectorcraft-cli" not in output:
        raise RuntimeError(f"VectorCraft CLI help unavailable: {output[-1200:]}")
    return {"executable": str(executable()), "help": output}

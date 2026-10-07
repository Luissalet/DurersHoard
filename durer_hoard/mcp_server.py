"""Faustus MCP server exposing project workflows and the complete VectorCraft catalog."""
from __future__ import annotations

import json
import uuid
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent, Tool

from .native import catalog, failed_results
from .history import execute as history_execute
from .sessions import sessions
from . import store
from .config import settings

server = Server("durer-hoard")


def _text(value: Any, *, is_error: bool = False) -> CallToolResult:
    if isinstance(value, dict):
        is_error = is_error or failed_results(value.get("results", []))
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(value, ensure_ascii=False, default=str))],
        structuredContent=value if isinstance(value, dict) else None,
        isError=is_error,
    )


@server.list_tools()
async def list_tools():
    native = catalog()
    tools = [
        Tool(name="illustration_list", description="List persistent Dürer's Hoard vector projects.", inputSchema={"type": "object", "properties": {}}),
        Tool(name="illustration_create", description="Create an editable VectorCraft project.", inputSchema={"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]}),
        Tool(name="illustration_inspect", description="Inspect a project's native document using VectorCraft.", inputSchema={"type": "object", "properties": {"project_id": {"type": "string"}}, "required": ["project_id"]}),
        Tool(name="illustration_native_call", description="Call any verified native VectorCraft MCP tool in a persistent project session. Discover exact names and schemas from vectorcraft_catalog.", inputSchema={"type": "object", "properties": {"project_id": {"type": "string"}, "tool": {"type": "string"}, "arguments": {"type": "object"}}, "required": ["project_id", "tool", "arguments"]}),
        Tool(name="vectorcraft_catalog", description="Return the full native tool schema, CLI help, and unfiltered command registry.", inputSchema={"type": "object", "properties": {}}),
        Tool(name="illustration_export", description="Export the current native project using VectorCraft's export tool.", inputSchema={"type": "object", "properties": {"project_id": {"type": "string"}, "format": {"type": "string", "enum": ["svg", "png", "pdf", "jpg", "webp"]}}, "required": ["project_id", "format"]}),
    ]
    for item in native.get("tools", []):
        if not isinstance(item, dict) or not item.get("name"):
            continue
        schema = item.get("inputSchema") or {"type": "object", "properties": {}}
        props = dict(schema.get("properties", {}))
        props["project_id"] = {"type": "string", "description": "Persistent Hoard illustration ID"}
        required = list(schema.get("required", [])) + ["project_id"]
        schema = {**schema, "properties": props, "required": required}
        tools.append(Tool(name="vectorcraft_" + item["name"], description=item.get("description", "Native VectorCraft operation."), inputSchema=schema))
    return tools


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]):
    try:
        if name == "vectorcraft_catalog":
            return _text(catalog())
        if name == "illustration_list":
            return _text(store.list_projects())
        if name == "illustration_create":
            item = store.create(str(arguments["title"]))
            root = store.project_root(item["id"])
            result = sessions.execute(item["id"], root / "project.vectorcraft", [])
            return _text({"illustration": store.read(item["id"]), "results": result})
        project_id = str(arguments.get("project_id", ""))
        item = store.read(project_id)
        root = store.project_root(project_id)
        if name == "illustration_inspect":
            result = sessions.execute(project_id, root / "project.vectorcraft", [{"name": "inspect_document", "arguments": {}}])
            return _text({"illustration": item, "results": result})
        if name == "illustration_export":
            fmt = str(arguments["format"])
            target = root / "exports" / f"{project_id}-{uuid.uuid4().hex}.{fmt}"
            result = sessions.execute(project_id, root / "project.vectorcraft", [{"name": "export", "arguments": {"format": fmt, "path": str(target)}}])
            if failed_results(result):
                return _text({"path": str(target), "exists": target.is_file(), "results": result,
                              "error": "VectorCraft reported an export error"}, is_error=True)
            if not target.is_file() or target.stat().st_size == 0:
                return _text({"path": str(target), "exists": False, "results": result,
                              "error": "Native export did not produce a new file"}, is_error=True)
            return _text({"path": str(target), "exists": target.is_file(), "results": result})
        if name == "illustration_native_call":
            tool, args = str(arguments["tool"]), arguments["arguments"]
            catalog_tools = {entry["name"] for entry in catalog().get("tools", [])}
            if tool not in catalog_tools:
                raise ValueError("Tool name is absent from the verified native catalog")
        elif name.startswith("vectorcraft_"):
            tool = name[len("vectorcraft_"):]
            catalog_tools = {entry["name"] for entry in catalog().get("tools", [])}
            if tool not in catalog_tools:
                raise ValueError("Tool name is absent from the verified native catalog")
            args = {key: value for key, value in arguments.items() if key != "project_id"}
        else:
            raise ValueError(f"Unknown Dürer tool: {name}")
        results = history_execute(project_id, root / "project.vectorcraft", [{"name": tool, "arguments": args}])
        return _text({"illustration": store.read(project_id), "results": results})
    except Exception as exc:
        return _text({"error": str(exc)}, is_error=True)


async def main():
    try:
        from hoard_link import family
        from hoard_link.tokens import read_or_create_token
        data_dir = settings().data_dir
        read_or_create_token(data_dir / "mcp-token")
        family.configure("durer", str(data_dir))
    except ImportError:
        pass
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

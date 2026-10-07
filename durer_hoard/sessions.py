"""One persistent native MCP process per project, serialized through a private event loop."""
from __future__ import annotations

import asyncio
from concurrent.futures import TimeoutError as FutureTimeout
import hashlib
import threading
import uuid
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .native import environment, executable, serial

READ_ONLY = {"inspect_document", "inspect_ui", "screenshot", "list_commands"}


class _Session:
    def __init__(self, task: asyncio.Task, queue: asyncio.Queue):
        self.task, self.queue = task, queue


class NativeSessions:
    def __init__(self):
        self.lock = threading.Lock()
        self.loop = None
        self.thread = None
        self.sessions: dict[str, _Session] = {}
        self.connections: dict[str, str] = {}
        self.project_locks: dict[str, asyncio.Lock] = {}
        self.operations: dict[str, dict[str, Any]] = {}

    def _ensure(self):
        with self.lock:
            if self.loop and self.thread and self.thread.is_alive():
                return self.loop
            ready = threading.Event()
            def run_loop():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                self.loop = loop
                ready.set()
                loop.run_forever()
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.close()
            self.thread = threading.Thread(target=run_loop, name="durer-vectorcraft-mcp", daemon=True)
            self.thread.start()
            if not ready.wait(5):
                raise RuntimeError("Could not start VectorCraft session loop")
            return self.loop

    def execute(self, project_id: str, path: Path, actions: list[dict[str, Any]], timeout: int = 180, new_document: dict[str, Any] | None = None):
        loop = self._ensure()
        operation_id = uuid.uuid4().hex
        with self.lock:
            while len(self.operations) >= 256:
                removable = next((key for key, record in self.operations.items()
                                  if record["state"] != "pending"), None)
                if removable is None:
                    break
                self.operations.pop(removable, None)
            self.operations[operation_id] = {
                "operation_id": operation_id, "project_id": project_id,
                "state": "pending", "result": None, "error": None,
            }
        future = asyncio.run_coroutine_threadsafe(self._execute(project_id, path, actions, new_document), loop)
        try:
            result = future.result(timeout=timeout)
            with self.lock:
                self.operations[operation_id].update(state="completed", result=result)
            return result
        except FutureTimeout as exc:
            def reconcile(done):
                try:
                    result = done.result()
                    update = {"state": "completed", "result": result}
                except BaseException as error:
                    update = {"state": "failed", "error": str(error)}
                with self.lock:
                    record = self.operations.get(operation_id)
                    if record:
                        record.update(update)
            future.add_done_callback(reconcile)
            raise TimeoutError(
                f"VectorCraft operation {operation_id} exceeded {timeout}s; it may still complete. "
                f"Check /api/operations/{operation_id} before retrying."
            ) from exc
        except BaseException as exc:
            with self.lock:
                self.operations[operation_id].update(state="failed", error=str(exc))
            raise

    def operation(self, operation_id: str):
        with self.lock:
            record = self.operations.get(operation_id)
            return dict(record) if record else None

    async def _start(self, project_id: str, path: Path, new_document: dict[str, Any] | None = None):
        queue = asyncio.Queue()
        ready = asyncio.get_running_loop().create_future()
        async def worker():
            address = self.connections.get(project_id)
            args = ["mcp", "--connect", address] if address else ["mcp", "--headless"]
            params = StdioServerParameters(command=str(executable()), args=args, env=environment())
            try:
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as client:
                        await client.initialize()
                        if path.exists() and path.stat().st_size:
                            opened = await client.call_tool("open_file", {"path": str(path)})
                            if opened.isError:
                                raise RuntimeError("VectorCraft could not reopen the saved project: " + str(serial(opened)))
                        else:
                            created = await client.call_tool("run_command", {"command": "file.new", "params": dict(new_document or {})})
                            if created.isError:
                                raise RuntimeError("VectorCraft could not create a document: " + str(serial(created)))
                            saved = await client.call_tool("save_file", {"path": str(path)})
                            if saved.isError:
                                raise RuntimeError("VectorCraft could not initialize the native project: " + str(serial(saved)))
                        ready.set_result(True)
                        while True:
                            item = await queue.get()
                            if item is None:
                                return
                            actions, answer = item
                            try:
                                results = []
                                for action in actions:
                                    kind = action.get("kind", "tool")
                                    name = str(action.get("name", ""))
                                    args = action.get("arguments", {})
                                    if kind != "tool" or not name or not isinstance(args, dict):
                                        raise ValueError("Persistent project sessions accept named native tools only")
                                    result = await client.call_tool(name, args)
                                    item_result = {"kind": kind, "name": name, "is_error": bool(result.isError), "result": serial(result)}
                                    results.append(item_result)
                                    if result.isError:
                                        break
                                needs_save = any(
                                    action.get("kind", "tool") == "tool"
                                    and str(action.get("name", "")) not in READ_ONLY
                                    for action in actions
                                )
                                if needs_save and (not results or results[-1].get("name") != "save_file"):
                                    saved = await client.call_tool("save_file", {"path": str(path)})
                                    results.append({"kind": "tool", "name": "save_file", "is_error": bool(saved.isError), "result": serial(saved)})
                                inspect = await client.call_tool("inspect_document", {})
                                results.append({"kind": "tool", "name": "inspect_document", "is_error": bool(inspect.isError), "result": serial(inspect)})
                                answer.set_result(results)
                            except BaseException as exc:
                                if not answer.done():
                                    answer.set_exception(exc)
            except BaseException as exc:
                if not ready.done():
                    ready.set_exception(exc)
        task = asyncio.create_task(worker(), name=f"vectorcraft-{project_id}")
        await ready
        return _Session(task, queue)

    async def _execute(self, project_id, path, actions, new_document=None):
        lock = self.project_locks.setdefault(project_id, asyncio.Lock())
        async with lock:
            session = self.sessions.get(project_id)
            if session is None or session.task.done():
                session = await self._start(project_id, path, new_document)
                self.sessions[project_id] = session
            answer = asyncio.get_running_loop().create_future()
            await session.queue.put((actions, answer))
            return await answer

    def close(self):
        loop, thread = self.loop, self.thread
        if not loop or not thread:
            return
        async def close_all():
            for sid, session in list(self.sessions.items()):
                await session.queue.put(None)
                await asyncio.gather(session.task, return_exceptions=True)
                self.sessions.pop(sid, None)
        asyncio.run_coroutine_threadsafe(close_all(), loop).result(timeout=20)
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)
        self.loop = self.thread = None

    def reset(self, project_id: str):
        loop, thread = self.loop, self.thread
        if not loop or not thread or not thread.is_alive():
            return
        async def stop_one():
            session = self.sessions.pop(project_id, None)
            if session:
                await session.queue.put(None)
                await asyncio.gather(session.task, return_exceptions=True)
        asyncio.run_coroutine_threadsafe(stop_one(), loop).result(timeout=20)

    def connect(self, project_id: str, address: str):
        self.reset(project_id)
        self.connections[project_id] = address


sessions = NativeSessions()

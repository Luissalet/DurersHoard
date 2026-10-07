"""Durable file snapshots around native actions, with native undo/redo while sessions are live."""
from __future__ import annotations

import hashlib
import json
import shutil
import threading
import time
from pathlib import Path

from .sessions import sessions
from . import store

READ_ONLY = {"inspect_document", "inspect_ui", "screenshot", "list_commands"}
_locks: dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


def _snapshot_name(label: str) -> str:
    return f"{time.time_ns()}-{label}.vectorcraft"


def _save(path: Path, data: dict) -> None:
    store.write_json_atomic(path, data)


def execute(project_id: str, project_path: Path, actions: list[dict]):
    with _locks_guard:
        lock = _locks.setdefault(project_id, threading.RLock())
    with lock:
        return _execute(project_id, project_path, actions)


def _execute(project_id: str, project_path: Path, actions: list[dict]):
    manifest_path = store.manifest_path(project_id)
    metadata = json.loads(manifest_path.read_text(encoding="utf-8"))
    history = metadata.setdefault("history", {"undo": [], "redo": []})
    history.setdefault("undo", [])
    history.setdefault("redo", [])
    snapshots = store.project_root(project_id) / "snapshots"
    snapshots.mkdir(exist_ok=True)
    before_hash = _hash(project_path)
    action_names = [str(action.get("name", "")) for action in actions]

    if len(actions) == 1 and action_names[0] in {"undo", "redo"}:
        direction = action_names[0]
        source, target = ((history["undo"], history["redo"]) if direction == "undo"
                          else (history["redo"], history["undo"]))
        if not source:
            return [{"kind": "tool", "name": direction, "is_error": True,
                     "result": {"error": "No saved changes available to " + direction}}]
        prior_snapshot = source[-1]
        inverse_name = _snapshot_name(direction)
        if before_hash:
            shutil.copyfile(project_path, snapshots / inverse_name)
        native = sessions.execute(project_id, project_path, actions)
        after_hash = _hash(project_path)
        expected_hash = _hash(snapshots / prior_snapshot)
        engine_failed = any(row.get("name") == direction and row.get("is_error") for row in native)
        if not after_hash or after_hash != expected_hash or engine_failed:
            # Reopen the previous durable document when the engine has no in-memory history.
            shutil.copyfile(snapshots / prior_snapshot, project_path)
            sessions.reset(project_id)
            source.pop()
            for row in native:
                if row.get("name") == direction:
                    row["is_error"] = False
                    row["result"] = {"snapshot_fallback": True, "project_file": str(project_path)}
            reopened = sessions.execute(project_id, project_path, [{"name": "inspect_document", "arguments": {}}])
            native = [row for row in native if row.get("name") != "inspect_document"] + reopened
        else:
            source.pop()
        target.append(inverse_name)
        metadata["updated_at"] = store._now()
        _save(manifest_path, metadata)
        return native

    mutating = any(name not in READ_ONLY for name in action_names)
    pre_name = _snapshot_name("before")
    if mutating and before_hash:
        shutil.copyfile(project_path, snapshots / pre_name)
    native = sessions.execute(project_id, project_path, actions)
    after_hash = _hash(project_path)
    if mutating and before_hash and after_hash and before_hash != after_hash:
        history["undo"].append(pre_name)
        history["undo"] = history["undo"][-100:]
        history["redo"] = []
    metadata["updated_at"] = store._now()
    _save(manifest_path, metadata)
    return native

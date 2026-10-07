"""Reusable gallery thumbnails without populating persistent editor sessions."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path

from PIL import Image

from .native import environment, executable
from .store import write_json_atomic

# Gallery traffic gets two transient converters, independently of live editors.
_renders = threading.BoundedSemaphore(2)
_locks = tuple(threading.Lock() for _ in range(32))


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _convert(source: Path, destination: Path) -> None:
    # convert opens a disposable snapshot and exports, never saves the project.
    with _renders:
        result = subprocess.run([str(executable()), "convert", str(source), str(destination)],
                                env=environment(), capture_output=True, timeout=120, check=False)
    if result.returncode:
        message = (result.stderr or result.stdout).decode("utf-8", "replace")[-2000:]
        raise RuntimeError(f"Native thumbnail conversion failed: {message}")
    if not destination.is_file() or not destination.stat().st_size:
        raise RuntimeError("Native thumbnail conversion produced no PNG")


def thumbnail(project: Path, *, refresh: bool = False) -> tuple[Path, bool]:
    """Cache a 512px saved-document thumbnail; return path and cache-hit flag.

    SHA-256 detects external file changes regardless of manifest timestamps.
    Live editor previews remain separate so their native undo/state is untouched.
    """
    if not project.is_file() or not project.stat().st_size:
        raise FileNotFoundError("Native project is not saved")
    cache = project.parent / "cache"
    cache.mkdir(exist_ok=True)
    record_path = cache / "thumbnail.json"
    cli = executable()
    stat = cli.stat()
    engine = [str(cli), stat.st_size, stat.st_mtime_ns]
    with _locks[hash(str(project.resolve())) % len(_locks)]:
        source_hash = _sha(project)
        record = {}
        if record_path.exists():
            try:
                record = json.loads(record_path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                pass
        filename = record.get("file", "") if isinstance(record, dict) else ""
        cached = cache / filename if isinstance(filename, str) else cache
        if (not refresh and isinstance(record, dict) and record.get("source_sha256") == source_hash
                and record.get("engine") == engine and isinstance(filename, str)
                and Path(filename).name == filename and filename.startswith("thumbnail-")
                and cached.is_file() and cached.stat().st_size):
            return cached, True
        # Snapshot first. Never expose the real project file to a preview converter.
        with tempfile.TemporaryDirectory(prefix="render-", dir=cache) as staging:
            stage = Path(staging)
            # Keep the snapshot beside its original so relative linked assets
            # resolve against the same directory. The source file stays read-only.
            with tempfile.NamedTemporaryFile(prefix=".thumbnail-source-", suffix=".vectorcraft", dir=project.parent, delete=False) as stream:
                snapshot = Path(stream.name)
            try:
                shutil.copyfile(project, snapshot)
                snapshot_hash = _sha(snapshot)
                rendered = stage / "render.png"
                _convert(snapshot, rendered)
                with Image.open(rendered) as image:
                    image.load()
                    image.thumbnail((512, 512), Image.Resampling.LANCZOS)
                    output_name = "thumbnail-" + uuid.uuid4().hex + ".png"
                    staged_thumbnail = stage / output_name
                    image.save(staged_thumbnail, format="PNG")
                target = cache / output_name
                staged_thumbnail.replace(target)
                write_json_atomic(record_path, {"source_sha256": snapshot_hash, "engine": engine,
                                               "file": output_name, "png_sha256": _sha(target), "max_side": 512})
            finally:
                snapshot.unlink(missing_ok=True)
        # Immutable names allow FileResponse readers to finish during refresh.
        # Keep current and previous frames; a busy Windows reader is pruned later.
        old = sorted(cache.glob("thumbnail-*.png"), key=lambda p: p.stat().st_mtime_ns, reverse=True)
        for obsolete in old[2:]:
            try:
                obsolete.unlink()
            except OSError:
                pass
        return target, False

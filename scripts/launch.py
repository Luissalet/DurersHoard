from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from durer_hoard.config import settings
from hoard_link.net import already_running, find_available_port, open_in_browser, wait_healthy


def main() -> int:
    configured = settings()
    preferred = int(os.environ.get("DURER_PORT", configured.port))
    if already_running("durers-hoard", preferred):
        open_in_browser(f"http://127.0.0.1:{preferred}")
        return 0
    port = find_available_port(preferred, span=20)
    env = dict(os.environ, DURER_HOST="127.0.0.1", DURER_PORT=str(port), DURER_DATA_DIR=str(configured.data_dir))
    url = f"http://127.0.0.1:{port}"
    child = subprocess.Popen([sys.executable, "-m", "durer_hoard"], cwd=ROOT, env=env)
    if not wait_healthy(url, "durers-hoard", timeout=30):
        child.terminate()
        print(f"Dürer's Hoard did not become ready at {url}.", file=sys.stderr)
        return 1
    if not open_in_browser(url):
        print(f"Open {url} in your browser.")
    else:
        print(f"Dürer's Hoard is ready at {url}.")
    try:
        return child.wait()
    except KeyboardInterrupt:
        child.terminate()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

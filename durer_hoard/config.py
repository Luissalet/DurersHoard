from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    vectorcraft_cli: Path | None
    vectorcraft_gui: Path | None
    host: str = "127.0.0.1"
    port: int = 5222


def settings() -> Settings:
    config_path = Path(os.environ.get("DURER_CONFIG", ROOT / "local-config.json"))
    data: dict = {}
    if config_path.exists():
        data = json.loads(config_path.read_text(encoding="utf-8"))
    data_dir = Path(os.environ.get("DURER_DATA_DIR", data.get("data_dir", ROOT / "data"))).expanduser().resolve()
    cli = os.environ.get("DURER_VECTORCRAFT_CLI", data.get("vectorcraft_cli"))
    gui = os.environ.get("DURER_VECTORCRAFT_GUI", data.get("vectorcraft_gui"))
    if not gui and cli:
        sibling = Path(cli).expanduser().resolve().with_name("vectorcraft.exe")
        gui = str(sibling) if sibling.is_file() else None
    return Settings(data_dir=data_dir, vectorcraft_cli=Path(cli).expanduser().resolve() if cli else None,
                    vectorcraft_gui=Path(gui).expanduser().resolve() if gui else None,
                    host=os.environ.get("DURER_HOST", "127.0.0.1"),
                    port=int(os.environ.get("DURER_PORT", data.get("port", 5222))))

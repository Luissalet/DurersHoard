from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
CONFIGURE = ROOT / "scripts" / "configure.py"
def _fake_cli(tmp_path: Path) -> Path:
    bundle = tmp_path / "portable-engine"
    bundle.mkdir(exist_ok=True)
    cli = bundle / "vectorcraft-cli.exe"
    cli.write_bytes(b"test fixture only; never executed")
    cli.with_name("vectorcraft.exe").write_bytes(b"test fixture only; never executed")
    return cli


def _load_configure():
    spec = importlib.util.spec_from_file_location("durer_configure", CONFIGURE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_configure_is_idempotent_and_preserves_local_paths_and_running_port(tmp_path, monkeypatch):
    module = _load_configure()
    cli = _fake_cli(tmp_path)
    config_path = tmp_path / "isolated-local-config.json"
    data_dir = tmp_path / "existing-artifact-store"
    original = {
        "vectorcraft_cli": str(cli),
        "vectorcraft_gui": str(cli.with_name("vectorcraft.exe")),
        "data_dir": str(data_dir),
        "port": 5222,
        "host": "0.0.0.0",
        "other_user_setting": {"keep": True},
    }
    config_path.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setenv("DURER_CONFIG", str(config_path))
    monkeypatch.delenv("DURER_VECTORCRAFT_CLI", raising=False)
    monkeypatch.setattr(module, "_can_bind", lambda port: False)
    monkeypatch.setattr(module, "_existing_service", lambda port: port == 5222)

    first = module.configure()
    second = module.configure()

    assert first == second
    assert second["port"] == 5222
    assert second["host"] == "127.0.0.1"
    assert second["data_dir"] == str(data_dir)
    assert second["vectorcraft_cli"] == str(cli.resolve())
    assert second["vectorcraft_gui"] == str(cli.with_name("vectorcraft.exe").resolve())
    assert second["other_user_setting"] == {"keep": True}
    assert not data_dir.exists()
    assert json.loads(config_path.read_text(encoding="utf-8")) == second
    assert not list(tmp_path.glob("*.tmp"))


def test_explicit_cli_path_overrides_local_configuration_without_absolute_product_paths(tmp_path, monkeypatch):
    module = _load_configure()
    cli = _fake_cli(tmp_path)
    config_path = tmp_path / "explicit-cli-config.json"
    config_path.write_text(json.dumps({"data_dir": str(tmp_path / "data"), "port": 5000}), encoding="utf-8")
    monkeypatch.setenv("DURER_CONFIG", str(config_path))
    monkeypatch.delenv("DURER_VECTORCRAFT_CLI", raising=False)
    monkeypatch.setattr(module, "_can_bind", lambda port: True)
    monkeypatch.setattr(module, "_existing_service", lambda port: False)

    result = module.configure(str(cli))

    assert result["vectorcraft_cli"] == str(cli.resolve())
    assert result["port"] == 5000
    product_sources = (CONFIGURE.read_text(encoding="utf-8") +
                       (ROOT / "scripts" / "setup.ps1").read_text(encoding="utf-8"))
    assert "LocalAI" not in product_sources and "luism" not in product_sources


def test_configure_command_is_idempotent_with_an_isolated_config(tmp_path):
    cli = _fake_cli(tmp_path)
    config_path = tmp_path / "cli-local-config.json"
    isolated_data = tmp_path / "keep-this-data"
    config_path.write_text(json.dumps({
        "vectorcraft_cli": str(cli), "data_dir": str(isolated_data), "port": 5222,
        "custom_setting": "preserved",
    }), encoding="utf-8")
    env = dict(os.environ, DURER_CONFIG=str(config_path))
    env.pop("DURER_VECTORCRAFT_CLI", None)
    env.pop("DURER_NATIVE_BUNDLE_DIR", None)

    outputs = []
    for _ in range(2):
        result = subprocess.run([sys.executable, str(CONFIGURE)], env=env,
                                capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stderr
        outputs.append(json.loads(result.stdout))

    assert outputs[0] == outputs[1]
    assert outputs[1]["port"] == 5222
    assert outputs[1]["data_dir"] == str(isolated_data)
    assert outputs[1]["custom_setting"] == "preserved"
    assert not isolated_data.exists()

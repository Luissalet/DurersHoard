"""Build and install this repository's own engine and desktop editor."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    command = ["cargo", "+1.95.0", "build", "--locked", "-p", "durer-cli", "-p", "durer"]
    if not args.debug:
        command.append("--release")
    subprocess.run(command, cwd=ROOT / "native", check=True)
    profile = "debug" if args.debug else "release"
    source = Path(os.environ.get("CARGO_TARGET_DIR", ROOT / "native/target")) / profile
    target = ROOT / "native/bin"
    target.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in ("durer-cli", "durer"):
        filename = name + (".exe" if os.name == "nt" else "")
        destination = target / filename
        shutil.copyfile(source / filename, destination)
        rows.append({"file": filename, "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()})
    (target / "build.json").write_text(json.dumps({"profile": profile, "source": "native", "binaries": rows}, indent=2), encoding="utf-8")
    print(json.dumps(rows))

if __name__ == "__main__":
    main()

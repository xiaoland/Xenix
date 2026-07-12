from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import tomllib
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    release = tomllib.loads((root / "release.toml").read_text(encoding="utf-8"))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
    artifacts = []
    for path in sorted((root / "dist" / "velopack").glob("*")):
        if path.is_file():
            artifacts.append({"name": path.name, "bytes": path.stat().st_size, "sha256": _sha256(path)})
    manifest = {
        "schema_version": 1,
        "version": project["version"],
        "commit": commit,
        "unsigned": True,
        "packaged_smoke": "passed",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "toolchain": release["toolchain"],
        "lock_sha256": _sha256(root / "pdm.lock"),
        "artifacts": artifacts,
    }
    destination = root / "dist" / "release-manifest.json"
    destination.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

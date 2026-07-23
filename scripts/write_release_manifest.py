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
            artifact_type = "update_feed" if path.name in {
                "assets.win-x64-stable.json",
                "releases.win-x64-stable.json",
                "RELEASES-win-x64-stable",
            } else "desktop_release"
            artifacts.append(
                {
                    "type": artifact_type,
                    "path": f"velopack/{path.name}",
                    "name": path.name,
                    "bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )
    catalog_path = root / "dist" / "knowledge-ocr" / "runtime_catalog.json"
    if not catalog_path.is_file():
        raise RuntimeError("Knowledge OCR runtime catalog is missing from the candidate.")
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(catalog, dict) or catalog.keys() != {
        "schema_version",
        "artifact_name",
        "artifact_bytes",
        "artifact_sha256",
        "protocol_version",
        "runtime_id",
        "model_pack_id",
    }:
        raise RuntimeError("Knowledge OCR runtime catalog shape is invalid.")
    artifact_name = str(catalog.get("artifact_name") or "")
    if Path(artifact_name).name != artifact_name or artifact_name in {"", ".", ".."}:
        raise RuntimeError("Knowledge OCR runtime artifact name is unsafe.")
    ocr_archive = catalog_path.parent / artifact_name
    if (
        not ocr_archive.is_file()
        or ocr_archive.stat().st_size != catalog.get("artifact_bytes")
        or _sha256(ocr_archive) != catalog.get("artifact_sha256")
    ):
        raise RuntimeError("Knowledge OCR runtime artifact does not match its catalog.")
    artifacts.append(
        {
            "type": "knowledge_ocr_runtime",
            "path": f"knowledge-ocr/{ocr_archive.name}",
            "name": ocr_archive.name,
            "bytes": ocr_archive.stat().st_size,
            "sha256": _sha256(ocr_archive),
        }
    )
    manifest = {
        "schema_version": 2,
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

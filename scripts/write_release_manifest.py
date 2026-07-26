from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import tomllib
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _optional_positive_int(name: str) -> int | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    value = int(raw)
    if value < 1:
        raise RuntimeError(f"{name} must be a positive integer.")
    return value


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    release = tomllib.loads((root / "release.toml").read_text(encoding="utf-8"))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
    configured_commit = os.environ.get("XENIX_BUILD_COMMIT", "").strip().lower()
    if configured_commit and configured_commit != commit:
        raise RuntimeError(
            "Release manifest commit does not match the packaged build commit."
        )
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
        raise RuntimeError("Knowledge OCR runtime catalog is missing from the release.")
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
    tag = os.environ.get("XENIX_RELEASE_TAG", "").strip() or None
    promotion_pr = _optional_positive_int("XENIX_PROMOTION_PR")
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip() or None
    run_id = _optional_positive_int("GITHUB_RUN_ID")
    run_attempt = _optional_positive_int("GITHUB_RUN_ATTEMPT")
    if os.environ.get("XENIX_PUBLIC_RELEASE_BUILD") == "1":
        expected_tag = f"v{project['version']}"
        if tag != expected_tag or promotion_pr is None or repository is None:
            raise RuntimeError(
                "Public release manifest requires the exact release tag, "
                "promotion PR, and GitHub repository identity."
            )
        if run_id is None or run_attempt is None:
            raise RuntimeError(
                "Public release manifest requires GitHub workflow run identity."
            )
    manifest = {
        "schema_version": 3,
        "version": project["version"],
        "commit": commit,
        "release": {
            "protocol_version": release["release"]["protocol_version"],
            "tag": tag,
            "promotion_pr": promotion_pr,
        },
        "workflow": {
            "repository": repository,
            "run_id": run_id,
            "run_attempt": run_attempt,
        },
        "unsigned": True,
        "packaged_smoke": "passed",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "toolchain": release["toolchain"],
        "release_toml_sha256": _sha256(root / "release.toml"),
        "lock_sha256": _sha256(root / "pdm.lock"),
        "artifacts": artifacts,
    }
    destination = root / "dist" / "release-manifest.json"
    destination.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

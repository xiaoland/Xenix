from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, TypedDict


class ArtifactIndexEntry(TypedDict):
    path: str
    reason: str
    scenario_id: str | None
    policy: str
    render_environment: dict[str, object]
    root_geometry: dict[str, object]
    files: list[dict[str, object]]


class ArtifactIndex(TypedDict):
    schema_version: int
    artifact_count: int
    artifacts: list[ArtifactIndexEntry]


def build_artifact_index(root: Path) -> ArtifactIndex:
    root.mkdir(parents=True, exist_ok=True)
    artifacts: list[ArtifactIndexEntry] = []
    for manifest_path in sorted(root.rglob("manifest.json")):
        manifest = _read_object(manifest_path)
        artifacts.append(
            {
                "path": manifest_path.parent.relative_to(root).as_posix(),
                "reason": _string_value(manifest.get("reason")),
                "scenario_id": _optional_string_value(manifest.get("scenario_id")),
                "policy": _string_value(manifest.get("policy")),
                "render_environment": _object_value(manifest.get("render_environment")),
                "root_geometry": _object_value(manifest.get("root_geometry")),
                "files": _object_list_value(manifest.get("files")),
            }
        )
    index: ArtifactIndex = {
        "schema_version": 1,
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }
    (root / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return index


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"UI artifact manifest is not an object: {path}")
    return value


def _string_value(value: object) -> str:
    return value if isinstance(value, str) else ""


def _optional_string_value(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _object_value(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def _object_list_value(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a bounded UI artifact inventory")
    parser.add_argument("--root", type=Path, required=True, help="Allowlisted UI artifact root")
    args = parser.parse_args()
    index = build_artifact_index(args.root.resolve())
    print(json.dumps(index, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

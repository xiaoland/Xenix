from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_script(name: str):
    path = Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"xenix_{name}_for_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


package_velopack = _load_script("package_velopack")
publish_candidate = _load_script("publish_oss_candidate")


def test_package_assets_drop_deleted_portable(tmp_path: Path) -> None:
    setup_name = "xenix-Setup.exe"
    full_name = "xenix-full.nupkg"
    (tmp_path / setup_name).write_bytes(b"setup")
    (tmp_path / full_name).write_bytes(b"full")
    assets_path = tmp_path / "assets.win-x64-stable.json"
    assets_path.write_text(
        json.dumps(
            [
                {"RelativeFileName": setup_name, "Type": "Installer"},
                {"RelativeFileName": full_name, "Type": "Full"},
                {"RelativeFileName": "xenix-Portable.zip", "Type": "Portable"},
            ]
        ),
        encoding="utf-8",
    )

    package_velopack.prune_missing_assets(tmp_path)

    assert json.loads(assets_path.read_text(encoding="utf-8")) == [
        {"RelativeFileName": setup_name, "Type": "Installer"},
        {"RelativeFileName": full_name, "Type": "Full"},
    ]


def test_public_assets_project_from_manifest_artifacts() -> None:
    candidate = json.dumps(
        [
            {"RelativeFileName": "xenix-Setup.exe", "Type": "Installer"},
            {"RelativeFileName": "xenix-full.nupkg", "Type": "Full"},
            {"RelativeFileName": "xenix-Portable.zip", "Type": "Portable"},
        ],
        separators=(",", ":"),
    ).encode("utf-8")

    projected = publish_candidate.public_feed_data(
        "assets.win-x64-stable.json",
        candidate,
        {"assets.win-x64-stable.json", "xenix-Setup.exe", "xenix-full.nupkg"},
    )

    assert json.loads(projected) == [
        {"RelativeFileName": "xenix-Setup.exe", "Type": "Installer"},
        {"RelativeFileName": "xenix-full.nupkg", "Type": "Full"},
    ]

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tomllib
from pathlib import Path


def prune_missing_assets(output: Path) -> None:
    artifact_names = {path.name for path in output.iterdir() if path.is_file()}
    for assets_path in output.glob("assets.*.json"):
        assets = json.loads(assets_path.read_text(encoding="utf-8"))
        retained = [
            asset
            for asset in assets
            if str(asset.get("RelativeFileName") or "") in artifact_names
        ]
        assets_path.write_text(
            json.dumps(retained, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )


def _resolve_build_epoch(project_root: Path) -> int:
    raw = os.environ.get("SOURCE_DATE_EPOCH", "").strip()
    if raw.isdigit():
        return int(raw)
    result = subprocess.run(
        ["git", "show", "-s", "--format=%ct", "HEAD"],
        check=True,
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    value = result.stdout.strip()
    if not value.isdigit():
        raise RuntimeError(f"Resolved build timestamp is not a Unix epoch: {value!r}.")
    return int(value)


def _normalize_mtimes(directory: Path, epoch: int) -> None:
    for path in directory.rglob("*"):
        if path.is_file():
            os.utime(path, (epoch, epoch))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    release = tomllib.loads((root / "release.toml").read_text(encoding="utf-8"))
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    app = release["application"]
    source = root / "dist" / "xenix"
    if not (source / app["main_exe"]).is_file():
        raise RuntimeError("Run 'pdm run package' and 'pdm run smoke-package' first.")
    staging = root / "build" / "velopack-staging"
    output = root / "dist" / "velopack"
    shutil.rmtree(staging, ignore_errors=True)
    shutil.rmtree(output, ignore_errors=True)
    shutil.copytree(source, staging)
    output.mkdir(parents=True)
    command = [
        "dotnet", "tool", "run", "vpk", "--", "pack",
        "--packId", app["pack_id"],
        "--packVersion", project["version"],
        "--packDir", str(staging),
        "--mainExe", app["main_exe"],
        "--packTitle", app["title"],
        "--packAuthors", app["authors"],
        "--channel", app["channel"],
        "--runtime", app["runtime"],
        "--icon", str(root / "logo.ico"),
        "--outputDir", str(output),
    ]
    epoch = _resolve_build_epoch(root)
    _normalize_mtimes(staging, epoch)
    env = dict(os.environ)
    env["SOURCE_DATE_EPOCH"] = str(epoch)
    subprocess.run(command, cwd=root, check=True, env=env)
    for portable in output.glob("*-Portable.*"):
        portable.unlink()
    prune_missing_assets(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

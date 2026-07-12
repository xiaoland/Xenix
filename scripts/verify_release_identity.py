from __future__ import annotations

import argparse
import subprocess
import tomllib
from pathlib import Path


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


def verify(root: Path, *, require_tag: bool) -> tuple[str, str]:
    version = str(tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"])
    commit = _git(root, "rev-parse", "HEAD")
    if require_tag:
        expected = f"v{version}"
        tags = _git(root, "tag", "--points-at", "HEAD").splitlines()
        if tags != [expected]:
            raise RuntimeError(f"Release commit must have exactly tag {expected!r}; found {tags!r}.")
    print(f"version={version}")
    print(f"commit={commit}")
    return version, commit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-tag", action="store_true")
    args = parser.parse_args()
    verify(Path(__file__).resolve().parents[1], require_tag=args.require_tag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

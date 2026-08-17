from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


RELEASE_PROTOCOL_VERSION = 1
_REPOSITORY_PATTERN = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class ReleaseIdentity:
    version: str
    tag: str
    commit: str
    promotion_pr: int | None
    protocol_version: int


def _run(
    command: list[str],
    *,
    cwd: Path,
) -> str:
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _git(root: Path, *args: str) -> str:
    return _run(["git", *args], cwd=root)


def _release_configuration(root: Path) -> tuple[str, int]:
    project = tomllib.loads(
        (root / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]
    version = str(project["version"])
    release = tomllib.loads((root / "release.toml").read_text(encoding="utf-8"))
    protocol_version = release.get("release", {}).get("protocol_version")
    if protocol_version != RELEASE_PROTOCOL_VERSION:
        raise RuntimeError(
            "Release protocol is unsupported: "
            f"expected {RELEASE_PROTOCOL_VERSION}, found {protocol_version!r}."
        )
    release_python = release.get("toolchain", {}).get("python")
    project_python = project.get("requires-python")
    if project_python != f"=={release_python}":
        raise RuntimeError(
            "Release Python toolchain must exactly match project requires-python: "
            f"release.toml declares {release_python!r}, "
            f"pyproject.toml declares {project_python!r}."
        )
    return version, protocol_version


def _exact_release_tag(root: Path, *, commit: str, version: str) -> str:
    expected = f"v{version}"
    tags = sorted(
        tag
        for tag in _git(root, "tag", "--points-at", commit).splitlines()
        if tag
    )
    if tags != [expected]:
        raise RuntimeError(
            f"Release commit must have exactly tag {expected!r}; found {tags!r}."
        )
    return expected


def _require_main_first_parent(root: Path, *, commit: str, main_ref: str) -> None:
    first_parent = {
        value
        for value in _git(root, "rev-list", "--first-parent", main_ref).splitlines()
        if value
    }
    if commit not in first_parent:
        raise RuntimeError(
            f"Release commit {commit} was not a completed state on {main_ref}."
        )


def _associated_pull_requests(
    root: Path,
    *,
    repository: str,
    commit: str,
) -> list[dict[str, Any]]:
    # Best-effort promotion provenance: never blocks the release.
    #
    # The commits/{sha}/pulls endpoint does not reliably associate a merge
    # commit with its promotion PR, and the search index is itself
    # eventually-consistent. This lookup only records the promotion PR number
    # for the release manifest; the hard promotion gate is
    # _require_main_first_parent. Any failure therefore resolves to no
    # provenance instead of an error.
    if not _REPOSITORY_PATTERN.fullmatch(repository) or not _COMMIT_PATTERN.fullmatch(commit):
        return []
    try:
        search_payload = _run(
            ["gh", "api", f"search/issues?q=repo:{repository}+type:pr+sha:{commit}"],
            cwd=root,
        )
        search_value = json.loads(search_payload)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError):
        return []
    if not isinstance(search_value, dict):
        return []
    items = search_value.get("items", [])
    if not isinstance(items, list):
        return []
    records: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        number = item.get("number")
        if type(number) is not int or number <= 0:
            continue
        try:
            record_payload = _run(
                ["gh", "api", f"repos/{repository}/pulls/{number}"],
                cwd=root,
            )
            record = json.loads(record_payload)
        except (OSError, subprocess.CalledProcessError, json.JSONDecodeError):
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def _promotion_pr_number(
    records: list[dict[str, Any]],
    *,
    repository: str,
    commit: str,
) -> int | None:
    matches: list[int] = []
    for record in records:
        head = record.get("head")
        base = record.get("base")
        if not isinstance(head, dict) or not isinstance(base, dict):
            continue
        head_repository = head.get("repo")
        base_repository = base.get("repo")
        number = record.get("number")
        if (
            record.get("merged_at")
            and record.get("merge_commit_sha") == commit
            and head.get("ref") == "develop"
            and isinstance(head_repository, dict)
            and head_repository.get("full_name") == repository
            and base.get("ref") == "main"
            and isinstance(base_repository, dict)
            and base_repository.get("full_name") == repository
            and type(number) is int
            and number > 0
        ):
            matches.append(number)
    return matches[0] if len(matches) == 1 else None


def verify(
    root: Path,
    *,
    require_tag: bool,
    require_promotion: bool = False,
    main_ref: str = "origin/main",
    repository: str | None = None,
) -> ReleaseIdentity:
    version, protocol_version = _release_configuration(root)
    commit = _git(root, "rev-parse", "HEAD")
    if not _COMMIT_PATTERN.fullmatch(commit):
        raise RuntimeError(f"Invalid release commit identity: {commit!r}.")
    if require_promotion:
        require_tag = True
    tag = _exact_release_tag(root, commit=commit, version=version) if require_tag else ""
    promotion_pr: int | None = None
    if require_promotion:
        selected_repository = (repository or os.environ.get("GITHUB_REPOSITORY", "")).strip()
        _require_main_first_parent(root, commit=commit, main_ref=main_ref)
        promotion_pr = _promotion_pr_number(
            _associated_pull_requests(
                root,
                repository=selected_repository,
                commit=commit,
            ),
            repository=selected_repository,
            commit=commit,
        )
    identity = ReleaseIdentity(
        version=version,
        tag=tag,
        commit=commit,
        promotion_pr=promotion_pr,
        protocol_version=protocol_version,
    )
    print(f"version={identity.version}")
    print(f"tag={identity.tag}")
    print(f"commit={identity.commit}")
    print(f"promotion_pr={identity.promotion_pr or ''}")
    print(f"protocol_version={identity.protocol_version}")
    return identity


def _write_github_outputs(identity: ReleaseIdentity) -> None:
    destination = os.environ.get("GITHUB_OUTPUT", "").strip()
    if not destination:
        return
    with Path(destination).open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(f"version={identity.version}\n")
        stream.write(f"tag={identity.tag}\n")
        stream.write(f"commit={identity.commit}\n")
        stream.write(f"promotion_pr={identity.promotion_pr or ''}\n")
        stream.write(f"protocol_version={identity.protocol_version}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-tag", action="store_true")
    parser.add_argument("--require-promotion", action="store_true")
    parser.add_argument("--main-ref", default="origin/main")
    parser.add_argument("--repository")
    args = parser.parse_args()
    identity = verify(
        Path(__file__).resolve().parents[1],
        require_tag=args.require_tag,
        require_promotion=args.require_promotion,
        main_ref=args.main_ref,
        repository=args.repository,
    )
    _write_github_outputs(identity)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

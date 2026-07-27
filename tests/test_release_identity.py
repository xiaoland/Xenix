from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_script(name: str):
    path = Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"xenix_{name}_for_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


release_identity = _load_script("verify_release_identity")


def _write_release_configuration(
    root: Path,
    *,
    version: str = "1.2.0",
    python: str = "3.14.2",
    protocol_version: int = 1,
) -> None:
    (root / "pyproject.toml").write_text(
        f'[project]\nversion = "{version}"\nrequires-python = "=={python}"\n',
        encoding="utf-8",
    )
    (root / "release.toml").write_text(
        "[release]\n"
        f"protocol_version = {protocol_version}\n"
        "[toolchain]\n"
        f'python = "{python}"\n',
        encoding="utf-8",
    )


def _promotion_record(
    commit: str,
    *,
    number: int = 42,
    head: str = "develop",
    repository: str = "xiaoland/Xenix",
) -> dict:
    return {
        "number": number,
        "merged_at": "2026-07-26T00:00:00Z",
        "merge_commit_sha": commit,
        "head": {
            "ref": head,
            "repo": {"full_name": repository},
        },
        "base": {
            "ref": "main",
            "repo": {"full_name": repository},
        },
    }


def test_promotion_selection_requires_exact_same_repository_merge_outcome() -> None:
    commit = "a" * 40

    assert (
        release_identity._promotion_pr_number(
            [_promotion_record(commit)],
            repository="xiaoland/Xenix",
            commit=commit,
        )
        == 42
    )

    with pytest.raises(RuntimeError, match="unique merge outcome"):
        release_identity._promotion_pr_number(
            [_promotion_record(commit, head="feature")],
            repository="xiaoland/Xenix",
            commit=commit,
        )


def test_verify_accepts_historical_first_parent_promotion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit = "a" * 40
    _write_release_configuration(tmp_path)

    def git(_root: Path, *args: str) -> str:
        if args == ("rev-parse", "HEAD"):
            return commit
        if args == ("tag", "--points-at", commit):
            return "v1.2.0"
        if args == ("rev-list", "--first-parent", "origin/main"):
            return f"{'b' * 40}\n{commit}\n{'c' * 40}"
        raise AssertionError(args)

    monkeypatch.setattr(release_identity, "_git", git)
    monkeypatch.setattr(
        release_identity,
        "_associated_pull_requests",
        lambda *_args, **_kwargs: [_promotion_record(commit)],
    )

    identity = release_identity.verify(
        tmp_path,
        require_tag=True,
        require_promotion=True,
        repository="xiaoland/Xenix",
    )

    assert identity.version == "1.2.0"
    assert identity.tag == "v1.2.0"
    assert identity.commit == commit
    assert identity.promotion_pr == 42


def test_verify_rejects_side_branch_ancestor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit = "a" * 40
    _write_release_configuration(tmp_path)

    def git(_root: Path, *args: str) -> str:
        if args == ("rev-parse", "HEAD"):
            return commit
        if args == ("tag", "--points-at", commit):
            return "v1.2.0"
        if args == ("rev-list", "--first-parent", "origin/main"):
            return "b" * 40
        raise AssertionError(args)

    monkeypatch.setattr(release_identity, "_git", git)

    with pytest.raises(RuntimeError, match="not a completed state"):
        release_identity.verify(
            tmp_path,
            require_tag=True,
            require_promotion=True,
            repository="xiaoland/Xenix",
        )


def test_release_protocol_and_tag_must_match_project_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit = "a" * 40
    _write_release_configuration(tmp_path)
    monkeypatch.setattr(
        release_identity,
        "_git",
        lambda _root, *args: commit
        if args == ("rev-parse", "HEAD")
        else "v1.1.0",
    )

    with pytest.raises(RuntimeError, match="exactly tag"):
        release_identity.verify(tmp_path, require_tag=True)

    _write_release_configuration(tmp_path, protocol_version=2)
    with pytest.raises(RuntimeError, match="protocol is unsupported"):
        release_identity.verify(tmp_path, require_tag=False)

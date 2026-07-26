from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path, PurePosixPath
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "tests" / "suites.toml"
_TOPOLOGY_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


class _ManifestDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class TestCohort(_ManifestDocument):
    paths: tuple[str, ...]

    @field_validator("paths", mode="before")
    @classmethod
    def _convert_toml_array(cls, value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        return value

    @field_validator("paths")
    @classmethod
    def _validate_paths(cls, paths: tuple[str, ...]) -> tuple[str, ...]:
        if not paths:
            raise ValueError("Test cohort must contain a test path.")
        return tuple(_normalized_test_path(path) for path in paths)


class TestShard(_ManifestDocument):
    cohorts: dict[str, TestCohort]

    @field_validator("cohorts")
    @classmethod
    def _validate_cohorts(
        cls,
        cohorts: dict[str, TestCohort],
    ) -> dict[str, TestCohort]:
        if not cohorts:
            raise ValueError("Test shard must contain a process cohort.")
        for cohort_name in cohorts:
            _validate_topology_name(cohort_name, kind="cohort")
        return cohorts


class TestSuiteManifest(_ManifestDocument):
    version: Literal[1]
    shards: dict[str, TestShard]

    @field_validator("version", mode="before")
    @classmethod
    def _validate_version_type(cls, version: object) -> object:
        if type(version) is not int:
            raise ValueError("Test suite manifest version must be the integer 1.")
        return version

    @field_validator("shards")
    @classmethod
    def _validate_shards(cls, shards: dict[str, TestShard]) -> dict[str, TestShard]:
        if not shards:
            raise ValueError("Test suite manifest must declare a semantic shard.")
        for shard_name in shards:
            _validate_topology_name(shard_name, kind="shard")
        return shards

    @model_validator(mode="after")
    def _validate_topology(self) -> Self:
        owners: dict[str, tuple[str, str]] = {}
        for shard_name, shard in self.shards.items():
            for cohort_name, cohort in shard.cohorts.items():
                for test_path in cohort.paths:
                    previous = owners.get(test_path)
                    if previous is not None:
                        raise ValueError(
                            f"Test path {test_path!r} belongs to both "
                            f"{previous[0]}/{previous[1]} and "
                            f"{shard_name}/{cohort_name}."
                        )
                    owners[test_path] = (shard_name, cohort_name)

        return self

    @property
    def shard_names(self) -> tuple[str, ...]:
        return tuple(self.shards)

    def cohorts_for(self, shard: str) -> tuple[tuple[str, TestCohort], ...]:
        try:
            return tuple(self.shards[shard].cohorts.items())
        except KeyError as exc:
            choices = ", ".join(self.shards)
            raise ValueError(
                f"Unknown test shard {shard!r}; choose one of: {choices}."
            ) from exc


def load_test_suite_manifest(path: Path = MANIFEST_PATH) -> TestSuiteManifest:
    document = tomllib.loads(path.read_text(encoding="utf-8"))
    manifest = TestSuiteManifest.model_validate(document)

    discovered = _discover_test_modules()
    declared = {
        test_path
        for shard in manifest.shards.values()
        for cohort in shard.cohorts.values()
        for test_path in cohort.paths
    }
    if missing := sorted(discovered - declared):
        raise ValueError("Test suite manifest does not own: " + ", ".join(missing))
    if stale := sorted(declared - discovered):
        raise ValueError(
            "Test suite manifest references missing paths: " + ", ".join(stale)
        )
    return manifest


def _discover_test_modules() -> set[str]:
    tests_root = PROJECT_ROOT / "tests"
    candidates = set(tests_root.rglob("test_*.py"))
    candidates.update(tests_root.rglob("*_test.py"))
    return {
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in candidates
        if path.is_file()
    }


def _validate_topology_name(value: str, *, kind: str) -> None:
    if _TOPOLOGY_NAME.fullmatch(value) is None:
        raise ValueError(f"Invalid test {kind} name: {value!r}.")


def _normalized_test_path(value: str) -> str:
    if not value:
        raise ValueError("Test suite paths must be non-empty strings.")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or path.as_posix() != value
        or not value.startswith("tests/")
        or path.name == "conftest.py"
        or not (path.name.startswith("test_") or path.name.endswith("_test.py"))
        or path.suffix != ".py"
    ):
        raise ValueError(f"Invalid test suite path: {value!r}.")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate or inspect the authoritative Xenix test-suite topology."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check")
    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("shard")
    args = parser.parse_args()

    manifest = load_test_suite_manifest()
    if args.command == "list":
        print(
            "\n".join(
                path
                for _, cohort in manifest.cohorts_for(args.shard)
                for path in cohort.paths
            )
        )
        return 0
    file_count = sum(
        len(cohort.paths)
        for shard in manifest.shards.values()
        for cohort in shard.cohorts.values()
    )
    print(
        f"Checked {file_count} test files across "
        f"{len(manifest.shards)} semantic shards."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

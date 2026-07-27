from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from test_suites import load_test_suite_manifest


def _generate_agent_skill_catalog() -> None:
    project_root = Path(__file__).resolve().parents[1]
    subprocess.run(
        [sys.executable, str(project_root / "scripts" / "agent_skills.py"), "generate"],
        check=True,
        cwd=project_root,
    )
    subprocess.run(
        [sys.executable, str(project_root / "scripts" / "agent_skills.py"), "check"],
        check=True,
        cwd=project_root,
    )


def _has_basetemp_argument(args: list[str]) -> bool:
    for index, arg in enumerate(args):
        if arg == "--basetemp":
            return True
        if arg.startswith("--basetemp="):
            return True
        if index > 0 and args[index - 1] == "--basetemp":
            return True
    return False


def _default_basetemp() -> Path:
    run_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}"
    return Path(tempfile.gettempdir()) / "xenix-native-pytest-runs" / run_id


def _pop_value_option(args: list[str], name: str) -> tuple[str | None, list[str]]:
    value: str | None = None
    remaining: list[str] = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == name:
            if value is not None or index + 1 >= len(args):
                raise SystemExit(f"{name} must be supplied exactly once with a value.")
            value = args[index + 1]
            index += 2
            continue
        prefix = f"{name}="
        if arg.startswith(prefix):
            if value is not None or not arg[len(prefix) :]:
                raise SystemExit(f"{name} must be supplied exactly once with a value.")
            value = arg[len(prefix) :]
            index += 1
            continue
        remaining.append(arg)
        index += 1
    return value, remaining


def _pop_flag(args: list[str], name: str) -> tuple[bool, list[str]]:
    found = False
    remaining: list[str] = []
    for arg in args:
        if arg != name:
            remaining.append(arg)
            continue
        if found:
            raise SystemExit(f"{name} may be supplied only once.")
        found = True
    return found, remaining


def _report_path(path: str, label: str, *, group_count: int) -> str:
    if group_count == 1:
        return path
    report = Path(path)
    suffix = report.suffix or ".xml"
    stem = report.name[: -len(report.suffix)] if report.suffix else report.name
    return str(report.with_name(f"{stem}-{label}{suffix}"))


def _execution_groups(
    suite_names: tuple[str, ...],
) -> list[tuple[str, tuple[str, ...]]]:
    manifest = load_test_suite_manifest()
    groups: list[tuple[str, tuple[str, ...]]] = []
    for suite_name in suite_names:
        groups.extend(
            (f"{suite_name}--{cohort_name}", cohort.paths)
            for cohort_name, cohort in manifest.cohorts_for(suite_name)
        )
    return groups


def _run_groups(
    suite_names: tuple[str, ...],
    pytest_args: list[str],
    *,
    junitxml: str | None,
) -> int:
    project_root = Path(__file__).resolve().parents[1]
    basetemp = _default_basetemp()
    basetemp.mkdir(parents=True, exist_ok=True)
    groups = _execution_groups(suite_names)
    for label, paths in groups:
        command = [
            sys.executable,
            "-m",
            "pytest",
            *paths,
            *pytest_args,
            f"--basetemp={basetemp / label}",
        ]
        if junitxml is not None:
            command.append(
                "--junitxml="
                + _report_path(junitxml, label, group_count=len(groups))
            )
        completed = subprocess.run(command, cwd=project_root, check=False)
        if completed.returncode:
            return completed.returncode
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    _generate_agent_skill_catalog()

    direct, args = _pop_flag(args, "--direct")
    suite, args = _pop_value_option(args, "--promotion-shard")
    junitxml, args = _pop_value_option(args, "--junitxml")
    junit_xml, args = _pop_value_option(args, "--junit-xml")
    if junitxml is not None and junit_xml is not None:
        raise SystemExit("Use only one of --junitxml and --junit-xml.")
    junitxml = junitxml or junit_xml
    if direct:
        if suite is not None:
            raise SystemExit("--direct and --promotion-shard are mutually exclusive.")
        if junitxml is not None:
            args.append(f"--junitxml={junitxml}")
        if not _has_basetemp_argument(args):
            basetemp = _default_basetemp()
            basetemp.parent.mkdir(parents=True, exist_ok=True)
            args.append(f"--basetemp={basetemp}")
        return pytest.main(args)

    manifest = load_test_suite_manifest()
    if suite is not None:
        if suite not in manifest.shards:
            choices = ", ".join(manifest.shard_names)
            raise SystemExit(f"Unknown test shard {suite!r}; choose one of: {choices}.")
        return _run_groups((suite,), args, junitxml=junitxml)

    # Reporting must not collapse repository verification into one process.
    # Qt owns native process-global state, and each semantic shard may exercise
    # multiprocessing or native libraries. A default run therefore follows the
    # same authoritative topology as Promotion CI, while MainWindow remains in
    # its own clean process.
    if any(not arg.startswith("-") for arg in args):
        raise SystemExit(
            "Targeted pytest selectors require explicit --direct mode. "
            "Use --option=value form for topology-wide options with values."
        )
    if _has_basetemp_argument(args):
        raise SystemExit(
            "The test topology owns an isolated --basetemp for every process cohort."
        )
    return _run_groups(manifest.shard_names, args, junitxml=junitxml)


if __name__ == "__main__":
    raise SystemExit(main())

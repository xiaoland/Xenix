from __future__ import annotations

import argparse
import json
import statistics
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RunTiming:
    run_id: int
    url: str
    controlled_minutes: float
    calendar_minutes: float
    queue_minutes: float


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise RuntimeError("GitHub workflow timestamp is missing.")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def run_timing(record: dict[str, Any]) -> RunTiming:
    created = _timestamp(record.get("createdAt"))
    started = _timestamp(record.get("startedAt"))
    updated = _timestamp(record.get("updatedAt"))
    run_id = record.get("databaseId")
    url = record.get("url")
    if (
        type(run_id) is not int
        or run_id < 1
        or not isinstance(url, str)
        or updated < started
        or started < created
    ):
        raise RuntimeError("GitHub workflow timing record is invalid.")
    return RunTiming(
        run_id=run_id,
        url=url,
        controlled_minutes=round((updated - started).total_seconds() / 60, 2),
        calendar_minutes=round((updated - created).total_seconds() / 60, 2),
        queue_minutes=round((started - created).total_seconds() / 60, 2),
    )


def summarize(
    timings: list[RunTiming],
    *,
    required_samples: int,
    median_budget: float | None,
    maximum_budget: float,
) -> dict[str, Any]:
    controlled = [item.controlled_minutes for item in timings]
    sample_count = len(controlled)
    median = round(statistics.median(controlled), 2) if controlled else None
    maximum = round(max(controlled), 2) if controlled else None
    enough_samples = sample_count >= required_samples
    within_budget = (
        enough_samples
        and maximum is not None
        and maximum <= maximum_budget
        and (median_budget is None or (median is not None and median <= median_budget))
    )
    return {
        "sample_count": sample_count,
        "required_samples": required_samples,
        "median_controlled_minutes": median,
        "maximum_controlled_minutes": maximum,
        "median_budget_minutes": median_budget,
        "maximum_budget_minutes": maximum_budget,
        "enough_samples": enough_samples,
        "within_budget": within_budget,
        "runs": [asdict(item) for item in timings],
    }


def _gh_json(root: Path, arguments: list[str]) -> Any:
    completed = subprocess.run(
        ["gh", *arguments],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or f"exit code {completed.returncode}"
        raise RuntimeError(f"GitHub timing query failed: {detail}")
    return json.loads(completed.stdout)


def _successful_runs(
    root: Path,
    *,
    repository: str,
    workflow: str,
    limit: int,
    required_jobs: set[str] | None = None,
) -> list[RunTiming]:
    records = _gh_json(
        root,
        [
            "run",
            "list",
            "--repo",
            repository,
            "--workflow",
            workflow,
            "--all",
            "--status",
            "success",
            "--limit",
            str(limit),
            "--json",
            "databaseId,createdAt,startedAt,updatedAt,url",
        ],
    )
    if not isinstance(records, list):
        raise RuntimeError("GitHub workflow run response is invalid.")
    timings = [run_timing(item) for item in records if isinstance(item, dict)]
    if not required_jobs:
        return timings
    qualified = []
    for timing in timings:
        detail = _gh_json(
            root,
            [
                "run",
                "view",
                str(timing.run_id),
                "--repo",
                repository,
                "--json",
                "jobs",
            ],
        )
        jobs = detail.get("jobs") if isinstance(detail, dict) else None
        successful_names = set()
        if isinstance(jobs, list):
            successful_names = {
                job.get("name")
                for job in jobs
                if isinstance(job, dict) and job.get("conclusion") == "success"
            }
        if required_jobs <= successful_names:
            qualified.append(timing)
    return qualified


def build_report(
    root: Path,
    *,
    repository: str,
    limit: int,
) -> dict[str, Any]:
    unavailable: dict[str, str] = {}
    try:
        promotion_runs = _successful_runs(
            root,
            repository=repository,
            workflow="native-ci.yml",
            limit=limit,
            required_jobs={"Promotion Contract", "Native CI Gate"},
        )
    except RuntimeError as exc:
        promotion_runs = []
        unavailable["promotion_ci"] = str(exc)
    try:
        release_runs = _successful_runs(
            root,
            repository=repository,
            workflow="native-release.yml",
            limit=limit,
        )
    except RuntimeError as exc:
        release_runs = []
        unavailable["native_release"] = str(exc)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "repository": repository,
        "definitions": {
            "controlled": "run.startedAt to run.updatedAt",
            "calendar": "run.createdAt to run.updatedAt",
            "queue": "run.createdAt to run.startedAt",
        },
        "promotion_ci": summarize(
            promotion_runs,
            required_samples=5,
            median_budget=18,
            maximum_budget=25,
        ),
        "native_release": summarize(
            release_runs,
            required_samples=1,
            median_budget=None,
            maximum_budget=90,
        ),
        "unavailable": unavailable,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 100:
        raise RuntimeError("--limit must be between 1 and 100.")
    report = build_report(
        Path(__file__).resolve().parents[1],
        repository=args.repository,
        limit=args.limit,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.strict:
        accepted = (
            not report["unavailable"]
            and report["promotion_ci"]["within_budget"]
            and report["native_release"]["within_budget"]
        )
        return 0 if accepted else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_script(name: str):
    path = Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"xenix_{name}_for_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


timings = _load_script("report_native_workflow_timings")


def _run(run_id: int, controlled: float):
    return timings.RunTiming(
        run_id=run_id,
        url=f"https://example.test/runs/{run_id}",
        controlled_minutes=controlled,
        calendar_minutes=controlled + 2,
        queue_minutes=2,
    )


def test_promotion_budget_requires_five_samples_and_checks_median_and_tail() -> None:
    insufficient = timings.summarize(
        [_run(index, 14) for index in range(1, 5)],
        required_samples=5,
        median_budget=18,
        maximum_budget=25,
    )
    accepted = timings.summarize(
        [_run(index, value) for index, value in enumerate([14, 16, 17, 18, 24], 1)],
        required_samples=5,
        median_budget=18,
        maximum_budget=25,
    )
    slow_tail = timings.summarize(
        [_run(index, value) for index, value in enumerate([14, 15, 16, 17, 26], 1)],
        required_samples=5,
        median_budget=18,
        maximum_budget=25,
    )

    assert insufficient["within_budget"] is False
    assert accepted["within_budget"] is True
    assert accepted["median_controlled_minutes"] == 17
    assert slow_tail["within_budget"] is False


def test_run_timing_separates_queue_controlled_and_calendar_clocks() -> None:
    value = timings.run_timing(
        {
            "databaseId": 42,
            "url": "https://example.test/runs/42",
            "createdAt": "2026-07-26T00:00:00Z",
            "startedAt": "2026-07-26T00:03:00Z",
            "updatedAt": "2026-07-26T00:23:00Z",
        }
    )

    assert value.queue_minutes == 3
    assert value.controlled_minutes == 20
    assert value.calendar_minutes == 23


def test_promotion_samples_require_stable_gate_job(
    monkeypatch,
    tmp_path: Path,
) -> None:
    records = [
        {
            "databaseId": 42,
            "url": "https://example.test/runs/42",
            "createdAt": "2026-07-26T00:00:00Z",
            "startedAt": "2026-07-26T00:01:00Z",
            "updatedAt": "2026-07-26T00:11:00Z",
        }
    ]
    responses = iter(
        [
            records,
            {
                "jobs": [
                    {"name": "Native CI Gate", "conclusion": "success"},
                ]
            },
        ]
    )
    monkeypatch.setattr(
        timings,
        "_gh_json",
        lambda *_args, **_kwargs: next(responses),
    )

    selected = timings._successful_runs(
        tmp_path,
        repository="xiaoland/Xenix",
        workflow="native-ci.yml",
        limit=10,
        required_jobs={"Native CI Gate"},
    )

    assert [item.run_id for item in selected] == [42]

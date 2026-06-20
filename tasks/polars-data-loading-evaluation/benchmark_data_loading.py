from __future__ import annotations

import argparse
import csv
import gc
import json
import math
import os
import statistics
import time
import tracemalloc
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


DEFAULT_XLSX = Path(r"F:\CODING\Project\Xenix\ml\recommendations\movie_recommendations.xlsx")
TASK_DIR = Path(__file__).resolve().parent
FIXTURE_DIR = TASK_DIR / "fixtures"
ARTIFACT_DIR = TASK_DIR / "artifacts"


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    operation: Callable[[], dict[str, Any]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    parser.add_argument("--csv-rows", type=int, default=500_000)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--suite", choices=["all", "csv", "excel"], default="all")
    parser.add_argument("--output", type=Path, default=ARTIFACT_DIR / "benchmark-results.json")
    args = parser.parse_args()

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    csv_path = FIXTURE_DIR / f"mixed-{args.csv_rows}.csv"
    if not csv_path.exists():
        _write_csv_fixture(csv_path, args.csv_rows)

    env = _environment()
    cases = _build_cases(args.xlsx, csv_path, suite=args.suite)
    results = []
    for case in cases:
        print(f"running {case.name} ...", flush=True)
        case_runs = []
        for run_index in range(args.repeats):
            case_runs.append(_measure(case.operation, run_index=run_index))
        results.append(_summarize_case(case.name, case_runs))

    payload = {
        "environment": env,
        "inputs": {
            "xlsx": str(args.xlsx),
            "xlsx_exists": args.xlsx.exists(),
            "xlsx_size_bytes": args.xlsx.stat().st_size if args.xlsx.exists() else None,
            "csv": str(csv_path),
            "csv_rows": args.csv_rows,
            "csv_size_bytes": csv_path.stat().st_size,
            "repeats": args.repeats,
        },
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)


def _environment() -> dict[str, Any]:
    import platform

    packages: dict[str, str | None] = {}
    for name, import_name in {
        "pandas": "pandas",
        "openpyxl": "openpyxl",
        "polars": "polars",
        "pyarrow": "pyarrow",
        "python-calamine": "python_calamine",
        "fastexcel": "fastexcel",
    }.items():
        try:
            module = __import__(import_name)
            packages[name] = getattr(module, "__version__", "installed")
        except Exception:
            packages[name] = None
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": packages,
    }


def _build_cases(xlsx_path: Path, csv_path: Path, *, suite: str) -> list[BenchmarkCase]:
    cases: list[BenchmarkCase] = []

    if suite in {"all", "csv"}:
        cases.extend(
            [
                BenchmarkCase(
                    "pandas.read_csv.full",
                    lambda: _pandas_csv_full(csv_path),
                ),
                BenchmarkCase(
                    "pandas.read_csv.profile_like",
                    lambda: _pandas_csv_profile_like(csv_path),
                ),
                BenchmarkCase(
                    "polars.read_csv.full",
                    lambda: _polars_csv_full(csv_path),
                ),
                BenchmarkCase(
                    "polars.scan_csv.profile_like",
                    lambda: _polars_csv_profile_like(csv_path),
                ),
            ]
        )

    if suite in {"all", "excel"} and xlsx_path.exists():
        cases.extend(
            [
                BenchmarkCase(
                    "pandas.read_excel.openpyxl.full",
                    lambda: _pandas_excel_full(xlsx_path, engine="openpyxl"),
                ),
                BenchmarkCase(
                    "pandas.read_excel.calamine.full",
                    lambda: _pandas_excel_full(xlsx_path, engine="calamine"),
                ),
                BenchmarkCase(
                    "polars.read_excel.calamine.full",
                    lambda: _polars_excel_full(xlsx_path),
                ),
                BenchmarkCase(
                    "polars.read_excel.calamine.inspect_like",
                    lambda: _polars_excel_inspect_like(xlsx_path),
                ),
            ]
        )
    return cases


def _measure(operation: Callable[[], dict[str, Any]], *, run_index: int) -> dict[str, Any]:
    gc.collect()
    rss_before = _rss_bytes()
    tracemalloc.start()
    started = time.perf_counter()
    try:
        result = operation()
        status = "succeeded"
        error = None
    except Exception as exc:
        result = {}
        status = "failed"
        error = f"{type(exc).__name__}: {exc}"
    elapsed = time.perf_counter() - started
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    rss_after = _rss_bytes()
    return {
        "run_index": run_index,
        "status": status,
        "elapsed_seconds": elapsed,
        "rss_before_bytes": rss_before,
        "rss_after_bytes": rss_after,
        "rss_delta_bytes": rss_after - rss_before if rss_before is not None and rss_after is not None else None,
        "tracemalloc_current_bytes": current,
        "tracemalloc_peak_bytes": peak,
        "result": result,
        "error": error,
    }


def _summarize_case(name: str, runs: list[dict[str, Any]]) -> dict[str, Any]:
    succeeded = [run for run in runs if run["status"] == "succeeded"]
    failed = [run for run in runs if run["status"] != "succeeded"]
    elapsed = [run["elapsed_seconds"] for run in succeeded]
    peaks = [run["tracemalloc_peak_bytes"] for run in succeeded]
    rss_deltas = [
        run["rss_delta_bytes"]
        for run in succeeded
        if run.get("rss_delta_bytes") is not None
    ]
    return {
        "name": name,
        "status": "succeeded" if succeeded and not failed else "failed" if not succeeded else "mixed",
        "runs": runs,
        "summary": {
            "elapsed_median_seconds": statistics.median(elapsed) if elapsed else None,
            "elapsed_min_seconds": min(elapsed) if elapsed else None,
            "elapsed_max_seconds": max(elapsed) if elapsed else None,
            "peak_median_bytes": statistics.median(peaks) if peaks else None,
            "peak_min_bytes": min(peaks) if peaks else None,
            "peak_max_bytes": max(peaks) if peaks else None,
            "rss_delta_median_bytes": statistics.median(rss_deltas) if rss_deltas else None,
            "rss_delta_min_bytes": min(rss_deltas) if rss_deltas else None,
            "rss_delta_max_bytes": max(rss_deltas) if rss_deltas else None,
        },
    }


def _write_csv_fixture(path: Path, rows: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "row_id",
                "user_id",
                "movie_id",
                "rating",
                "segment",
                "is_premium",
                "watched_at",
                "comment",
            ]
        )
        for index in range(rows):
            segment = f"s{index % 25:02d}"
            writer.writerow(
                [
                    index,
                    index % 50_000,
                    index % 12_000,
                    round(1.0 + (index % 9) * 0.5, 1),
                    segment,
                    "true" if index % 3 == 0 else "false",
                    f"2025-{(index % 12) + 1:02d}-{(index % 28) + 1:02d}",
                    "" if index % 17 == 0 else f"note {index % 100}",
                ]
            )


def _pandas_csv_full(path: Path) -> dict[str, Any]:
    import pandas as pd

    frame = pd.read_csv(path)
    return _pandas_shape(frame)


def _pandas_csv_profile_like(path: Path) -> dict[str, Any]:
    import pandas as pd

    frame = pd.read_csv(path)
    numeric = pd.to_numeric(frame["rating"], errors="coerce")
    grouped = frame.groupby("segment", dropna=False)["rating"].agg(["count", "mean"]).head(10)
    return {
        **_pandas_shape(frame),
        "rating_mean": _number(numeric.mean()),
        "rating_q1": _number(numeric.quantile(0.25)),
        "rating_q3": _number(numeric.quantile(0.75)),
        "segment_rows": int(len(grouped.index)),
        "null_comments": int(frame["comment"].isna().sum()),
    }


def _pandas_excel_full(path: Path, *, engine: str) -> dict[str, Any]:
    import pandas as pd

    frame = pd.read_excel(path, engine=engine)
    return _pandas_shape(frame)


def _polars_csv_full(path: Path) -> dict[str, Any]:
    import polars as pl

    frame = pl.read_csv(path)
    return _polars_shape(frame)


def _polars_csv_profile_like(path: Path) -> dict[str, Any]:
    import polars as pl

    frame = pl.scan_csv(path)
    summary = frame.select(
        [
            pl.len().alias("row_count"),
            pl.col("rating").mean().alias("rating_mean"),
            pl.col("rating").quantile(0.25).alias("rating_q1"),
            pl.col("rating").quantile(0.75).alias("rating_q3"),
            pl.col("comment").is_null().sum().alias("null_comments"),
        ]
    ).collect()
    grouped = (
        frame.group_by("segment")
        .agg([pl.len().alias("count"), pl.col("rating").mean().alias("mean")])
        .limit(10)
        .collect()
    )
    schema = frame.collect_schema()
    return {
        "rows": int(summary["row_count"][0]),
        "columns": len(schema),
        "column_names": list(schema.names()),
        "dtypes": {name: str(dtype) for name, dtype in schema.items()},
        "rating_mean": _number(summary["rating_mean"][0]),
        "rating_q1": _number(summary["rating_q1"][0]),
        "rating_q3": _number(summary["rating_q3"][0]),
        "segment_rows": int(grouped.height),
        "null_comments": int(summary["null_comments"][0]),
    }


def _polars_excel_full(path: Path) -> dict[str, Any]:
    import polars as pl

    frame = pl.read_excel(path, engine="calamine")
    return _polars_shape(frame)


def _polars_excel_inspect_like(path: Path) -> dict[str, Any]:
    import polars as pl

    frame = pl.read_excel(path, engine="calamine")
    preview = frame.head(5)
    nulls = frame.null_count()
    return {
        **_polars_shape(frame),
        "preview_rows": preview.height,
        "nullable_columns": [
            name for name in frame.columns if int(nulls[name][0]) > 0
        ],
    }


def _pandas_shape(frame: Any) -> dict[str, Any]:
    return {
        "rows": int(len(frame.index)),
        "columns": int(len(frame.columns)),
        "column_names": [str(column) for column in frame.columns],
        "dtypes": {str(column): str(dtype) for column, dtype in frame.dtypes.items()},
    }


def _polars_shape(frame: Any) -> dict[str, Any]:
    return {
        "rows": int(frame.height),
        "columns": int(frame.width),
        "column_names": [str(column) for column in frame.columns],
        "dtypes": {str(name): str(dtype) for name, dtype in frame.schema.items()},
    }


def _number(value: Any) -> float | int | None:
    if value is None:
        return None
    try:
        if math.isnan(float(value)):
            return None
    except (TypeError, ValueError):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return round(float(value), 6)


def _rss_bytes() -> int | None:
    try:
        import psutil

        return int(psutil.Process(os.getpid()).memory_info().rss)
    except Exception:
        return None


if __name__ == "__main__":
    main()

"""One-off public ML lifecycle diagnosis; no provider calls or pytest collection."""

import argparse
import csv
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src")]


MODEL = "text.classification.multilingual_logistic_regression_tfidf"


class InlineWorker:
    max_dispatch_threads = 1

    def run(self, entrypoint, task_dir, *, cancel_requested=None):
        entrypoint(str(task_dir))
        return 0


def main():
    import polars as pl

    from xenix.config import ensure_app_dirs, get_app_paths
    from xenix.exceptions import ValidationError
    from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
    from xenix.services.job_scheduler import JobScheduler
    from xenix.services.ml_job_handler import MLJobHandler
    from xenix.services.ml_service import (
        ApplySourceInput,
        ApplyWithFilesInput,
        CreateColumnBindingInput,
        FitWithEvaluateInput,
        MLService,
    )
    from xenix.services.ml_task_service import MLTaskService
    from xenix.services.storage import StorageBootstrapService

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    observations = []
    with TemporaryDirectory(prefix="xenix-ml-diagnosis-") as temporary:
        os.environ["XENIX_APP_HOME"] = temporary
        paths = ensure_app_dirs(get_app_paths())
        storage = StorageBootstrapService().initialize(paths)
        datasets = DatasetService(storage.session_factory, paths)
        tasks = MLTaskService(storage.session_factory, paths, worker_runner=InlineWorker())
        scheduler = JobScheduler(storage.session_factory, [MLJobHandler(tasks)])
        scheduler.start()
        ml = MLService(paths, storage.session_factory, datasets, tasks, scheduler)
        try:
            folder = ROOT / "tests/e2e/agent_harness/fixtures/business_tasks/routing/standard"
            history = datasets.register_dataset(RegisterDatasetInput(source_path=str(folder / "history.csv")))
            new = datasets.register_dataset(
                RegisterDatasetInput(source_path=str(folder / "new_tickets.csv"), project_id=history.project_id)
            )
            with (folder / "history.csv").open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            for row in rows:
                row["message"] = "the and"
            empty_path = Path(temporary) / "empty_text.csv"
            with empty_path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            empty = datasets.register_dataset(
                RegisterDatasetInput(source_path=str(empty_path), project_id=history.project_id)
            )
            for name, grouped, dataset in (
                ("automatic_groups", False, history),
                ("business_groups", True, history),
                ("empty_vocabulary", False, empty),
            ):
                roles = [{"role": "text", "columns": ["message"]}, {"role": "target", "columns": ["queue"]}]
                if grouped:
                    roles.append({"role": "group", "columns": ["customer_batch"]})
                binding = ml.create_column_binding(
                    CreateColumnBindingInput(dataset_id=dataset.id, model_key=MODEL, role_bindings=roles)
                )
                task = ml.fit_with_evaluate(FitWithEvaluateInput(binding_id=binding.id, model_key=MODEL))
                row = {"scenario": name, "policy": task.request_payload["evaluation_policy"]}
                try:
                    settled = ml.wait_for_training_models([task.id], cancel_requested=lambda: False, timeout_seconds=60)
                    assert settled is not None
                    completed, models = settled
                    row["statuses"] = [item.status.value for item in completed]
                    row["split"] = completed[0].result_payload["split_facts"]
                    applied = ml.apply(
                        ApplyWithFilesInput(
                            trained_model_id=models[0].id,
                            input_sources=[ApplySourceInput(source_path=new.source_path, dataset_id=new.id)],
                        )
                    )
                    result = ml.wait_for_task(applied.id, cancel_requested=lambda: False, timeout_seconds=60)
                    assert result is not None
                    row["apply_status"] = result.status.value
                    row["apply_row_count"] = result.result_payload["row_count"]
                    output = datasets.get_dataset(result.result_payload["result_dataset_id"])
                    predictions = pl.read_parquet(output.source_path).select("ticket_id", "prediction").to_dicts()
                    expected = json.loads((folder / "oracle.json").read_text(encoding="utf-8"))["labels"]
                    row["new_batch_accuracy"] = sum(
                        item["prediction"] == expected[item["ticket_id"]] for item in predictions
                    ) / len(predictions)
                except ValidationError as exc:
                    row["training_wait_error"] = str(exc)
                    row["stored_error"] = tasks.get_ml_task(task.id).error_summary
                    try:
                        ml.wait_for_task(task.id, cancel_requested=lambda: False, timeout_seconds=5)
                    except ValidationError as task_exc:
                        row["task_wait_error"] = str(task_exc)
                observations.append(row)
        finally:
            scheduler.shutdown()
            storage.engine.dispose()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(observations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(observations, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

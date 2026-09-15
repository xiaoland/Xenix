"""One-off replay of observed model parameters through native ML, without an LLM."""

import argparse
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
    from xenix.services.agent._model_tools import ModelTools
    from xenix.services.agent.tool_inputs import ModelTaskQueryInput
    from xenix.services.artifact_service import ArtifactService
    from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
    from xenix.services.job_scheduler import JobScheduler
    from xenix.services.ml_job_handler import MLJobHandler
    from xenix.services.ml_service import (
        ApplySourceInput, ApplyWithFilesInput, CreateColumnBindingInput,
        FitWithEvaluateInput, MLService,
    )
    from xenix.services.ml_task_service import MLTaskService
    from xenix.services.storage import StorageBootstrapService
    from xenix.services.llm.tooling import ToolExecutionContext

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    observations = []
    index = json.loads((ROOT / "tasks/harness-benchmark-failures/live-observations.json").read_text(encoding="utf-8"))
    selected = [cell for cell in index["cells"] if cell["phase"] == "content_split_v2"]
    with TemporaryDirectory(prefix="xenix-routing-evidence-") as temporary:
        os.environ["XENIX_APP_HOME"] = temporary
        paths = ensure_app_dirs(get_app_paths())
        storage = StorageBootstrapService().initialize(paths)
        datasets = DatasetService(storage.session_factory, paths)
        tasks = MLTaskService(storage.session_factory, paths, worker_runner=InlineWorker())
        scheduler = JobScheduler(storage.session_factory, [MLJobHandler(tasks)])
        scheduler.start()
        ml = MLService(paths, storage.session_factory, datasets, tasks, scheduler)
        artifacts = ArtifactService(storage.session_factory)
        tools = ModelTools(paths=paths, dataset_service=datasets, artifact_service=artifacts,
                           ml_service=ml, model_key_aliases={MODEL: MODEL})
        context = ToolExecutionContext(thread_id="diagnostic", tool_call_message_id="diagnostic")
        try:
            for cell in selected:
                if args.limit is not None and len(observations) >= args.limit:
                    break
                report = json.loads((ROOT / cell["report"]).read_text(encoding="utf-8"))
                trace = next(e["attributes"] for e in report["trace"]["events"] if e["name"] == "benchmark.subject.outcome")
                variant = cell["case_id"].split(".")[-1]
                folder = ROOT / "tests/e2e/agent_harness/fixtures/business_tasks/routing" / variant
                history = datasets.register_dataset(RegisterDatasetInput(source_path=str(folder / "history.csv")))
                batch = datasets.register_dataset(RegisterDatasetInput(
                    source_path=str(folder / "new_tickets.csv"), project_id=history.project_id,
                ))
                expected = json.loads((folder / "oracle.json").read_text(encoding="utf-8"))["labels"]
                roles = next(call["arguments"]["role_bindings"] for call in trace["tool_calls"] if call["name"] == "data.feature.select")
                binding = ml.create_column_binding(CreateColumnBindingInput(
                    dataset_id=history.id, model_key=MODEL, role_bindings=roles,
                ))
                call_round = {call["provider_call_id"]: response["round"] for response in trace["sampling_responses"] for call in response["tool_calls"]}
                for call in trace["tool_calls"]:
                    if args.limit is not None and len(observations) >= args.limit:
                        break
                    if call["name"] != "model.train":
                        continue
                    params = call["arguments"].get("params_by_model", {}).get(MODEL, {})
                    fit = ml.fit_with_evaluate(FitWithEvaluateInput(binding_id=binding.id, model_key=MODEL, params=params))
                    settled = ml.wait_for_training_models([fit.id], cancel_requested=lambda: False, timeout_seconds=60)
                    if settled is None:
                        raise RuntimeError("Native training did not settle within the diagnostic deadline.")
                    completed, models = settled
                    tool_value = tools._training_completion(history.id, completed, models).value
                    query_value = tools._model_task_query(ModelTaskQueryInput(task_ids=[fit.id]), context).value
                    diagnostic_value = tools._model_task_query(ModelTaskQueryInput(
                        task_ids=[fit.id], include_details=True, include_logs=True,
                    ), context).value
                    evaluation = next(task.result_payload for task in completed if task.result_payload.get("evaluation"))
                    predictions = {}
                    for source, target_column, name in ((history, "queue", "history"), (batch, None, "new_batch")):
                        applied = ml.apply(ApplyWithFilesInput(
                            trained_model_id=models[0].id,
                            input_sources=[ApplySourceInput(source_path=source.source_path, dataset_id=source.id)],
                        ))
                        result = ml.wait_for_task(applied.id, cancel_requested=lambda: False, timeout_seconds=60)
                        if result is None:
                            raise RuntimeError("Native apply did not settle within the diagnostic deadline.")
                        output = datasets.get_dataset(result.result_payload["result_dataset_id"])
                        rows = pl.read_parquet(output.source_path).to_dicts()
                        wrong = [row["ticket_id"] for row in rows if row["prediction"] != (row[target_column] if target_column else expected[row["ticket_id"]])]
                        predictions[name] = {"count": len(rows), "accuracy": 1 - len(wrong) / len(rows), "wrong_ticket_ids": wrong}
                    item = {
                        "variant": variant, "trace_run": cell["run_id"], "trace_round": call_round[call["provider_call_id"]],
                        "run_name": call["arguments"].get("run_name"), "params": params,
                        "holdout": evaluation["evaluation"]["metrics"],
                        "confusion": evaluation["evaluation"]["details"]["confusion_matrix"],
                        "baseline_accuracy": evaluation["baseline_evaluation"]["metrics"]["accuracy"],
                        "split": {k: evaluation["split_facts"][k] for k in ("realized_strategy", "train_row_count", "holdout_row_count", "eligible_group_count", "group_overlap_count")},
                        "applied": predictions,
                        "tool_result_bytes": len(json.dumps(tool_value, ensure_ascii=False).encode()),
                        "tool_result_top_level_bytes": {k: len(json.dumps(v, ensure_ascii=False).encode()) for k, v in tool_value.items()},
                        "tool_return_artifact_kinds": [a["kind"] for a in tool_value["artifacts"]],
                        "fit_and_eval_payload_keys": [list(task.result_payload) for task in completed],
                        "public_links_resolve": [artifacts.resolve_uri(a["uri"]).exists for a in tool_value["artifacts"]],
                        "tool_feedback": tool_value,
                        "query_feedback": query_value,
                        "query_bytes": len(json.dumps(query_value, ensure_ascii=False).encode()),
                        "full_diagnostic_bytes": len(json.dumps(diagnostic_value, ensure_ascii=False).encode()),
                        "full_diagnostics_match_storage": [
                            item["details"]["task"]["result_payload"] == ml.get_task_details(item["task_id"]).task.result_payload
                            for item in diagnostic_value["tasks"]
                        ],
                    }
                    observations.append(item)
                    print(json.dumps({k: item[k] for k in ("variant", "trace_round", "params", "applied", "tool_result_bytes")}, ensure_ascii=False), flush=True)
        finally:
            scheduler.shutdown()
            storage.engine.dispose()
    args.output.write_text(json.dumps(observations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

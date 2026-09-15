"""Manual native tuning/feedback observation; no provider calls or pytest collection."""

import json
import math
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src")]

from probe_model_evidence import InlineWorker  # noqa: E402


def main():
    import polars as pl

    from xenix.config import ensure_app_dirs, get_app_paths
    from xenix.services.agent._model_tools import ModelTools
    from xenix.services.agent.tool_inputs import ModelHyperTrainInput, ModelTaskQueryInput
    from xenix.services.artifact_service import ArtifactService
    from xenix.services.dataset_service import DatasetService, RegisterDatasetInput
    from xenix.services.job_scheduler import JobScheduler
    from xenix.services.llm.tooling import ToolExecutionContext
    from xenix.services.ml_job_handler import MLJobHandler
    from xenix.services.ml_service import CreateColumnBindingInput, MLService
    from xenix.services.ml_task_service import MLTaskService
    from xenix.services.storage import StorageBootstrapService

    with TemporaryDirectory(prefix="xenix-tuning-feedback-") as temporary:
        os.environ["XENIX_APP_HOME"] = temporary
        paths = ensure_app_dirs(get_app_paths())
        storage = StorageBootstrapService().initialize(paths)
        datasets = DatasetService(storage.session_factory, paths)
        tasks = MLTaskService(storage.session_factory, paths, worker_runner=InlineWorker())
        scheduler = JobScheduler(storage.session_factory, [MLJobHandler(tasks)])
        scheduler.start()
        try:
            ml = MLService(paths, storage.session_factory, datasets, tasks, scheduler)
            artifacts = ArtifactService(storage.session_factory)
            model_key = "regression.ridge"
            tools = ModelTools(paths=paths, dataset_service=datasets, artifact_service=artifacts,
                               ml_service=ml, model_key_aliases={model_key: model_key})
            context = ToolExecutionContext(thread_id="diagnostic", tool_call_message_id="diagnostic")
            source = Path(temporary) / "observations.csv"
            pl.DataFrame({
                "x": list(range(60)), "y": [2 * x + math.sin(x) for x in range(60)],
            }).write_csv(source)
            dataset = datasets.register_dataset(RegisterDatasetInput(source_path=str(source)))
            binding = ml.create_column_binding(CreateColumnBindingInput(
                dataset_id=dataset.id, model_key=model_key,
                role_bindings=[{"role": "feature", "columns": ["x"]}, {"role": "target", "columns": ["y"]}],
            ))
            feedback = tools._model_hyper_train(ModelHyperTrainInput(
                binding_id=binding.id, param_grids_by_model={model_key: {"alpha": [0.1, 1.0]}},
            ), context).value
            query = tools._model_task_query(ModelTaskQueryInput(task_ids=feedback["task_ids"]), context).value
            observation = {
                "feedback": feedback, "query": query,
                "serialized_bytes": len(json.dumps(feedback, ensure_ascii=False).encode()),
                "public_links_resolve": [artifacts.resolve_uri(a["uri"]).exists for a in feedback["artifacts"]],
            }
            (Path(__file__).parent / "tuning-feedback-evidence.json").write_text(
                json.dumps(observation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
            )
            print(json.dumps({"serialized_bytes": observation["serialized_bytes"],
                              "public_links_resolve": observation["public_links_resolve"],
                              "models": feedback["models"]}, ensure_ascii=False))
        finally:
            scheduler.shutdown()
            storage.engine.dispose()


if __name__ == "__main__":
    main()

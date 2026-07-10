import json
from pathlib import Path

import xenix.services.preprocessing_worker as preprocessing_worker_module
from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.data_transform import (
    DataQueryTransformService,
    DataTransformInput,
    DatasetSqlBinding,
)
from xenix.services.dataset_inspection import detect_source_format, load_dataframe
from xenix.services.preprocessing_worker import (
    LocalPreprocessingWorkerRunner,
    run_preprocessing_worker_task,
)


def test_local_preprocessing_worker_runner_uses_spawn_process(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    captured: dict[str, object] = {}

    class FakeProcess:
        exitcode = 0

        def __init__(self, *, target, args) -> None:
            captured["target"] = target
            captured["args"] = args
            self._target = target
            self._args = args
            self._alive = False

        def start(self) -> None:
            task_dir = Path(self._args[0])
            captured["task_dir"] = task_dir
            request = json.loads((task_dir / "request.json").read_text(encoding="utf-8"))
            captured["request"] = request
            (task_dir / "result.json").write_text(
                json.dumps({"ok": True, "result": {"worker": "ok"}}),
                encoding="utf-8",
            )

        def is_alive(self) -> bool:
            return self._alive

        def join(self, timeout: float | None = None) -> None:
            captured["join_timeout"] = timeout

    class FakeContext:
        def Process(self, *, target, args):
            return FakeProcess(target=target, args=args)

    def fake_get_context(name: str):
        captured["context_name"] = name
        return FakeContext()

    monkeypatch.setattr(preprocessing_worker_module, "get_context", fake_get_context)

    result = LocalPreprocessingWorkerRunner().run(
        "data.transform",
        {"input": {"sql": "SELECT 1"}},
        paths=paths,
    )

    assert result == {"worker": "ok"}
    assert captured["context_name"] == "spawn"
    assert captured["target"] is run_preprocessing_worker_task
    assert captured["request"]["operation"] == "data.transform"
    assert captured["request"]["payload"] == {"input": {"sql": "SELECT 1"}}
    assert not captured["task_dir"].exists()


def test_default_preprocessing_worker_runner_executes_transform_in_child_process(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    source = tmp_path / "orders.csv"
    source.write_text("order_id,amount\n1,10\n2,20\n", encoding="utf-8")

    result = DataQueryTransformService(paths).transform(
        DataTransformInput(
            bindings=[
                DatasetSqlBinding(
                    alias="input",
                    dataset_id="orders-id",
                    source_path=str(source.resolve()),
                )
            ],
            sql="SELECT order_id, amount * 2 AS doubled FROM input ORDER BY order_id",
            name="Orders doubled",
        )
    )

    output_path = Path(result.output_path)
    frame = load_dataframe(output_path, detect_source_format(output_path))
    assert output_path.suffix == ".parquet"
    assert result.row_count == 2
    assert frame.to_dict(orient="records") == [
        {"order_id": 1, "doubled": 20},
        {"order_id": 2, "doubled": 40},
    ]

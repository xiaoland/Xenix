from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.ml.execution import SshMLWorkerRunner
from xenix.services.ml.operations import run_apply_task
from xenix.services.ml.ssh_worker_setup import SshWorkerSetupInput, SshWorkerSetupResult, SshWorkerSetupService
from xenix.services.ml.worker_pool import MLWorkerPool
from xenix.services.ml.worker_settings import (
    MLWorkerConfig,
    MLWorkerKind,
    MLWorkerPoolConfig,
    MLWorkerSettings,
    MLWorkerSettingsService,
    MLWorkerSetupState,
    MLWorkerValidationRecord,
    MLWorkerValidationStatus,
)
from xenix.ui.ssh_worker_setup_wizard import SshWorkerSetupWizard


def test_ml_worker_settings_persist_pool_and_ssh_worker(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    service = MLWorkerSettingsService(paths)
    worker = MLWorkerConfig(
        id="xenix.gpu",
        display_name="GPU worker",
        kind=MLWorkerKind.SSH,
        host="gpu.example.test",
        user="analyst",
        ssh_alias="xenix.gpu",
        remote_root="~/.xenix/workers/gpu",
        setup_state=MLWorkerSetupState.READY,
        last_validation=MLWorkerValidationRecord(
            status=MLWorkerValidationStatus.SUCCEEDED,
            summary="ready",
        ),
    )

    service.add_or_update_worker(worker)
    loaded = service.load()

    assert service.settings_path == paths.config / "ml_workers.json"
    assert [item.id for item in loaded.workers] == ["local", "xenix.gpu"]
    assert loaded.workers[1].target == "xenix.gpu"


def test_ssh_setup_writes_marked_xenix_config_block(tmp_path: Path) -> None:
    config_path = tmp_path / ".ssh" / "config"
    config_path.parent.mkdir()
    config_path.write_text("Host existing\n    HostName existing.example.test\n", encoding="utf-8")
    service = SshWorkerSetupService()
    worker = MLWorkerConfig(
        id="xenix.gpu",
        display_name="GPU",
        kind=MLWorkerKind.SSH,
        host="gpu.example.test",
        user="analyst",
        ssh_alias="xenix.gpu",
        identity_file_path="~/.ssh/id_xenix",
    )

    service.write_ssh_config(worker, config_path)
    service.write_ssh_config(worker.model_copy(update={"host": "gpu2.example.test"}), config_path)
    text = config_path.read_text(encoding="utf-8")

    assert "Host existing" in text
    assert text.count("# BEGIN XENIX MANAGED HOST xenix.gpu") == 1
    assert "Host xenix.gpu" in text
    assert "HostName gpu2.example.test" in text
    assert "IdentityFile ~/.ssh/id_xenix" in text
    assert config_path.with_suffix(".xenix.bak").exists()


def test_ssh_setup_without_config_uses_direct_host_when_alias_is_empty() -> None:
    service = SshWorkerSetupService()

    worker = service.build_worker(
        SshWorkerSetupInput(
            display_name="Direct worker",
            host="gpu.example.test",
            user="analyst",
            write_ssh_config=False,
        )
    )

    assert worker.id.startswith("xenix.ssh.")
    assert worker.ssh_alias == ""
    assert worker.target == "analyst@gpu.example.test"


def test_worker_pool_prefers_ready_ssh_worker_over_local(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    service = MLWorkerSettingsService(paths)
    service.save(
        MLWorkerSettings(
            workers=[
                MLWorkerConfig(
                    id="local",
                    display_name="This computer",
                    kind=MLWorkerKind.LOCAL,
                    setup_state=MLWorkerSetupState.READY,
                    last_validation=MLWorkerValidationRecord(status=MLWorkerValidationStatus.SUCCEEDED),
                ),
                MLWorkerConfig(
                    id="xenix.gpu",
                    display_name="GPU worker",
                    kind=MLWorkerKind.SSH,
                    host="gpu.example.test",
                    ssh_alias="xenix.gpu",
                    setup_state=MLWorkerSetupState.READY,
                    last_validation=MLWorkerValidationRecord(status=MLWorkerValidationStatus.SUCCEEDED),
                ),
            ]
        )
    )
    pool = MLWorkerPool(service)

    selected = pool._acquire_worker()
    try:
        assert selected.id == "xenix.gpu"
    finally:
        pool._release_worker(selected.id)


def test_worker_pool_respects_global_concurrency_cap(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    paths = ensure_app_dirs(get_app_paths())
    service = MLWorkerSettingsService(paths)
    service.save(
        MLWorkerSettings(
            pool=MLWorkerPoolConfig(max_concurrent_tasks=1),
            workers=[
                MLWorkerConfig(
                    id="xenix.gpu-a",
                    display_name="GPU A",
                    kind=MLWorkerKind.SSH,
                    host="gpu-a.example.test",
                    ssh_alias="xenix.gpu-a",
                    setup_state=MLWorkerSetupState.READY,
                    last_validation=MLWorkerValidationRecord(status=MLWorkerValidationStatus.SUCCEEDED),
                ),
                MLWorkerConfig(
                    id="xenix.gpu-b",
                    display_name="GPU B",
                    kind=MLWorkerKind.SSH,
                    host="gpu-b.example.test",
                    ssh_alias="xenix.gpu-b",
                    setup_state=MLWorkerSetupState.READY,
                    last_validation=MLWorkerValidationRecord(status=MLWorkerValidationStatus.SUCCEEDED),
                ),
            ],
        )
    )
    pool = MLWorkerPool(service)

    selected = pool._acquire_worker()
    try:
        with pool._lock:
            assert pool._select_worker_locked(service.load()) is None
    finally:
        pool._release_worker(selected.id)


def test_ssh_runner_downloads_result_and_rewrites_remote_paths(tmp_path: Path) -> None:
    task_dir = tmp_path / "local-task" / "task-1"
    task_dir.mkdir(parents=True)
    dataset = tmp_path / "dataset.csv"
    dataset.write_text("a\n1\n", encoding="utf-8")
    task_dir.joinpath("request.json").write_text(
        json.dumps({"task_id": "task-1", "input_files": [{"absolute_path": str(dataset)}]}),
        encoding="utf-8",
    )
    remote_root = "remote-root"
    fake_client = _FakeSshClient(tmp_path / "remote")
    worker = MLWorkerConfig(
        id="xenix.gpu",
        display_name="GPU",
        kind=MLWorkerKind.SSH,
        host="gpu.example.test",
        ssh_alias="xenix.gpu",
        remote_root=remote_root,
        setup_state=MLWorkerSetupState.READY,
        last_validation=MLWorkerValidationRecord(status=MLWorkerValidationStatus.SUCCEEDED),
    )

    return_code = SshMLWorkerRunner(worker, client=fake_client).run(run_apply_task, task_dir)
    result_text = task_dir.joinpath("result.json").read_text(encoding="utf-8")
    result = json.loads(result_text)

    assert return_code == 0
    assert result["output_file_path"] == str(task_dir / "output" / "predictions.csv")
    assert (task_dir / "output" / "predictions.csv").read_text(encoding="utf-8") == "prediction\n1\n"
    assert not (task_dir / "input" / "staged").exists()
    assert "remote-root" not in result_text


def test_ssh_worker_setup_wizard_saves_worker_without_password_field(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(tmp_path / "xenix-home"))
    app = QApplication.instance() or QApplication([])
    paths = ensure_app_dirs(get_app_paths())
    settings_service = MLWorkerSettingsService(paths)

    class FakeSetupService:
        def setup(self, input_data: SshWorkerSetupInput) -> SshWorkerSetupResult:
            worker = MLWorkerConfig(
                id="xenix.fake",
                display_name=input_data.display_name,
                kind=MLWorkerKind.SSH,
                host=input_data.host,
                ssh_alias="xenix.fake",
                setup_state=MLWorkerSetupState.READY,
                last_validation=MLWorkerValidationRecord(
                    status=MLWorkerValidationStatus.SUCCEEDED,
                    summary="ready",
                ),
            )
            return SshWorkerSetupResult(worker=worker, details=["ready"])

    wizard = SshWorkerSetupWizard(settings_service, setup_service=FakeSetupService())
    try:
        wizard._name_input.setText("Fake worker")
        wizard._host_input.setText("fake.example.test")
        wizard._run_setup()
        for _ in range(100):
            app.processEvents()
            if settings_service.load().workers[-1].id == "xenix.fake":
                break
            time.sleep(0.01)
        loaded = settings_service.load()
        assert loaded.workers[-1].id == "xenix.fake"
        assert not hasattr(wizard, "_password_input")
        assert not hasattr(wizard, "_passphrase_input")
    finally:
        wizard.close()


class _FakeSshClient:
    def __init__(self, root: Path) -> None:
        self._root = root

    def run(self, remote_command: str, *, check: bool = False, timeout=None):
        if "test -f" in remote_command:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        for path in _quoted_paths_after(remote_command, "mkdir -p"):
            self._map(path).mkdir(parents=True, exist_ok=True)
        for path in _quoted_paths_after(remote_command, "touch"):
            self._map(path).parent.mkdir(parents=True, exist_ok=True)
            self._map(path).write_text("", encoding="utf-8")
        if "remote_worker" in remote_command:
            remote_task = remote_command.split("'")[-2]
            output = self._map(f"{remote_task}/output/predictions.csv")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("prediction\n1\n", encoding="utf-8")
            self._map(f"{remote_task}/result.json").write_text(
                (
                    "{"
                    f'"task_id": "task-1", "trained_model_id": "model-1", "model_key": "regression.ridge", '
                    f'"output_file_path": "{remote_task}/output/predictions.csv", '
                    '"summary": {"row_count": 1, "input_file_count": 1, "prediction_column_name": "prediction"}'
                    "}"
                ),
                encoding="utf-8",
            )
            self._map(f"{remote_task}/logs.jsonl").write_text("", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def upload(self, local_path: Path, remote_path: str) -> None:
        destination = self._map(remote_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_path, destination)

    def upload_tree(self, local_path: Path, remote_parent: str) -> None:
        destination = self._map(remote_parent) / local_path.name
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(local_path, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    def download(self, remote_path: str, local_path: Path) -> bool:
        source = self._map(remote_path)
        if not source.exists():
            return False
        local_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, local_path)
        return True

    def download_tree_contents(self, remote_dir: str, local_dir: Path) -> None:
        source = self._map(remote_dir)
        local_dir.mkdir(parents=True, exist_ok=True)
        if not source.exists():
            return
        for item in source.iterdir():
            destination = local_dir / item.name
            if item.is_dir():
                if destination.exists():
                    shutil.rmtree(destination)
                shutil.copytree(item, destination)
            else:
                shutil.copy2(item, destination)

    def _map(self, remote_path: str) -> Path:
        path = self._root
        for part in remote_path.strip("/").split("/"):
            if part:
                path = path / part
        return path


def _quoted_paths_after(command: str, prefix: str) -> list[str]:
    paths: list[str] = []
    marker = f"{prefix} '"
    start = 0
    while True:
        index = command.find(marker, start)
        if index < 0:
            return paths
        begin = index + len(marker)
        end = command.find("'", begin)
        if end < 0:
            return paths
        paths.append(command[begin:end])
        start = end + 1

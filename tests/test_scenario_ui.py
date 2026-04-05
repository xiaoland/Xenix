import threading
import time
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from xenix.app import build_main_window
from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.dataset_service import DatasetService
from xenix.services.ml_service import MLService
from xenix.services.ml_task_service import MLTaskService
from xenix.services.project_service import ProjectService
from xenix.services.scenario_template_service import ScenarioTemplateService
from xenix.services.scenario_workflow_service import PrepareScenarioWorkItemInput, ScenarioWorkflowService
from xenix.services.storage import StorageBootstrapService
from xenix.services.work_item_service import WorkItemService
from xenix.ui.scenario_data_preparation_dialog import ScenarioDataPreparationDialog
from xenix.ui.scenario_training_dialog import ScenarioTrainingDialog


@pytest.fixture()
def app(monkeypatch) -> QApplication:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance()
    if instance is not None:
        return instance
    return QApplication([])


def test_scenario_home_card_opens_data_preparation_dialog(
    monkeypatch,
    tmp_path: Path,
    app: QApplication,
) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    _app, window = build_main_window(show=False)
    try:
        window._home_view._scenario_buttons["sales_demand_forecast.v1"].click()
        app.processEvents()

        assert isinstance(window._scenario_data_preparation_dialog, ScenarioDataPreparationDialog)
        assert window._scenario_data_preparation_dialog.isVisible()
        assert window._scenario_data_preparation_dialog.windowTitle() == "Prepare Scenario Data"
    finally:
        if window._scenario_data_preparation_dialog is not None:
            window._scenario_data_preparation_dialog.close()
        window._ml_workspace._timer.stop()
        window.close()


def test_scenario_training_dialog_starts_a_run_for_prepared_work_item(
    monkeypatch,
    tmp_path: Path,
    app: QApplication,
) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    project_service = ProjectService(context.session_factory)
    work_item_service = WorkItemService(context.session_factory, paths)
    dataset_service = DatasetService(context.session_factory, paths)
    ml_task_service = MLTaskService(context.session_factory, paths)
    ml_service = MLService(
        paths,
        context.session_factory,
        dataset_service,
        work_item_service,
        ml_task_service,
    )
    template_service = ScenarioTemplateService()
    workflow_service = ScenarioWorkflowService(
        project_service=project_service,
        work_item_service=work_item_service,
        dataset_service=dataset_service,
        ml_service=ml_service,
        template_service=template_service,
    )
    dataset_file = tmp_path / "demand.csv"
    dataset_file.write_text(
        "feature_a,feature_b,target\n"
        "1,2,5\n"
        "2,1,5\n"
        "3,5,11\n"
        "4,2,10\n",
        encoding="utf-8",
    )
    prepared = workflow_service.prepare_work_item(
        PrepareScenarioWorkItemInput(
            template_key="sales_demand_forecast.v1",
            source_path=str(dataset_file.resolve()),
            feature_columns=["feature_a", "feature_b"],
            target_columns=["target"],
        )
    )
    template = template_service.get_template(prepared.template_key)

    dialog = ScenarioTrainingDialog(
        template=template,
        preparation_result=prepared,
        workflow_service=workflow_service,
        ml_service=ml_service,
    )
    try:
        dialog.show()
        app.processEvents()

        assert dialog.isVisible()
        assert dialog._current_run is not None
        assert len(dialog._current_run.root_task_ids) == 3
        assert dialog.windowTitle() == "Training Dashboard"
        assert dialog._title_label.text() == "Sales Demand Forecast"
        assert dialog._step_table.rowCount() == 3
        assert dialog._continue_button.isEnabled() is False
    finally:
        dialog.close()


def test_scenario_data_preparation_dialog_shows_busy_state_while_inspecting_dataset(
    monkeypatch,
    tmp_path: Path,
    app: QApplication,
) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    paths = ensure_app_dirs(get_app_paths())
    context = StorageBootstrapService().initialize(paths)
    project_service = ProjectService(context.session_factory)
    work_item_service = WorkItemService(context.session_factory, paths)
    dataset_service = DatasetService(context.session_factory, paths)
    ml_task_service = MLTaskService(context.session_factory, paths)
    ml_service = MLService(
        paths,
        context.session_factory,
        dataset_service,
        work_item_service,
        ml_task_service,
    )
    template_service = ScenarioTemplateService()
    workflow_service = ScenarioWorkflowService(
        project_service=project_service,
        work_item_service=work_item_service,
        dataset_service=dataset_service,
        ml_service=ml_service,
        template_service=template_service,
    )

    dataset_file = tmp_path / "slow-demand.csv"
    dataset_file.write_text(
        "feature_a,feature_b,target\n"
        "1,2,5\n"
        "2,1,5\n"
        "3,5,11\n",
        encoding="utf-8",
    )

    started = threading.Event()
    release = threading.Event()
    original_inspect = dataset_service.inspect_source_file

    def slow_inspect(input_data):
        started.set()
        if not release.wait(timeout=5):
            raise AssertionError("Timed out waiting to release the slow inspection stub.")
        return original_inspect(input_data)

    monkeypatch.setattr(dataset_service, "inspect_source_file", slow_inspect)
    dialog = ScenarioDataPreparationDialog(
        template=template_service.get_template("sales_demand_forecast.v1"),
        dataset_service=dataset_service,
        workflow_service=workflow_service,
    )
    try:
        dialog.show()
        dialog._inspect_path(str(dataset_file.resolve()))

        deadline = time.time() + 5
        while not started.is_set() and time.time() < deadline:
            app.processEvents()
            time.sleep(0.01)

        assert started.is_set()
        app.processEvents()
        assert dialog._busy_indicator.isVisible()
        assert dialog._busy_label.isVisible()
        assert dialog._busy_label.text() == "Inspecting dataset..."
        assert dialog._choose_file_button.isEnabled() is False
        assert dialog._continue_button.isEnabled() is False

        release.set()
        deadline = time.time() + 5
        while dialog._busy_indicator.isVisible() and time.time() < deadline:
            app.processEvents()
            time.sleep(0.01)

        assert dialog._busy_indicator.isVisible() is False
        assert dialog._current_inspection is not None
        assert dialog._continue_button.isEnabled() is True
    finally:
        release.set()
        dialog.close()

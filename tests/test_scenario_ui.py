import shutil
import threading
import time
from pathlib import Path
from uuid import uuid4

import pytest
from PySide6.QtWidgets import QApplication, QPlainTextEdit

from xenix.datetime_utils import format_datetime_for_display

from xenix.app import build_main_window
from xenix.config import ensure_app_dirs, get_app_paths
from xenix.services.dataset_inspection import DatasetColumnKind, DatasetColumnMetadata
from xenix.services.dataset_service import DatasetService
from xenix.services.ml_service import FitWithEvaluateInput, MLService
from xenix.services.ml_task_service import MLTaskService
from xenix.services.project_service import ProjectService
from xenix.services.scenario_model_source_service import (
    ListCompatibleTrainedModelsInput,
    ScenarioModelSourceService,
)
from xenix.services.scenario_template_service import ScenarioTemplateService, ScenarioTrainingOperation
from xenix.services.scenario_training_preset_service import ScenarioTrainingPresetService
from xenix.services.scenario_workflow_service import (
    PrepareScenarioWorkItemInput,
    ScenarioTrainingRun,
    ScenarioTrainingRunSnapshot,
    ScenarioTrainingStepSnapshot,
    ScenarioTrainingStepStatus,
    ScenarioWorkflowService,
    StartScenarioTrainingRunInput,
)
from xenix.services.storage import StorageBootstrapService
from xenix.services.storage.models import MLTaskStatus, MLTaskType
from xenix.services.work_item_service import WorkItemService
from xenix.ui.scenario_data_preparation_dialog import ScenarioDataPreparationDialog
from xenix.ui.inference_history_dialog import InferenceHistoryDialog
from xenix.ui.scenario_inference_dialog import ScenarioInferenceDialog
from xenix.ui.scenario_model_source_dialog import ScenarioModelSourceDialog, ScenarioModelSourceKind
from xenix.ui.scenario_training_dialog import ScenarioTrainingDialog
from xenix.ui.scenario_training_selection_dialog import ScenarioTrainingSelectionDialog
from xenix.ui.widgets.column_selection import ColumnSelectionWidget


@pytest.fixture()
def app(monkeypatch) -> QApplication:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance()
    if instance is not None:
        return instance
    return QApplication([])


@pytest.fixture()
def tmp_path() -> Path:
    root = Path.cwd() / ".codex-test-tmp"
    root.mkdir(parents=True, exist_ok=True)
    path = root / uuid4().hex
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
        try:
            root.rmdir()
        except OSError:
            pass


def test_prediction_scenario_card_opens_data_preparation_dialog(
    monkeypatch,
    tmp_path: Path,
    app: QApplication,
) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    _app, window = build_main_window(show=False)
    try:
        assert window._home_view._analysis_buttons["prediction"].isEnabled() is True
        assert window._home_view._analysis_buttons["classification"].isEnabled() is True
        assert window._home_view._analysis_buttons["clustering"].isEnabled() is False

        window._home_view._analysis_buttons["prediction"].click()
        app.processEvents()

        assert isinstance(window._scenario_data_preparation_dialog, ScenarioDataPreparationDialog)
        assert window._scenario_data_preparation_dialog.isVisible()
        assert window._scenario_data_preparation_dialog.windowTitle() == "Prepare Scenario Data"
    finally:
        if window._scenario_data_preparation_dialog is not None:
            window._scenario_data_preparation_dialog.close()
        window._ml_workspace._timer.stop()
        window.close()


def test_history_button_opens_history_dialog(
    monkeypatch,
    tmp_path: Path,
    app: QApplication,
) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    _app, window = build_main_window(show=False)
    try:
        window._home_view._history_button.click()
        app.processEvents()

        assert isinstance(window._inference_history_dialog, InferenceHistoryDialog)
        assert window._inference_history_dialog.isVisible()
        assert window._inference_history_dialog.windowTitle() == "History"
    finally:
        if window._inference_history_dialog is not None:
            window._inference_history_dialog.close()
        window._ml_workspace._timer.stop()
        window.close()


def test_column_selection_widget_uses_checkbox_groups_for_single_target_selection(
    app: QApplication,
) -> None:
    widget = ColumnSelectionWidget(single_target_selection=True)
    widget.set_columns(
        [
            DatasetColumnMetadata(name="feature_a", kind=DatasetColumnKind.NUMERIC, nullable=False),
            DatasetColumnMetadata(name="feature_b", kind=DatasetColumnKind.NUMERIC, nullable=False),
            DatasetColumnMetadata(name="target", kind=DatasetColumnKind.NUMERIC, nullable=False),
        ]
    )
    try:
        widget.show()
        app.processEvents()

        widget._target_checkboxes["target"].setChecked(True)
        widget._feature_checkboxes["feature_a"].setChecked(True)
        widget._feature_checkboxes["feature_b"].setChecked(True)
        app.processEvents()

        assert widget.selected_target_columns() == ["target"]
        assert widget.selected_feature_columns() == ["feature_a", "feature_b"]

        widget._target_checkboxes["feature_a"].setChecked(True)
        app.processEvents()

        assert widget.selected_target_columns() == ["feature_a"]
        assert widget.selected_feature_columns() == ["feature_b"]
        assert widget._feature_checkboxes["feature_a"].isChecked() is False

        widget._feature_checkboxes["feature_b"].setChecked(False)
        app.processEvents()

        assert widget.selected_feature_columns() == []
    finally:
        widget.close()


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
    fake_run = ScenarioTrainingRun(
        template_key=template.key,
        work_item_id=prepared.work_item_id,
        root_task_ids=["root-1", "root-2", "root-3"],
    )

    def fake_start_training_run(_input):
        return fake_run

    def fake_get_training_run_snapshot(_run):
        return ScenarioTrainingRunSnapshot(
            template_key=template.key,
            work_item_id=prepared.work_item_id,
            step_snapshots=[
                ScenarioTrainingStepSnapshot(
                    step_key=step.step_key,
                    operation=step.operation,
                    model_key=step.model_key,
                    model_display_name=step.model_key,
                    root_task_id=fake_run.root_task_ids[index],
                    root_status=MLTaskStatus.PENDING,
                    status=ScenarioTrainingStepStatus.RUNNING,
                )
                for index, step in enumerate(template.training_plan)
            ],
            best_trained_model_id=None,
            is_terminal=False,
            can_proceed_to_inference=False,
        )

    monkeypatch.setattr(workflow_service, "start_training_run", fake_start_training_run)
    monkeypatch.setattr(workflow_service, "get_training_run_snapshot", fake_get_training_run_snapshot)

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
        assert len(dialog._result_cards) == 3
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
        assert dialog._summary_widget._preview_table.rowCount() == 3
        assert dialog._summary_widget._preview_table.columnCount() == 3
        assert dialog._continue_button.isEnabled() is False

        dialog._column_selection._target_checkboxes["target"].setChecked(True)
        dialog._column_selection._feature_checkboxes["feature_a"].setChecked(True)
        app.processEvents()

        assert dialog._continue_button.isEnabled() is True
    finally:
        release.set()
        dialog.close()


def test_scenario_model_source_dialog_lists_compatible_trained_models_for_matching_columns(
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
    model_source_service = ScenarioModelSourceService(context.session_factory, template_service)

    dataset_file = tmp_path / "source-demand.csv"
    dataset_file.write_text(
        "feature_a,feature_b,target\n"
        "1,2,5\n"
        "2,1,5\n"
        "3,5,11\n"
        "4,2,10\n"
        "5,3,13\n"
        "6,6,18\n"
        "7,5,19\n"
        "8,4,20\n"
        "9,7,25\n"
        "10,8,28\n",
        encoding="utf-8",
    )
    trained_prepared = workflow_service.prepare_work_item(
        PrepareScenarioWorkItemInput(
            template_key="sales_demand_forecast.v1",
            source_path=str(dataset_file.resolve()),
            feature_columns=["feature_a", "feature_b"],
            target_columns=["target"],
            work_item_name="existing-demand-model",
        )
    )
    ml_service.fit_with_evaluate(
        FitWithEvaluateInput(
            work_item_id=trained_prepared.work_item_id,
            model_key="regression.linear",
            params={"fit_intercept": True},
        )
    )

    deadline = time.time() + 60
    while time.time() < deadline:
        work_item = work_item_service.get_work_item(trained_prepared.work_item_id)
        if work_item.best_trained_model_id is not None:
            break
        time.sleep(0.1)
    else:
        raise AssertionError("Timed out waiting for a compatible trained model.")

    prepared_for_selection = workflow_service.prepare_work_item(
        PrepareScenarioWorkItemInput(
            template_key="sales_demand_forecast.v1",
            source_path=str(dataset_file.resolve()),
            feature_columns=["feature_a", "feature_b"],
            target_columns=["target"],
            work_item_name="new-demand-run",
        )
    )
    compatible_models = model_source_service.list_compatible_trained_models(
        ListCompatibleTrainedModelsInput(
            template_key=prepared_for_selection.template_key,
            feature_columns=prepared_for_selection.feature_columns,
            target_columns=prepared_for_selection.target_columns,
        )
    )
    assert len(compatible_models) >= 1

    dialog = ScenarioModelSourceDialog(
        template=template_service.get_template(prepared_for_selection.template_key),
        preparation_result=prepared_for_selection,
        model_source_service=model_source_service,
    )
    try:
        dialog.show()
        app.processEvents()

        assert dialog._model_list.count() >= 1
        assert dialog._train_new_button.isEnabled() is True
        assert dialog._use_trained_button.isEnabled() is False

        dialog._model_list.setCurrentRow(0)
        app.processEvents()

        selected_option = dialog.selected_trained_model()
        assert selected_option is not None
        assert selected_option.created_at.tzinfo is not None
        assert dialog._use_trained_button.isEnabled() is True
        assert format_datetime_for_display(
            selected_option.created_at,
            format_string="%Y-%m-%d %H:%M",
        ) in dialog._selected_model_label.text()
        dialog._choose_trained_model_branch()
        assert dialog.selected_source_kind() is ScenarioModelSourceKind.TRAINED_MODEL
        assert dialog.selected_trained_model() is not None
    finally:
        dialog.close()


def test_scenario_training_selection_dialog_persists_default_model_selection(
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
    preset_service = ScenarioTrainingPresetService(paths, template_service)
    workflow_service = ScenarioWorkflowService(
        project_service=project_service,
        work_item_service=work_item_service,
        dataset_service=dataset_service,
        ml_service=ml_service,
        template_service=template_service,
    )

    dataset_file = tmp_path / "selection-demand.csv"
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

    dialog = ScenarioTrainingSelectionDialog(
        template=template,
        preparation_result=prepared,
        training_preset_service=preset_service,
    )
    try:
        dialog.show()
        app.processEvents()

        assert dialog.isVisible()
        assert dialog.windowTitle() == "Choose Models and Train"
        assert [step.model_key for step in dialog.selected_steps()] == [
            "regression.linear",
            "regression.ridge",
            "regression.random_forest",
        ]

        dialog._model_cards["regression.ridge"]._selected_checkbox.setChecked(False)
        dialog._model_cards["regression.random_forest"]._selected_checkbox.setChecked(False)
        app.processEvents()
        dialog._save_defaults_button.click()
        app.processEvents()

        assert [step.model_key for step in dialog.selected_steps()] == ["regression.linear"]
        assert dialog._message_label.text() == "Saved the current model selection as the default."
    finally:
        dialog.close()

    second_dialog = ScenarioTrainingSelectionDialog(
        template=template,
        preparation_result=prepared,
        training_preset_service=preset_service,
    )
    try:
        second_dialog.show()
        app.processEvents()

        assert [step.model_key for step in second_dialog.selected_steps()] == ["regression.linear"]
    finally:
        second_dialog.close()


def test_scenario_training_selection_dialog_switches_to_multivalue_param_grid_inputs(
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
    preset_service = ScenarioTrainingPresetService(paths, template_service)
    workflow_service = ScenarioWorkflowService(
        project_service=project_service,
        work_item_service=work_item_service,
        dataset_service=dataset_service,
        ml_service=ml_service,
        template_service=template_service,
    )

    dataset_file = tmp_path / "linear-demand.csv"
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

    dialog = ScenarioTrainingSelectionDialog(
        template=template,
        preparation_result=prepared,
        training_preset_service=preset_service,
    )
    try:
        dialog.show()
        app.processEvents()

        linear_card = dialog._model_cards["regression.linear"]
        tuning_index = linear_card._operation_selector.findData(ScenarioTrainingOperation.HYPERPARAMETER_TUNING)
        linear_card._operation_selector.setCurrentIndex(tuning_index)
        app.processEvents()

        binding = linear_card._config_form._bindings["fit_intercept"]
        assert isinstance(binding.widget, QPlainTextEdit)
        binding.widget.setPlainText("true\nfalse")  # type: ignore[union-attr]

        selected_step = linear_card.selected_step()
        assert selected_step is not None
        assert selected_step.operation.value == "hyperparameter_tuning"
        assert selected_step.param_grid == {"fit_intercept": [True, False]}
    finally:
        dialog.close()


def test_main_window_opens_model_source_dialog_after_preparation(
    monkeypatch,
    tmp_path: Path,
    app: QApplication,
) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    dataset_file = tmp_path / "prepared-demand.csv"
    dataset_file.write_text(
        "feature_a,feature_b,target\n"
        "1,2,5\n"
        "2,1,5\n"
        "3,5,11\n"
        "4,2,10\n",
        encoding="utf-8",
    )
    _app, window = build_main_window(show=False)
    try:
        prepared = window._scenario_workflow_service.prepare_work_item(
            PrepareScenarioWorkItemInput(
                template_key="sales_demand_forecast.v1",
                source_path=str(dataset_file.resolve()),
                feature_columns=["feature_a", "feature_b"],
                target_columns=["target"],
            )
        )

        class _PreparedDialogStub:
            def preparation_result(self_nonlocal):
                return prepared

        window._scenario_data_preparation_dialog = _PreparedDialogStub()
        window._open_model_source_after_preparation()
        app.processEvents()

        assert isinstance(window._scenario_model_source_dialog, ScenarioModelSourceDialog)
        assert window._scenario_model_source_dialog.isVisible()
        assert window._scenario_model_source_dialog.windowTitle() == "Choose Model Source"
    finally:
        if window._scenario_model_source_dialog is not None:
            window._scenario_model_source_dialog.close()
        window._ml_workspace._timer.stop()
        window.close()


def test_main_window_train_new_flow_opens_training_selection_and_starts_selected_steps(
    monkeypatch,
    tmp_path: Path,
    app: QApplication,
) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    dataset_file = tmp_path / "train-new-demand.csv"
    dataset_file.write_text(
        "feature_a,feature_b,target\n"
        "1,2,5\n"
        "2,1,5\n"
        "3,5,11\n"
        "4,2,10\n",
        encoding="utf-8",
    )
    _app, window = build_main_window(show=False)
    captured_inputs: list[StartScenarioTrainingRunInput] = []

    def fake_start_training_run(input_data: StartScenarioTrainingRunInput) -> ScenarioTrainingRun:
        captured_inputs.append(input_data)
        return ScenarioTrainingRun(
            template_key=input_data.template_key,
            work_item_id=input_data.work_item_id,
            steps=input_data.selected_steps,
            root_task_ids=[f"root-{index + 1}" for index, _step in enumerate(input_data.selected_steps)],
        )

    def fake_get_training_run_snapshot(run: ScenarioTrainingRun) -> ScenarioTrainingRunSnapshot:
        return ScenarioTrainingRunSnapshot(
            template_key=run.template_key,
            work_item_id=run.work_item_id,
            step_snapshots=[
                ScenarioTrainingStepSnapshot(
                    step_key=step.step_key,
                    operation=step.operation,
                    model_key=step.model_key,
                    model_display_name=step.model_key,
                    root_task_id=run.root_task_ids[index],
                    root_status=MLTaskStatus.PENDING,
                    status=ScenarioTrainingStepStatus.RUNNING,
                )
                for index, step in enumerate(run.steps)
            ],
            best_trained_model_id=None,
            is_terminal=False,
            can_proceed_to_inference=False,
        )

    monkeypatch.setattr(window._scenario_workflow_service, "start_training_run", fake_start_training_run)
    monkeypatch.setattr(window._scenario_workflow_service, "get_training_run_snapshot", fake_get_training_run_snapshot)

    try:
        prepared = window._scenario_workflow_service.prepare_work_item(
            PrepareScenarioWorkItemInput(
                template_key="sales_demand_forecast.v1",
                source_path=str(dataset_file.resolve()),
                feature_columns=["feature_a", "feature_b"],
                target_columns=["target"],
            )
        )

        class _PreparedDialogStub:
            def preparation_result(self_nonlocal):
                return prepared

        class _ModelSourceDialogStub:
            def selected_source_kind(self_nonlocal):
                return ScenarioModelSourceKind.TRAIN_NEW

        window._scenario_data_preparation_dialog = _PreparedDialogStub()
        window._scenario_model_source_dialog = _ModelSourceDialogStub()

        window._continue_after_model_source_selection()
        app.processEvents()

        assert isinstance(window._scenario_training_selection_dialog, ScenarioTrainingSelectionDialog)
        assert window._scenario_training_selection_dialog.isVisible()

        window._scenario_training_selection_dialog._model_cards["regression.ridge"]._selected_checkbox.setChecked(False)
        window._scenario_training_selection_dialog._model_cards["regression.random_forest"]._selected_checkbox.setChecked(False)
        app.processEvents()
        window._scenario_training_selection_dialog._start_training_button.click()
        app.processEvents()

        assert len(captured_inputs) == 1
        assert [step.model_key for step in captured_inputs[0].selected_steps] == ["regression.linear"]
        assert isinstance(window._scenario_training_dialog, ScenarioTrainingDialog)
        assert window._scenario_training_dialog.isVisible()
        assert len(window._scenario_training_dialog._result_cards) == 1
    finally:
        if window._scenario_training_selection_dialog is not None:
            window._scenario_training_selection_dialog.close()
        if window._scenario_training_dialog is not None:
            window._scenario_training_dialog.close()
        window._ml_workspace._timer.stop()
        window.close()


def test_main_window_trained_model_flow_opens_inference_with_selected_compatible_model(
    monkeypatch,
    tmp_path: Path,
    app: QApplication,
) -> None:
    runtime_home = tmp_path / "xenix-home"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("XENIX_APP_HOME", str(runtime_home))

    dataset_file = tmp_path / "reuse-demand.csv"
    dataset_file.write_text(
        "feature_a,feature_b,target\n"
        "1,2,5\n"
        "2,1,5\n"
        "3,5,11\n"
        "4,2,10\n",
        encoding="utf-8",
    )
    _app, window = build_main_window(show=False)
    try:
        source_prepared = window._scenario_workflow_service.prepare_work_item(
            PrepareScenarioWorkItemInput(
                template_key="sales_demand_forecast.v1",
                source_path=str(dataset_file.resolve()),
                feature_columns=["feature_a", "feature_b"],
                target_columns=["target"],
                work_item_name="source-model-run",
            )
        )
        window._ml_service.fit_with_evaluate(
            FitWithEvaluateInput(
                work_item_id=source_prepared.work_item_id,
                model_key="regression.linear",
                params={"fit_intercept": True},
            )
        )

        deadline = time.time() + 60
        while time.time() < deadline:
            source_work_item = window._work_item_service.get_work_item(source_prepared.work_item_id)
            if source_work_item.best_trained_model_id is not None:
                break
            time.sleep(0.1)
        else:
            raise AssertionError("Timed out waiting for the source work item to get a best model.")

        prepared = window._scenario_workflow_service.prepare_work_item(
            PrepareScenarioWorkItemInput(
                template_key="sales_demand_forecast.v1",
                source_path=str(dataset_file.resolve()),
                feature_columns=["feature_a", "feature_b"],
                target_columns=["target"],
                work_item_name="reuse-target-run",
            )
        )
        compatible_models = window._scenario_model_source_service.list_compatible_trained_models(
            ListCompatibleTrainedModelsInput(
                template_key=prepared.template_key,
                feature_columns=prepared.feature_columns,
                target_columns=prepared.target_columns,
            )
        )
        assert compatible_models
        selected_model = compatible_models[0]

        class _PreparedDialogStub:
            def preparation_result(self_nonlocal):
                return prepared

        class _ModelSourceDialogStub:
            def selected_source_kind(self_nonlocal):
                return ScenarioModelSourceKind.TRAINED_MODEL

            def selected_trained_model(self_nonlocal):
                return selected_model

            def compatible_models(self_nonlocal):
                return compatible_models

        window._scenario_data_preparation_dialog = _PreparedDialogStub()
        window._scenario_model_source_dialog = _ModelSourceDialogStub()

        window._continue_after_model_source_selection()
        app.processEvents()

        assert isinstance(window._scenario_inference_dialog, ScenarioInferenceDialog)
        assert window._scenario_inference_dialog.isVisible()
        assert window._scenario_inference_dialog._current_model_id() == selected_model.trained_model_id
    finally:
        if window._scenario_inference_dialog is not None:
            window._scenario_inference_dialog.close()
        window._ml_workspace._timer.stop()
        window.close()


def test_scenario_training_dialog_shows_regression_result_cards_with_metrics_and_save_state(
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
    dataset_file = tmp_path / "metrics-demand.csv"
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
    fake_run = ScenarioTrainingRun(
        template_key=template.key,
        work_item_id=prepared.work_item_id,
        steps=template.training_plan[:1],
        root_task_ids=["root-1"],
    )

    def fake_start_training_run(_input):
        return fake_run

    def fake_get_training_run_snapshot(_run):
        return ScenarioTrainingRunSnapshot(
            template_key=template.key,
            work_item_id=prepared.work_item_id,
            step_snapshots=[
                ScenarioTrainingStepSnapshot(
                    step_key="fit_linear",
                    operation=template.training_plan[0].operation,
                    model_key="regression.linear",
                    model_display_name="Linear Regression",
                    root_task_id="root-1",
                    root_status=MLTaskStatus.SUCCEEDED,
                    evaluate_task_id="eval-1",
                    evaluate_status=MLTaskStatus.SUCCEEDED,
                    trained_model_id="trained-1",
                    training_params={"fit_intercept": True},
                    evaluation_metrics={"r2": 0.9123, "rmse": 1.5, "mae": 1.0},
                    primary_metric_name="r2",
                    primary_metric_value=0.9123,
                    status=ScenarioTrainingStepStatus.SUCCEEDED,
                )
            ],
            best_trained_model_id="trained-1",
            is_terminal=True,
            can_proceed_to_inference=True,
        )

    monkeypatch.setattr(workflow_service, "start_training_run", fake_start_training_run)
    monkeypatch.setattr(workflow_service, "get_training_run_snapshot", fake_get_training_run_snapshot)

    dialog = ScenarioTrainingDialog(
        template=template,
        preparation_result=prepared,
        workflow_service=workflow_service,
        ml_service=ml_service,
    )
    try:
        dialog.show()
        app.processEvents()

        assert len(dialog._result_cards) == 1
        card = dialog._result_cards["fit_linear"]
        assert "R²" in card._metrics_label.text()
        assert "MSE" in card._metrics_label.text()
        assert "saved automatically" in card._save_state_label.text().lower()
        assert "Best Model" in card._title_label.text()
        assert dialog._continue_button.isEnabled() is True
    finally:
        dialog.close()


def test_scenario_inference_dialog_queues_manual_prediction_with_best_model(
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

    dataset_file = tmp_path / "predict-demand.csv"
    dataset_file.write_text(
        "feature_a,feature_b,target\n"
        "1,2,5\n"
        "2,1,5\n"
        "3,5,11\n"
        "4,2,10\n"
        "5,3,13\n"
        "6,6,18\n"
        "7,5,19\n"
        "8,4,20\n"
        "9,7,25\n"
        "10,8,28\n",
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
    ml_service.fit_with_evaluate(
        FitWithEvaluateInput(
            work_item_id=prepared.work_item_id,
            model_key="regression.linear",
            params={"fit_intercept": True},
        )
    )

    deadline = time.time() + 60
    while time.time() < deadline:
        work_item = work_item_service.get_work_item(prepared.work_item_id)
        if work_item.best_trained_model_id is not None:
            break
        time.sleep(0.1)
    else:
        raise AssertionError("Timed out waiting for the scenario work item to get a best model.")

    monkeypatch.setattr("xenix.ui.scenario_inference_dialog.QMessageBox.information", lambda *args, **kwargs: None)
    dialog = ScenarioInferenceDialog(
        template=template,
        preparation_result=prepared,
        work_item_service=work_item_service,
        dataset_service=dataset_service,
        ml_service=ml_service,
    )
    try:
        dialog.show()
        app.processEvents()

        assert dialog.windowTitle() == "Prediction"
        assert dialog._title_label.text() == "Sales Demand Forecast"
        assert dialog._best_model_label.text().startswith("Best model selected:")
        assert dialog._manual_submit_button.isEnabled() is False

        dialog._row_editor._table.item(0, 0).setText("11")
        app.processEvents()
        assert dialog._manual_submit_button.isEnabled() is False
        dialog._row_editor._table.item(0, 1).setText("9")
        app.processEvents()
        assert dialog._manual_submit_button.isEnabled() is True
        dialog._submit_manual_inference()
        app.processEvents()

        inference_tasks = [
            task
            for task in ml_service.list_work_item_tasks(prepared.work_item_id)
            if task.task_type is MLTaskType.INFERENCE
        ]
        assert len(inference_tasks) == 1
        assert dialog._task_table.rowCount() == 1

        inference_task_id = inference_tasks[0].id
        deadline = time.time() + 60
        while time.time() < deadline:
            inference_task = next(
                task
                for task in ml_service.list_work_item_tasks(prepared.work_item_id)
                if task.id == inference_task_id
            )
            if inference_task.status in {MLTaskStatus.SUCCEEDED, MLTaskStatus.FAILED, MLTaskStatus.CANCELLED}:
                break
            time.sleep(0.1)
        else:
            raise AssertionError("Timed out waiting for the scenario prediction task to finish.")

        dialog.refresh_runtime()
        app.processEvents()

        assert dialog._result_group.title() == "Prediction Result"
        assert dialog._result_table.columnCount() >= 3
        assert "prediction" in [
            dialog._result_table.horizontalHeaderItem(index).text()
            for index in range(dialog._result_table.columnCount())
        ]
        assert "Output column: prediction" in dialog._result_summary_label.text()
    finally:
        dialog.close()


def test_scenario_inference_dialog_uses_selected_model_and_previews_batch_input(
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

    dataset_file = tmp_path / "predict-selected-model.csv"
    dataset_file.write_text(
        "feature_a,feature_b,target\n"
        "1,2,5\n"
        "2,1,5\n"
        "3,5,11\n"
        "4,2,10\n"
        "5,3,13\n"
        "6,6,18\n"
        "7,5,19\n"
        "8,4,20\n"
        "9,7,25\n"
        "10,8,28\n",
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

    ml_service.fit_with_evaluate(
        FitWithEvaluateInput(
            work_item_id=prepared.work_item_id,
            model_key="regression.linear",
            params={"fit_intercept": True},
        )
    )
    ml_service.fit_with_evaluate(
        FitWithEvaluateInput(
            work_item_id=prepared.work_item_id,
            model_key="regression.ridge",
            params={"alpha": 1.0},
        )
    )

    deadline = time.time() + 60
    while time.time() < deadline:
        trained_models = ml_service.list_trained_models(prepared.work_item_id)
        if len(trained_models) >= 2:
            break
        time.sleep(0.1)
    else:
        raise AssertionError("Timed out waiting for two trained models.")

    batch_file = tmp_path / "batch-preview.csv"
    batch_file.write_text(
        "feature_a,feature_b\n"
        "11,9\n"
        "12,10\n"
        "13,11\n"
        "14,12\n"
        "15,13\n"
        "16,14\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("xenix.ui.scenario_inference_dialog.QMessageBox.information", lambda *args, **kwargs: None)
    dialog = ScenarioInferenceDialog(
        template=template,
        preparation_result=prepared,
        work_item_service=work_item_service,
        dataset_service=dataset_service,
        ml_service=ml_service,
    )
    try:
        dialog.show()
        app.processEvents()

        assert dialog._model_selector.count() >= 2
        dialog._load_batch_files([str(batch_file.resolve())])
        app.processEvents()

        assert dialog._batch_submit_button.isEnabled() is True
        assert dialog._batch_preview_table.rowCount() == 5
        assert "batch-preview.csv" in dialog._batch_preview_summary_label.text()

        selected_index = dialog._model_selector.findText("Ridge Regression")
        if selected_index < 0:
            selected_index = dialog._model_selector.findText("[Best] Ridge Regression")
        assert selected_index >= 0
        dialog._model_selector.setCurrentIndex(selected_index)
        app.processEvents()

        selected_model_id = dialog._current_model_id()
        assert selected_model_id is not None

        dialog._submit_batch_inference()
        app.processEvents()

        inference_tasks = [
            task
            for task in ml_service.list_work_item_tasks(prepared.work_item_id)
            if task.task_type is MLTaskType.INFERENCE
        ]
        assert len(inference_tasks) >= 1
        latest_task = inference_tasks[-1]
        assert latest_task.request_payload["inference_model"]["trained_model_id"] == selected_model_id
    finally:
        dialog.close()


def test_scenario_inference_dialog_reuses_compatible_model_from_previous_work_item(
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
    model_source_service = ScenarioModelSourceService(context.session_factory, template_service)

    dataset_file = tmp_path / "reuse-model-demand.csv"
    dataset_file.write_text(
        "feature_a,feature_b,target\n"
        "1,2,5\n"
        "2,1,5\n"
        "3,5,11\n"
        "4,2,10\n"
        "5,3,13\n"
        "6,6,18\n"
        "7,5,19\n"
        "8,4,20\n"
        "9,7,25\n"
        "10,8,28\n",
        encoding="utf-8",
    )
    source_prepared = workflow_service.prepare_work_item(
        PrepareScenarioWorkItemInput(
            template_key="sales_demand_forecast.v1",
            source_path=str(dataset_file.resolve()),
            feature_columns=["feature_a", "feature_b"],
            target_columns=["target"],
            work_item_name="source-trained-model",
        )
    )
    ml_service.fit_with_evaluate(
        FitWithEvaluateInput(
            work_item_id=source_prepared.work_item_id,
            model_key="regression.linear",
            params={"fit_intercept": True},
        )
    )

    deadline = time.time() + 60
    while time.time() < deadline:
        source_work_item = work_item_service.get_work_item(source_prepared.work_item_id)
        if source_work_item.best_trained_model_id is not None:
            break
        time.sleep(0.1)
    else:
        raise AssertionError("Timed out waiting for the source work item to get a best model.")

    prepared = workflow_service.prepare_work_item(
        PrepareScenarioWorkItemInput(
            template_key="sales_demand_forecast.v1",
            source_path=str(dataset_file.resolve()),
            feature_columns=["feature_a", "feature_b"],
            target_columns=["target"],
            work_item_name="reuse-target",
        )
    )
    template = template_service.get_template(prepared.template_key)
    compatible_models = model_source_service.list_compatible_trained_models(
        ListCompatibleTrainedModelsInput(
            template_key=prepared.template_key,
            feature_columns=prepared.feature_columns,
            target_columns=prepared.target_columns,
        )
    )
    assert compatible_models
    selected_model = compatible_models[0]

    monkeypatch.setattr("xenix.ui.scenario_inference_dialog.QMessageBox.information", lambda *args, **kwargs: None)
    dialog = ScenarioInferenceDialog(
        template=template,
        preparation_result=prepared,
        work_item_service=work_item_service,
        dataset_service=dataset_service,
        ml_service=ml_service,
        available_trained_models=compatible_models,
        preferred_trained_model_id=selected_model.trained_model_id,
    )
    try:
        dialog.show()
        app.processEvents()

        assert dialog._current_model_id() == selected_model.trained_model_id
        assert dialog._best_model_label.text().startswith("Compatible model selected:")

        dialog._row_editor._table.item(0, 0).setText("11")
        dialog._row_editor._table.item(0, 1).setText("9")
        app.processEvents()
        assert dialog._manual_submit_button.isEnabled() is True

        dialog._submit_manual_inference()
        app.processEvents()

        inference_tasks = [
            task
            for task in ml_service.list_work_item_tasks(prepared.work_item_id)
            if task.task_type is MLTaskType.INFERENCE
        ]
        assert len(inference_tasks) == 1
        assert inference_tasks[0].request_payload["inference_model"]["trained_model_id"] == selected_model.trained_model_id
    finally:
        dialog.close()

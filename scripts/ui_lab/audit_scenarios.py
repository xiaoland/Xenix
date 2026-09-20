"""Deterministic evidence ports driving the production centers, without a runtime home."""

from dataclasses import replace
from datetime import datetime, timezone
from functools import partial
from pathlib import Path

from PySide6.QtCore import QTranslator
from PySide6.QtWidgets import QApplication
from types import SimpleNamespace

from xenix.services.audit_contracts import (
    AuditDetail,
    AuditExplanation,
    AuditFile,
    AuditInput,
    AuditReference,
    AuditSummary,
)
from xenix.services.job_service import JobDomain, JobItem, JobStatus
from xenix.services.ml.contracts import TaskLogEntry
from xenix.ui.audit_center import AuditCenterDialog
from xenix.ui.job_center import JobCenterDialog

from .contracts import ScenarioHandle, ScenarioSpec

NOW = datetime(2026, 9, 20, 8, 30, tzinfo=timezone.utc)


class SyntheticAudit:
    def __init__(self, variant="model-explained"):
        self.variant = variant
        self.fail = False
        model = AuditSummary(
            reference=AuditReference(kind="model", id=105),
            title="区域需求预测 · 线性回归",
            category="model",
            created_at=NOW,
            thread_id=201,
            thread_title="下季度备货计划",
            thread_available=True,
            task_id=103,
            status="succeeded",
            rationale="先建立易于理解的基线模型，判断历史销量能否帮助安排下季度备货。固定测试集，便于公平比较其他方法。",
        )
        dataset = AuditSummary(
            reference=AuditReference(kind="dataset", id=102),
            title="合并后的区域销量",
            category="dataset",
            created_at=NOW,
            thread_id=201,
            thread_title="下季度备货计划",
            thread_available=True,
            rationale="按月份和区域合并销量与库存，保留缺失标记以便检查。",
        )
        chart = AuditSummary(
            reference=AuditReference(kind="artifact", id=110),
            title="各区域销售趋势",
            category="chart",
            created_at=NOW,
            thread_id=201,
            thread_available=True,
            rationale="比较各区域销量趋势，帮助发现补货节奏的差异。",
        )
        self.details = {
            "model:105": AuditDetail(
                summary=model,
                submitted_parameters={"test_size": 0.2},
                effective_parameters={"random_state": 42, "test_size": 0.2, "model": "linear_regression"},
                selected_parameters={"fit_intercept": True},
                inputs=[AuditInput(reference=dataset.reference, title=dataset.title, role="training input")],
                evidence={
                    "evaluation": {"evaluation": {"MAE": 12.4}, "split_facts": {"train_rows": 80, "test_rows": 20}}
                },
                files=[AuditFile(artifact_id=111, title="评估报告", available=True)],
                explanations=[
                    AuditExplanation(
                        id=501,
                        text="在保留的 20 条记录上，预测销量平均偏差约 12 件。这可作为备货参考，但不能保证未来月份同样准确。先检查高误差区域与近期促销，再决定是否用于采购。",
                        thread_id=201,
                        created_at=NOW,
                        evidence=[dataset.reference],
                    )
                ],
            ),
            "dataset:102": AuditDetail(
                summary=dataset,
                inputs=[
                    AuditInput(reference=AuditReference(kind="dataset", id=101), title="原始月度销售记录", role="sales")
                ],
                submitted_parameters={"join": "left", "keys": ["month", "region"]},
                evidence={"operation": "data.integrate"},
            ),
            "dataset:101": AuditDetail(
                summary=dataset.model_copy(
                    update={
                        "reference": AuditReference(kind="dataset", id=101),
                        "title": "原始月度销售记录",
                        "rationale": None,
                    }
                ),
                evidence={"source_file": "monthly-sales.xlsx", "sheet": "Sales"},
            ),
            "artifact:110": AuditDetail(
                summary=chart,
                inputs=[AuditInput(reference=dataset.reference, title=dataset.title)],
                evidence={
                    "analysis_graph": {
                        "row_count": 50000,
                        "rendered_row_count": 2000,
                        "truncated": True,
                        "warnings": ["展示仅覆盖前 2000 行；不代表完整分布。"],
                    }
                },
                files=[AuditFile(artifact_id=110, title="趋势图.svg", available=True)],
            ),
        }
        if variant == "awaiting-interpretation":
            self.details["model:105"].explanations = []
        if variant == "history-incomplete":
            detail = self.details["model:105"]
            detail.summary.rationale = None
            detail.summary.thread_available = False
            detail.summary.thread_title = None
            detail.explanations = []
            detail.effective_parameters = None
            detail.files[0].available = False
        if variant == "wide-en":
            detail = self.details["model:105"]
            detail.summary.title = "Regional demand forecast"
            detail.summary.rationale = "Start with an interpretable baseline and a fixed holdout for fair comparison."
            detail.explanations[
                0
            ].text = "Average error on 20 held-out records is 12.4 units. Check high-error regions and recent promotions before using this forecast for purchasing. This does not establish future seasonal accuracy."

    def list_outputs(self, scope, *, category="", search="", limit=50, task_id=None):
        if self.fail:
            raise RuntimeError("Synthetic evidence read failed")
        if self.variant == "empty-and-error" or (not scope.all_threads and scope.thread_id is None):
            return []
        key = {"dataset-lineage": "dataset:102", "chart-limits": "artifact:110"}.get(self.variant, "model:105")
        items = [self.details[key].summary]
        if scope.all_threads:
            items += [self.details["dataset:101"].summary]
        return [
            item.model_copy(deep=True)
            for item in items
            if (not category or item.category == category)
            and search.casefold() in item.title.casefold()
            and (task_id is None or item.task_id == task_id)
        ][:limit]

    def get_detail(self, reference, *, thread_id=None):
        return self.details[reference.key].model_copy(deep=True)


class SyntheticJobs:
    def list_jobs(self, *, domain=None, status=None, search="", limit=50, scope=None):
        base = JobItem(
            reference="ml:103",
            raw_reference=103,
            domain=JobDomain.ML,
            kind="fit",
            target="区域需求预测",
            status=JobStatus.SUCCEEDED,
            phase="completed",
            updated_at=NOW,
            thread_id=201,
            thread_title="下季度备货计划",
            started_at=NOW,
            finished_at=NOW,
        )
        items = [
            base,
            replace(
                base,
                reference="ml:104",
                raw_reference=104,
                kind="evaluate",
                status=JobStatus.RUNNING,
                phase="evaluating",
                finished_at=None,
            ),
            replace(
                base,
                reference="ml:106",
                raw_reference=106,
                status=JobStatus.FAILED,
                error_summary="目标列含缺失值，请检查输入数据。",
            ),
            replace(
                base,
                reference="knowledge:1",
                raw_reference=1,
                domain=JobDomain.KNOWLEDGE,
                kind="import",
                target="采购政策.pdf",
                thread_id=None,
                thread_title=None,
            ),
        ]
        return [
            item
            for item in items
            if (
                scope is None
                or scope.all_threads
                or (scope.thread_id is not None and item.thread_id == scope.thread_id)
            )
            and (domain is None or item.domain == domain)
            and (status is None or item.status == status)
            and search.casefold() in f"{item.reference} {item.target}".casefold()
        ][:limit]

    def get_task_details(self, task_id):
        return SimpleNamespace(
            logs=[
                TaskLogEntry(
                    timestamp=NOW.isoformat(), level="INFO", message=f"Task {task_id}: 已读取数据并记录执行参数。"
                )
            ],
            artifacts=[111] if task_id == 103 else [],
        )


def _translate(dialog, locale="zh_CN"):
    translator = QTranslator(dialog)
    catalog = Path(__file__).resolve().parents[2] / "src/xenix/translations" / f"xenix_{locale}.qm"
    if not translator.load(str(catalog)):
        raise RuntimeError(f"Missing compiled UI Lab translation: {catalog}")
    app = QApplication.instance()
    app.installTranslator(translator)
    dialog._scenario_translator = translator

    def stop():
        dialog.shutdown()
        app.removeTranslator(translator)

    return stop


def build_audit(_context, *, variant):
    dialog = AuditCenterDialog(service=SyntheticAudit(variant), thread_id=201)
    return ScenarioHandle(
        dialog,
        lambda: not dialog._list_loading and not dialog._detail_loading,
        _translate(dialog, "en_US" if variant == "wide-en" else "zh_CN"),
    )


def build_jobs(_context, *, variant):
    service = SyntheticJobs()
    dialog = JobCenterDialog(service, ml_service=service, thread_id=201)
    if variant == "running-and-failed":
        dialog._focus_reference = "ml:106"
    if variant == "session-and-global":
        dialog._scope_filter.setCurrentIndex(1)
    return ScenarioHandle(dialog, lambda: dialog._load is None and not dialog._details_read.busy, _translate(dialog))


AUDIT_SCENARIOS = tuple(
    ScenarioSpec(
        id=f"audit.{variant}",
        title=f"Audit · {variant}",
        description="Production Audit Center with synthetic recorded evidence.",
        viewport_width=800 if variant == "compact-zh" else 1280 if variant == "wide-en" else 1100,
        viewport_height=600 if variant == "compact-zh" else 800 if variant == "wide-en" else 740,
        font_family="Microsoft YaHei",
        locale_name="en_US" if variant == "wide-en" else "zh_CN",
        build=partial(build_audit, variant=variant),
    )
    for variant in (
        "model-explained",
        "dataset-lineage",
        "chart-limits",
        "awaiting-interpretation",
        "history-incomplete",
        "empty-and-error",
        "compact-zh",
        "wide-en",
    )
) + tuple(
    ScenarioSpec(
        id=f"jobs.{variant}",
        title=f"Jobs · {variant}",
        description="Production Job Center with scoped synthetic tasks and logs.",
        viewport_width=1100,
        viewport_height=740,
        font_family="Microsoft YaHei",
        locale_name="zh_CN",
        build=partial(build_jobs, variant=variant),
    )
    for variant in ("session-and-global", "running-and-failed")
)


def build_navigation(_context):
    from xenix.ui.windows.auxiliary import AuxiliaryWindowCoordinator

    service = SyntheticJobs()
    root = JobCenterDialog(service, ml_service=service, thread_id=201)
    coordinator = AuxiliaryWindowCoordinator(
        root,
        settings_factory=lambda owner: None,
        knowledge_factory=None,
        job_center_factory=lambda owner: root,
        audit_center_factory=lambda owner, thread: AuditCenterDialog(
            service=SyntheticAudit(), thread_id=thread, parent=owner
        ),
    )
    coordinator.set_thread_id(201)
    coordinator.show_jobs()
    root._scenario_coordinator = coordinator
    translated_stop = _translate(root)

    def stop():
        coordinator.shutdown()
        translated_stop()

    return ScenarioHandle(root, lambda: root._load is None and not root._details_read.busy, stop)


AUDIT_SCENARIOS += (
    ScenarioSpec(
        id="centers.navigation",
        title="Center navigation",
        description="Production coordinator routes tasks to outputs and back.",
        viewport_width=1100,
        viewport_height=740,
        font_family="Microsoft YaHei",
        locale_name="zh_CN",
        build=build_navigation,
    ),
)

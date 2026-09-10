from xenix.services.llm import LLMSettings

from tests.e2e.agent_harness._infra.budgets import BenchmarkBudgetController
from tests.e2e.agent_harness._infra.runner import DEFAULT_BUDGET_POLICY, _HeadlessBenchmarkCell


def test_headless_cell_opens_production_services_without_provider_calls(app_paths):
    budget = BenchmarkBudgetController(DEFAULT_BUDGET_POLICY)
    cell = _HeadlessBenchmarkCell(
        paths=app_paths, settings=LLMSettings(), embedding_settings=None, budget=budget,
    )
    try:
        snapshot = cell.harness.create_thread(title="Offline composition")
        assert cell.harness.get_thread_snapshot(snapshot.thread.id).messages == []
        assert cell.datasets.list_datasets() == []
    finally:
        cell.close()

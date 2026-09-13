from dataclasses import replace

import pytest

from xenix.services.agent import SubmitUserTurnInput
from xenix.services.llm import LLMProviderConfig, LLMService, LLMSettings
from xenix.services.llm.providers import ProviderResponse, ProviderStreamEvent

from tests.e2e.agent_harness._infra.contracts import (
    BenchmarkCaseAssessment,
    BenchmarkExecutionMode,
    BenchmarkIdentity,
    BenchmarkRunStatus,
    OutcomeCheck,
)
from tests.e2e.agent_harness._infra.runner import (
    DEFAULT_BUDGET_POLICY,
    _JudgeConfiguration,
    _run_model_cell,
)


class _TwoRequestTask:
    case_id = "offline-two-request-task"

    def build_submissions(self, *, thread_id, fq_model_key):
        return tuple(
            SubmitUserTurnInput(thread_id=thread_id, fq_model_key=fq_model_key, text=text)
            for text in ("Remember the first delivery.", "Continue using that delivery.")
        )

    def capture_source_state(self, *, snapshot, services):
        return None

    def capture_turn(self, *, context):
        return context.snapshot.messages[-1].text

    def assess(self, *, context):
        assert context.turns[0].snapshot.messages[-1].text == "First delivery"
        assert context.turns[0].evidence == "First delivery"
        checks = tuple(
            (OutcomeCheck("answer", turn.evidence in {"First delivery", "Second delivery"}, "answer captured"),)
            for turn in context.turns
        )
        return BenchmarkCaseAssessment(
            semantic_checks=tuple(check for group in checks for check in group),
            integrity_checks=(OutcomeCheck("state", True, "same thread"),),
            turn_checks=checks,
        )


@pytest.mark.parametrize("round_limit", [12, 1])
def test_headless_task_preserves_state_and_accumulates_budget(monkeypatch, tmp_path, round_limit):
    requests = []

    def offline_stream(_service, *, messages, before_provider_request=None, **_kwargs):
        before_provider_request()
        requests.append(messages)
        if len(requests) == 2:
            assert any("First delivery" in str(message) for message in messages)
        yield ProviderStreamEvent(
            response=ProviderResponse(
                assistant_content_blocks=[
                    {"type": "text", "text": "First delivery" if len(requests) == 1 else "Second delivery"}
                ],
                usage_payload={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            )
        )

    monkeypatch.setattr(LLMService, "stream", offline_stream)
    settings = LLMSettings(
        providers=[LLMProviderConfig(key="offline", models=["model"], api_key="offline")],
        default_fq_model_key="offline/model",
    )
    result = _run_model_cell(
        run_id="offline",
        case=_TwoRequestTask(),
        execution_mode=BenchmarkExecutionMode.HEADLESS,
        settings=settings,
        embedding_settings=None,
        model_key="offline/model",
        identity=BenchmarkIdentity(),
        judge_configuration=_JudgeConfiguration(),
        budget_policy=replace(DEFAULT_BUDGET_POLICY, max_sampling_rounds=round_limit),
        temporary_parent=tmp_path,
        trace_journal_path=tmp_path / "trace.jsonl",
    )
    assert result.planned_turn_count == 2
    assert len(result.turns) == 2
    assert result.turns[0].run_status is BenchmarkRunStatus.COMPLETED
    assert result.turns[0].subject_metrics.sampling_round_count == 1
    assert result.subject_metrics.sampling_round_count == min(round_limit, 2)
    assert result.budget.reported_subject_tokens == 15 * len(requests)
    assert (
        sum(turn.subject_metrics.token_usage.total_tokens for turn in result.turns if turn.subject_metrics.token_usage)
        == result.subject_metrics.token_usage.total_tokens
    )
    if round_limit == 1:
        assert result.run_status is BenchmarkRunStatus.BUDGET_EXCEEDED
        assert result.turns[1].run_status is BenchmarkRunStatus.BUDGET_EXCEEDED
    else:
        assert result.run_status is BenchmarkRunStatus.COMPLETED
        assert result.subject_metrics.message_counts["user"] == 2
        assert all(turn.subject_metrics.message_counts["user"] == 1 for turn in result.turns)

"""Exercise the actual UI submission boundary with an offline provider."""

from dataclasses import replace
import importlib
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
runner = importlib.import_module("tests.e2e.agent_harness._infra.runner")
contracts = importlib.import_module("tests.e2e.agent_harness._infra.contracts")
budgets = importlib.import_module("tests.e2e.agent_harness._infra.budgets")
existing = importlib.import_module("tests.e2e.agent_harness._infra_tests.test_cell_composition")
llm = importlib.import_module("xenix.services.llm")
providers = importlib.import_module("xenix.services.llm.providers")


def main():
    requests = []

    def offline_stream(_service, *, messages, before_provider_request=None, **_kwargs):
        before_provider_request()
        requests.append(messages)
        if len(requests) == 2:
            assert any("First delivery" in str(message) for message in messages)
        yield providers.ProviderStreamEvent(
            response=providers.ProviderResponse(
                assistant_content_blocks=[
                    {"type": "text", "text": "First delivery" if len(requests) == 1 else "Second delivery"}
                ],
                usage_payload={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            )
        )

    settings = llm.LLMSettings(
        providers=[llm.LLMProviderConfig(key="offline", models=["model"], api_key="offline")],
        default_fq_model_key="offline/model",
    )
    with (
        tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp,
        patch.object(llm.LLMService, "stream", offline_stream),
    ):
        from xenix.services.agent import SourceAttachmentInput

        sources = [Path(tmp) / name for name in ("initial.csv", "update.csv")]
        for index, source in enumerate(sources):
            source.write_text(f"record_id,amount\nR1,{10 + index}\n", encoding="utf-8")

        class AttachedTask(existing._TwoRequestTask):
            def build_submissions(self, **kwargs):
                return tuple(
                    submission.model_copy(update={"source_attachments": [SourceAttachmentInput(file_path=str(source))]})
                    for submission, source in zip(super().build_submissions(**kwargs), sources, strict=True)
                )

        result = runner._run_model_cell(
            run_id="offline-headed-two-turns",
            case=AttachedTask(),
            execution_mode=contracts.BenchmarkExecutionMode.HEADED,
            settings=settings,
            embedding_settings=None,
            model_key="offline/model",
            identity=contracts.BenchmarkIdentity(),
            judge_configuration=runner._JudgeConfiguration(),
            budget_policy=runner.DEFAULT_BUDGET_POLICY,
            temporary_parent=Path(tmp),
            trace_journal_path=Path(tmp) / "trace.jsonl",
        )
    sys.excepthook = sys.__excepthook__
    output = Path(__file__).with_name("headed_turn_observations.json")
    output.write_text(json.dumps(result.to_payload(), ensure_ascii=False, indent=2), encoding="utf-8")
    assert result.run_status is contracts.BenchmarkRunStatus.COMPLETED, result.failure_kind
    assert result.integrity_passed, result.integrity_checks
    assert len(result.turns) == 2
    assert all(turn.subject_metrics.message_counts["user"] == 1 for turn in result.turns)
    assert result.budget.reported_subject_tokens == 30

    # Recover a trace cut during the second provider call, as the process
    # watchdog sees it. Earlier completed work must survive in the report.
    events = result.trace.events
    starts = [i for i, event in enumerate(events) if event.name == "benchmark.subject.sampling_started"]
    interrupted = replace(
        result,
        run_status=contracts.BenchmarkRunStatus.BUDGET_EXCEEDED,
        failure_kind="process_wall_time_exceeded",
        turns=(),
        subject_metrics=contracts.BenchmarkMetrics(),
        trace=replace(result.trace, events=events[: starts[1] + 1]),
    )
    recovered = runner._recover_partial_task(interrupted)
    assert len(recovered.turns) == 2
    assert recovered.turns[0].run_status is contracts.BenchmarkRunStatus.COMPLETED
    assert recovered.turns[1].run_status is contracts.BenchmarkRunStatus.BUDGET_EXCEEDED
    assert recovered.budget.reported_subject_tokens == 15
    assert recovered.budget.status is budgets.BenchmarkBudgetStatus.UNVERIFIABLE
    assert recovered.subject_metrics.token_usage is None
    Path(__file__).with_name("interrupted_turn_observations.json").write_text(
        json.dumps(recovered.to_payload(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Two visible UI submissions, shared state, incremental metrics and interrupted-task recovery passed.")


if __name__ == "__main__":
    main()

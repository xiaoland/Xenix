from __future__ import annotations

import json
from typing import Any

import pytest

from xenix.services.llm import AssistantOutputItem, FrozenLLMSettingsSource, LLMService, LLMSettings
from xenix.services.llm.providers import ProviderResponse

from tests.e2e.agent_harness._infra.contracts import JudgeInput, JudgeRubric, JudgeStatus, SemanticVerdict
from tests.e2e.agent_harness._infra.judge import run_judge


def test_judge_reads_complete_evidence_and_tolerates_response_formatting(monkeypatch: pytest.MonkeyPatch) -> None:
    answer = "Regional results: 1,000, 2,000, 3,000, 4,000.\n" * 20 + "Final conclusion."
    response = {
        "verdict": "pass",
        "scores": {"grounding": 2},
        "reason_codes": ["supported", "supported"],
        "explanation": "Additional provider field",
    }
    requests: list[dict[str, Any]] = []

    def complete(_service: LLMService, **kwargs: Any) -> ProviderResponse:
        requests.append(kwargs)
        return ProviderResponse(output_items=[AssistantOutputItem(text="```json\n" + json.dumps(response) + "\n```")])

    monkeypatch.setattr(LLMService, "complete", complete)
    service = LLMService(FrozenLLMSettingsSource(LLMSettings()))
    evidence = JudgeInput(
        rubric=JudgeRubric("example", ("grounding",), ("supported",)),
        task_intent="Explain the results.",
        facts=("Four regions.",),
        artifact_evidence=(answer,),
    )
    result = run_judge(
        llm=service, judge_input=evidence, judge_model_key="judge/model", subject_model_key="subject/model"
    )

    assert result.status is JudgeStatus.COMPLETED
    assert result.verdict is SemanticVerdict.PASS
    assert result.reason_codes == ("supported",)
    assert json.dumps(answer, ensure_ascii=False) in requests[0]["messages"][1].content
    assert requests[0]["tools"] == []

    # Tolerating presentation must not turn an unusable score into a pass.
    response["scores"] = {"grounding": "uncertain"}
    invalid = run_judge(
        llm=service, judge_input=evidence, judge_model_key="judge/model", subject_model_key="subject/model"
    )
    assert invalid.status is JudgeStatus.INVALID_RESPONSE
    assert invalid.verdict is SemanticVerdict.NOT_EVALUATED

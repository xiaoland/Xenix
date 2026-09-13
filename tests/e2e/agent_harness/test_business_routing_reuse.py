"""Retain a routing analyzer, then use it on a later batch in the same thread."""

import pytest

from ._infra.business_tasks import (
    BusinessTask,
    completion_checks,
    deliveries,
    prediction_projections,
    task_checks,
    task_integrity,
)
from ._infra.contracts import BenchmarkCaseAssessment, BenchmarkCaseContext, JudgeInput, JudgeRubric, OutcomeCheck

pytestmark = pytest.mark.agent_harness_live

RUBRIC = JudgeRubric(
    rubric_id="business.routing_reuse.explanation.v1",
    score_dimensions=(
        "adoption_evidence",
        "manual_correction_estimate",
        "selected_analyzer_reused",
        "usable_queue_labels",
    ),
    allowed_reason_codes=(
        "grounded_reuse",
        "unsupported_quality_claim",
        "missing_estimate",
        "different_analyzer",
        "ambiguous_delivery",
    ),
    scoring_guidance=(
        "adoption_evidence: 2 if round 1 explains whether to adopt the saved analyzer using relevant evaluation evidence, accounting for related customer batches and the distinction between past evaluation and future batches. No particular algorithm, metric name or split recipe is required. Training-set scores alone cannot substantiate future accuracy. 1 for incomplete reasoning; 0 for materially false evidence or unjustified quality claims.",
        "manual_correction_estimate: 2 if the explanation estimates how many tickets may need manual re-routing with a defensible basis (accuracy/error rate or observed counts); 1 if omitted or unclear; 0 if misleading. F1 is not an error rate; an estimate may be cautious without being punished. No generic safety warning is required.",
        "selected_analyzer_reused: 2 if round 2's public retained-model identity matches the analyzer actually selected in round 1. If round 1 discusses several models, matching a rejected alternative is insufficient. A new model substituted for the earlier selection fails. Wording, column names, order and additional notes may vary.",
        "usable_queue_labels: Select the column actually delivered as the suggested queue, then use that column's program-computed accuracy. Input channels or other descriptive columns are not predictions merely because a permutation matches the truth. The actual prediction must reach 90%; a different column's higher score cannot substitute. Score 2 for business queue names or an explicitly explained alternative encoding consistent with the candidate mapping; 1 for incomplete label explanations; 0 for an unexplained/contradictory mapping or accuracy below 90%. Those outcomes fail the task. A candidate bijection computed by the oracle does not prove the user was given that mapping.",
        "Program checks establish saved-object identity and complete new-batch predictions with at least 90% accuracy. Correct outputs missing requested explanations are partial; material false claims, selecting the wrong delivery, or falsely claiming reuse are fail. Judge both rounds, not just the last answer.",
    ),
)


class RoutingReuseTask(BusinessTask):
    task = "routing"
    attachments = (("history.csv", "queue_notes.txt"), ("new_tickets.csv",))

    def assess(self, *, context: BenchmarkCaseContext) -> BenchmarkCaseAssessment:
        observed = deliveries(context)
        first = observed[0] if observed else None
        second = observed[1] if len(observed) > 1 else None
        expected = self.oracle()
        saved = (
            {artifact.model_id for artifact in first.artifacts if artifact.model_id and artifact.model_available}
            if first
            else set()
        )
        candidates = (
            [
                (artifact, projection)
                for artifact in second.artifacts
                if artifact.frame is not None
                for projection in prediction_projections(artifact.frame, expected["labels"])
            ]
            if second
            else []
        )
        best = max(
            (value for _, value in candidates if value is not None), key=lambda item: item.accuracy, default=None
        )
        accuracy = best.accuracy if best is not None else None
        reused = any(
            value is not None
            and value.accuracy >= expected["minimum_accuracy"]
            and artifact.model_available
            and artifact.model_id in saved
            for artifact, value in candidates
        )
        checks = (
            (
                *completion_checks(first),
                OutcomeCheck("reusable_analyzer_saved", bool(saved), f"saved_model_ids={sorted(saved)}"),
            ),
            (
                *completion_checks(second),
                OutcomeCheck(
                    "complete_batch_quality",
                    accuracy is not None and accuracy >= expected["minimum_accuracy"],
                    f"accuracy={accuracy}; required={expected['minimum_accuracy']}",
                ),
                OutcomeCheck("saved_analyzer_reused", reused, "delivered_predictions_reference_same_persisted_model"),
            ),
        )
        return BenchmarkCaseAssessment(
            semantic_checks=task_checks(checks),
            turn_checks=checks,
            integrity_checks=task_integrity(context),
            judge_required=True,
            judge_input=JudgeInput(
                rubric=RUBRIC,
                task_intent=self.intent(),
                facts=(
                    f"Best candidate column accuracy={accuracy}; minimum_accuracy=0.9; candidate_with_public_saved_model_reuse={reused}; first-turn saved_model_ids={sorted(saved)}",
                    f"All candidate column projections (Judge must select the actual prediction, not the largest score): {[(artifact.uri, artifact.model_id, projection) for artifact, projection in candidates]}",
                    "channel is an entry point, not the routing target. customer_batch records may describe related events. The second batch was not supplied during training.",
                ),
                artifact_evidence=tuple(
                    item for index, delivery in enumerate(observed, 1) for item in delivery.judge_evidence(index)
                ),
            ),
        )


def test_business_routing_reuse(agent_harness_benchmark) -> None:
    agent_harness_benchmark.run(RoutingReuseTask(agent_harness_benchmark.business_variant))

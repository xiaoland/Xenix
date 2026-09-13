"""A monthly close remains one task when corrected transactions arrive."""

import pytest

from ._infra.business_tasks import (
    BusinessTask,
    completion_checks,
    deliveries,
    monetary_mapping,
    task_checks,
    task_integrity,
)
from ._infra.contracts import BenchmarkCaseAssessment, BenchmarkCaseContext, JudgeInput, JudgeRubric, OutcomeCheck

pytestmark = pytest.mark.agent_harness_live

RUBRIC = JudgeRubric(
    rubric_id="business.revenue_revision.explanation.v1",
    score_dimensions=("month_close_grounding", "revision_explanation"),
    allowed_reason_codes=("grounded_delivery", "missing_explanation", "incorrect_business_claim", "ambiguous_delivery"),
    scoring_guidance=(
        "month_close_grounding: 2 if round 1 explains the net-receipt basis and material treatment of old-order refunds and duplicate exports consistently with the delivered table; 1 for missing explanation; 0 for a material contradiction.",
        "revision_explanation: 2 if round 2 explains each region's change from round 1 and whether the ranking changed, grounded in the corrected table; 1 if an explanation is incomplete; 0 for stale values or false changes.",
        "Correct tables do not excuse false claims about refunds, affected regions or the reason for a revision. Treat an asserted wrong business fact as fail even when the main net-receipt table is correct. Partial is for omitted explanation, not a softer verdict for a contradiction. Check such claims against the supplied source records and deliveries; do not infer missing business rules.",
        "Program checks match each required region once in a candidate amount column. Confirm that this is the recommended net-receipt column. Additional clearly identified totals or subtotals are acceptable if correct; extra invented regions, misleading totals or a wrong selected column are not. Do not reject a correct summary merely for including an aggregate row.",
        "Judge every user turn's actual delivery. Program facts establish the amounts, not which of several contradictory linked outputs the answer recommends. Conflicting final deliverables or a materially false conclusion mean fail; correct tables with omitted explanation mean partial. Equivalent wording, units explicitly identified by the author, recomputation or incremental updates are acceptable. Do not require a tool sequence or additional workflow warnings.",
    ),
)


class RevenueRevisionTask(BusinessTask):
    task = "revenue"
    attachments = (("orders.csv", "stores.csv", "refunds.csv", "business_notes.txt"), ("refund_updates.csv",))

    def judge_facts(self) -> tuple[str, ...]:
        return (
            f"Authoritative net receipts and changes in yuan: {self.oracle()}",
            (self.folder / "business_notes.txt").read_text(encoding="utf-8"),
            *(
                f"Authoritative user input {name}:\n{(self.folder / name).read_text(encoding='utf-8')}"
                for name in ("orders.csv", "stores.csv", "refunds.csv", "refund_updates.csv")
            ),
        )

    def assess(self, *, context: BenchmarkCaseContext) -> BenchmarkCaseAssessment:
        observed = deliveries(context)
        expected = self.oracle()
        checks = []
        for index, amounts in enumerate(expected["rounds"]):
            delivery = observed[index] if index < len(observed) else None
            exact = delivery is not None and any(
                artifact.frame is not None and monetary_mapping(artifact.frame, amounts, delivery.final_text)
                for artifact in delivery.artifacts
            )
            checks.append(
                (
                    *completion_checks(delivery),
                    OutcomeCheck("net_receipts_delivered", exact, f"expected_yuan={amounts}"),
                )
            )
        per_turn = tuple(checks)
        return BenchmarkCaseAssessment(
            semantic_checks=task_checks(per_turn),
            turn_checks=per_turn,
            integrity_checks=task_integrity(context),
            judge_required=True,
            judge_input=JudgeInput(
                rubric=RUBRIC,
                task_intent=self.intent(),
                facts=self.judge_facts(),
                artifact_evidence=tuple(
                    item for index, delivery in enumerate(observed, 1) for item in delivery.judge_evidence(index)
                ),
            ),
        )


def test_business_revenue_revision(agent_harness_benchmark) -> None:
    agent_harness_benchmark.run(RevenueRevisionTask(agent_harness_benchmark.business_variant))

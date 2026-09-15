"""Apply the policy effective on the activity date, including limited exceptions."""

import time

import polars as pl
import pytest

from ._infra.business_tasks import (
    BusinessTask,
    completion_checks,
    deliveries,
    keyed_columns,
    task_checks,
    task_integrity,
)
from ._infra.contracts import (
    BenchmarkCaseAssessment,
    BenchmarkCaseContext,
    BenchmarkCasePreparationServices,
    BenchmarkInputError,
    JudgeInput,
    JudgeRubric,
    OutcomeCheck,
)

pytestmark = pytest.mark.agent_harness_live

RUBRIC = JudgeRubric(
    rubric_id="business.campaign_eligibility.explanation.v1",
    score_dimensions=("effective_rule", "exceptions_explained"),
    allowed_reason_codes=(
        "grounded_delivery",
        "expired_policy",
        "incorrect_exception",
        "missing_explanation",
        "ambiguous_delivery",
    ),
    scoring_guidance=(
        "effective_rule: 2 for explaining the policy applicable on the requested date and its selection conditions; 1 for an incomplete explanation; 0 for an expired policy or false eligibility claim. A document title/date or an accurate description suffices; no specific retrieval tool or citation syntax is required.",
        "exceptions_explained: 2 for correctly explaining VIP's limited spending exemption, never-contacted customers, contact-day boundaries and open-case exclusion; 1 for missing material explanation; 0 for an incorrect exemption. Do not require listing every excluded person.",
        "Evaluate the actual recommended list, including contradictory linked lists. A filtered list and a full audit table with an explicitly labelled eligibility column are equivalent. Program facts establish membership; confirm that the matched selection column actually denotes eligibility. Correct membership with missing explanation is partial; wrong membership or materially false policy claims is fail. Additional operational warnings are not requested.",
    ),
)


class CampaignEligibilityTask(BusinessTask):
    task = "campaign"
    attachments = (("customers.csv", "data_notes.txt"),)

    def prepare(self, *, services: BenchmarkCasePreparationServices) -> None:
        for path in sorted((self.folder / "knowledge").glob("*.txt")):
            imported = services.knowledge_import.import_file(path, timeout=60)
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                status = services.knowledge_derivation.status_for_import(imported.import_id)
                if status is not None and status.status == "succeeded":
                    break
                if status is not None and status.status == "failed":
                    raise BenchmarkInputError("campaign_policy_derivation_failed")
                time.sleep(0.02)
            else:
                raise BenchmarkInputError("campaign_policy_derivation_timeout")
        task_id = services.knowledge_index.enqueue_rebuild(("text_vector",), trigger="manual")
        if services.knowledge_index.rebuild_now(task_id).status != "succeeded":
            raise BenchmarkInputError("campaign_policy_index_failed")

    def assess(self, *, context: BenchmarkCaseContext) -> BenchmarkCaseAssessment:
        observed = deliveries(context)
        delivery = observed[0] if observed else None
        expected = self.oracle()
        exact = delivery is not None and any(
            artifact.frame is not None and _contains_eligible_list(artifact.frame, set(expected["eligible"]))
            for artifact in delivery.artifacts
        )
        checks = (
            (
                *completion_checks(delivery),
                OutcomeCheck("eligible_list_delivered", bool(exact), f"expected_customer_ids={expected['eligible']}"),
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
                    f"Authoritative current eligibility and exclusion reasons: {expected}",
                    *tuple(
                        path.read_text(encoding="utf-8") for path in sorted((self.folder / "knowledge").glob("*.txt"))
                    ),
                ),
                artifact_evidence=delivery.judge_evidence(1) if delivery else (),
            ),
        )


def _contains_eligible_list(frame: pl.DataFrame, expected: set[str]) -> bool:
    """A filtered list and an explicitly flagged audit table carry the same list.

    Judge checks the selected column's meaning in the actual delivery; these
    checks establish customer identities without prescribing a header.
    """
    if keyed_columns(frame, expected):
        return True
    true_values = {"true", "1", "1.0", "yes", "是", "入选", "符合", "可回访", "eligible"}
    false_values = {"false", "0", "0.0", "no", "否", "未入选", "不入选", "不符合", "不可回访", "ineligible"}
    for column in frame.columns:
        flags = [str(value).strip().casefold() for value in frame[column].to_list()]
        if set(flags) <= true_values | false_values:
            selected = frame.filter(pl.Series([flag in true_values for flag in flags]))
            if keyed_columns(selected, expected):
                return True
    return False


def test_business_campaign_eligibility(agent_harness_benchmark) -> None:
    agent_harness_benchmark.run(CampaignEligibilityTask(agent_harness_benchmark.business_variant))


@pytest.mark.parametrize("scenario", ("spending_threshold", "contact_interval"))
def test_campaign_contrast(agent_harness_benchmark, scenario) -> None:
    agent_harness_benchmark.run(CampaignEligibilityTask(scenario))

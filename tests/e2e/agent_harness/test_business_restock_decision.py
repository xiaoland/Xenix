"""Choose useful purchases under business constraints, including no purchase."""

import csv
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation

import polars as pl
import pytest

from ._infra.business_tasks import BusinessTask, completion_checks, deliveries, task_checks, task_integrity
from ._infra.contracts import BenchmarkCaseAssessment, BenchmarkCaseContext, JudgeInput, JudgeRubric, OutcomeCheck

pytestmark = pytest.mark.agent_harness_live

RUBRIC = JudgeRubric(
    rubric_id="business.restock_decision.explanation.v1",
    score_dimensions=("selected_plan", "business_explanation"),
    allowed_reason_codes=("grounded_decision", "wrong_plan", "incorrect_business_claim", "missing_explanation"),
    scoring_guidance=(
        "selected_plan: Confirm which linked table and column actually communicate the recommended purchase quantities. Program projections provide the corresponding cost, capacity, margin and constraint violations. Input stock, costs or other descriptive columns cannot substitute for the actual recommendation. Score 2 only if the recommended plan is feasible and reaches the stated optimum; 0 for a different or contradictory recommendation. Any equally optimal plan is acceptable; no preferred product or algorithm is required.",
        "An optimum of zero permits a clear no-purchase answer without an empty artifact. Score 2 only if the actual answer recommends no purchase and gives the applicable business reason. Generic caution, claiming more data is necessary despite complete inputs, or recommending unaffordable purchases fails. An implicit zero-plan candidate in program facts does not mean the answer made that recommendation.",
        "business_explanation: 2 for a correct explanation of the material tradeoff, used budget and capacity (or why no batch can be ordered); 1 for omitted requested explanation; 0 for materially false claims. Planned margin is not guaranteed realized sales profit, and procurement cost must not be subtracted twice. No extra workflow, safety warnings, training or optimality proof is required.",
        "Unexpected rows in program projections must be identified from the actual delivery: correct totals and notes are acceptable; invented purchase identities are not. Additional tables must not contradict the recommended plan. Any material false business claim or selected_plan=0 means fail; correct decisions missing explanation are partial. Otherwise pass.",
    ),
)


@dataclass(frozen=True)
class PlanProjection:
    identity_column: str | None
    quantity_column: str | None
    quantities: dict[str, int]
    cost_cents: int
    boxes: int
    margin_cents: int
    violations: tuple[str, ...]
    extra_rows: tuple[dict, ...] = ()


def _integer(value) -> int | None:
    try:
        number = Decimal(str(value).strip().replace(",", "").replace("，", ""))
        return int(number) if number.is_finite() and number == number.to_integral_value() else None
    except InvalidOperation, ValueError:
        return None


def evaluate_plan(quantities: dict[str, int], offers: dict, expected: dict) -> PlanProjection:
    """Evaluate a purchase decision; the reference does not prescribe its identity."""
    cost = boxes = margin = 0
    violations = []
    for identity, batches in quantities.items():
        if identity not in offers:
            violations.append(f"unknown_offer:{identity}")
            continue
        row = offers[identity]
        if not 0 <= batches <= int(row["max_batches"]):
            violations.append(f"unavailable_quantity:{identity}")
        if batches > 0 and row["arrival_date"] > expected["deadline"]:
            violations.append(f"late_arrival:{identity}")
        cost += batches * int(Decimal(row["cost_yuan"]) * 100)
        margin += batches * int(Decimal(row["margin_yuan"]) * 100)
        boxes += batches * int(row["boxes"])
    if cost > expected["budget_cents"]:
        violations.append("over_budget")
    if boxes > expected["capacity_boxes"]:
        violations.append("over_capacity")
    return PlanProjection(None, None, quantities, cost, boxes, margin, tuple(violations))


def plan_projections(frame: pl.DataFrame, offers: dict, expected: dict) -> tuple[PlanProjection, ...]:
    """Project candidate quantity columns; Judge chooses the actual recommendation.

    Extra aggregate rows and alternate column names are allowed. The full
    delivery remains evidence, so ignoring an invented purchase cannot pass.
    """
    from dataclasses import replace

    if frame.is_empty():
        return (evaluate_plan({}, offers, expected),)
    projections = []
    rows = frame.to_dicts()
    for identity_column in frame.columns:
        known = [row for row in rows if str(row[identity_column]).strip() in offers]
        if not known:
            continue
        extras = tuple(row for row in rows if str(row[identity_column]).strip() not in offers)
        for quantity_column in frame.columns:
            if quantity_column == identity_column:
                continue
            quantities = {}
            for row in known:
                value = row[quantity_column]
                batches = 0 if value is None else _integer(value)
                if batches is None:
                    break
                identity = str(row[identity_column]).strip()
                quantities[identity] = quantities.get(identity, 0) + batches
            else:
                projections.append(
                    replace(
                        evaluate_plan(quantities, offers, expected),
                        identity_column=identity_column,
                        quantity_column=quantity_column,
                        extra_rows=extras,
                    )
                )
    return tuple(projections)


class RestockDecisionTask(BusinessTask):
    task = "restock"
    attachments = (("offers.csv", "business_notes.txt"),)

    def offers(self) -> dict:
        with (self.folder / "offers.csv").open(encoding="utf-8", newline="") as stream:
            return {row["offer_id"]: row for row in csv.DictReader(stream)}

    def assess(self, *, context: BenchmarkCaseContext) -> BenchmarkCaseAssessment:
        observed = deliveries(context)
        delivery = observed[0] if observed else None
        expected, offers = self.oracle(), self.offers()
        candidates = (
            [
                {"uri": artifact.uri, **asdict(projection)}
                for artifact in delivery.artifacts
                if artifact.frame is not None
                for projection in plan_projections(artifact.frame, offers, expected)
            ]
            if delivery
            else []
        )
        if expected["optimal_margin_cents"] == 0:
            candidates.append(
                {
                    "uri": None,
                    "requires_explicit_no_purchase_answer": True,
                    **asdict(evaluate_plan({}, offers, expected)),
                }
            )
        feasible = [plan for plan in candidates if not plan["violations"]]
        best = max((plan["margin_cents"] for plan in feasible), default=None)
        checks = (
            (
                *completion_checks(delivery),
                OutcomeCheck("feasible_decision_available", bool(feasible), f"candidate_count={len(feasible)}"),
                OutcomeCheck(
                    "optimal_decision_available",
                    best == expected["optimal_margin_cents"],
                    f"best_feasible_margin_cents={best}; optimum={expected['optimal_margin_cents']}",
                ),
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
                    (self.folder / "business_notes.txt").read_text(encoding="utf-8"),
                    f"Authoritative constraints and optimum (money in cents): {expected}",
                    f"Offered batches (cost_yuan and margin_yuan are yuan per batch): {list(offers.values())}",
                    f"Candidate projections; select the actual recommended table and quantity column: {candidates}",
                ),
                artifact_evidence=delivery.judge_evidence(1) if delivery else (),
            ),
        )


def test_business_restock_decision(agent_harness_benchmark) -> None:
    agent_harness_benchmark.run(RestockDecisionTask(agent_harness_benchmark.business_variant))


@pytest.mark.parametrize(
    "scenario", ("budget_tight", "arrival_earlier", "margin_lower", "margin_higher", "no_purchase")
)
def test_restock_contrast(agent_harness_benchmark, scenario) -> None:
    agent_harness_benchmark.run(RestockDecisionTask(scenario))

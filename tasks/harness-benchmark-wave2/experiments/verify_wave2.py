"""Independent decision enumeration and outcome-boundary design probes."""

from decimal import Decimal
import importlib
from itertools import product
import json
from pathlib import Path
import sys

import duckdb
import polars as pl

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
cases = importlib.import_module("tests.e2e.agent_harness.test_business_restock_decision")
support = importlib.import_module("tests.e2e.agent_harness._infra.business_tasks")
contracts = importlib.import_module("tests.e2e.agent_harness._infra.contracts")
campaign = importlib.import_module("tests.e2e.agent_harness.test_business_campaign_eligibility")


def context(frame=None, text="按附件计划采购。"):
    artifacts = (
        ()
        if frame is None
        else (support.DeliveredArtifact("artifact://plan", "采购计划", "dataset", frame, None, None, False),)
    )
    delivery = support.Delivery(text, artifacts, (), True, True)
    turn = contracts.BenchmarkTurnObservation(
        None,
        delivery,
        contracts.BenchmarkTurnResult(1, contracts.BenchmarkRunStatus.COMPLETED, contracts.BenchmarkMetrics()),
    )
    return contracts.BenchmarkCaseContext(None, None, None, frozenset(), ROOT, (turn,))


def enumerate_plans(task):
    rows = list(task.offers().values())
    expected = task.oracle()
    costs = [Decimal(row["cost_yuan"]) for row in rows]
    margins = [Decimal(row["margin_yuan"]) for row in rows]
    best, winners = Decimal(-1), []
    ranges = [
        range(int(row["max_batches"]) + 1) if row["arrival_date"] <= expected["deadline"] else range(1) for row in rows
    ]
    for counts in product(*ranges):
        spent = sum(n * cost for n, cost in zip(counts, costs, strict=True))
        volume = sum(n * int(row["boxes"]) for n, row in zip(counts, rows, strict=True))
        if spent * 100 > expected["budget_cents"] or volume > expected["capacity_boxes"]:
            continue
        value = sum(n * margin for n, margin in zip(counts, margins, strict=True))
        if value > best:
            best, winners = value, []
        if value == best:
            winners.append({row["offer_id"]: n for row, n in zip(rows, counts, strict=True) if n})
    assert best * 100 == expected["optimal_margin_cents"]
    return best, winners


def frame(plan):
    return pl.DataFrame(
        {"报价编号": list(plan), "本次订货批数": list(plan.values())},
        schema={"报价编号": pl.String, "本次订货批数": pl.Int64},
    )


def main():
    results = {}
    for scenario in (
        "standard",
        "budget_tight",
        "arrival_earlier",
        "margin_lower",
        "margin_higher",
        "no_purchase",
        "confirmation",
    ):
        task = cases.RestockDecisionTask(scenario)
        task.validate_input()
        best, winners = enumerate_plans(task)
        for plan in winners:
            assert task.assess(context=context(frame(plan))).semantic_checks_passed
        winner = winners[0]
        # A full audit with explicit zero quantities is a legitimate plan too.
        audit = frame({identity: winner.get(identity, 0) for identity in task.offers()}).reverse()
        assert task.assess(context=context(audit)).semantic_checks_passed
        if best > 0:
            assert not task.assess(context=context(frame({}))).semantic_checks_passed
            assert not task.assess(context=context()).semantic_checks_passed
            assert not task.assess(context=context(frame({key: 100 for key in winner}))).semantic_checks_passed
            fractional = frame(winner).with_columns(pl.lit(0.5).alias("本次订货批数"))
            assert not task.assess(context=context(fractional)).semantic_checks_passed
            one = next(iter(winner))
            assert cases.evaluate_plan({one: -1}, task.offers(), task.oracle()).violations
            assert cases.evaluate_plan({"UNKNOWN": 1}, task.offers(), task.oracle()).violations
            # Totals are retained for Judge review, without imposing exact row count.
            total = pl.DataFrame({"报价编号": ["合计"], "本次订货批数": [sum(winner.values())]})
            assert task.assess(context=context(pl.concat([frame(winner), total]))).semantic_checks_passed
        else:
            assessment = task.assess(context=context(text="预算 120 元低于最便宜批次 150 元，本次不下单。"))
            assert assessment.semantic_checks_passed and assessment.judge_required
        results[scenario] = {"optimum_yuan": str(best), "optimal_plan_count": len(winners), "optimal_plans": winners}
    assert results["standard"]["optimal_plan_count"] > 1
    assert results["standard"]["optimal_plans"] == results["margin_higher"]["optimal_plans"]
    assert results["standard"]["optimal_plans"] != results["budget_tight"]["optimal_plans"]

    campaign_results = {}
    for scenario in ("standard", "spending_threshold", "contact_interval"):
        task = campaign.CampaignEligibilityTask(scenario)
        expected = task.oracle()
        with duckdb.connect() as db:
            db.read_csv(str(task.folder / "customers.csv")).create_view("customers")
            selected = db.execute(
                "SELECT customer_id FROM customers WHERE city IN ('南京','苏州') AND active AND open_service_cases=0 AND (vip OR net_spend_90d_yuan>=?) AND (last_contact_date IS NULL OR date_diff('day',last_contact_date,DATE '2026-07-01')>=?)",
                [expected["threshold_yuan"], expected["contact_days"]],
            ).fetchall()
        ids = sorted(row[0] for row in selected)
        assert ids == sorted(expected["eligible"])
        assert task.assess(context=context(pl.DataFrame({"客户": ids}))).semantic_checks_passed
        campaign_results[scenario] = ids
    assert campaign_results["standard"] != campaign_results["spending_threshold"]
    assert campaign_results["standard"] != campaign_results["contact_interval"]
    # Each contrast changes one policy value, leaving request/customer inputs intact.
    base = support.FIXTURE_ROOT / "campaign" / "standard"
    for scenario, old, new in (("spending_threshold", "1000 元", "1200 元"), ("contact_interval", "30 天", "45 天")):
        folder = support.FIXTURE_ROOT / "campaign" / scenario
        for name in ("request_1.txt", "customers.csv", "data_notes.txt"):
            assert (base / name).read_bytes() == (folder / name).read_bytes()
        policy = Path("knowledge/客户运营七月活动.txt")
        assert (base / policy).read_text().replace(old, new) == (folder / policy).read_text()
    target = Path(__file__).with_name("formal_observations.json")
    target.write_text(
        json.dumps({"restock": results, "campaign": campaign_results}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "restock": {
                    key: {k: v for k, v in value.items() if k != "optimal_plans"} for key, value in results.items()
                },
                "campaign": campaign_results,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

"""Offline authoring probes, deliberately outside the regression portfolio."""

from __future__ import annotations

import csv
from dataclasses import replace
import importlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

import duckdb
import polars as pl
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
support = importlib.import_module("tests.e2e.agent_harness._infra.business_tasks")
contracts = importlib.import_module("tests.e2e.agent_harness._infra.contracts")
revenue_module = importlib.import_module("tests.e2e.agent_harness.test_business_revenue_revision")
campaign_module = importlib.import_module("tests.e2e.agent_harness.test_business_campaign_eligibility")


def revenue_amounts(folder: Path, *, revised=False, append=False, all_refunds=False, drop_old=False):
    with duckdb.connect() as con:
        for name in ("orders", "stores", "refunds", "refund_updates"):
            con.read_csv(str(folder / f"{name}.csv")).create_view(name)
        refund_source = "SELECT *, 0 AS priority FROM refunds"
        if revised:
            refund_source += " UNION ALL SELECT *, 1 AS priority FROM refund_updates"
        refund_dedup = (
            "QUALIFY ROW_NUMBER() OVER(PARTITION BY refund_id ORDER BY priority DESC)=1" if not append else ""
        )
        refund_dates = "TRUE" if all_refunds else "r.refund_date BETWEEN DATE '2026-06-01' AND DATE '2026-06-30'"
        old_order_filter = "AND o.paid_date BETWEEN DATE '2026-06-01' AND DATE '2026-06-30'" if drop_old else ""
        rows = con.execute(f"""
            WITH o AS (SELECT * FROM orders QUALIFY ROW_NUMBER() OVER(PARTITION BY order_id)=1),
            r AS (SELECT * FROM ({refund_source}) {refund_dedup}),
            entries AS (
                SELECT s.region, o.amount_yuan AS amount FROM o JOIN stores s USING(store_id)
                WHERE o.status='paid' AND o.paid_date BETWEEN DATE '2026-06-01' AND DATE '2026-06-30'
                UNION ALL
                SELECT s.region, -r.amount_yuan FROM r JOIN o USING(order_id) JOIN stores s USING(store_id)
                WHERE {refund_dates} {old_order_filter}
            )
            SELECT s.region, COALESCE(SUM(e.amount),0) FROM (SELECT DISTINCT region FROM stores) s
            LEFT JOIN entries e USING(region) GROUP BY s.region
        """).fetchall()
        return {key: float(value) for key, value in rows}


def campaign_ids(folder: Path, *, threshold=None, gap=None, universal_vip=False):
    expected = json.loads((folder / "oracle.json").read_text(encoding="utf-8"))
    with duckdb.connect() as con:
        con.read_csv(str(folder / "customers.csv")).create_view("customers")
        city_sql = ",".join("'" + city + "'" for city in expected["cities"])
        predicate = f"""city IN ({city_sql}) AND active AND open_service_cases=0
            AND (vip OR net_spend_90d_yuan >= {threshold or expected["threshold_yuan"]})
            AND (last_contact_date IS NULL OR date_diff('day',last_contact_date,DATE '{expected["date"]}') >= {gap or expected["contact_days"]})"""
        if universal_vip:
            predicate = f"({predicate}) OR vip"
        return {row[0] for row in con.execute(f"SELECT customer_id FROM customers WHERE {predicate}").fetchall()}


def delivery(frame):
    artifact = support.DeliveredArtifact("artifact://output", "业务结果", "dataset", frame, None, None, None)
    return support.Delivery("结果已交付。", (artifact,), (), True, True)


def context(*outputs):
    turns = tuple(
        contracts.BenchmarkTurnObservation(
            snapshot=None,
            evidence=output,
            result=contracts.BenchmarkTurnResult(
                index=index,
                run_status=contracts.BenchmarkRunStatus.COMPLETED,
                subject_metrics=contracts.BenchmarkMetrics(),
            ),
        )
        for index, output in enumerate(outputs, 1)
    )
    return contracts.BenchmarkCaseContext(None, None, None, frozenset(), ROOT, turns)


def prediction_accuracy(frame, labels):
    return max((item.accuracy for item in support.prediction_projections(frame, labels)), default=None)


def verify_delivery_boundary():
    """A correct orphan does not count; a later overwrite cannot revise round 1."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        correct = folder / "correct.csv"
        wrong = folder / "wrong.csv"
        pl.DataFrame({"区域": ["东区"], "净回款": [10]}).write_csv(correct)
        pl.DataFrame({"区域": ["东区"], "净回款": [99]}).write_csv(wrong)
        paths = {"artifact://correct": correct, "artifact://wrong": wrong}

        class Artifacts:
            def resolve_uri(self, uri):
                return SimpleNamespace(
                    exists=True,
                    ready_to_open=True,
                    absolute_path=paths[uri],
                    title="结果",
                    kind=SimpleNamespace(value="dataset"),
                    metadata_payload={},
                )

        task = revenue_module.RevenueRevisionTask()
        task.validate_input()
        services = contracts.BenchmarkCaseServices(None, Artifacts())
        snapshot = SimpleNamespace(
            messages=[SimpleNamespace(kind="assistant", text="[结果](artifact://wrong)", refusal=None)]
        )
        ctx = contracts.BenchmarkCaseContext(snapshot, services, None, frozenset(), folder)
        first = task.capture_turn(context=ctx)
        assert len(first.artifacts) == 1 and first.artifacts[0].frame["净回款"][0] == 99
        pl.DataFrame({"区域": ["东区"], "净回款": [10]}).write_csv(wrong)
        second = task.capture_turn(context=ctx)
        assert first.artifacts[0].frame["净回款"][0] == 99
        assert second.artifacts[0].frame["净回款"][0] == 10


def run():
    findings = {}
    for variant in ("standard", "confirmation"):
        a = revenue_module.RevenueRevisionTask(variant)
        expected = a.oracle()
        reference = [revenue_amounts(a.folder), revenue_amounts(a.folder, revised=True)]
        assert reference == expected["rounds"]
        frames = [
            pl.DataFrame(
                {"地区": list(values), "净回款": list(values.values()), "说明": ["月结"] * len(values)}
            ).reverse()
            for values in reference
        ]
        assert a.assess(context=context(*(delivery(frame) for frame in frames))).semantic_checks_passed
        totals = [
            pl.concat([frame, pl.DataFrame({"地区": ["合计"], "净回款": [sum(values.values())], "说明": ["月结"]})])
            for frame, values in zip(frames, reference, strict=True)
        ]
        assert a.assess(context=context(*(delivery(frame) for frame in totals))).semantic_checks_passed
        duplicate = pl.concat([frames[0], frames[0].head(1)])
        assert not a.assess(context=context(delivery(duplicate), delivery(frames[1]))).semantic_checks_passed
        assert not a.assess(context=context(delivery(frames[0]), delivery(frames[0]))).semantic_checks_passed
        assert not a.assess(context=context(delivery(frames[1]), delivery(frames[1]))).semantic_checks_passed
        wrong = {
            "append_corrections": revenue_amounts(a.folder, revised=True, append=True),
            "lifetime_refunds": revenue_amounts(a.folder, revised=True, all_refunds=True),
            "drop_old_order_refunds": revenue_amounts(a.folder, revised=True, drop_old=True),
        }
        assert all(values != reference[1] for values in wrong.values())
        a_results = {
            "sql_reference_matches": True,
            "equivalent_table_passes": True,
            "aggregate_rows_allowed_duplicate_regions_rejected": True,
            "stale_or_wrong_earlier_delivery_rejected": True,
            "distinct_wrong_strategies": list(wrong),
        }

        b = campaign_module.CampaignEligibilityTask(variant)
        expected_ids = set(b.oracle()["eligible"])
        assert campaign_ids(b.folder) == expected_ids
        frame = pl.DataFrame({"客户编号": sorted(expected_ids, reverse=True), "备注": ["可回访"] * len(expected_ids)})
        assert b.assess(context=context(delivery(frame))).semantic_checks_passed
        wrong_lists = {
            "expired_threshold": campaign_ids(b.folder, threshold=800, gap=14),
            "all_vip_exemptions": campaign_ids(b.folder, universal_vip=True),
        }
        assert all(values != expected_ids for values in wrong_lists.values())
        assert not b.assess(context=context(delivery(frame.head(frame.height - 1)))).semantic_checks_passed
        audit = pl.read_csv(b.folder / "customers.csv").with_columns(
            pl.col("customer_id").is_in(sorted(expected_ids)).alias("本次入选")
        )
        assert b.assess(context=context(delivery(audit))).semantic_checks_passed
        wrong_audit = audit.with_columns(
            pl.when(pl.col("customer_id") == sorted(expected_ids)[0])
            .then(False)
            .otherwise(pl.col("本次入选"))
            .alias("本次入选")
        )
        assert not b.assess(context=context(delivery(wrong_audit))).semantic_checks_passed

        folder = support.FIXTURE_ROOT / "routing" / variant
        with (folder / "history.csv").open(encoding="utf-8") as file:
            history = list(csv.DictReader(file))
        with (folder / "new_tickets.csv").open(encoding="utf-8") as file:
            incoming = list(csv.DictReader(file))
        labels = json.loads((folder / "oracle.json").read_text(encoding="utf-8"))["labels"]
        model = make_pipeline(
            TfidfVectorizer(analyzer="char", ngram_range=(2, 4)), LogisticRegression(C=10, max_iter=1000)
        )
        model.fit([row["message"] for row in history], [row["queue"] for row in history])
        predictions = model.predict([row["message"] for row in incoming]).tolist()
        frame = pl.DataFrame(
            {"编号": [row["ticket_id"] for row in incoming], "队列": predictions, "备注": ["分流"] * len(incoming)}
        )
        accuracy = prediction_accuracy(frame, labels)
        assert accuracy is not None and accuracy >= 0.9
        assert prediction_accuracy(frame.reverse().select("备注", "队列", "编号"), labels) == accuracy
        channel_map = {row["channel"]: row["queue"] for row in history}
        shortcut = sum(channel_map[row["channel"]] == labels[row["ticket_id"]] for row in incoming) / len(incoming)
        assert shortcut == 0
        encoded = frame.with_columns(pl.col("队列").replace({"物流": "A", "退换货": "B", "发票": "C"}))
        assert prediction_accuracy(encoded, labels) == accuracy
        projections = support.prediction_projections(
            frame.with_columns(pl.Series("channel", [row["channel"] for row in incoming])), labels
        )
        assert any(item.prediction_column == "队列" and item.accuracy == accuracy for item in projections)
        routing_module = importlib.import_module("tests.e2e.agent_harness.test_business_routing_reuse")
        c = routing_module.RoutingReuseTask(variant)
        first = replace(
            delivery(None), artifacts=(replace(delivery(None).artifacts[0], model_id="saved", model_available=True),)
        )
        second = replace(
            delivery(frame), artifacts=(replace(delivery(frame).artifacts[0], model_id="saved", model_available=True),)
        )
        assert c.assess(context=context(first, second)).semantic_checks_passed
        replacement = replace(second, artifacts=(replace(second.artifacts[0], model_id="new"),))
        assert not c.assess(context=context(first, replacement)).semantic_checks_passed
        findings[variant] = {
            "revenue": a_results,
            "campaign": {
                "sql_reference_matches": True,
                "eligible": sorted(expected_ids),
                "distinct_wrong_policies": list(wrong_lists),
            },
            "routing": {
                "reference_accuracy": accuracy,
                "channel_shortcut_accuracy": shortcut,
                "same_model_required": True,
                "equivalent_table_passes": True,
            },
        }
    verify_delivery_boundary()
    findings["delivery_boundary"] = {"orphan_ignored": True, "earlier_content_frozen": True}
    destination = Path(__file__).with_name("formal_observations.json")
    destination.write_text(json.dumps(findings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(findings, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()

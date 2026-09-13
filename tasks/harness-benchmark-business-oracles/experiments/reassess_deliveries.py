"""Reassess a preserved real delivery; never relabel this as a new Subject run."""

import argparse
import importlib
import json
from pathlib import Path
import sys

import polars as pl

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
support = importlib.import_module("tests.e2e.agent_harness._infra.business_tasks")
contracts = importlib.import_module("tests.e2e.agent_harness._infra.contracts")
runner = importlib.import_module("tests.e2e.agent_harness._infra.runner")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--judge-settings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(args.report.read_text(encoding="utf-8"))
    variant = source["case_id"].rsplit(".", 1)[-1]
    module, class_name = {
        "campaign": ("test_business_campaign_eligibility", "CampaignEligibilityTask"),
        "revenue": ("test_business_revenue_revision", "RevenueRevisionTask"),
    }[source["case_id"].split(".")[1]]
    case = getattr(importlib.import_module(f"tests.e2e.agent_harness.{module}"), class_name)(variant)
    turns = []
    for turn in source["turns"]:
        evidence = turn["delivery_evidence"]
        final_text = evidence[0].partition("final_answer=")[2]
        artifacts = []
        for item in evidence[1:]:
            payload = json.loads(item)
            artifacts.append(
                support.DeliveredArtifact(
                    uri=payload["uri"],
                    title=payload["title"],
                    kind="dataset",
                    frame=pl.DataFrame(payload["rows"]) if payload["rows"] is not None else None,
                    report=payload["report"],
                    model_id=None,
                    model_available=False,
                )
            )
        delivery = support.Delivery(final_text, tuple(artifacts), (), True, source["integrity"]["passed"])
        turns.append(
            contracts.BenchmarkTurnObservation(
                snapshot=None,
                evidence=delivery,
                result=contracts.BenchmarkTurnResult(
                    index=turn["index"],
                    run_status=contracts.BenchmarkRunStatus(turn["run_status"]),
                    subject_metrics=contracts.BenchmarkMetrics(),
                ),
            )
        )
    context = contracts.BenchmarkCaseContext(
        snapshot=None,
        services=None,
        source_state=None,
        run_dataset_ids=frozenset(),
        runtime_home=ROOT,
        turns=tuple(turns),
    )
    assessment = case.assess(context=context)
    judge = runner._evaluate_judge(
        assessment=assessment,
        run_status=contracts.BenchmarkRunStatus(source["run_status"]),
        configuration=runner._load_judge_configuration(judge_settings_path=args.judge_settings, judge_model_key=None),
        subject_model_key=source["provider_model"],
    )
    result = {
        "report_kind": "xenix.agent_harness.delivery_reassessment",
        "source_run_id": source["run_id"],
        "source_report": str(args.report.resolve()),
        "original_fixture_sha256": source["identity"]["fixture_sha256"],
        "case_id": case.case_id,
        "new_subject_calls": 0,
        "semantic_checks": [check.to_payload() for check in assessment.semantic_checks],
        "judge": judge.to_payload(),
        "note": "Current oracle applied to preserved delivery; original live report remains unchanged. This is evaluator correction, not Subject improvement.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        {
            "structural_pass": assessment.semantic_checks_passed,
            "judge_status": judge.status.value,
            "judge_verdict": judge.verdict.value,
            "judge_tokens": judge.metrics.token_usage.total_tokens if judge.metrics.token_usage else None,
        }
    )


if __name__ == "__main__":
    main()

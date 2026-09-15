"""Two labelled counterexamples for candidate-column and extra-row judgement."""

import argparse
import importlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
probe = importlib.import_module("tasks.harness-benchmark-wave2.experiments.verify_wave2")
runner = importlib.import_module("tests.e2e.agent_harness._infra.runner")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--judge-settings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    task = probe.cases.RestockDecisionTask()
    fixture_hash = task.validate_input()
    _, winners = probe.enumerate_plans(task)
    correct = probe.frame(winners[0])
    cases = (
        (
            "wrong_selected_column",
            correct.rename({"本次订货批数": "备选但未采用"}).with_columns(probe.pl.lit(0).alias("推荐采购批数")),
            "本次我决定不下单。推荐采购批数均为零；表中另一个备选组合没有采用。",
        ),
        (
            "invented_purchase",
            probe.pl.concat([correct, probe.frame({"NOT-OFFERED": 1})]),
            "请采购表内所有报价，包含最后一行 NOT-OFFERED 一批；全部满足要求。",
        ),
    )
    configuration = runner._load_judge_configuration(judge_settings_path=args.judge_settings, judge_model_key=None)
    results = []
    for name, frame, text in cases:
        assessment = task.assess(context=probe.context(frame, text))
        # These specifically exercise the required Judge seam after a matching
        # candidate projection; deterministic facts alone must not claim success.
        assert assessment.semantic_checks_passed
        result = runner._evaluate_judge(
            assessment=assessment,
            run_status=probe.contracts.BenchmarkRunStatus.COMPLETED,
            configuration=configuration,
            subject_model_key="deepseek/deepseek-v4-flash",
        )
        results.append(
            {
                "name": name,
                "expected_verdict": "fail",
                "artifact_evidence": list(assessment.judge_input.artifact_evidence),
                "judge": result.to_payload(),
            }
        )
    payload = {
        "report_kind": "xenix.agent_harness.author_judge_probe",
        "fixture_sha256": fixture_hash,
        "new_subject_calls": 0,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print([(item["name"], item["judge"]["status"], item["judge"]["verdict"]) for item in results])


if __name__ == "__main__":
    main()

"""Label a preserved revenue delivery and explicit author-edited contrasts."""

from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
cases = importlib.import_module("tests.e2e.agent_harness.test_business_revenue_revision")


def main():
    source = (
        ROOT
        / "build/agent-harness-business-confirmation/business.revenue.v1.confirmation-deepseek-deepseek-v4-flash-66f6f9ecc29f466995ee090e5b8190a9.json"
    )
    report = json.loads(source.read_text(encoding="utf-8"))
    actual = [item for turn in report["turns"] for item in turn["delivery_evidence"]]
    artifacts = [[json.loads(item) for item in turn["delivery_evidence"][1:]] for turn in report["turns"]]
    texts = (
        "2026 年 6 月净回款按本月已支付订单减本月发生退款计算；订单、退款分别按业务编号去重，不同编号即使内容相同也保留。cancelled 不计收入；旧订单在六月发生的退款仍计本月，月外退款不计。四区域均保留，区域按门店表。东区 40,750、西区 32,900、北区 22,000、南区 -1,200 元，东区净回款最高；南区无本月已支付订单，只有旧订单退款。仅比较本月账务结果，不据此推出长期经营优劣。可继续使用的表见 {links}。",
        "同 refund_id 用新文件覆盖，其他退款保留。更新后东区 40,350、西区 22,900、北区 22,000、南区 0 元，分别变化 -400、-10,000、0、+1,200；排序仍为东、西、北、南。东区新增旧订单退款 R21 计六月；西区 R20 增加退款 11,000，同时 R05 从 1,500 更正到 500，合计多退 10,000。南区 R12 改为七月发生，移出六月；北区新增 R22 也是七月，所以六月不变。西区退款 14,400.25 高于东区 9,000.50，不应说东区退款最高。七月新增/转入影响南、北区。更新表见 {links}。",
    )

    def evidence(final_texts, tables):
        values = []
        for index, (text, outputs) in enumerate(zip(final_texts, tables, strict=True), 1):
            links = "、".join(f"[汇总表]({item['uri']})" for item in outputs)
            values.append(f"user_turn={index}; final_answer={text.format(links=links)}")
            values.extend(json.dumps(item, ensure_ascii=False) for item in outputs)
        return values

    equivalent = deepcopy(artifacts)
    for turn in equivalent:
        for artifact in turn:
            rows = artifact["rows"]
            if rows:
                total = {key: "合计" if key == "region" else sum(row[key] for row in rows) for key in rows[0]}
                artifact["rows"] = [*reversed(rows), total]
    task = cases.RevenueRevisionTask("confirmation")
    packets = [
        {
            "fixture_id": "complete_correct",
            "expected_verdict": "pass",
            "origin": "Author-corrected explanation with preserved real linked tables.",
            "artifact_evidence": evidence(texts, artifacts),
        },
        {
            "fixture_id": "equivalent_totals",
            "expected_verdict": "pass",
            "origin": "Author-edited row ordering and correct aggregate rows; same decision.",
            "artifact_evidence": evidence(texts, equivalent),
        },
        {
            "fixture_id": "missing_revision_explanation",
            "expected_verdict": "partial",
            "origin": "Author removes only requested second-turn change explanation.",
            "artifact_evidence": evidence((texts[0], "更新后的区域净回款已计算，下载表见 {links}。"), artifacts),
        },
        {
            "fixture_id": "real_material_false_claim",
            "expected_verdict": "fail",
            "origin": f"Unedited final delivery from run {report['run_id']}; materially wrong refund ranking and affected-region claims despite correct tables.",
            "artifact_evidence": actual,
        },
    ]
    manifest = {
        "manifest_kind": "xenix.agent_harness.judge_calibration_manifest",
        "schema_version": 1,
        "manifest_id": "business.revenue.severity.v1",
        "source_run_id": report["run_id"],
        "label_basis": "Labels were authored from user rules, source records and visible claims before this calibration run; original Subject/Judge report remains unchanged.",
        "suites": [
            {
                "suite_id": "revenue_severity",
                "rubric_symbol": "tests.e2e.agent_harness.test_business_revenue_revision:RUBRIC",
                "task_intent": task.intent(),
                "facts": list(task.judge_facts()),
                "packets": packets,
            }
        ],
    }
    output = ROOT / "tests/e2e/agent_harness/fixtures/business_tasks/revenue/judge_calibration.json"
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {len(packets)} labelled packets: {output}")


if __name__ == "__main__":
    main()

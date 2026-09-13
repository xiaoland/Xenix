"""Disposable task-design experiments; not collected by pytest or the benchmark.

Generate new miniature business inputs and author-only observations. No Xenix
runtime or provider is started. The routing probe uses the installed sklearn.
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import random


ROOT = Path(__file__).resolve().parent


def write_csv(relative, rows):
    path = ROOT / "inputs" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_text(relative, text):
    path = ROOT / "inputs" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def unique(rows, key):
    return list({row[key]: row for row in rows}.values())


def revenue_probe():
    stores = [
        dict(store_id=s, region=r) for s, r in [("S01", "东区"), ("S02", "西区"), ("S03", "西区"), ("S04", "东区")]
    ]
    order_values = [
        ("O01", "2026-06-01", "S01", 10000, "paid"),
        ("O02", "2026-06-30", "S01", 20000, "paid"),
        ("O03", "2026-06-10", "S02", 8000, "paid"),
        ("O04", "2026-06-20", "S02", 12000, "paid"),
        ("O05", "2026-06-12", "S03", 9000, "paid"),
        ("O06", "2026-06-18", "S03", 7000, "paid"),
        ("O07", "2026-06-15", "S04", 15000, "paid"),
        ("O08", "2026-05-31", "S02", 5000, "paid"),
        ("O09", "2026-07-01", "S04", 11000, "paid"),
        ("O10", "2026-06-24", "S01", 3000, "cancelled"),
        ("O11", "2026-06-29", "S04", 1000, "paid"),
        ("O12", "2026-06-25", "S01", 2000, "paid"),
    ]
    orders = [
        dict(zip(("order_id", "paid_date", "store_id", "amount_yuan", "status"), row, strict=True))
        for row in order_values
    ]
    orders.append(dict(orders[-1]))
    refund_values = [
        ("R01", "O01", "2026-06-10", 1000),
        ("R02", "O02", "2026-07-03", 3000),
        ("R03", "O08", "2026-06-05", 2000),
        ("R04", "O03", "2026-06-15", 500),
        ("R05", "O05", "2026-06-23", 1500),
        ("R06", "O12", "2026-06-29", 200),
        ("R07", "O07", "2026-06-30", 7000),
        ("R08", "O08", "2026-05-31", 500),
        ("R09", "O11", "2026-06-30", 100),
    ]
    refunds = [
        dict(zip(("refund_id", "order_id", "refund_date", "amount_yuan"), row, strict=True)) for row in refund_values
    ]
    refunds.append(dict(refunds[-1]))
    updates = [
        dict(refund_id="R07", order_id="O07", refund_date="2026-06-30", amount_yuan=9000),
        dict(refund_id="R10", order_id="O02", refund_date="2026-06-30", amount_yuan=9000),
        dict(refund_id="R11", order_id="O05", refund_date="2026-07-01", amount_yuan=500),
    ]
    regions = {row["store_id"]: row["region"] for row in stores}

    def totals(order_rows, refund_rows, *, deduplicate=True, only_june_orders=False, all_refund_dates=False):
        order_rows = unique(order_rows, "order_id") if deduplicate else order_rows
        refund_rows = unique(refund_rows, "refund_id") if deduplicate else refund_rows
        if only_june_orders:
            order_rows = [r for r in order_rows if r["paid_date"].startswith("2026-06")]
        by_id = {row["order_id"]: row for row in order_rows}
        result = {"东区": 0, "西区": 0}
        for row in order_rows:
            if row["status"] == "paid" and row["paid_date"].startswith("2026-06"):
                result[regions[row["store_id"]]] += row["amount_yuan"]
        for row in refund_rows:
            if row["order_id"] in by_id and (all_refund_dates or row["refund_date"].startswith("2026-06")):
                result[regions[by_id[row["order_id"]]["store_id"]]] -= row["amount_yuan"]
        return result

    first = totals(orders, refunds)
    merged = unique(refunds + updates, "refund_id")
    second = totals(orders, merged)
    manual_first = {"东区": 39700, "西区": 32000}
    manual_second = {"东区": 28700, "西区": 32000}
    if first != manual_first or second != manual_second:
        raise RuntimeError("Revenue draft disagrees with the hand-calculated example")
    shuffled_orders, shuffled_refunds = list(orders), list(refunds)
    random.Random(77).shuffle(shuffled_orders)
    random.Random(23).shuffle(shuffled_refunds)
    mutants = {
        "count_export_duplicates": totals(orders, refunds, deduplicate=False),
        "drop_refunds_of_prior_month_orders": totals(orders, refunds, only_june_orders=True),
        "use_all_refund_dates": totals(orders, refunds, all_refund_dates=True),
        "ignore_refunds": totals(orders, []),
    }
    second_mutants = {
        "reuse_stale_answer": first,
        "append_replacement_as_new_refund": totals(
            unique(orders, "order_id"), unique(refunds, "refund_id") + updates, deduplicate=False
        ),
    }
    for name, rows in [("orders.csv", orders), ("refunds.csv", refunds), ("stores.csv", stores)]:
        write_csv(f"revenue/round1/{name}", rows)
    write_csv("revenue/round2/refund_updates.csv", updates)
    write_text(
        "revenue/round1/business_notes.txt",
        "月结口径：2026 年 6 月净回款，单位元。计入本月 paid 订单的回款，减去本月实际退款；"
        "退款按发生月计入，即使原订单来自以前月份。日期均为本地业务日期，月初月末均包含。"
        "按门店信息表中的区域归属。订单与退款分别以各自编号识别，同编号完全相同的重复导出行不重复计数。"
        "cancelled 订单不形成回款。附件包含相邻月份记录以供业务关联。\n",
    )
    write_text(
        "revenue/round1/request.txt",
        "请按附件中的月结口径，整理各区域 2026 年 6 月的净回款，说明哪个区域表现更好。"
        "请交付可继续使用的汇总表，并简要解释会影响结论的数据处理。\n",
    )
    write_text(
        "revenue/round2/request.txt",
        "这里是刚补登记和更正的退款。同退款编号以本次文件为准，原来未出现于本文件的退款仍保留。"
        "请沿用刚才的月结口径更新结果，说明各区域相对上一版的变化，以及区域排序是否改变。\n",
    )
    return {
        "round1": first,
        "round2": second,
        "delta": {k: second[k] - first[k] for k in first},
        "rank_reverses": max(first, key=first.get) != max(second, key=second.get),
        "equivalent_row_permutation": totals(shuffled_orders, shuffled_refunds) == first,
        "equivalent_additional_duplicate": totals(orders + [dict(orders[0])], refunds) == first,
        "wrong_round1_outputs": mutants,
        "wrong_round2_outputs": second_mutants,
        "wrong_behaviors_distinguished": sum(v != first for v in mutants.values())
        + sum(v != second for v in second_mutants.values()),
    }


def campaign_probe():
    rows = [
        ("C01", "南京", "1000", "2026-05-31", False, 0, True),
        ("C02", "苏州", "999.99", "2026-05-01", False, 0, True),
        ("C03", "南京", "1000", "2026-06-01", False, 0, True),
        ("C04", "苏州", "1000", "2026-06-02", False, 0, True),
        ("C05", "无锡", "3000", "2026-04-01", False, 0, True),
        ("C06", "苏州", "0", "2026-05-01", True, 0, True),
        ("C07", "南京", "2000", "2026-05-01", True, 1, True),
        ("C08", "南京", "2000", "", False, 0, True),
        ("C09", "苏州", "2000", "2026-05-01", False, 0, False),
        ("C10", "南京", "800", "2026-05-01", False, 0, True),
        ("C11", "苏州", "1000", "2026-05-01", False, 0, True),
        ("C12", "南京", "1000", "2026-05-01", False, 2, True),
        ("C13", "南京", "1000", "2026-07-01", False, 0, True),
        ("C14", "苏州", "0", "2026-06-15", True, 0, True),
        ("C15", "南京", "1000", "2026-05-02", False, 0, True),
        ("C16", "苏州", "999.99", "2026-05-30", True, 0, True),
    ]
    fields = ("customer_id", "city", "net_spend_90d_yuan", "last_contact_date", "vip", "open_service_cases", "active")
    customers = [dict(zip(fields, row, strict=True)) for row in rows]

    def eligible(
        source,
        *,
        threshold="1000",
        cooldown=30,
        strict_spend=False,
        strict_days=False,
        ignore_open=False,
        all_cities=False,
        ignore_vip=False,
    ):
        selected = []
        for row in source:
            days = (
                (date(2026, 7, 1) - date.fromisoformat(row["last_contact_date"])).days
                if row["last_contact_date"]
                else 10000
            )
            enough = (
                Decimal(row["net_spend_90d_yuan"]) > Decimal(threshold)
                if strict_spend
                else Decimal(row["net_spend_90d_yuan"]) >= Decimal(threshold)
            )
            if (
                row["active"]
                and (all_cities or row["city"] in {"南京", "苏州"})
                and (ignore_open or row["open_service_cases"] == 0)
                and (days > cooldown if strict_days else days >= cooldown)
                and (enough or (row["vip"] and not ignore_vip))
            ):
                selected.append(row["customer_id"])
        return sorted(selected)

    expected = ["C01", "C03", "C06", "C08", "C11", "C15", "C16"]
    actual = eligible(customers)
    if actual != expected:
        raise RuntimeError("Campaign draft disagrees with manually reviewed eligibility")
    variants = {
        "use_superseded_policy": eligible(customers, threshold="800", cooldown=14),
        "amount_boundary_exclusive": eligible(customers, strict_spend=True),
        "contact_boundary_exclusive": eligible(customers, strict_days=True),
        "ignore_open_service_cases": eligible(customers, ignore_open=True),
        "ignore_applicable_cities": eligible(customers, all_cities=True),
        "ignore_vip_exception": eligible(customers, ignore_vip=True),
    }
    reordered = list(reversed(customers))
    renamed = [dict(row, customer_id="NEW-" + row["customer_id"]) for row in customers]
    write_csv("campaign/customers.csv", customers)
    write_text(
        "campaign/current_policy.txt",
        "七月老客回访规则，自 2026-07-01 生效，替代六月版本。仅对南京、苏州的在营客户。"
        "最近 90 天净消费至少 1000 元；VIP 免除此金额门槛。所有客户均须没有未结服务单，"
        "且距上次回访至少 30 天，未回访过的客户满足间隔要求。VIP 不免除城市、在营、服务单或间隔要求。\n",
    )
    write_text(
        "campaign/superseded_policy.txt",
        "六月老客回访规则，有效期 2026-06-01 至 2026-06-30。仅对南京、苏州的在营客户，"
        "最近 90 天净消费至少 800 元，VIP 免金额门槛；没有未结服务单，距上次回访至少 14 天，未回访过的满足间隔要求。\n",
    )
    current_policy = (ROOT / "inputs/campaign/current_policy.txt").read_text(encoding="utf-8")
    write_text("campaign/counterfactual/current_policy_1200.txt", current_policy.replace("1000 元", "1200 元"))
    write_text(
        "campaign/data_notes.txt",
        "客户表是 2026-07-01 的业务快照。净消费已按统一口径扣除退款，无需再次扣除。"
        "last_contact_date 为空表示从未回访；vip、active 为 True/False；open_service_cases 为未结服务单数。\n",
    )
    write_text(
        "campaign/request.txt",
        "今天是 2026 年 7 月 1 日。请根据知识库中适用的老客回访规则和这份客户快照，"
        "交付本次可以回访的客户名单。简要说明采用的规则依据，以及会影响入选的主要例外。\n",
    )
    return {
        "eligible_ids": actual,
        "wrong_outputs": variants,
        "wrong_behaviors_distinguished": sum(v != expected for v in variants.values()),
        "policy_counterfactual_1200": eligible(customers, threshold="1200"),
        "equivalent_row_permutation": eligible(reordered) == expected,
        "equivalent_customer_renaming": eligible(renamed) == ["NEW-" + x for x in expected],
    }


def routing_probe():
    import sklearn
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, f1_score
    from sklearn.pipeline import make_pipeline

    training = {
        "物流": [
            "快递一直没送到，请查运输进度",
            "包裹在中转站停了三天",
            "运单显示派送但没有收到",
            "想知道快递什么时候到",
            "物流记录已经两天没更新",
            "包裹送错地址请帮忙查询",
            "显示签收但我还没拿到包裹",
            "快递送到哪个驿站了",
            "发货后一直查不到物流",
            "运单号查询不到运输信息",
            "包裹在配送途中丢失了吗",
            "快递延误请联系配送员",
        ],
        "退换": [
            "收到的杯子破损了需要换货",
            "衣服尺寸不合适想退货",
            "商品颜色发错了申请换货",
            "产品无法正常使用要求退货",
            "收到的商品少了配件要补发",
            "商品有质量问题想换一个",
            "刚收到的电器不能开机想换货",
            "退货申请什么时候处理",
            "想更换商品的尺寸",
            "包装内商品损坏要求补发",
            "买错型号需要办理退货",
            "申请换货后如何寄回商品",
        ],
        "票据": [
            "发票抬头写错了需要更正",
            "公司税号错误请重新开票",
            "付款后还没收到电子发票",
            "发票金额与实付金额不一致",
            "需要下载本次订单的发票",
            "申请补开上个月的电子发票",
            "请修改发票上的公司名称",
            "开票信息中的税号需要更新",
            "已付款订单如何获取发票",
            "电子发票文件打不开",
            "需要重新发送开具的发票",
            "发票上显示了错误的金额",
        ],
    }
    future = {
        "物流": [
            "请查一下包裹的运输进度，三天没动了",
            "快递显示已签收实际还没收到",
            "物流停在中转站很久了",
            "运单号有了却查不到包裹",
            "包裹送错了驿站，麻烦查询",
            "配送延误了，想知道到货时间",
        ],
        "退换": [
            "新收到的商品破损，想换货",
            "尺码小了，需要办理退货",
            "发来的商品型号不对，申请换货",
            "商品缺少配件，希望补发",
            "设备刚到就不能使用，要求退货",
            "退货申请已经提交，怎么寄回商品",
        ],
        "票据": [
            "公司名称开错了，麻烦重开发票",
            "付款完成了，请补开电子发票",
            "发票中的税号需要修改",
            "发票金额不对，请核对实付金额",
            "请重新发送电子发票文件",
            "已开具的发票在哪里下载",
        ],
    }
    labels = list(training)
    channels = {"物流": "网页", "退换": "电话", "票据": "应用"}
    shifted = {"物流": "电话", "退换": "应用", "票据": "网页"}
    train_rows, future_rows, truths = [], [], []
    for queue, texts in training.items():
        for i, text in enumerate(texts):
            train_rows.append(
                dict(
                    ticket_id=f"H{labels.index(queue)}-{i:02}",
                    customer_batch=f"G{labels.index(queue)}-{i // 2:02}",
                    channel=channels[queue],
                    message=text,
                    queue=queue,
                )
            )
    for queue, texts in future.items():
        for i, text in enumerate(texts):
            identity = f"N{labels.index(queue)}-{i:02}"
            future_rows.append(
                dict(
                    ticket_id=identity,
                    customer_batch=f"NEW{labels.index(queue)}-{i:02}",
                    channel=shifted[queue],
                    message=text,
                )
            )
            truths.append(dict(ticket_id=identity, queue=queue))
    pipe = make_pipeline(TfidfVectorizer(analyzer="char", ngram_range=(2, 4)), LogisticRegression(C=10, max_iter=1000))
    pipe.fit([r["message"] for r in train_rows], [r["queue"] for r in train_rows])
    prediction = pipe.predict([r["message"] for r in future_rows])
    expected = [r["queue"] for r in truths]
    channel_lookup = {v: k for k, v in channels.items()}
    channel_prediction = [channel_lookup[r["channel"]] for r in future_rows]
    reordered_rows = [
        dict(
            message=r["message"],
            channel=r["channel"],
            customer_batch=r["customer_batch"],
            ticket_id=r["ticket_id"],
            followup_note="新增批次",
        )
        for r in reversed(future_rows)
    ]
    reordered_prediction = pipe.predict([r["message"] for r in reordered_rows])
    changed_meaning = []
    changed_truth = []
    for row, truth in zip(future_rows, truths, strict=True):
        new_queue = labels[(labels.index(truth["queue"]) + 1) % len(labels)]
        changed_meaning.append(dict(row, message=future[new_queue][0]))
        changed_truth.append(new_queue)
    changed_prediction = pipe.predict([r["message"] for r in changed_meaning])
    write_csv("routing/history.csv", train_rows)
    write_csv("routing/round2/new_tickets.csv", future_rows)
    write_csv("routing/equivalent/new_tickets_reordered.csv", reordered_rows)
    write_csv("routing/counterfactual/new_tickets_changed_meaning.csv", changed_meaning)
    write_text(
        "routing/queue_definitions.txt",
        "物流队列处理包裹运输、配送和签收查询；退换队列处理商品质量、错发缺件与退换货；"
        "票据队列处理开票、发票更正与获取。channel 只是客户发起工单的入口，不决定处理队列。"
        "同一 customer_batch 可能有同一事件的多次沟通记录。\n",
    )
    write_text(
        "routing/round1_request.txt",
        "我们会持续收到新工单，希望至少九成能够进入合适队列。请根据历史记录和队列说明，建立并保存可供后续批次使用的分流方案，"
        "说明你用什么证据判断它是否值得采用，以及大概有多少需要人工改队列。\n",
    )
    write_text(
        "routing/round2/request.txt", "这是一批新工单，请沿用刚才保存的方案，交付包含每个工单编号和建议队列的结果。\n"
    )
    return {
        "sklearn_version": sklearn.__version__,
        "reference_model": "character TF-IDF (2-4 grams) + logistic regression, C=10",
        "training_rows": len(train_rows),
        "new_rows": len(future_rows),
        "reference_text_accuracy": float(accuracy_score(expected, prediction)),
        "reference_text_macro_f1": float(f1_score(expected, prediction, average="macro")),
        "majority_accuracy": 1 / len(labels),
        "channel_shortcut_accuracy": float(accuracy_score(expected, channel_prediction)),
        "equivalent_reordering_and_extra_column": list(prediction) == list(reversed(reordered_prediction)),
        "meaning_counterfactual_accuracy": float(accuracy_score(changed_truth, changed_prediction)),
        "meaning_counterfactual_truth": [
            dict(ticket_id=r["ticket_id"], queue=q) for r, q in zip(changed_meaning, changed_truth, strict=True)
        ],
        "new_ticket_truth": truths,
        "reference_errors": [
            dict(ticket_id=r["ticket_id"], expected=y, observed=p)
            for r, y, p in zip(future_rows, expected, prediction, strict=True)
            if y != p
        ],
        "limitation": "Miniature hand-authored texts prove only candidate signal and a shortcut contrast; no subject run, retained-model reuse, calibrated quality threshold or representative language coverage was tested.",
    }


def main():
    report = {
        "kind": "task_design_probe",
        "design_date": "2026-09-13",
        "executed_at": datetime.now().astimezone().isoformat(),
        "provider_calls": 0,
        "revenue": revenue_probe(),
        "campaign": campaign_probe(),
        "routing": routing_probe(),
    }
    path = ROOT / "observations.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name in ("revenue", "campaign", "routing"):
        print(
            name,
            json.dumps(
                {
                    k: v
                    for k, v in report[name].items()
                    if k
                    not in {
                        "wrong_round1_outputs",
                        "wrong_round2_outputs",
                        "wrong_outputs",
                        "new_ticket_truth",
                        "meaning_counterfactual_truth",
                    }
                },
                ensure_ascii=False,
            ),
        )
    print(path)


if __name__ == "__main__":
    main()

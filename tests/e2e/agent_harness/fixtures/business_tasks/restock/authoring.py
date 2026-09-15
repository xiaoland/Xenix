"""Author independent purchase catalogs and controlled business contrasts.

The dynamic program produces author-side truth only; live tasks never import it.
"""

import csv
from datetime import date
from decimal import Decimal
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STANDARD = """offer_id,product,cost_yuan,margin_yuan,boxes,arrival_date,max_batches
Q101,气泡水,780.00,460.00,5,2026-09-23,2
Q102,无糖茶,760.00,460.00,5,2026-09-24,2
Q203,每日坚果,520.00,360.00,3,2026-09-22,2
Q204,燕麦饼干,440.00,235.00,3,2026-09-25,2
Q305,纸杯,150.00,60.00,1,2026-09-23,3
Q306,便携湿巾,210.00,90.00,2,2026-09-24,2
Q407,保温袋,610.00,330.00,4,2026-09-26,1
Q408,节日礼盒,1250.00,640.00,9,2026-09-24,1
Q509,挂耳咖啡,680.00,430.00,4,2026-09-23,1
Q510,小点心,380.00,195.00,2,2026-09-24,1
Q611,便携餐具,290.00,145.00,2,2026-09-25,2
Q612,混合果汁,560.00,420.00,3,2026-09-29,2
"""
CONFIRMATION = """offer_id,product,cost_yuan,margin_yuan,boxes,arrival_date,max_batches
P71,护手霜套装,425.50,238.20,2,2026-10-08,3
P26,旅行洗护装,610.25,350.50,3,2026-10-09,2
P90,香薰礼盒,920.00,465.00,5,2026-10-07,1
P13,小支润唇膏,188.75,103.25,1,2026-10-09,4
P64,补水面膜,355.00,219.00,2,2026-10-10,2
P38,试用礼袋,130.00,-8.00,1,2026-10-07,3
P52,限量香水,700.00,590.00,2,2026-10-08,0
P87,美容工具,280.00,165.00,4,2026-10-08,2
P45,洁面巾,245.00,121.00,3,2026-10-09,2
P09,紧急调拨套装,1600.00,610.00,2,2026-10-09,1
"""


def cents(value):
    return int(Decimal(str(value)) * 100)


def optimum(rows, budget, capacity, deadline):
    # State is total spend and occupied boxes, not a preferred SKU combination.
    states = {(0, 0): 0}
    for row in rows:
        limit = int(row["max_batches"]) if date.fromisoformat(row["arrival_date"]) <= deadline else 0
        next_states = {}
        for (spent, occupied), margin in states.items():
            for batches in range(limit + 1):
                cost = spent + batches * cents(row["cost_yuan"])
                boxes = occupied + batches * int(row["boxes"])
                value = margin + batches * cents(row["margin_yuan"])
                if cost <= budget and boxes <= capacity:
                    key = (cost, boxes)
                    next_states[key] = max(next_states.get(key, value), value)
        states = next_states
    return max(states.values())


def main():
    for scenario in (
        "standard",
        "budget_tight",
        "arrival_earlier",
        "margin_lower",
        "margin_higher",
        "no_purchase",
        "confirmation",
    ):
        confirmed = scenario == "confirmation"
        rows = list(csv.DictReader(io.StringIO(CONFIRMATION if confirmed else STANDARD)))
        budget, capacity, deadline = (247500, 11, "2026-10-09") if confirmed else (300000, 18, "2026-09-25")
        if scenario == "budget_tight":
            budget = 225000
        elif scenario == "no_purchase":
            budget = 12000
        for row in rows:
            if scenario == "arrival_earlier" and row["offer_id"] == "Q612":
                row["arrival_date"] = "2026-09-24"
            if row["offer_id"] == "Q203":
                if scenario == "margin_lower":
                    row["margin_yuan"] = "220.00"
                elif scenario == "margin_higher":
                    row["margin_yuan"] = "380.00"
        folder = ROOT / scenario
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / "offers.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        request = (
            f"请根据供应商报价，为本次门店活动制定补货计划。采购预算上限 {Decimal(budget) / 100} 元，"
            f"新增货物最多占 {capacity} 箱仓容，只采购不晚于 {deadline} 到货的批次。"
            "在这些条件下，使本次预计增量毛利最高；同样好的方案任选其一，不要求花完预算。"
            "交付可下载的采购表，包含报价编号和采购批数，说明选择依据、预算与仓容使用量。"
            "如果没有可采购的批次，请说明本次不下单及具体原因，无需制作空文件。\n"
        )
        (folder / "request_1.txt").write_text(request, encoding="utf-8")
        notes = (
            "报价说明\n每行是一种 offer_id 报价，product 为商品名称。cost_yuan 与 margin_yuan 分别是每批采购成本和已确认的预计增量毛利，均为人民币元；boxes 是每批占用箱数。"
            "批次不可拆分，只能订非负整数批；max_batches 是本次最多可订批数，0 表示已无供应。arrival_date 是承诺到货日期，截止当日到货可用。"
            "各批次的成本、毛利和仓容按批数相加，没有额外运费、组合折扣、需求重叠或最低订单额。毛利已扣采购及本次业务费用，不再减一次采购成本。"
            "预计毛利只是本次计划参数，不保证实际销售收益。不同编号是不同报价，即使部分属性相同，也不去重。\n"
        )
        (folder / "business_notes.txt").write_text(notes, encoding="utf-8")
        truth = {
            "budget_cents": budget,
            "capacity_boxes": capacity,
            "deadline": deadline,
            "optimal_margin_cents": optimum(rows, budget, capacity, date.fromisoformat(deadline)),
        }
        (folder / "oracle.json").write_text(json.dumps(truth, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(scenario, truth)


if __name__ == "__main__":
    main()

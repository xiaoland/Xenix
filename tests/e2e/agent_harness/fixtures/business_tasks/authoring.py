"""Reproduce authored business inputs; never imported by the Subject or runner.

Truth files stay on the evaluator side. Each ticket sentence describes a distinct
event; row counts are not increased through template expansion or random copies.
"""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from hashlib import sha256
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def table(path: Path, columns: str, rows: list[list[object]]) -> None:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(columns.split(","))
    writer.writerows(rows)
    write(path, stream.getvalue())


def truth(path: Path, payload: object) -> None:
    write(path / "oracle.json", json.dumps(payload, ensure_ascii=False, indent=2))


ORDERS = """order_id,paid_date,store_id,amount_yuan,status
O01,2026-06-01,S01,10000,paid
O02,2026-06-30,S01,20000,paid
O03,2026-06-10,S02,8000,paid
O04,2026-06-20,S02,12000,paid
O05,2026-06-12,S03,9000,paid
O06,2026-06-18,S03,7000,paid
O07,2026-06-15,S04,15000,paid
O08,2026-05-31,S02,5000,paid
O09,2026-07-01,S04,11000,paid
O10,2026-06-24,S01,3000,cancelled
O11,2026-06-29,S04,1000,paid
O12,2026-06-25,S01,2000,paid
O12,2026-06-25,S01,2000,paid
O13,2026-06-09,S05,11000,paid
O14,2026-06-09,S05,11000,paid
O15,2026-04-30,S06,1800,paid
O16,2026-06-21,S07,950.25,paid
O17,2026-06-21,S08,900.50,paid
O18,2026-05-20,S05,6500,paid
O19,2026-07-02,S03,4100,paid
O20,2026-06-30,S06,2700,cancelled
O21,2026-06-02,S07,350,paid
O22,2026-06-16,S08,450,paid
O23,2026-06-26,S05,0,paid
O24,2026-05-01,S04,7800,paid
"""
STORES = """store_id,region
S01,东区
S02,西区
S03,西区
S04,东区
S05,北区
S06,南区
S07,西区
S08,东区
"""
REFUNDS = """refund_id,order_id,refund_date,amount_yuan
R01,O01,2026-06-10,1000
R02,O02,2026-07-03,3000
R03,O08,2026-06-05,2000
R04,O03,2026-06-15,500
R05,O05,2026-06-23,1500
R06,O12,2026-06-29,200
R07,O07,2026-06-30,7000
R08,O08,2026-05-31,500
R09,O11,2026-06-30,100
R09,O11,2026-06-30,100
R12,O15,2026-06-01,1200
R13,O16,2026-06-22,50.25
R14,O17,2026-06-23,100.50
R15,O21,2026-06-30,350
R16,O22,2026-06-30,100
R17,O22,2026-06-30,100
R18,O18,2026-05-31,500
"""
REVENUE_NOTES = """2026 年 6 月区域月结口径
各区域净回款 = 本月已支付订单金额减本月发生的退款金额。退款按退款发生日计入，即使原订单是以前月份；一笔订单可以有多次退款。门店区域以门店表为准。
本月指本地日期 2026-06-01 至 2026-06-30，含首尾两日；所有金额均为人民币元。门店表中的四个区域都要列出，即使没有本月销售；净回款可以为负。
订单只按 order_id、退款只按 refund_id 识别业务记录。导出中相同编号的重复行仅计一次；不同编号即使日期和金额相同也是不同交易。cancelled 订单未收到款项。邻月和更早订单用于解释退款关系，不代表全部属于本月销售。
"""
REVENUE_REQUESTS = (
    "请按下面的月结口径和附件，整理各区域 2026 年 6 月的净回款，说明哪个区域表现更好。请交付可下载、继续使用的汇总表，并简要解释会影响结论的数据处理。",
    "这里是刚补登记和更正的退款。同退款编号以本次文件为准，原来未出现于本文件的退款仍保留。请沿用刚才的月结口径更新结果，说明各区域相对上一版的变化，以及区域排序是否改变。",
)


def revenue() -> None:
    for variant, updates in {
        "standard": """refund_id,order_id,refund_date,amount_yuan
R07,O07,2026-06-30,9000
R10,O02,2026-06-30,9000
R11,O05,2026-07-01,500
R12,O15,2026-06-01,900
R19,O13,2026-07-02,500
""",
        "confirmation": """refund_id,order_id,refund_date,amount_yuan
R05,O05,2026-06-23,500
R20,O04,2026-06-30,11000
R12,O15,2026-07-01,1200
R21,O24,2026-06-30,400
R22,O14,2026-07-01,600
""",
    }.items():
        folder = ROOT / "revenue" / variant
        for name, content in {
            "orders.csv": ORDERS,
            "stores.csv": STORES,
            "refunds.csv": REFUNDS,
            "refund_updates.csv": updates,
            "business_notes.txt": REVENUE_NOTES,
        }.items():
            write(folder / name, content)
        for i, request in enumerate(REVENUE_REQUESTS, 1):
            write(folder / f"request_{i}.txt", request)
        orders = {r["order_id"]: r for r in csv.DictReader(io.StringIO(ORDERS))}
        stores = {r["store_id"]: r["region"] for r in csv.DictReader(io.StringIO(STORES))}
        refunds = {r["refund_id"]: r for r in csv.DictReader(io.StringIO(REFUNDS))}

        def totals(orders, stores, refunds) -> dict[str, float]:
            values = dict.fromkeys(stores.values(), Decimal(0))
            for order in orders.values():
                if order["status"] == "paid" and order["paid_date"].startswith("2026-06"):
                    values[stores[order["store_id"]]] += Decimal(order["amount_yuan"])
            for refund in refunds.values():
                if refund["refund_date"].startswith("2026-06"):
                    values[stores[orders[refund["order_id"]]["store_id"]]] -= Decimal(refund["amount_yuan"])
            return {key: float(value) for key, value in values.items()}

        first = totals(orders, stores, refunds)
        refunds.update({r["refund_id"]: r for r in csv.DictReader(io.StringIO(updates))})
        second = totals(orders, stores, refunds)
        truth(folder, {"rounds": [first, second], "delta": {key: second[key] - value for key, value in first.items()}})


CUSTOMERS = """customer_id,city,net_spend_90d_yuan,last_contact_date,vip,open_service_cases,active
C01,南京,1000,2026-06-01,false,0,true
C02,南京,999.99,2026-05-01,false,0,true
C03,苏州,1600,2026-05-31,false,0,true
C04,南京,1500,2026-06-02,false,0,true
C05,南京,2000,2026-05-01,false,1,true
C06,南京,200,2026-05-01,true,0,true
C07,苏州,400,2026-06-10,true,0,true
C08,苏州,0,,true,0,true
C09,上海,2500,2026-05-01,false,0,true
C10,南京,2200,2026-05-01,false,0,false
C11,苏州,1100,,false,0,true
C12,南京,900,2026-06-10,false,0,true
C13,南京,800,2026-06-01,false,0,true
C14,南京,800,2026-06-01,true,2,true
C15,苏州,1000,,false,0,true
C16,南京,2500,2026-01-01,false,0,true
C17,杭州,1900,2026-04-01,false,0,true
C18,杭州,0,,true,0,true
C19,南京,1199.99,2026-05-15,false,0,true
C20,苏州,1200,2026-06-17,false,0,true
C21,南京,3000,2026-06-18,false,0,true
C22,苏州,5000,,false,3,true
C23,南京,-120,,true,0,true
C24,苏州,1600,2026-05-31,true,0,false
C25,杭州,2400,2026-02-02,true,1,true
C26,无锡,2400,,true,0,true
C27,苏州,1000,2026-06-01,false,0,true
C28,南京,1200,2026-06-16,false,0,true
C29,南京,1300,2026-06-17,false,0,true
C30,杭州,1300,2026-06-18,false,0,true
C31,苏州,1199.99,,false,0,true
C32,南京,0,2026-05-01,false,0,true
"""


def campaign() -> None:
    for variant, today, threshold, gap, cities in (
        ("standard", "2026-07-01", 1000, 30, ("南京", "苏州")),
        ("confirmation", "2026-08-01", 1200, 45, ("南京", "苏州", "杭州")),
    ):
        folder = ROOT / "campaign" / variant
        write(folder / "customers.csv", CUSTOMERS)
        write(
            folder / "data_notes.txt",
            "这是本次活动当日的客户快照。金额为已扣退款的近 90 日净消费（人民币元），无须重算。last_contact_date 为空表示从未回访；true/false 为布尔值；open_service_cases 是未结服务单数量。不同 customer_id 是不同客户，即使其他字段相同。",
        )
        write(
            folder / "request_1.txt",
            f"今天是 {today}。请根据知识库中适用的老客回访规则和这份客户快照，交付可下载的本次回访名单表（仅列入选客户或明确标记是否入选均可）。简要说明采用的规则依据，以及会影响入选的主要例外。",
        )
        rules = {
            "客户运营六月活动.txt": "老客回访活动规则（2026-06-01 至 2026-06-30 有效）\n仅限南京、苏州在营客户，近 90 日净消费至少 800 元，距离上次回访至少 14 天或从未回访。VIP 仅免消费门槛。有未结服务单的客户不回访。",
            "客户运营七月活动.txt": "老客回访活动规则（2026-07-01 至 2026-07-31 有效）\n仅限南京、苏州在营客户，近 90 日净消费至少 1000 元，距离上次回访至少 30 天或从未回访。VIP 仅免消费门槛，城市、在营、间隔和未结服务单要求仍适用。有未结服务单的客户不回访。以上日期均含首尾日。",
        }
        if variant == "confirmation":
            rules["客户运营八月活动.txt"] = (
                "老客回访活动规则（2026-08-01 至 2026-08-31 有效）\n本月范围增加杭州，南京、苏州继续参与，仅限在营客户。近 90 日净消费门槛改为至少 1200 元，距离上次回访至少 45 天或从未回访。VIP 仅免消费门槛，其他条件不豁免。有未结服务单的客户不回访。以上日期均含首尾日。"
            )
        for name, content in rules.items():
            write(folder / "knowledge" / name, content)
        eligible = []
        reasons = {}
        for row in csv.DictReader(io.StringIO(CUSTOMERS)):
            checks = {
                "city": row["city"] in cities,
                "active": row["active"] == "true",
                "spend_or_vip": Decimal(row["net_spend_90d_yuan"]) >= threshold or row["vip"] == "true",
                "service_cases": row["open_service_cases"] == "0",
                "contact_gap": not row["last_contact_date"]
                or (date.fromisoformat(today) - date.fromisoformat(row["last_contact_date"])).days >= gap,
            }
            if all(checks.values()):
                eligible.append(row["customer_id"])
            reasons[row["customer_id"]] = [key for key, value in checks.items() if not value]
        truth(
            folder,
            {
                "eligible": eligible,
                "excluded_by": reasons,
                "date": today,
                "threshold_yuan": threshold,
                "contact_days": gap,
                "cities": cities,
            },
        )


HISTORY = {
    "物流": """包裹三天没更新物流，想知道现在到哪里了。
收货地址门牌号写错了，请帮我改到 302 室。
快递显示签收，可是前台说没收到。
我的订单还未发货，明天出差能否今天寄出？
物流电话一直打不通，需要联系派件员。
Shipment is stuck at the sorting center since Monday.
Please deliver the parcel after 6pm when someone is home.
Tracking says delivered to a neighbor but nobody has it.
I changed offices; can you reroute the parcel before dispatch?
The courier attempted delivery while our shop was closed.
两箱货只送到一箱，另一箱运单在哪里？
快递柜取件码没有收到，请协助查询。
Can you confirm whether the carrier collected my order?
The tracking number on my order does not work.
台风之后物流中断了，预计哪天恢复配送？
包裹被退回寄件仓，我还想收到这件货。
运单里的联系电话少了一位，请更正给快递。
Could the driver leave the package at our reception desk?
The delivery route shows the wrong city for my package.
预约周六配送，为什么今天就来派送？
预售商品已到约定日期，发货时间能确认吗？
I need the tracking link for a shipment sent yesterday.
包裹在中转站破损，快递要求寄件方查件。
收到发货通知但物流网站查不到该运单。
The warehouse split my shipment; where is the second carton?
快递小哥说地址超区，能转到附近自提点吗？
My parcel was sent to the old postcode; please trace it.
派送员将商品放进了错误的快递柜。
Could you arrange a new delivery attempt on Friday?
购买时承诺隔日达，现在仍显示待揽收。""",
    "退换货": """鞋子尺码太小，想换大一码。
杯子到货有裂纹，申请退货退款。
多买了一份，未拆封的那份可以退吗？
退货包裹已经签收，退款什么时候到账？
衣服颜色与页面不符，需要换成蓝色。
The jacket arrived with a broken zip; I need a replacement.
I returned the blender last week but no refund has arrived.
Can I exchange this shirt for a smaller size?
The product is defective and I want my money back.
I ordered two by mistake and would like to return one.
售后同意退款了，银行卡仍没收到款项。
刚收到的耳机没有声音，如何办理换新？
The replacement has the same fault; please arrange a refund.
Please send me the return label for the damaged lamp.
退货申请填错了数量，需要改成两件。
这个配件不兼容我的设备，想退掉。
换货地址已经提交，请确认售后是否收到。
My refund was less than the amount I paid for the returned item.
I want to exchange the unopened item for another color.
商品到手缺了零件，请走售后补换完整一套。
退回的机器还在检测，能确认退款进度吗？
How do I return a gift without the original outer box?
裤子洗前发现开线，希望免费换货。
退款失败提示账户错误，可以重新处理吗？
The replacement size is also wrong; I would like to return it.
退款金额漏算了一件已退回的商品。
My return request was closed even though the item is faulty.
我不再需要这台机器，七天内能申请无理由退货吗？
The shoes have different sizes in the same box; please replace them.
换新后机器仍无法启动，我希望结束换货直接退款。""",
    "发票": """请把发票抬头改成公司的全称。
订单已完成，需要补开电子发票。
发票税号少了一位，能作废重开吗？
下载发票链接过期了，麻烦重新发送。
财务需要专用发票，我之前选成普通发票了。
Please issue an invoice with our company tax number.
The invoice total does not match the paid order amount.
I need a PDF copy of the VAT invoice for reimbursement.
Our billing department requires the company name on the invoice.
Could you correct the tax identification number on my invoice?
上个月的发票邮箱填错了，需要再寄一份电子版。
多张订单能否合并开具一张发票？
The invoice download is blank when opened by our accountant.
Please split the invoice between the two purchasing departments.
发票项目名称与实际购买商品不符。
退款后需要红字发票用于财务冲销。
发票税率显示错误，财务无法入账。
The invoice is marked personal but this was a business purchase.
We need an invoice dated in the month the order was completed.
开票资料已经更新，请按新公司地址开票。
电子发票上的金额小数位缺失了。
Could you resend the invoice attachment to our finance mailbox?
我要报销但没有找到订单的开票入口。
请提供此订单的发票号码供财务核对。
Our auditor needs the original electronic invoice, not a screenshot.
发票上的购方名称打错一个字，请更正。
The tax invoice lists a product we did not purchase.
两家分公司分别付款，需要分别开票。
Can you cancel the duplicate invoice issued for the same purchase?
专票申请显示已开具，但是下载按钮一直不可用。""",
}

NEW_TICKETS = {
    "standard": {
        "物流": """快递签收照片不是我家门口，请查一下送到哪里了。
订单拆单后另一个箱子一直未揽收。
收件人今天住院，可以延迟两天再派件吗？
取件短信丢失，能查出包裹所在的自提柜吗？
我只需要查物流，包裹绕到了隔壁省。
Could you trace a parcel that disappeared after customs clearance?
Please ask the courier to use the side entrance for delivery.
My tracking page has no movement after the depot scan.
We moved upstairs; please update the delivery floor before arrival.
The carrier returned my parcel because the house number was incomplete.""",
        "退换货": """开箱发现屏幕坏点，想退货而不是维修。
收到两个左脚鞋，请售后换成正确的一双。
已退货三件但只退了两件的钱。
替换的零件还是不匹配，我想申请全额退款。
杯盖密封失效漏水，能办理换新吗？
I sent the item back and need confirmation of the refund amount.
The replacement arrived scratched; can I return it for a refund?
Please exchange the medium sweater for a large one.
I want to return the unused charger because it is incompatible.
The stitching came apart on arrival; I need a return authorization.""",
        "发票": """财务说电子发票购方税号不对，需要重开。
请把这两笔订单的开票金额分别列出。
报销系统读不出发票文件，能重新下载原件吗？
退款已经到账，请补一张红字发票冲账。
公司更名后开票抬头需要更新。
Please regenerate the invoice PDF with the corrected legal entity.
The invoice tax rate is wrong for the items we purchased.
Could you issue separate tax invoices for each branch office?
My accountant cannot open the electronic invoice attachment.
We were charged correctly but the invoice description needs correction.""",
    },
    "confirmation": {
        "物流": """我不退货，只是物流页面显示寄回仓库，请重新投递。
包裹还没送到，运单却显示放在保安室，能帮忙找吗？
办公室周末无人值班，请通知派件员工作日送。
商品已备货一周，什么时候能有快递揽件记录？
自提点关门了，需要更换包裹领取地点。
No invoice issue here; I only need a working tracking number.
The delivery proof belongs to another street; please investigate the parcel.
Can the carrier hold the shipment until I return from travel?
Our receiving dock is closed; redirect the delivery to the front desk.
The first carton arrived but the remaining shipment has stalled.""",
        "退换货": """发票已经正常收到，但商品坏了，我要走退款。
运输外箱完好，里面的电器无法开机，希望换新。
售后退货已签收十天了，退款仍是处理中。
我把退货单号填错了，请协助确认退货进度。
尺码与标签不一致，需要换一件合身的。
The courier delivered correctly, but the item is faulty and needs replacing.
I do not need a new invoice; I need a refund for the returned kettle.
Can you refund the second returned unit as well as the first?
The exchange was approved but I now prefer a refund.
Please arrange a replacement for the cracked serving plate.""",
        "发票": """货已经收到也不用退，问题是没有电子发票。
退货退款已完成，只差红字发票提交财务。
物流运费也需要计入发票金额，能重新开票吗？
收件邮箱正确但开票附件损坏，请重新发送。
发票备注的订单号写错，影响公司报销。
Delivery is complete; our finance team still needs the tax invoice.
The refund is settled, but we require a credit invoice for bookkeeping.
Please add the freight charge to the invoice for this shipment.
The replacement works; only the invoice company address needs updating.
I am not returning anything; please fix the misspelled name on the invoice.""",
    },
}


def routing() -> None:
    history = []
    for label_index, (queue, sentences) in enumerate(HISTORY.items()):
        for index, sentence in enumerate(sentences.splitlines()):
            ticket_id = "T-" + sha256(sentence.encode("utf-8")).hexdigest()[:8].upper()
            history.append([ticket_id, f"B{index // 2 + 1:02}", ("微信", "电话", "邮件")[label_index], sentence, queue])
    for variant, queues in NEW_TICKETS.items():
        folder = ROOT / "routing" / variant
        table(folder / "history.csv", "ticket_id,customer_batch,channel,message,queue", history)
        incoming = []
        labels = {}
        for label_index, (queue, sentences) in enumerate(queues.items()):
            for index, sentence in enumerate(sentences.splitlines()):
                ticket_id = "T-" + sha256(sentence.encode("utf-8")).hexdigest()[:8].upper()
                incoming.append([ticket_id, f"NEW-{index:02}", ("邮件", "微信", "电话")[label_index], sentence])
                labels[ticket_id] = queue
        # Interleave queues without manufacturing extra observations.
        incoming.sort(key=lambda row: str(row[0]))
        table(folder / "new_tickets.csv", "ticket_id,customer_batch,channel,message", incoming)
        write(
            folder / "queue_notes.txt",
            "工单分流队列说明\n物流：发货、查件、配送地点和签收问题。退换货：商品退回、退款和售后换新。发票：开票、重开、红字发票和财务票据问题。以客户现在希望处理的事情判断队列；提到其他事项不代表要进入相应队列。channel 只是联系入口，不决定队列。customer_batch 标识同一批客户业务，其中可能有相似或关联事件。",
        )
        write(
            folder / "request_1.txt",
            "我们会持续收到新工单，希望至少九成能够进入合适队列。请根据历史记录和队列说明，建立并保存可供后续批次使用的分流分析器，交付分析器入口及评估结果，说明你用什么证据判断它是否值得采用，以及大概有多少需要人工改队列。",
        )
        write(
            folder / "request_2.txt",
            "这是一批新工单，请沿用刚才保存的方案，交付可下载的结果表，包含每个工单编号和建议队列。",
        )
        truth(folder, {"labels": labels, "minimum_accuracy": 0.9})


if __name__ == "__main__":
    revenue()
    campaign()
    routing()

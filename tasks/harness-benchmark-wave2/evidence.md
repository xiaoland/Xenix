# 第二批定位依据

本页保留实施前的调查，代码行号对应基线 `974db27`。当时读了 PRD、首批三项 case 与 fixture 作者脚本、执行/报告契约，复查旧聚类选择和预测验证题的题面及主要判据，并重读首批 10 个真实运行的记录；调查阶段未再次运行 live benchmark。批准后实现与真实试跑结果另见 [实施记录](implementation.md)。

## 本地证据

| 证据 | 可支持的结论 | 不应推出的结论 |
| --- | --- | --- |
| [PRD](../../docs/10-prd/README.md) 第 5–12 行，以及 Claims 表的业务解释目标 | 产品要帮助用户理解数据支持什么行动及剩余不确定性，任务可以直接围绕行动决策设计。 | 没有用户频率统计，不能声称补货是实际最高频业务。 |
| [月结 case](../../tests/e2e/agent_harness/test_business_revenue_revision.py) 第 40–47 行；[回访 case](../../tests/e2e/agent_harness/test_business_campaign_eligibility.py) 第 71–78 行 | 两题围绕确定金额或客户集合验收；这适合其业务目标，但没有提供多个不同业务方案同等可接受的覆盖。 | 精确 oracle 本身是错误，或需要把当前确定事实改成宽松评分。 |
| [分流 case](../../tests/e2e/agent_harness/test_business_routing_reuse.py) 第 70–89 行 | 已允许不同算法及达到门槛的预测，要求保存方案与复用；业务终点固定为可用分析器的交付。 | 三个核心任务都只有唯一输出，或者已有 C 失败时可以改判“不采用即成功”。 |
| [正式材料作者脚本](../../tests/e2e/agent_harness/fixtures/business_tasks/authoring.py) 第 204–209 行 | 八月政策同时改变消费金额、间隔与城市；这是综合变化，不是单条件诊断。 | 该确认变体无意义，或所有确认必须一次只改一个字段。 |
| [BusinessTask](../../tests/e2e/agent_harness/_infra/business_tasks.py) 第 109 行；[case 契约](../../tests/e2e/agent_harness/_infra/contracts.py) 第 185 行附近 | 多轮请求当前预先构造，适合固定的业务追加材料。 | 已经具有能理解 Agent 提问并公平作答的互动用户模拟器。 |
| [旧聚类选择](../../tests/e2e/agent_harness/test_ml_cluster_selection.py) 第 46 行的固定分区与第 208 行相等判定 | 旧题选择的业务分区被绑定为一份答案，不能直接承担开放客户理解中的多解评价。 | 聚类任务没有独立价值，或应该删除所有旧题。 |
| [旧预测验证](../../tests/e2e/agent_harness/test_ml_forecast_validation.py) 第 71–75 行和 149 行附近 | 已要求历史回测与采购建议；主要公共结果包含固定区域/日期的预测及评估。 | 题库完全没有未来决策相关内容，或更换数据就已建立采购效用判据。 |
| [首批验证记录](../harness-benchmark-business-oracles/verification.md) 的两次评测器修正及月结确认解释错误 | 合计/资格标记全表等合法交付曾被误判；数值正确但关键解释错误被 Judge 判 partial，需校准严重程度。 | 应加更多格式或一致性字段，或通过反复试 Judge 把原报告刷到期望 verdict。 |

## Judge 配套项的具体边界

首批月结确认运行 `66f6f9ecc29f466995ee090e5b8190a9` 的数字正确，却声称东区退款仍最高，并说错转入七月退款影响的区域。当前 rubric 要求实质错误应失败，原 Judge 为 partial。这个现成例子适合检验“错误”和“缺少说明”的区别，优先级高于换 Judge 框架。

建议先为月结保存四类人工标注材料：完整正确说明（pass）、包含正确合计等合法等价交付（pass）、正确表但缺少所请求的修订说明（partial）、正确表配上述实质错误（fail）。原始真实交付可复用；编辑出的对照明确标记为作者材料。每包包含与该判断有关的权威事实；如果 Judge 看不到断言涉及的原始事实，应先补事实，不能仅把评分文字写得更严厉。

[已有校准实现](../../tests/e2e/agent_harness/_infra/judge_calibration.py) 第 30 行支持最多四包，第 135 行说明三次重复。初期范围能容纳上述材料，无需增加抽象、改上限或强制所有 benchmark 在每次运行前校准。本轮只定位这项工作，没有新建校准 suite 或调用 Judge。

## 离线探针如何复现

运行 `.venv/Scripts/python.exe tasks/harness-benchmark-wave2/experiments/probe_decisions.py`，只写本目录 `observations.json`。Python 标准库穷举 256 个子集，不读取应用数据、配置或网络，不被 pytest 收集。

该实验支持“有多个合法最优方案”“业务条件改变可使行动改变或保持”“空行动是否正确依赖输入”的任务设计判断；它没有验证真实 Subject 的求解难度、输出定位或 Judge 分数。实验脚本不是未来正式 oracle 必须采用的实现，也不把任务规模固定为 8 个批次。

## 本轮排除的捷径

增加相同模板的题数不能补齐行动决策；改变列名与随机种子不能替代业务判断变化；模型调用失败不能靠改成“没有条件就不做”的题面消失；让所有输出都多走一层校验不能修正错误的成功定义。后续选择以业务缺口与可验收性为准，当前代码是否最容易适配仅影响落地顺序。

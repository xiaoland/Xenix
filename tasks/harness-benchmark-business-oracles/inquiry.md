# 调查记录：任务覆盖、设计与判据

## 结论与证据范围

旧题调查于 2026-09-12 进行，记录于 2026-09-13 整理。Xenix 基线为 `dcec815b23369832307e26b96daf1a6961541a8b`，FrontierHarness Eval 参考版本为 `8f11b130c30bbf76ca1f3edeea70abc773bd8d2c`。调查开始时工作区干净。随后新增任务设计与隔离实验，当前结果见 [任务规格](design.md) 和 [实验记录](experiments/README.md)；未修改生产或正式 benchmark。

已检查 Xenix 现有 13 个 live case 的题面与主要 OutcomeCheck，深入阅读图表、补货、预测的产物选择、oracle、judge 输入，并抽查 ML 判据和校准。这不是全量运行或全部判据审计。用户初步分析基于更早的 Xenix `476015b…`，适用性以当前代码复核为准。

原调查主要解释判据偏差：部分题面已从固定能力演示转成自主业务任务，但验收没有同步转变；另一些判据把“存在合格产物”近似成“完成交付”，或让 judge 在关键事实缺失时判定。这个解释来自源码与反例，不是对最初设计动机的断言，也不能单凭它决定任务改进的最高优先级。

2026-09-13 用户先指出任务设计与任务组织更有价值，随后明确长期正确优先，不能受现有数据与题目限制。本任务据 [PRD](../../docs/10-prd/README.md) 定义目标覆盖，旧题仅作为对照与迁移材料。下表是旧题的分析分组，不是目标题库的分类或保留承诺；原有 F1–F8 是局部判据证据。

## 旧题覆盖盘点与潜在复用价值

目标覆盖和首批选择独立于下表。即使旧题具备某种专项价值，是否保留仍取决于目标组合的需要；先前据现有材料选出的三个试点已撤回预定名额，待与新候选统一比较。

| 旧题分析分组 | 当前材料（覆盖全部 13 题） | 当前测量与缺口 | 潜在价值，目标选定后再决定是否复用 |
| --- | --- | --- | --- |
| 数据准备与经营分析 | [四月清洗](../../tests/e2e/agent_harness/test_cleaning_april.py)、[履约清洗](../../tests/e2e/agent_harness/test_ml_cleaning.py)、[地区收入图表](../../tests/e2e/agent_harness/test_revenue_by_region_chart.py) | 分别测清洗规则和小表可视化，尚未把数据口径处理与业务结论联系起来；四月任务的大文件另有规模价值 | 小表可辅助核对明确事实，大型导出表可揭露规模问题；是否值得保留取决于目标输入分布，不承诺用它们搭建经营分析任务 |
| 知识规则驱动的行动 | [雨季补货](../../tests/e2e/agent_harness/test_rainy_season_restock.py) | 已有规则与数据结合的业务闭环；适用范围改变时能否迁移判断尚未由任务变化检验 | 可对照规则应用类目标，但雨季、库存字段和现有规则都可被替换，不占据预定核心名额 |
| 客户理解与业务分流 | [两群聚类](../../tests/e2e/agent_harness/test_ml_clustering.py)、[聚类选择](../../tests/e2e/agent_harness/test_ml_cluster_selection.py)、[反馈词频](../../tests/e2e/agent_harness/test_ml_text_insight.py)、[主题发现](../../tests/e2e/agent_harness/test_ml_text_topic_discovery.py)、[有标签分流](../../tests/e2e/agent_harness/test_ml_text_grouped_classification.py) | 无标签发现、有标签预测、方案选择并非同一个能力，不能仅按文件数合并；指定群数和列格式的题有明确边界，但不能代表自主客户理解 | 可帮助区分发现结构、按既有标签处理业务和选择方法的差异；目标任务可以采用全新的业务场景和数据，不要求保留每种算法题 |
| 面向未来的预测与推荐决策 | [四周预测](../../tests/e2e/agent_harness/test_ml_forecasting.py)、[预测验证](../../tests/e2e/agent_harness/test_ml_forecast_validation.py)、[相似商品](../../tests/e2e/agent_harness/test_ml_recommendation.py)、[用户推荐](../../tests/e2e/agent_harness/test_ml_recommendation_ranking.py) | 四周题明确要求延续最近周期，方案选择题要求比较证据；两种推荐分别针对相似商品和具体用户，也不应视为完全重复 | 可为方法选择和证据解释提供反例；预测验证不是预定首批任务，旧分数与指定结果不能成为新任务真值 |

题面抽取说明：当前多个任务直接要求两个群组、三个主题、延续最近周期、词频或特定结果列。这些不一定是错误题面，可能就是用户的明确目标；组合层面却需要额外检验 Agent 如何选择问题的处理方式，不能只测试遵守这些预设。10 个模块使用 `test_ml_` 前缀只是组织线索，不是“10 道题必须调用 ML”或“10 道题冗余”的证据。

PRD 强调通过对话从表格得到可用于决策的分析、复用分析器和继续使用既有结果。当前 13 个 case 的 submission 都是一条用户请求；有些已包含多份附件、模型评估和多个交付物，不能说它们都是单工具测试。但它们尚未直接覆盖用户追加条件后的跨轮继续工作。

高杠杆假设：同一任务族中一个需要改变判断的变体，比继续增加相似的能力演示更能帮助发现固定方案依赖。尚未用试跑验证该假设。变体应能说明因果关系：改变什么、为什么答案应改变或保持；它不是随机改写措辞，也不保证每个变体必须得出不同赢家。

后续已独立于旧题形成三个新材料原型，详见 [任务规格](design.md)。当前未决事项转为输入分布推广、完整业务验收和真实试跑；不能把原型表现当成代表性证据。上表仍不构成迁移要求，尚未删除、合并或重命名任何旧 case。

设计依据的局限：目前有 PRD 与代码证据，没有系统性的真实用户任务频率、失败损失和新题区分度数据。可据产品目标形成工作假设，但不能将已有 case 数量当成业务需求权重。跨轮继续工作与分析器复用是产品支持的工作方式，不能因当前 13 题均为单次 submission 就在目标覆盖中自动降级。

## FrontierHarness：采用什么，保留什么疑问

| 来源 | 可采用的设计 | Xenix 的取舍 |
| --- | --- | --- |
| [多源合并](https://github.com/frontier-harness-eval/eval/blob/8f11b130c30bbf76ca1f3edeea70abc773bd8d2c/tasks/multi-source-data-merger/instruction.md) | 主键、同义字段、来源优先级、最终表与冲突报告 | 学习可核对的业务条件，不照搬路径、技术格式和执行步骤 |
| [日期汇总](https://github.com/frontier-harness-eval/eval/blob/8f11b130c30bbf76ca1f3edeea70abc773bd8d2c/tasks/log-summary-date-ranges/instruction.md) | 固定参考日期、包含当天、完整统计维度 | 适合作为未来业务边界题，预期答案不依赖运行当天 |
| [约束排期](https://github.com/frontier-harness-eval/eval/blob/8f11b130c30bbf76ca1f3edeea70abc773bd8d2c/tasks/constraints-scheduling/instruction.md) | 硬约束、偏好、提示信息分开，保留原始输入 | “最早可行”与“避免周一”仍需审视优先关系，详细题面不保证无歧义 |
| [FastAPI 响应头](https://github.com/frontier-harness-eval/eval/blob/8f11b130c30bbf76ca1f3edeea70abc773bd8d2c/tasks/fastapi-deprecation-response-headers/instruction.md) | 新结果、已有值保留、冲突优先关系 | 对应业务记录保留与规则冲突；不学习其具体 API 和实现要求 |

[项目说明](https://github.com/frontier-harness-eval/eval/blob/8f11b130c30bbf76ca1f3edeea70abc773bd8d2c/README.md) 声明采用 verifier-based pass/fail，公开题面、元数据、结果和运行流程，但没有完整公开每题 verifier。不能把题面视为已验证的完美 oracle，也不能由上游 grader 推断冻结运行中的全部行为。本次没有独立复核 DeepSWE grader，用户附件相关结论仅作背景。

## Xenix 发现

| 编号 | 源码与事实 | 影响及判断边界 |
| --- | --- | --- |
| F1 | [图表](../../tests/e2e/agent_harness/test_revenue_by_region_chart.py)：`REGIONAL_REVENUE_FACTS` 只有地区与排序；`_project_svg_evidence` 提取可见文字及 accessibility 标签 | 缺少完整金额真值且看不到几何。排序正确的错误金额有漏判风险；相同标签、不同柱高的证据碰撞已由 E1 确认 |
| F2 | [补货](../../tests/e2e/agent_harness/test_rainy_season_restock.py)：`_resolve_exact_derived_dataset` 遍历本次直接派生的数据集，发现正确映射即返回；`assess` 不核对最终答复的规则和数量 | 正确中间表可掩盖错误交付，E3 已确认。直接父级限制还可能漏掉合理的多步转换后代，这一点是代码推断，未实验 |
| F3 | [图表](../../tests/e2e/agent_harness/test_revenue_by_region_chart.py)：`_resolve_terminal_artifact` 从成功 tool result 倒序寻找 SVG | 未证明该图就是最终答复或附件选定的交付物；完整用户路径尚未实验 |
| F4 | [预测](../../tests/e2e/agent_harness/test_ml_forecast_validation.py)：`_matching_forecast_model` 要求列集合精确相等，并固定 `residual_quantile.v1`、模型键集合；`_matches_evaluation_report` 固定多项评估表示 | 附加列误拒由 E2 确认；替代算法是否等价需评估事实支持，不能仅移除全部约束 |
| F5 | 同一预测文件：`_build_judge_input` 投影选中模型指标、区间和完整答复，没有其他候选的评估事实 | 题面要求比较方案，当前证据不足以充分核对相对优势；不证明所有实际选型答案都会误判 |
| F6 | [推荐](../../tests/e2e/agent_harness/test_ml_recommendation_ranking.py) 固定分数和策略名；[分类](../../tests/e2e/agent_harness/test_ml_text_grouped_classification.py) 固定模型键；[聚类](../../tests/e2e/agent_harness/test_ml_cluster_selection.py) 固定分组、三群和质量阈值 | 需区分业务真值、产品能力范围和实现默认值。合成数据的明确分组可能有充分依据，不能一概删除 |
| F7 | [四月清洗](../../tests/e2e/agent_harness/test_cleaning_april.py) 题面只有“清洗”，判据要求表头处理、去除汇总行、去重和记录保留 | 检查哪些要求可从导出表和产品约定推导，哪些需补充业务语义；短题面不等于公平且唯一的验收口径 |
| F8 | [judge](../../tests/e2e/agent_harness/_infra/judge.py) 有通用四档政策；[图表校准](../../tests/e2e/agent_harness/fixtures/regional_sales_judge_calibration.json) 和 [ML 校准](../../tests/e2e/agent_harness/fixtures/ml_formal_judge_calibrations.json) 使用手写证据包 | 通用政策不是各题的具体评分锚点；摘要校准不能覆盖实际产物选择、提取与前置判据，无需因此增加总体 judge |

已过时的发现：当前预测不再用固定关键词门槛判定最终说明，judge 输入保留完整答复，题面不再要求固定三个模型或恰好三个回测窗口。不要把已修复问题重新列入实施任务。[当前 unit-tdd](../../docs/30-unit-tdd/agent-harness-benchmark.md) 也明确了这些变化。

## 已执行的离线反例

实验于 2026-09-12 使用项目 `.venv/Scripts/python.exe`、`src` 导入路径及现有 case 函数执行。输入为临时 SVG、内存 DataFrame 和简化 context；未启动 Harness、调用 LLM、写入用户运行数据或增加测试文件。以下保存复现条件和观察值。

| 实验 | 构造与调用 | 观察值 | 证明范围 |
| --- | --- | --- | --- |
| E1：图形证据碰撞 | 两份 SVG 的 North/South/East/West 标签均为 10/20/25/30，柱高分别为 10/20/25/30 与 30/25/20/10；比较 `_project_svg_evidence` 输出 | `SVG reversed geometry produces identical judge evidence: True` | 提取丢失该视觉差异，不证明实际 judge 的评分 |
| E2：附加列误拒 | 两区域 × 2026 年 1—6 月的 12 行表，字段与区间符合现有条件；再增加 `note` 列，分别调用 `_matching_forecast_model` | 原表返回 `forecasting.seasonal_naive`，附加列后返回 `None` | 列集合相等条件导致局部误拒；合成表不代表真实预测质量 |
| E3：正确中间表遮蔽错误交付 | 简化 context 含同源直接派生的正确表 U100=130/R200=75 和错误表 999/999，终态答复指向错误表；调用 `_resolve_exact_derived_dataset`，加载函数仅在实验进程中返回对应内存表 | `Restock resolves correct intermediate despite wrong final delivery: True` | 选择函数忽略终态交付并返回正确中间表；未运行完整 UI、Harness 或 assessment |

实验退出成功，调查后的 `git status --short` 为空。它们是局部实验，不能称为全量 benchmark、端到端回放或统计误判率。

## 判据取证重点（随所选任务推进）

以下不是任务设计前的全局前置清单。只在所选任务确实受到对应问题影响时处理；最新优先级由 [任务入口](packet.md) 决定。

- F2/F3：确认现有产品的答复引用和交付附件表示，再调整定位；不另建最终产物注册机制，不要求固定话术。
- F5：查看实际报告中的候选与切分事实，区分 Agent 未交付比较依据和评判器未读取已有依据；不以整段工具对话代替结果证据。
- F6：构造合法替代结果与决定性错误，确认判据应当如何区分；不重新实现整套 ML 训练器作为 oracle。
- 图表：数据语义、图形与数据一致性、可读性是不同主张，只声称完成已取得证据的部分；自动视觉判断的成本和接口能力尚未评估。
- 校准：区分业务证据缺失、评判器遗漏和 judge 自身不可用。关键事实错误不能被其他高分平均抵消，`partial` 由本题的业务影响决定。

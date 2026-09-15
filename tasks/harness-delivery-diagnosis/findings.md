# 三项实际失败的分组诊断

本轮将三项失败收敛到两类机制：一个预测回答损坏了公开引用，两个收入月结回答在正确结果之外作出了错误解释；目前没有证据证明这是新的数据服务、上下文截断或 GUI 实现缺陷。

诊断基于原始 `81fb9bb` 运行和当前 `a94aa28` 代码；所检查的工具、转换、预览、provider、conversation 和默认提示词在两个提交间没有变化；前序两项 oracle 修复已经提交，本轮只新增任务材料，未修改生产代码、提示词、判分或自动化测试。

## 分组结论

| 运行单元 | 已证实的错误 | 主要定位 | 尚不能推出的结论 |
| --- | --- | --- | --- |
| `ml.forecast_validation_v1` | `model.apply` 的正确 Artifact URI 在最终回答中错了一位 | 回答生成的引用复制；下游解析和渲染保持原字符 | 不能将旧 oracle 的失败直接解释为所有可用预测交付均缺失 |
| `business.revenue.v1.standard` | 西区退款被说成比东区更多；东区退款比例被说成最低之一；单笔小于区域差额的退款被说成足以改变排名 | 从已计算事实生成业务比较时出现矛盾 | 不能归因于工具没返回计算值，或推断多一次核对必然有效 |
| `business.revenue.v1.confirmation` | 东区 cancelled 订单数量错误；11,000 元退款被说成对 12,000 元订单的整单退款 | 从源记录生成归属、数量和业务标签时出现矛盾 | 不能把正确净回款表等同于正确解释，也不能据此断言 SQL 服务有错 |

## A：预测引用的错误发生在哪里

原始报告中的 `model.apply` 在第 11 轮成功返回 `artifact://59137ebae3ed4eb6ac3555e1a271187c`；第 16 轮最终回答将预测表链接写成 `artifact://59137ebae3ed4eb6ac5555e1a271187c`；URI 的第 29 个零基索引字符由 `3` 变成 `5`。

[工具完成结果](../../src/xenix/services/agent/_model_tools.py) 的 `_apply_completion` 同时返回准确的 `artifact_id` 和完整 `uri`；这不是调用者必须自行发现产物或从本地文件路径猜引用的问题。

[provider](../../src/xenix/services/llm/providers.py) 将 content 原样组成 `AssistantOutputItem`，流式路径只拼接 content 分片；[conversation](../../src/xenix/services/llm/conversation.py) 的 `_final_message_rows` 将 `item.text` 写入 canonical row；[Chatbot 投影](../../src/xenix/services/agent/chatbot_events.py) 保留 assistant text；[Markdown renderer](../../src/xenix/ui/markdown_renderer.py) 的 URI 规范化只移除 `view` 查询参数，不修改 Artifact ID；[ArtifactService](../../src/xenix/services/artifact_service.py) 按该 ID 精确查找产物。

离线将正确和错误两个 URI 分别送入真实 provider parser、canonical row 构造、Chatbot 投影和 Markdown renderer，两个 URI 都逐步保持原样；这验证了所检查路径没有把正确链接改成错字，不能理解为错误链接可打开。

原始报告保存了工具 URI 与 canonical 最终回答，没有冻结网络分片；错误第一次被直接观察到的状态是 canonical 回答，结合不改字符的代码路径，证据指向模型输出中的复制错误；不能冒称抓到了当次 provider 原始报文，也不能从这一例判断错误概率或认定五轮间隔就是原因。

接口层面的脆弱点是：公开引用的选择与 32 位不可读标识的字符复制一起交给了自然语言生成；这解释了“产物已正确生成，用户明确点击的主链接却坏了”为何可能发生，但不是缺少某个安全校验的证据。

### 预测 oracle 仍有内部表示限制

最终回答另提供了 `combined series` 工作簿；成功的 `data.transform` SQL 将历史记录与未来预测拼接，未来部分明确选择了 `region`、`period`、`forecast`、`lower_80`、`upper_80`，对应结果数据集也出现在运行记录中；这是需要检查的替代交付，不能因不是原始 apply 产物就忽略。

[预测 oracle](../../tests/e2e/agent_harness/test_ml_forecast_validation.py) 的 `_resolve_apply_artifact` 只接受 `kind == prediction` 且 `metadata.result_dataset_id` 等于所选原生预测 Dataset 的 Artifact；即使导出的组合工作簿包含同样的未来值和区间，也不能通过这个检查；`_matching_forecast_model` 还要求精确的 12 行和 9 列内部输出结构，保留了另一处与实际用户交付无关的约束。

因此本例同时包含确定的坏链接和 oracle 识别范围不足；旧报告的 `linked_future_artifact_missing` 不能单独证明没有其他可复用预测表；修正判据也不能抹掉明确作为预测结果推荐的坏链接。

旧题没有冻结最终链接工作簿内容，原临时 runtime 已清理，本轮只能证明替代交付的生成意图、成功转换与 oracle 的排除条件，不能补称当次组合工作簿已完成内容和可访问性验收；forecast 的 Judge 被结构检查阻断，其余文字解释也没有通过语义验收。

## B：两个月结用例的事实是可见的

两个用例的订单、门店、退款、修订文件分别只有 25、8、17、5 行；成功查询的 limit 为 30、40 或 50，原始成功 SQL 经生产 CSV 导入、`DataQueryTransformService`、查询结果格式化和 provider wire 编码重放，没有一处截断。

转换反馈并非只有 Dataset/Artifact ID：[注册 worker](../../src/xenix/services/preprocessing_worker.py) 会检查生成的数据集，[inspection](../../src/xenix/services/dataset_inspection.py) 默认取前 5 行，[XTT formatter](../../src/xenix/services/llm/xenix_table_text.py) 将预览写入 canonical ToolResult；本例每张汇总表只有 4 行，所以四次转换都完整返回了结果。

本轮重放 standard 的 6 次成功查询和 2 次转换、confirmation 的 4 次成功查询和 2 次转换；共 14 份工具反馈均未截断，按原报告相同 JSON 序列化口径计算的字节数全部吻合；转换重建使用明确标注的占位 Artifact ID，字节数吻合是旁证而不是原文哈希证明；[离线证据](offline-evidence.json) 保留了重建的完整 XTT 文本、行数、来源哈希与原调用轮次。

原始 benchmark 已读取并冻结两个月结用例每个请求的实际链接交付，数值与可访问性检查全部通过；离线重放进一步解释模型通过工具能看到什么，不替代原验收，也不新增 Subject 样本。

### standard：正确数值被解释成错误比较

| 断言 | 可核对的事实 | 定位 |
| --- | --- | --- |
| 西区相比东区“只是退款更多” | 西区退款 4,400.25 元，东区 8,600.50 元 | 与自己最终表格也直接矛盾 |
| 东区“退款占已支付金额比例最低之一（约 17%）” | 东区约 17.43%，西区约 11.80%，北区 0%；南区没有已支付金额，比例不适用 | 数值约数合理，比较方向错误 |
| 区域差额约 7,850 元，而“单笔退款（如……7,000 元、……2,000 元）就能改变排名” | 两笔中任何单笔都小于差额 | 从金额跳到了没有被计算支持的排名反事实 |

第 4 轮的转换反馈已经给出全部四区的支付、退款、净回款；第 5 轮又成功查询了订单和退款的区域归属、月份处理明细；最终第 7 轮仍作出上述错误比较；这为“强制再核对一次即可修复”提供了反例背景，而不是有效性证明。

更正前序 findings 的一句事实陈述：standard 第 2 轮确有三次 `data.query` 失败，因为单 Dataset 的 SQL 默认别名是 `input`，模型用了 `orders`、`stores`、`refunds`；第 3 轮均改为 `SELECT * FROM input` 并成功；没有证据将已恢复的别名错误与第 7 轮的文字矛盾建立因果联系；confirmation 没有工具失败，也出现同类解释错误。

### confirmation：记录归属与业务标签被写错

| 断言 | 可核对的事实 | 定位 |
| --- | --- | --- |
| “东区有 2 笔 cancelled 订单” | O10 属东区，O20 属南区，各一笔 | 同一回答后面的处理说明又正确列出这两个区域，说明错误不只是源记录缺失 |
| R20 是“11,000 元的整单退款” | 对应 O04 订单金额 12,000 元 | 更新表给出正确退款金额，模型额外赋予了不成立的“整单”含义 |

这些错误覆盖两个用户请求，不能只检查最后一次修改后的表格；“退款日期、金额、区域与变化均算对”不能替代对追加业务断言的验收。

两个用例共四次最终回答长度为 1,684、1,722、1,696、1,702 个字符；题面要求简要解释，错误集中在正确表格以外的比较、稳定性评价或额外标签；解释扩展增加了出错机会是有根据的假设，但尚未通过控制其他条件的实验验证，不能保证缩短回答就能修好。

[默认 system prompt](../../src/xenix/services/storage/models.py) 已要求用 computed results 支持 factual claims and comparisons；[数据分析 skill](../../src/xenix/services/agent/skills/xenix-data-analysis/SKILL.md) 已明确不要求额外查询或多章节报告；因此不能把这次问题归因为缺少“基于证据回答”这句话，也不能把继续叠加同义流程要求当作已证实方案。

## Judge：错误事实成立，具体判错依据没有保存

两个用例的 Judge 都返回 `fail / incorrect_business_claim`；standard 的两个分项同时为 2，confirmation 为 0 和 2；本轮列出的错误句子由原答复和源记录独立核对得出，不是从 Judge 的隐藏推理恢复出来的。

[月结 rubric](../../tests/e2e/agent_harness/test_business_revenue_revision.py) 同时定义了两个聚焦口径及修订的维度，以及任何错误业务事实均应 fail 的整体原则；[Judge parser](../../tests/e2e/agent_harness/_infra/judge.py) 接收独立的 verdict，没有执行“满分自动变 pass”的二次映射；目前证据不能认定 parser 改坏了评分；维度满分与整体 fail 的关系仍需要具体错误定位来校准，也不应自动覆盖 fail。

当前 Judge 只交付 verdict、scores、reason_codes，缺少违反哪句断言、对照哪个事实的简短证据；增加“错误原句＋对应事实或交付位置＋理由”能够直接减少分流成本；这是评估可解释性改进，不是要求模型输出推理过程，也不需要新增一致性拒绝器。

## 决策与建议的下一步

本轮不提出已经证实有效的生产修复补丁：可观察的错误边界已经定位，但“什么改动会提高生成质量”仍需干预证据；把所有实际任务失败改写成 Harness 实现缺陷，会引入没有被这批证据支持的机制。

| 优先级 | 建议目标 | 可观察的状态变化 | 验证边界 |
| --- | --- | --- | --- |
| 1 | 预测交付判据与 Judge 失分定位 | 预测按实际链接表的未来区域、月份、数值、区间识别；坏链接单独保留；Judge 失败能定位到具体断言和事实 | 对已有实际交付做判分校准，不把修 oracle 宣称为修复模型输出 |
| 2 | 月结最后回答的小规模对照实验 | 对同一组可见事实，比较现有生成方式与简短、只保留必要事实的回答表达；若仍出错，再比较候选 Subject 模型能力 | 同时记录解释完整性、错误断言、token 与成本，保留所有尝试；完整生产上下文未冻结时须标明重建范围 |
| 3 | 公开产物引用接口的轻量实验 | 研究由模型选择短引用、程序解析成真实 URI，减少不可读 ID 的复制负担 | 先验证选择歧义、多轮复用和现有 canonical 边界；不要因单次错字直接引入持久映射、migration 或新的一套会话状态 |

暂不采纳模糊纠正 Artifact ID、强制追加查询/复核轮、所有回答再走一个生产 Judge、仅强化“必须先核对再回答”的提示词；这些方向缺少本轮因果证据，且会增加成本或固定流程。

## 证据范围与执行说明

[offline-evidence.json](offline-evidence.json) 记录原报告及 fixture SHA256、全部 14 次成功 SQL 结果重建、独立 Decimal 金额聚合、两条 URI 的真实函数路径实验；原始 SQL 可按 provider call 和轮次在链接报告中复核；本地一次性实验脚本位于 `build/harness-delivery-offline-diagnosis.py`，其 SHA256 已记录，不进入测试收集或持续验证流程。

首次实验直接将 CSV 传给 SQL 服务，因生产查询只接受导入后的格式而失败；改为真实 DatasetService 导入后重试；文件脚本的首次 worker 启动因缺少 main guard 失败，修正实验入口后全部完成；这两项是实验搭建问题，不是原 benchmark 的产品回归；未请求新的 Subject/Judge，未修改或覆盖原始报告。

实验失败留下的两处 `xenix-delivery-diagnosis-*` 系统临时目录清理被自动审批策略阻止，返回信息未说明更细原因；目录保留在系统临时目录，生产运行目录和项目源码不受影响。

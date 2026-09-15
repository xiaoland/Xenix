# 工具注册与展示解耦、旧 oracle 修正

- **Objective**: 工具展示不再充当执行授权；旧 oracle 按最终交付物判断业务结果。
- **Guardrails**: 用户已同意实现；保留注册、参数校验、调用记录、usage 与错误反馈；不增加自动化测试，不提交，不修改其它诊断任务的既有变更。
- **Verification**: 现有服务测试、真实 Provider 普通/流式协议的离线手动探针、oracle 正反例手动检验、静态检查和 benchmark 收集；必要时用已授权的 live 用例验证。
- **Current Truth**: 工具展示与注册语义混同已修正；参数 JSON 失败也已进入 canonical failed ToolResult，使其它调用、usage 及模型修正继续完成。另已修正 9 个旧 oracle，完成先前 10 项受影响用例及 2 项追加 live 验证，本次推荐单项又正常完成 15 轮；全部题库尚未通过。各阶段结果分别保留，原始 28 项结果冻结于 [上一轮证据](../harness-namespace-full-run/findings.md)，修复不回写旧成绩。
- **Next Step**: 本次参数 JSON 恢复的实现、离线验证及推荐单项复测完成，仍未提交。后续单独处理推荐 oracle 的列名和固定冷启动排名要求、4 月清洗误删业务记录及最终分群 Judge 复核；不能把诊断性证据重建当成 live 通过。

## 已授权的行为变化

Provider 只解析和保留 wire 工具名；Conversation 使用完整 Registry 将精确 alias 解析为 canonical 名；注册过但没有展示 schema 的工具可以直接执行。真正不存在的工具、参数 JSON 解析失败及已解码但类型错误的参数变成 failed ToolResult，让模型在同一会话继续修正。无法识别响应封装或调用身份的 wire 结构错误仍属于 Provider 错误。

旧 oracle 读取最终回答实际链接的表，删除内部 Dataset 血缘和 Artifact metadata 的重复交付门槛。保留行、值、分组、预测、评估依据和源文件完整性检查。4 月清洗保留业务行的重复次数，可省略全空列；主题归纳不再暗中限定 LDA 及其概率列。

## 已完成验证

现有离线套件 303 项通过，静态检查及隔离启动检查通过；完整目录收集 24 项（另有 4 个 confirmation 数据变体，总题库 28 cells），没有增加自动化测试。

[恢复探针](recovery-probe.json) 使用实际 OpenAICompatible Provider 的普通响应解析及流式参数分片解析，均验证：未展示的 model.hyper_train 直接执行，unknown Tool 返回 llm_tool_not_registered，错误参数保留字段详情，后续修正成功，4 次响应 usage 完整，重载后的 canonical 名和 provider replay alias 正确。

[Oracle 手动探针](oracle-probes.json) 覆盖无 lineage/metadata 的公开 CSV 交付、坏链接、可见 I/O 错误、8 个小型结果的正确/错误变体，以及真实 4 月原始文件。该文件业务部分 486119 行，盲目去重变成 485789 行；保留业务多重集、移除 3 个全空列可通过，去掉 330 行则失败。

第一轮 live 启动器遗漏 Windows multiprocessing 的 main guard，10 个 cell 均在 sampling 前结束；报告已保留，这是本次临时实验脚本的问题。更正启动器后在 attempt-2 独立目录重新执行；产品和 oracle 代码未随重试更改。最初计划的临时交付捕获未在重试使用，运行直接调用生产 benchmark launcher。

## Live 结果与剩余问题

Subject 为 deepseek/deepseek-v4-flash，Judge 为 deepseek/deepseek-v4-pro；本轮只复测 10 个受影响 cell，没有重跑完整 28 cells。设置仅保存路径与摘要，不把密钥写入任务材料。

[第一批结果](live-results.json) 和 [输入冻结记录](live-manifest.json) 保留全部 10 项原始成绩：6 项通过，分群及主题归纳的 2 项失败由 oracle 缺口阻挡，推荐及 4 月清洗的 2 项存在实际失败。通过项为服务工单清洗、季节朴素预测、关键词频次、补货 margin_higher、预测验证、分组文本分类。

| Cell | 第一批观察 | 处理与最终证据边界 |
| --- | --- | --- |
| 分群选择 | 成员划分正确；旧 oracle 要求模型报告使用原始字段尺度，拒绝了标准化特征画像 | 改为从最终交付表重算原始业务画像；追加 live 的确定性检查通过、Judge partial；之后修正遗漏比较表及无依据的客户编号扣分，但没有再次 live 评分 |
| 主题归纳 | 已交付模型，但中文列名及表格形式评估报告被旧 oracle 拒绝 | 根据记录标识、原文与主题划分识别结果，接受表格评估证据；追加 live 完整通过 |
| 推荐排序 | Provider 抛出 llm_tool_arguments_invalid_json，会话中断 | 未暴露工具已不再被拒绝；这次是参数 JSON 尚未解码便失败，仍需独立处理，失败响应 usage 尚未进入已观察总量 |
| 4 月堂食销售清洗 | 推荐的主文件将 486119 条业务记录去重为 485789 条，损失 330 条记录及 4969 销售额 | 保留行多重集检查；修正单列改名判断，新增主交付选择 Judge，防止正确参考表掩盖错误主文件；尚未重跑此 Subject |

[追加结果](followup-results.json) 与 [追加冻结记录](followup-manifest.json) 单独保存，不合并成同一版代码的通过率。主题归纳追加运行使用 14 轮、228755 个 Subject tokens；分群追加运行使用 11 轮、149207 个 Subject tokens。单次运行的轮数与 token 差异不能单独证明稳定性能收益。

[Live 直接调用证据](live-direct-calls.json) 记录推荐用例的 4 次未展示 data.query 调用：均正常进入注册工具的参数校验并返回 failed ToolResult，会话继续；该批没有未展示工具执行成功的样本。未展示工具成功执行由前述真实 Provider 协议离线探针验证，不能混称为 live 成功样本。

## Oracle 追加校准

[最后一组手动探针](final-oracle-probes.json) 验证标准化分群报告、中文主题列、表格质量证据及 4 月单列改名。使用真实 4 月源数据重建保留业务行与错误去重两种导出，并调用实际 Judge 做成对校准：错误主文件搭配正确参考表判失败；正确主文件搭配去重损失对照判通过。原 live 临时交付文件已清理，这不是对原文件重评分。

[分群比较证据探针](cluster-comparison-probe.json) 从保留的实际 SQL 重建 K=2/3/4 比较 CSV，并通过真实链接读取验证全部比较行进入 Judge；明细记录不会混入聚合证据。成员标签依私有真值重建，仅验证证据输送，不代表最终 Judge verdict。客户编号本就是题目允许的交付字段，删除无业务依据的 identifier_or_row_disclosure 扣分。

本次没有新增测试函数或 benchmark 基础设施自动化测试。手动探针与临时运行器留在忽略的 build/ 下，任务材料只保存结果、输入摘要与证据限制；旧失败成绩均保留。

## 推荐用例 JSON 失败的根因诊断

本节对应用户后续的只读排查请求；没有修改生产源代码、没有新增自动化测试，也没有重跑付费 Subject。原始失败为 run 96e4cdc4648748108f29e28f7362260f 的第 13 轮 analysis_graph 调用，JSONDecodeError 为 `Expecting property name enclosed in double quotes: line 1 column 986 (char 985)`。此时已完成 model.train、model.apply 和推荐结果转换；异常发生在调用图表服务之前，不能据此判断推荐算法执行失败。

已确认的链路是 `Provider.stream → _build_tool_calls → _parse_arguments → json.loads` 抛出异常；ProviderResponse 尚未构造，LLMService 不将该异常视为连接重试，Conversation 撤销 pending，Harness 向外传播异常。整轮响应没有进入 canonical staging，也就没有 ToolFailure 供下一轮修正。实际记录有 13 次请求、12 次已观察 usage；无法从保留证据确定第 13 次服务端是否已返回 usage，不能把已记录的 143180 tokens 当作全部消耗。

根本原因是“接收一次模型响应”依赖“其中每个工具参数成功解码”。ProviderToolCall、ToolCallOutputItem、StagedToolCall 都只表示 dict 参数；没有原始参数文本及解析失败的调用状态。于是单次调用的输入错误被提升为整轮响应错误。它与前一问题同属边界语义混同，但本次混同的是响应接收与调用有效性，适用于所有工具及普通、流式两条路径。

[离线边界探针](argument-json-probe.json) 经真实 Provider 解析、Conversation、Harness 与隔离 SQLite 验证 10 个组合：正常 JSON、未加引号的 key、尾逗号、非对象 JSON、已解码但字段类型错误，各覆盖普通和流式解析。前三类无效调用中的语法或根类型错误均使同轮正确调用也不执行、usage 观察数为零、持久化仅保留用户消息；字段类型错误则保留同轮正确调用、failed ToolResult、usage，下一轮正常完成。正常输入能经过逐字符、多调用交错分片完整还原；探针使用的图表输入模型为生产 AnalysisGraphInput，图表执行体为记录调用的离线替身。

没有证据表明本地流式拼接改坏了原始 JSON；目前实现按调用 index 原样追加参数分片，探针也通过。但原 live 的原始参数、分片和 finish_reason 没有保留，异常记录只包含类型、消息和堆栈，缺少 JSONDecodeError.doc；因此不能进一步断言是尾逗号、未加引号的 key、输出截断或服务端分片异常。已读取的 heatmap.vl.json 模板本身是合法 JSON；它不是可证实的直接错误来源。

建议修正调用表示：接收响应并保留 usage，允许调用携带原始参数及解码失败信息；把该调用写成 canonical ToolCall + failed ToolResult，将具体 JSON 错误位置反馈给模型，让正常会话循环继续。其它有效调用照常处理。无需增加第二套 Harness 重试循环，也不应把损坏参数默默改成空对象或猜测修复后执行；普通响应和流式响应应共用同一套参数解码与失败表示。当前流式路径“解码成 dict → dumps → 再解码”的重复归一化也可随该修正一并简化。

## 参数解析失败恢复的实现

用户明确授权“工具参数解析失败也要算作工具调用失败，可以反馈并继续”后，新增 InvalidToolArguments 值承载原始文本与 ToolFailure；Provider 对可识别调用的参数语法、对象根类型和既有参数边界错误返回该值，Registry 在正常调用入口直接产生对应失败结果，不执行无效调用。同轮其它调用、响应文本及 usage 继续完成。空参数文本不再被隐式改成空对象；缺省 arguments 的既有空对象语义保留。

普通和流式响应共用参数解析，流式只拼接 wire 调用，删除解码后 dumps 再次解码的路径。失败参数原文保存在 ToolCall content 的 raw_arguments，arguments_payload 为 null；历史回放、工具详情与 benchmark 诊断记录均读取该原文。没有改变存储表结构，没有增加 migration，没有增加另一套 Harness 重试循环，也没有新增自动化测试。

[恢复后的离线探针](argument-json-recovery-probe.json) 覆盖 14 个组合：合法 JSON、未引用 key、尾逗号、非对象根、空文本、截断文本和已解码字段类型错误，各验证普通与流式路径。流式分支走真实 LLMService.stream、Conversation 与 Harness；所有无效输入均有 failed ToolResult，同轮正确调用成功，下一轮修正调用成功，最后正常回答。每次修正流程的三轮 usage 完整，重新构造 Conversation 服务后原始坏参数可精确回放，工具详情可见原文。修复前探针保留，没有回写其失败结果。

[真实模型协议验证](live-argument-repair.json) 向 deepseek/deepseek-v4-flash 提交含合成坏 JSON 调用及真实解析失败值的历史；上游接受该历史并返回通过生产 AnalysisGraphInput 校验的修正调用，记录 1019 tokens。首次临时探针漏带该模型要求的 reasoning_content，被 HTTP 400 拒绝；补齐合成 reasoning 后重试成功，未改产品代码。此探针只验证协议与修正，不执行图表，也不是推荐 benchmark 成绩。

现有 21 项相关服务与 Chatbot 测试、完整离线套件 303 项、静态检查和隔离启动均通过；完整套件有 324 条既有 NumPy/joblib 废弃警告。没有注入故障的推荐用例复测独立运行，输入冻结见 [本次 manifest](json-recovery-live-manifest.json)，运行期间生产和 benchmark 源码摘要无变化。

[推荐单项结果](json-recovery-live-results.json)：run_status=completed，15 轮均有 usage，共 320837 tokens，30 次工具调用中 29 次成功、1 次图表数据源参数错误正常反馈；没有产生坏 JSON。本次没有复现原始偶发语法错误，不能拿此项的正常结束单独证明解析恢复，恢复证据由离线真实路径及合成历史的真实模型协议验证提供。pytest 的执行通过不等于业务通过：exact_private_top_k 失败，公开评估报告与源完整性通过，Judge 未进入。

剩余 oracle 冲突的初步观察：交付 SQL 使用 viewer_id/module_id 列名，oracle 固定 user_id/recommended_item；Subject 为冷启动学习者交付 EPSILON/ALPHA 并说明质量加权与覆盖考虑，而 oracle 固定 THETA/ETA。业务提示只要求合理推荐、两个未评分模块及说明评估，没有指定这些列名或该唯一冷启动组合。本次不修改其评分规则，也不把尚未独立评估的交付解释判为通过；这是后续 oracle 与业务质量诊断的入口。

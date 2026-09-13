# 工具定义消融

- **Objective**: 通过现有 harness benchmark 判断工具定义的有效信息，收敛隐含参数约定并分层删除重复说明，减少模型输入与无效调用，不以字符串缩短代替交付质量。
- **Guardrails**: 用户已批准同时实现显式 SQL 数据源映射、选择性删除重复说明，以及清除知识库 worker 的字符串 ID 断言，并已授权提交本批相关改动。保持系统提示词、Skill 正文、工具暴露范围、SQL 算法和 Judge；SQL 参考资料随参数契约更新。不增加回归测试或 benchmark 基建自动化测试，不增加 migration。上一轮完整定义与全删说明的原始证据单独保留；其他任务的诊断改动不纳入本次提交。
- **Current Truth**: SQL 工具现用必填 datasets 映射，已移除 dataset_id/bindings 两套输入及优先级；仅重复字段名、类型、schema 默认值的说明已删减，保留非显然语义。Analysis + Preprocessing 的工具定义为 12,382 → 11,160 字符（-9.9%），全激活为 16,594 → 15,062（-9.2%）。知识库独立 worker 使用整数任务队列与 None 停止信号，恢复记录类型已对齐。单一 owner、单一 packet 足够。
- **Verification**: 44 项现有测试、pdm run check、pdm run smoke --isolated 通过；真实工具/SQLite/SQL worker 人工验证通过单表、多表、索引查询、保存、全部源别名 lineage、explanation 分离及 Artifact 解析，见 [implementation.json](implementation.json)。忽略 description 后只有两份 SQL schema 的数据源字段发生变化。layered 四个 standard 任务的现有 oracle/Judge 报告均 pass，共 1 次 SQL 日期类型错误，0 次源别名错误；人工复核仍发现月结解释有被 Judge 漏掉的错误，详见下文。
- **Next Step**: 实现已提交为 41adb2f；重新执行的渐进实验现已完成 22 个有效 cell，另保留 2 个中断。G0/G1 固定新接口比较后，分别对 Knowledge 模式和 SQL 方言做了层内复原；第二层收益很小且未确立稳定因果收益，本轮不推进 G3。结果与收敛判断见 [progressive-findings.md](progressive-findings.md)，相邻 cohort 数字见 [progressive-summary.json](progressive-summary.json)。本轮只更新实验与 packet，没有新增生产改动或提交；任务目标扩张、解释缺少计算支撑及 Judge 漏判仍单列。

## 首批比较

| 组 | Subject 看到的工具定义 | 不变项 |
| --- | --- | --- |
| full | `f077816` 的完整定义 | 原生产配置 |
| no-parameter-descriptions | 删除 parameters 内的说明文字，包括嵌套字段说明 | 工具简介、名称、字段、类型、默认值、枚举、边界、required 及执行校验 |

预先选择四个代表任务的 standard：月结修订、客服分流复用、活动资格、补货决策，各组每题一次，共 8 个有效 cell。计划按月结 full→删说明、分流删说明→full、活动 full→删说明、补货删说明→full 顺序执行以平衡先后；活动准备失败后先继续补货，最终活动删说明与补货 full 有部分并行，不据本轮墙钟时间比较性能。每个 cell 新建独立 Thread/runtime，从任务开始接受干预；保持原生产 Subject/Embedding/Judge 配置和 benchmark 外部成本/时间限制，不添加轮次上限，不用上一组生成的答案、工具轨迹或对象替下一组铺路。

这是一轮机制筛选，不是正式验收或稳定通过率估计。若模型需要额外查询、读取参考资料或修复参数，相关轮次和 token 都计入结果；Judge 的业务错误需要对照公开交付与工具结果复核。结果将决定是否复验、是否保留少量不可从字段名推断的语义，以及是否需要转向参数接口或工具暴露粒度。

## 设计判断

参数描述是当前较大且可单独控制的变量；删除 description 不需要增加工具发现轮次，也不会删除可用能力。数值边界体积较小，本轮保留以免用额外错误恢复抵消节省。

图表工具同时携带词云的样式参数，分词工具有名称/位置两套选择器，SQL 工具有单 Dataset/多绑定两套输入；这些是参数接口和暴露粒度的候选问题，但改它们会同时改变调用方式。本批先隔离描述文字，避免把多种变化混成无法解释的一组结果。

删除所有 description 只是消融，不预设生产应永久删除所有参数说明。像 SQL 输入的默认别名、源列位置和查询结果位置的区别、词云数据由谁提供等信息，可能值得用少量准确文字保留；实验结果是取舍依据。

静态盘点见 [inventory.json](inventory.json)。临时入口与原始请求、报告保存在 `build/run-tool-definition-ablation.py` 和 `build/tool-definition-ablation/`，不进入自动化测试集合。

## 实验结果与解释

Subject 为配置中的 `deepseek/deepseek-v4-flash`，Judge 为 `deepseek/deepseek-v4-pro`。下表的 token 是报告中的 Subject 实际累计 input + output，包含缓存输入，不含 Judge；它不是费用，也不是静态字符估算。每格只跑一次有效样本，表格用于机制筛选，不能估计稳定通过率或因果效应。

| 任务 | 完整定义：结果 / 轮次 / 工具错误 / tokens | 删除参数说明：结果 / 轮次 / 工具错误 / tokens |
| --- | --- | --- |
| 月结修订 | fail / 9 / 0 / 87,621 | fail / 12 / 4 / 144,042 |
| 客服分流复用 | pass / 31 / 5 / 1,322,231 | pass / 21 / 1 / 425,011 |
| 活动资格（两组均临时修正准备 worker） | pass / 6 / 0 / 45,724 | pass / 11 / 1 / 99,724 |
| 补货决策 | pass / 5 / 0 / 34,962 | pass / 14 / 6 / 99,092 |

完整定义累计 51 轮、1,490,538 tokens；删说明累计 58 轮、767,869 tokens。总 tokens 的下降由分流任务主导：两次分流的训练工具调用数分别为 12 与 4，路线差异很大；其余三题的 tokens 均上升。因此既不能把总量下降当作普遍收益，也不能把每次工具错误都归因于删除说明。工具错误数只统计被实际返回、按 tool_call_id 去重的 ToolFailure；不把 ToolSuccess 内部的失败训练候选混算，也不累计历史重放次数。

月结两组的程序 oracle 均通过，最终 outcome 均被 Judge 的 `incorrect_business_claim` 判为 fail。完整定义组第二次回答先正确列出南区从 -1,200 到 -900、增加 300，随后又说南区不受更新影响；删说明组第一次回答说不去重会把东区虚增约 2,100，但重复的 2,000 订单和 100 退款对净回款的共同影响应为 +1,900。后者还有推测性口径扩张。本轮不修改这些已约定另行处理的解释问题，不因表格计算正确而改写 verdict。

删除参数说明后，月结猜 `orders/stores/refunds`、分流猜 `dataset_2`、活动猜 `customers`、补货猜 `offers/dataset_2`，共 7 次 SQL 源表别名错误。完整定义的分流也有 4 次 `FROM t` 配合单独 `dataset_id` 的错误，另外一次 transform 未提供数据源。当前 API 的单 Dataset 分支实际只绑定固定的 `input`；隐藏默认表名即使写在说明里也可能被历史 SQL 的别名干扰。删除说明使这项约定完全不可从参数推断，是可直接定位的损失；显式映射能消除这一隐含约定，但不能保证模型不再写错 SQL 或选错 Dataset。

补货删说明组的其余错误包括 DuckDB 的 generate_series 列命名、递归 CTE 数值类型及 UNION 的 ORDER BY 使用。这些不属于 SQL 源绑定问题，不能计作显式映射将会修复的错误。

## 静态体积的分母

Analysis + Preprocessing 的 14 个工具定义共 12,382 个 Unicode 字符；移除参数说明为 8,511（减少 31.3%），移除数值/长度边界只减少 7.4%。三个 Skill 全激活时的 19 个工具为 16,594 → 11,522（减少 30.6%）。较大的单工具为 graph 1,950、tokenize 1,800、transform 1,369、query 1,177。此处是紧凑 JSON 字符，不是 tokens。

工具定义占此前 analysis + preprocessing 的“系统 + catalog + 一次 Skill 激活 + 定义”小计约 78%，不能称为占真实完整输入 78%。例如本轮 full 月结最后一次请求共 43,159 字符，其中 9 个已暴露工具为 7,914 字符，约 18%；其余还包括用户输入、历史调用和结果。首轮仍只有 3 个基础工具和 catalog，没有预注入 Skill 正文。

## 已批准的 state diff

优先顺序按实际误用、覆盖业务范围、实现复杂度排序，不能只按定义长度排序。第一项是收敛 SQL 数据源接口；第二项是删除重复字段名/类型/schema 默认值的说明，并保留非显然的副作用、索引坐标系和输入输出格式。用户批准两项合并实施；本轮验证联合改动的行为，无法分别估计两项贡献。

| 面向 Agent 的状态 | 修改前 | 已实现 |
| --- | --- | --- |
| query / transform 的数据源 | 可选 dataset_id，或可选 bindings 列表；两者同时给出时 bindings 优先 | 必填 datasets 对象，SQL 别名直接映射到整数 Dataset ID |
| 单表 SQL 的别名 | 固定 input，靠说明记忆 | 调用显式声明，如 datasets={"orders": 12} 对应 FROM orders |
| 多表 SQL | [{"alias": "orders", "dataset_id": 12}, {"alias": "stores", "dataset_id": 19}] | {"orders": 12, "stores": 19}，与单表相同形式 |
| 输入分支 | 两个可选输入、运行时至少一个、优先级与隐式默认 | 一个必填输入；移除默认分支和优先级 |
| 保存结果 | query 只查询，transform 生成 Dataset/Artifact 并记录 lineage 和 explanation | 保持这两个明确的效果；映射转换为现有 DatasetSqlBinding，lineage 仍记录全部源及别名 |
| 历史与兼容性 | 已保存的 ToolCall 使用旧参数 | 旧历史保留；新调用改用新 schema，不引入双协议兼容层或数据库 migration。旧会话可能因沿用历史参数而需要一次错误恢复，后续应在真实续聊中验证 |

调用形状示例：`data.query(datasets={"orders": 12, "stores": 19}, sql="SELECT ... FROM orders JOIN stores ...")`。两份参数 schema 的原型分别从 969 → 645、1,156 → 832，合计减少 648 字符；收益主要是减少隐含约定，体积下降是附带结果。[explicit-sql-proposal.json](explicit-sql-proposal.json) 保存投影 schema 与实算结果：两个临时 Parquet 表完成区域汇总 East=30、West=15，transform 保存 2 行。此原型没有注册真实 Dataset ID，也没有经过完整 Agent dispatch 或真实模型调用，不能把它称为 benchmark 已验证的改进。

实施影响集中在 [tool_inputs.py](../../src/xenix/services/agent/tool_inputs.py) 的两份 SQL 输入模型、[_data_tools.py](../../src/xenix/services/agent/_data_tools.py) 的源映射和审计参数分离，以及三份 SQL 参考文档。SQL 服务的查询、执行、持久化、lineage 算法无需新增抽象。不要为隐藏定义另加一次工具搜索，也不要依据已知题目答案剪掉本次没用到的工具。

graph 的词云样式和 tokenize 的双选择器仍可后续审查，但本批没有充分调用证据支持直接删除其能力。单纯把图表拆成两个同时可见的工具并不会自动减少总定义体积；这些候选暂不排在 SQL 接口之前。

## 准备失败及实验偏差

第一次 full 活动运行（campaign-r1，trace `b8225c2af56341f394f3a316152cb5af`）在 0 轮、无 Subject 请求时失败，`failure_kind=campaign_policy_derivation_timeout`。日志明确显示 [knowledge_derivation_service.py](../../src/xenix/services/knowledge_derivation_service.py) 的 `_worker_main` 在 `assert isinstance(item, str)` 退出；`notify(job_id: int)` 接收到的已经是持久化整数 ID。此断言又位于任务异常记录的内层 try 之外，job 未转入 failed，case 只能等到准备超时。

正式桌面 composition 给知识服务注入 scheduler，benchmark 的知识准备使用独立 worker，因此本证据确认的是独立 worker 路径缺陷，不能推断所有 GUI 知识任务均失败。同文件的队列及 recover_pending 局部容器也保留了旧字符串类型标注，现已对齐。进一步检查确认通知回调传的是字符串 library_id（如 global），不是任务 ID；原先把该回调也列为遗留类型的推断不成立，保持其字符串契约。无需增加 migration 或更长的超时。

临时入口新增显式 `--repair-knowledge-worker-id`，只在内存中将这个断言的 str 改为 int，原方法其余代码不变；两组活动的有效运行均使用该修正，保存在 campaign-r2。`--harness-variant` 带 `-knowledge-worker-int`，每个 Subject 请求的 stats 记录修正标记。原 campaign-r1 报告仍在 results.json 中作为准备失败保留，不纳入工具定义效果比较；没有重复某个业务失败直到通过。实验包含 9 次尝试、8 个有模型执行的有效 cell。

## 本地复现与证据

当前实验入口只存在于忽略目录；常规命令为 `.venv/Scripts/python.exe build/run-tool-definition-ablation.py --arm full --task revenue`，另一个 arm 为 `no-parameter-descriptions`，任务选 revenue/routing/campaign/restock。活动有效配对均追加 `--repetition 2 --repair-knowledge-worker-id`。入口直接选择现有 standard 任务，通过 `.runtime/dev/config/` 下的 agent、embedding、judge settings 运行；不复制密钥进 packet 或捕获日志。每个 invocation 沿用 benchmark 自身预算，未添加额外轮次限制。

Provider 请求捕获逐份验证删除参数说明后，工具名称、简介、其余 schema 和执行契约保持一致；工具说明之外的 Subject 输入沿用真实运行轨迹，Judge 请求不做干预。原始请求/响应/stats 和报告在 `build/tool-definition-ablation/<arm>/<task>-rN/`，报告 trace、配置指纹、Judge rubric hash、token 指标和去重工具错误已归档于 [results.json](results.json)。本地汇总命令为 `.venv/Scripts/python.exe build/summarize-tool-definition-ablation.py`；显式映射原型命令为 `.venv/Scripts/python.exe build/probe-explicit-sql-datasets.py`。

## 选择性精简的实现与联合验证

这里的三层分工描述生产信息的放置方式：字段名/类型/枚举/schema 默认值表达显然的信息；简短 description 补足单位、索引坐标系、跨字段关系、源身份和执行效果；按需参考资料承载长例子。它不等于分层渐进的消融实验。上一轮直接比较完整说明和全删说明，本轮又同时更改接口与部分说明，均未逐层测出各类信息的贡献；之前用生产分层策略回应用户的实验方法批评，理解有误。历史 arm 名 layered 保留以对应原始报告，但它只表示联合实现候选，不表示已完成逐层消融。

已删除如 title、dataset_id、run_name、include_logs、task_ids、model_family 的重复说明，以及 phrase_mode 对 unigram/unigram_bigram 的重述；简化 numeric_summary_limit、correlation_column_limit、params_by_model 和 knowledge.lookup.mode 中的重复部分。保留 SQL 别名到 ID 的映射含义、源列 c0/c1 索引规则、transform 的最终 SELECT/output 行为、列选择器互斥、训练绑定来源、模型输入 URI/预测步数和词云的实际自动默认值。词云参数的 schema 默认是 None，因此 word/count、80、0.85 及依密度选择字体范围并非与 schema 重复，继续说明。

生产知识库 worker 的停止信号改用 None，使队列直接表达 int | None，移除字符串断言而非另加整数运行时断言；recover_pending 的任务列表和 generation 索引使用整数。任务执行异常仍沿既有 report_exception 与失败记录路径处理。

人工验证经生产 Tool registry、Dataset/Artifact 服务、临时 SQLite 和真实 preprocessing worker 完成；两个注册源的别名完整进入 lineage，explanation 不混入 SQL 参数，返回 Artifact 可解析。旧 dataset_id 输入在注册器入口得到参数验证异常，由既有 LLM 调用边界转为模型可见失败；现有 Harness 参数修复测试覆盖该边界。本人工场景没有伪造 canonical ToolCall，正式多轮行为交由后续 live 候选运行观察。

验证命令为 `pdm run pytest --direct tests/agent tests/llm/test_tool_result_pagination.py tests/ml/test_data_transform_service.py tests/ml/test_analysis_profile.py tests/knowledge/test_knowledge_import_authority.py tests/knowledge/test_knowledge_projection_chunking.py tests/knowledge/test_knowledge_lookup_tool.py tests/test_knowledge_job_handlers.py -q`（44 passed）、`pdm run check`、`pdm run smoke --isolated`，以及 `.venv/Scripts/python.exe build/probe-layered-tool-definitions.py`。所有新增 Python 实验入口均在 build 中，没有新增测试文件或用例。

本轮 live 候选为 `--arm layered`，使用新生产 schema 和说明，不对 Provider payload 进行消融，不传 `--repair-knowledge-worker-id`。选择四个 standard 任务，各一次，沿用原 Subject/Embedding/Judge 配置与 benchmark 预算，保留所有尝试。部分任务并行运行，不比较墙钟性能；结果写入 [implementation-results.json](implementation-results.json)，保持首轮 results.json 不变。

| 任务 | 现有 oracle/Judge 报告 | 轮次 | ToolFailure | Subject tokens |
| --- | --- | ---: | ---: | ---: |
| 月结修订 | pass | 10 | 1 | 109,824 |
| 客服分流复用 | pass | 20 | 0 | 484,886 |
| 活动资格 | pass | 5 | 0 | 34,753 |
| 补货决策 | pass | 8 | 0 | 69,585 |

合计 43 轮、699,048 Subject tokens，包含缓存输入。唯一 ToolFailure 是月结 transform 在 BETWEEN 中混用 VARCHAR 与 DATE，模型补充显式转换后继续完成；没有源别名错误或旧参数格式调用。原完整定义、全删说明、联合实现候选各四题的错误数为 5、12、1。这与参数收敛的目标一致，但样本量和联合改动均不足以证明稳定因果收益，也不能识别哪层说明可删；补货仍由基线 5 轮变为 8 轮，不能声称每题都更快。

人工复核不把报告的 4/4 等同于全部解释正确。layered 月结第一次回答称“不排除 cancelled 会改变南区最差的判断”；实际南区净回款从 -1,200 加上取消订单 O20 的 2,700 后为 1,500，仍低于北区 22,000、西区 32,900 和东区，排名不会改变。第二次回答又称 9,000 元退款冲掉 20,000 元订单的“大部分”，该笔比例实际为 45%。当前 Judge 给月结两个维度均为 2，漏掉这些解释错误；保留原始报告，并把这项人工发现带入后续解释/Judge 讨论，不改写本次机器判题结果。原始回答在 `build/tool-definition-ablation/layered/revenue-r1/capture/22976-006-response.json` 与 `22976-010-response.json`。

本轮未修改任何测试或 benchmark case/oracle/Judge 源码。仅使用现有用例与 build 中的临时测量入口；四个代表任务的结果也不等于整个历史题库、确认变体或稳定重复验收已经通过。

## 消融方法更正：逐层剥离、相邻对照

实验目标是识别各类说明的边际价值。生产如何放置信息与实验如何隔离变量是两个问题；“全部移除仍能否工作”只能给出极端情况，不能代替逐层删除。当前的 5 → 12 → 1 次错误分别来自旧接口完整说明、旧接口全删说明、新接口选择性删说明，既不是连续的同接口消融链，也不能证明选择性删说明导致错误下降。

下一轮固定本次提交后的 SQL 接口、字段/类型/默认值/约束、工具集合、运行逻辑、系统提示词、Skill 内容和 Judge，只改变发送给 Subject 的说明文字。首个对照在新接口上恢复未变字段的删减前说明；新 datasets 参数在所有组使用相同说明，移除的旧参数不复活。因此可以单独测量已落地的重复说明删除，不把旧接口的隐含别名问题混入说明效果。

| 阶段 | 相比上一已保留阶段的唯一变化 | 可回答的问题 |
| --- | --- | --- |
| G0 固定接口对照 | 新接口，未变字段恢复删减前说明 | 为同接口的说明消融提供起点 |
| G1 删除显然重复 | 仅移除字段名、类型、枚举、schema 默认值的重述 | 当前选择性删减在同接口上是否减少开销、增加误用 |
| G2 删除跨位置重复 | 按工具族逐步删去已由工具简介或其他仍可见字段完整表达的重复用途说明/例子 | 同一信息是否无需多处重述 |
| G3 探测非显然语义 | 从上一保留组出发，一次只移除一类提示，例如单位、索引坐标系或跨字段关系 | 哪类说明不可省略，哪些可以继续缩减 |

这是起始分组，不预设必须删到 G3，也不预设更短的阶段一定保留。每步与上一组在相同任务/配置下配对比较；先选择实际触发该类信息的任务，再用适度重复辨别随机波动。未调用相关能力的任务不能证明该层说明无价值。若某层出现失败或明显额外恢复，在该层按工具或字段进一步拆分、复原定位，不继续跨层全删；有收益信号再扩展代表任务。保留全部尝试，避免只挑通过样本。

观察交付正确性、参数/语义误用、恢复调用、轮次和实际 tokens，同时核查具体失败轨迹及 Judge 漏判。只有同接口、同条件下相邻组的差异可用于讨论该层贡献；前轮联合实现的 4/4 报告仍仅作为实现验证。更正设计时这些阶段尚未运行；后续新实验的完成情况见下节与 progressive-findings.md，历史结果没有被重新标记成渐进结果。

## 渐进实验执行登记（2026-09-13～14，已完成）

用户要求重新进行消融，起点固定为已提交的 41adb2f；生产源码、现有 case、Skill、系统提示词与 Judge 均不修改。执行前将三份配置复制到忽略目录并记录哈希，同时记录相关生产源码、用例与输入 schema 的指纹；每个 cell 检查输入文件未变，每次 Subject 请求验证除参数 description 外完整工具契约一致。原有 44 项测试、check 和 isolated smoke 已在此生产版本通过，本次 collect-only 选中一个标准业务 node，不新增回归测试或 benchmark 自动化测试。

逐项变化与预先登记的样本顺序在 [progressive-plan.json](progressive-plan.json)。G0 在新接口上恢复未变字段的旧说明；G1 使用当前精简说明，但恢复 analysis.graph.spec 的例子与 data.transform.explanation 的证据性质限定，使这两项不混入显然重复层。G1 相比 G0 有 21 处说明变化，其中未暴露/未调用的参数不纳入有效性结论。SQL datasets 映射及其描述在 G0/G1 相同，旧参数不恢复。

G0/G1 的初始范围是月结、分流、活动、补货各一对，并为月结与补货各增加一对新会话，总计 12 个 cell；交错组别先后，最多两个独立 cell 并行，不比较墙钟性能。每个 cell 沿用生产 Harness 配额和现有 benchmark 外部预算，不添加轮次上限。全部尝试保留，不以反复运行直到通过替换失败。

G2 预定只缩短 SQL/图表族的三处说明：图表 spec 删除工具简介已有的 Vega-Lite 格式名及示例键、query.sql 删除重复的 DuckDB 名称、transform.sql 删除重复的 DuckDB script 引导语；保留图表数据注入和 transform 最终 SELECT/output 语义。G3 单独探测 datasets 的别名到 ID 关系说明，在 G2 基础上只删除 query/transform 这两处同义描述；这一层是明确改变关系提示的实验，不能与 G0/G1 固定该描述的控制混淆。G2/G3 均先在月结与补货各运行一次，复核上一层后决定是否重复、拆分或停止；不预先承诺保留更短组。

临时执行入口为 `build/run-progressive-tool-ablation.py`，原始报告、请求与响应在 `build/tool-description-progressive/<arm>/<task>-rN/`。`build/batch-progressive-tool-ablation.py` 只启动显式列出的 cell，`build/summarize-progressive-tool-ablation.py` 从保存证据提取判题、真实 tokens、按 call ID 去重的 ToolFailure、实际参数使用及最终回答位置；不把静态字符缩减率当作 token 或费用节省。

# Impact Handshake：Harness benchmark 业务任务改造

状态：**approved，已实施并完成相称验证，已获准提交归档**。2026-09-13 用户明确批准开始实现并随后批准提交；基线 `dcec815b23369832307e26b96daf1a6961541a8b`。本文件中的 State Diff 指本次实施对 benchmark 的改造前后状态，不是测试运行时的应用状态差异。实际结果见 [验证记录](verification.md)，不构成 Harness 正式能力验收。

## State Diff — From → To

| 维度 | From：当前状态 | To：本轮实施后的状态 |
| --- | --- | --- |
| 核心任务组合 | 无显式文件选择时收集当前 13 个 live case；题目大多按清洗、聚类、预测、推荐、文本等能力展开 | 默认核心组合改为 A 月结结果修订、B 当期回访名单、C 持续工单分流；按完整业务任务说明覆盖与结果 |
| 旧题处置 | 原有 13 题与默认 benchmark 集合等同 | 13 题退出默认核心，暂保留具体文件/node 选择入口用于历史诊断；本轮不逐一修复、扩展或删除旧题，不宣称它们都值得长期保留 |
| 题面与数据 | 旧题面与固定 fixture 是当前执行材料；新设计只有 task packet 中的小型实验 | 新增正式业务题面和新数据，覆盖有意义的输入变化；三项原型用于论证与开发，不直接把手写小样本成绩当成正式基准质量 |
| 一次 case 的含义 | 一个隔离环境中创建会话、提交一次用户请求、评估一个终态 | 一个 case 是一项完整业务任务：A/C 在同一会话连续两次请求，B 一次；保留各轮交付，整体判断是否完成，第二轮不由评测器补送上一轮答案 |
| 判据与 judge | 各 case 独立检查产物，部分会寻找正确中间结果；共享 Judge 输入与报告按现有单次结果组织 | 新任务围绕实际交付验收金额与变化、名单资格、保存方案与复用结果；事实由程序核对，解释由必要的 judge 判断，允许合法等价方案；只修新任务所需的公共证据路径 |
| 资源与失败归因 | 单次请求构成一个 cell 的时间、轮次、tokens 和状态 | 资源按整项任务累计并保留各轮归因；后续请求不重置总消耗。中途失败能说明发生在哪轮及对任务完成的影响，不能只用最后一轮成功掩盖前面的缺失 |
| 报告与比较 | v5 cell 报告为当前格式，v4 保留诊断读取；主要描述单次终态 | 新任务报告增加逐轮结果与任务汇总，采用新版本表达改变的语义；旧报告保留读取用途，新旧任务与验收口径不直接混成同一通过率趋势 |
| 文档 | unit-tdd 描述现有单次提交、case 与评判边界 | 更新任务组织、跨轮执行、验收与报告的长期约定；设计决定归 unit-tdd，执行命令归贡献指南，AGENTS.md 不承载详细设计 |

旧题暂留是这一轮迁移范围的明确选择，不是为了给历史资产安排永久位置。后续是否淘汰依据独立价值与新覆盖决定；不会为修复旧题继续扩大本轮实施。

正式数据需要在当前设计原型基础上拓展实体关系、业务条件与语言表达，并保留未参与日常定向修改的语义变化；复制行、随机改名或扩充同质模板不能满足这一变化。具体内容以 [任务规格](design.md) 的业务要求为准，不要求固定变体数量。

默认资源阈值不因增加用户请求而自动成倍提高；计量与上限作用于整项任务。试跑如揭示预算与任务复杂度不匹配，依据实际消耗报告所需调整，不裁剪目标任务来隐藏差距。

## Address and Object

以下保留审批时的修改地址与作用；三个新 case 和正式 fixture 已落地，共享交付支持放在 `_infra/business_tasks.py`。`budgets.py`、`telemetry.py`、`case_support.py` 的现有接口已足够，未因本表列名而强行修改。

| 对象 | 拟修改地址与作用 |
| --- | --- |
| 新业务 case | 在 `tests/e2e/agent_harness/` 新增 `test_business_revenue_revision.py`、`test_business_campaign_eligibility.py`、`test_business_routing_reuse.py`，分别拥有题面、业务输入、完整任务判据 |
| 正式数据 | 在 `tests/e2e/agent_harness/fixtures/business_tasks/` 新增三项任务材料与作者侧真值/变化；实验目录继续仅作设计证据，不成为运行依赖 |
| 默认集合与显式选择 | [dispatch.py](../../tests/e2e/agent_harness/_infra/dispatch.py) 的 `benchmark_pytest_arguments`、[pytest_plugin.py](../../tests/e2e/agent_harness/_infra/pytest_plugin.py) 的收集与调用入口；保留 pytest 文件/node 选择习惯，不增加第二套任务注册器 |
| 任务执行与证据 | [contracts.py](../../tests/e2e/agent_harness/_infra/contracts.py) 的 `BenchmarkCase`、`BenchmarkCaseContext`、结果契约；[runner.py](../../tests/e2e/agent_harness/_infra/runner.py) 的 `_run_model_cell`、执行与测量；[headed.py](../../tests/e2e/agent_harness/_infra/headed.py) 的提交/终态处理；[case_support.py](../../tests/e2e/agent_harness/_infra/case_support.py) 的必要交付定位 |
| 任务资源累计 | [budgets.py](../../tests/e2e/agent_harness/_infra/budgets.py) 及调用处，仅在跨轮共享计量所需范围内改动 |
| 任务报告与评判 | [contracts.py](../../tests/e2e/agent_harness/_infra/contracts.py) 的报告结果、[report_policy.py](../../tests/e2e/agent_harness/_infra/report_policy.py) 的读取/验收/比较、[telemetry.py](../../tests/e2e/agent_harness/_infra/telemetry.py) 的任务与轮次诊断；[judge.py](../../tests/e2e/agent_harness/_infra/judge.py) 仅在新任务证据与题目评分锚点确需支持时调整 |
| 已有验证与文档 | 按实际改动更新 `_infra_tests/` 现有相关覆盖，移除失效的旧假设，不新增回归测试；更新 [benchmark unit-tdd](../../docs/30-unit-tdd/agent-harness-benchmark.md) 与必要的 [CONTRIBUTING.md](../../CONTRIBUTING.md) 命令说明 |

共享类型、具体分派和序列化细节可在上述范围内选择最简单实现；不因列出了某个文件就必须修改它，也不把本表扩展为通用工作流或全库判据审计。

## Blast Radius 与保持项

- 直接影响 benchmark 的默认选题、headless/headed 执行、消耗统计、Judge 证据与报告解释。无显式选择运行 benchmark 的开发者会得到新的核心组合，这是有意改变的开发行为。
- 生产 `src/xenix/` 的 Harness、Conversation、Dataset、ML、Knowledge 与 UI 不在这次改造范围；不修改 Skill 提示、数据库 migration、用户运行数据或安装配置。新题暴露的产品缺陷另列事实与影响，不为提高分数偷偷调整生产行为。
- 仍经真实 Harness 与已配置 provider 完成任务；普通测试保持离线。没有把 mock/replay、参考分类器或作者侧真值作为 Subject 的替代执行路径。
- 保持可计算事实与解释评判的职责区分、原始用户数据保留、错误可见和合理等价答案。这个 handshake 不引入运行时全库 State Diff 或全目录一致性校验。

## Verification

- 收集检查证明默认是三个新核心任务，旧题可经显式选择找到；headless/headed 指向相同任务定义。
- 运行受影响的已有离线覆盖与新任务设计实验，验证单轮兼容、多轮状态连续、各轮与整体资源累计、交付定位和新旧报告读取；不通过新增逐字或镜像实现测试堆积验收。
- 每项新任务有合理完成、关键业务错误和有意义变化的证据。A 验证修订后的数值与解释，B 验证当前规则下的名单，C 验证实际保留方案的跨轮复用与新批次质量。
- 使用明确的模型、设置与消耗记录进行相称 live 试跑，结果区分 Subject 失败、评判问题和预算不足。微型实验成功不能代替实际 Harness 完成，单次通过不能证明稳定性。
- 正式报告检查每轮与整项任务的结果可读，旧报告仍能解读；新任务的分数不能作为旧题库上 Harness 改进的直接证据。

## 当前证据与范围状态

[任务设计](design.md) 保留初始规格；[实验记录](experiments/README.md) 已补充正式材料探针、可见 UI 双请求、中断恢复与真实交付复评。[验证记录](verification.md) 区分实际通过、Subject 失败、评判错误和剩余限制。正式数据代表性、Judge 校准与三次 headless 加一次 headed 的正式验收均未建立。

上述 From → To 已落实。生产缺陷单独记录，默认预算保持不变；实施完成后用户另行明确批准提交。

> 阶段归档（2026-09-15）：用户已结束 benchmark 优化及相关失败排查。以下为历史记录，旧 Next Step 不再代表待执行任务；当前工作见 [1.5.0 收尾](../minor-1-5-closeout/packet.md)。

# Agent 上下文精简

- **Objective**: 减少 Agent Skill、系统提示词和工具定义的常驻、重复及无关信息，保留能力发现与调用所需语义。
- **Guardrails**: 整数身份已提交 `4abe48c`；用户已授权提交本批上下文精简，随后通过 harness benchmark 消融实验继续研究 Skill 和系统提示词。不增加回归测试或 benchmark 自动化测试。任务目标扩张、解释缺少计算支撑、题库和 Judge 另行处理，不据字符减少宣称回答更正确。
- **Current Truth**: 三处精简已实现并验证；analysis + preprocessing 的说明总量从 33,188 降到 15,820 个 Unicode 字符，减少 52.3%，工具仍为 14 个。另重写过时的预处理参考文档，移除只支持中文分词、原子清洗优先于 SQL、索引优先于名称等错误或固化的指引。单一 owner、单一 packet 足够，不需要并行 Track。
- **Verification**: 现有 Agent/LLM/Profile/Knowledge Tool 测试 28 passed；`pdm run check` 与更新后 catalog 检查通过；完整 benchmark 收集 24 项。人工实验经真实 Tool 注册、Dataset/Artifact/SQLite/图表服务生成分层图、分面图、词云并核对 SVG 内容；全部 21 个 Skill 资源经资源 Tool 可读取。排除 description 后，所有工具参数 schema 仅 `analysis.graph.spec` 有差异。本轮没有新增自动化测试，也没有调用真实 Provider 或重跑完整 benchmark。
- **Next Step**: 本批实现已获准提交；后续消融先明确首轮目录、激活后正文、逐轮工具定义的不同开销，再比较移除 Skill 正文和缩减系统提示词的效果。任务目标扩张与解释缺少计算支撑仍是独立议题。保留前序失败诊断记录。

## State diff 与决策

| 面向模型的状态 | 之前 | 本批实现 |
| --- | --- | --- |
| Skill 发现 | 每轮长简介、激活状态、资源数量及读取流程 | 简短的未激活能力入口与已激活名称；保留懒加载可发现性 |
| Skill 激活 | 简介、正文、重复 metadata、正文资源目录和结构化资源目录 | 正文与一次资源索引；维护元数据保留在本地 catalog |
| 指令职责 | 系统、Skill、工具重复能力/停止/检查/语言规则 | 系统保留通用行为与语言/交付约定；Skill 保留领域判断；工具说明输入、效果与返回值 |
| 图表参数 | 手抄部分 Vega-Lite 字段，开放其余字段 | 直接接收 Vega-Lite JSON；原图表服务继续解析、注入数据和渲染 |
| 其他工具参数 | 名称/默认值/枚举与文字反复说明相同内容 | 精简说明，保留字段、类型、约束、默认值及跨字段执行规则 |

直接删除重复信息比增加一层自动摘要或动态路由更有杠杆；本批不改变 Skill 到工具的暴露范围，也不引入新的激活、停用或审批流程。图表参数的标准语法由图表服务和渲染器解释，Agent 层继续验证参数是 JSON 对象以及两种图表模式互斥。

默认系统提示词只影响新 Thread；已保存的用户/系统提示词及历史 ToolResult 不被重写。新工具定义与精简目录可以用于已有 Thread；旧的 Skill 激活正文仍作为原始历史保留。

## 测量与证据

基线为整数 ID 提交 `4abe48c`，测量使用生产注册器、portable Tool schema、Skill catalog 和 `en_US` 默认系统提示词；每个激活 Skill 计一次激活结果，工具定义按紧凑 JSON 函数信封计算。不含用户数据、普通工具结果、其他历史或 Provider 专有信封开销。这里的字符数不是 token 数，也不能证明错误解释已经修复；持久化旧会话不会获得与新会话相同的完整降幅。

| 场景 | 工具数 | 修改前字符 | 修改后字符 | 减少 |
| --- | ---: | ---: | ---: | ---: |
| 未激活 | 3 | 7,524 | 3,156 | 58.1% |
| Analysis | 9 | 22,145 | 10,411 | 53.0% |
| Preprocessing | 13 | 25,142 | 12,887 | 48.7% |
| Modeling | 15 | 30,494 | 15,727 | 48.4% |
| Analysis + Preprocessing | 14 | 33,188 | 15,820 | 52.3% |
| 全部三个 Skill | 19 | 43,997 | 20,957 | 52.4% |

Analysis + Preprocessing 中，系统提示词为 1,992 → 946，目录为 3,315 → 372，激活结果为 8,406 → 2,120，工具定义为 19,475 → 12,382。按需读取的预处理参考文档另由 6,380 降到 3,191 字符，不计入上表。

完整数值和人工实验摘要保存在 [measurements.json](measurements.json)；设计职责归入 [Unit TDD](../../docs/30-unit-tdd/README.md)，未写入 AGENTS.md。原始测量脚本、参数 schema 快照和日志位于忽略目录 `build/agent-context-*`、`build/measure-agent-context.py`、`build/probe-agent-context.py`，不进入自动化测试集合。

本批没有修改生产工具的激活范围、执行配额、数据/模型算法、结果分页或 benchmark 判题条件。图表入口的行为差异是由图表服务和渲染器解释传入的 JSON，而非先套用 Agent 层手工列举的一部分 Vega-Lite 字段类型；显式 JSON 值也不再被该中间模型的 `exclude_none` 改写。词云参数和图表模式互斥约束保持原有契约。

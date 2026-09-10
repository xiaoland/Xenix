# AGENTS.md 规则检查与仓库外拟议修改

日期：2026-09-05。本文是检查记录和未应用的建议，不是新增的常驻指令。

## 已核实的继承关系

- 全局：`C:/Users/yyh/.codex/AGENTS.md`；同目录无 `AGENTS.override.md`，当前 `CODEX_HOME` 环境变量未设置。文件内容与本会话注入的全局规则一致。
- 父目录：`F:/`、`F:/CODING/`、`F:/CODING/Project/` 均未发现 `AGENTS.md` 或 `AGENTS.override.md`。不能把 Git 共用目录所在的兄弟仓库当作本工作树的父级规则。
- 当前项目根：`F:/CODING/Project/Xenix_native/AGENTS.md`，无根级 override；全局配置中未匹配到 `project_doc_fallback_filenames`、`project_doc_max_bytes`、`project_root_markers` 显式设置，项目 `.codex/config.toml` 不存在。仅筛选这些发现配置键，未输出其他配置。
- 仓库内发现 8 个局部 AGENTS：`src/xenix/ui/`、其 `widgets/`；`src/xenix/services/`、其 `storage/`、`agent/`、`llm/`、`ml/`；`tests/e2e/agent_harness/`。根目录任务并非自动受全部局部规则约束；涉及对应文件时才应用。services 的 Scope 明确只管直接位于该目录的服务文件（第 5 行起），不扩大为所有子包。
- [官方发现规则](https://learn.chatgpt.com/docs/agent-configuration/agents-md)：先全局，再项目根至当前目录；同层优先 override，较近规则覆盖冲突部分。并非无条件从盘符根加载全部祖先。本会话已有直接注入规则，磁盘修改也不等于重写现有会话中的历史指令。
- 未读取凭据、会话记录或缓存。只发现规则文件名、读取规则及明确相关的 CONTRIBUTING、命令定义和 pytest 入口；目录枚举遇到临时目录访问拒绝，没有进一步访问。

## 已应用的修改及依据

| 原规则与证据 | 具体问题 | 已实施处理 |
| --- | --- | --- |
| 全局 AGENTS 第 4–5 行：仅实质歧义才询问，同时“Modifying source code requires user approval” | 没有定义实施请求是否已经构成批准，容易重复确认；诊断例外也可能被误用为修复授权 | 根 AGENTS 第 42–44 行区分诊断、实施与实验，定义授权延续、完成标准及阻塞处理 |
| 原根 AGENTS 第 25 行：“Nearer ... are additive” | 只说明叠加，未说明局部范围与冲突处理 | 根 AGENTS 第 24–25 行明确范围、优先顺序与按需读取 |
| 原根 AGENTS 第 32 行：“Also run ... check ... smoke”；CONTRIBUTING 第 74 行要求最小验证集 | 同一仓库对每次验证范围给出不同信号 | 根 AGENTS 第 32–34 行采用 CONTRIBUTING 的影响面条件，区分启动、打包和纯文档验证 |
| 原根 AGENTS 第 32 行：“full manifest topology”；`scripts/run_pytest.py:23` 与 `pyproject.toml:85` | 当前入口直接调用 pytest，未见 manifest 拓扑编排；该表述与实际入口不符 | 去掉旧架构称谓，保留全部常用命令，不声称删掉测试能力 |
| storage AGENTS 原第 9–10 行要求新增迁移边及推进版本，Scope 却覆盖普通 repository 修改 | 缺少触发条件，可能为查询修改制造迁移 | storage AGENTS 第 9–10、15 行只在持久化契约需要迁移或 bootstrap 变化时要求相应步骤 |
| agent AGENTS 原第 27–30 行要求配套 LLM、storage、UI 路线 | 容易把局部修改扩大为所有跨层验证 | agent AGENTS 第 27 行只纳入受影响契约的路线 |
| 全局 AGENTS 第 11 行要求多种推理及图，第 20、23 行又要求不过度、考虑 ROI | 图与流程的适用条件不清 | 根 AGENTS 第 48 行补充按问题复杂度采用，无全任务子 agent 或多模型前置要求 |

保留了语言、Sir 称呼、提交授权、项目地图、版本和命令、legacy ml 边界以及发布门禁。局部 UI 的 splash/Windows 绘制约束是具体路径的历史故障防线（`src/xenix/ui/AGENTS.md:16`、`:20`），不是全局 Skill 流程，未因篇幅删除。storage 不可重写已部署迁移的约束仍保留。LLM 与 Agent 的 provider 数据边界、benchmark 的隔离、预算、显式 live 验收要求及 subject/Judge 模型规则均未改动（`tests/e2e/agent_harness/AGENTS.md:13` 起）。

## 仓库外建议：全局 AGENTS.md（未应用）

目标：`C:/Users/yyh/.codex/AGENTS.md`。以下 diff 保留独有偏好，只明确授权语义、流程适用条件和已有测试覆盖的优先级；不改变 Sol 专属偏好。

```diff
@@
- Modifying source code requires user approval (exploration, investigation, experiment, spiking, task packet are exceptions).
+ A user request to implement, fix, or optimize a defined target is approval for necessary source changes within that scope; do not request the same approval again. Explanation, review, and diagnosis do not authorize production fixes. Exploration, investigation, experiments, spikes, and task packets remain exceptions to separate source approval, but must not silently become production changes.
+ Complete authorized implementation with proportionate verification and a result report. Stop at a plan only when planning was requested or a concrete blocker prevents further dependent work; continue independent authorized work when possible.
+ Source-change approval does not itself authorize deployment, publication, sending messages, credential access or disclosure, or important-data deletion. Respect authorization for each action and platform permission boundaries.
@@
- Prefer thinking from first principles, leverage multiple reasoning methods (inductive/deductive, etc.), make use of topology, sequence diagram to analyze problem.
+ Prefer first-principles reasoning. Use additional reasoning methods, topology, or sequence diagrams when dependencies, ordering, or competing explanations make them useful; scale the workflow to the task.
@@
- Add tests for realistic observable regressions, non-trivial invariants or boundaries, and concrete bugs. Code changing or coverage increasing is not sufficient justification by itself.
+ Add tests when existing coverage does not adequately protect a realistic observable regression, non-trivial invariant or boundary, or concrete bug. Code changing or coverage increasing is not sufficient justification by itself.
```

需要保留并由 Sir 决定的疑问：全局第 39–43 行的 Sol 专属规则禁止所有 safety/security 审查，又禁止把 fail-closed/fail-fast 问题升级给用户。它们未区分“无任务依据的安全扩展”与“用户明确要求的审查或确实影响授权/数据语义的选择”，后者与全局第 4 行的实质风险询问条件存在张力。这是明确的模型偏好，不能擅自删掉或改成相反含义。本次原样保留；若想表达的只是防止无依据扩展，可另行批准限定为“未请求且无具体证据的安全审查”，同时保留真实权限边界。本次未发现 AGENTS 中要求把日常工作路由到其他模型的规则，不据此扫描模型配置。

## 仓库外建议：OpenAI Docs Skill（未应用）

目标：`C:/Users/yyh/.codex/skills/.system/openai-docs/SKILL.md:12`、`:14`。其“before ... inspecting local or repository files”与本次用户明确要求先读取本地规则的顺序冲突；用户要求优先，因此本次先本地检查，再通过官方文档核实继承机制。建议只增加本地审计例外，不取消实时产品事实的官方来源要求。

```diff
@@
- **Only exception:** An explicitly requested, genuinely broad, cross-topic Codex setup, orientation, or system-map synthesis may use the manual first when shell execution and an allowed temporary cache are available. A specific Codex feature, setting, command, error, model, or requested citation remains docs-first. Mixed Chat/Work/Codex comparisons are official documentation questions, not manual-first Codex requests.
+ **Exceptions:** When the user requests an audit of local instructions or configuration, inspect the explicitly scoped local evidence first, then consult official documentation for discovery, precedence, or other product behavior that needs verification. Do not read credentials, session records, or caches merely to establish local instruction scope. An explicitly requested, genuinely broad, cross-topic Codex setup, orientation, or system-map synthesis may use the manual first when shell execution and an allowed temporary cache are available. Other specific Codex feature, setting, command, error, model, or citation questions remain docs-first. Mixed Chat/Work/Codex comparisons remain official documentation questions.
```

没有扫描其他 Skills。`CONTRIBUTING.md:5` 的 `svc lookup` 指引未指定可读取的 Skill 文件；根规则已限定为任务相关时读取参考，不将其当作每次强制环境搭建或阻塞条件。本次不判断该外部工具是否废弃，也不移除该指引。

## 验证范围

仅修改三个 AGENTS.md，并新增本检查记录。采用针对这些文件的 diff 空白检查、引用目标存在性检查和规则复核，不运行与文档修改无关的测试、smoke、打包或付费 benchmark。不修改、暂存或提交其他已有或并行产生的源码改动。

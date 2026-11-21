# 2026-11 可维护性维护轮次

- **Objective**: 在不改变产品行为的前提下，拆分剩余 monolith、修正审计发现的坏味道与文档漂移、让离线测试组合在非 Windows 开发机可运行、补强诊断与类型检查。
- **Guardrails**: 默认行为等价；迁移边冻结；`ml/` 旧脚本不动；产品语义分歧（见「待决」）不在本轮擅自改变；用户授权自主推进与自由提交，推广仍走 develop → main PR。
- **Verification**: 每个切片在 macOS 上 `pdm run check` 与受影响的 `pdm run test` 选择通过；集成分支最终跑全量离线组合；Windows 打包与 native UI smoke 由 Native CI 在 PR 上证明。
- **Current Truth**: 集成分支 `maint/maintainability`（基于 origin/develop e87f138）。切片由 Codex worker 在 `~/Development/.worktrees/xenix-maint-*/xenix` 独立完成，orchestrator 审查后合入。

## 基线（macOS arm64，b5888e6）

- `pdm run check` 通过。
- `pdm run test`：227 passed / 97 errors / 132s；97 个 error 全部是 tests/ui 在非 Windows 上无法解析声明字体 Segoe UI。
- 修复前 `pdm run prepare` 在非 Windows 上直接失败（硬编码 `lrelease.exe`），已由 b5888e6 修正。

## 切片

| ID | 内容 | 分支 |
| --- | --- | --- |
| S1 | 拆分 `services/ml_service.py`：列角色绑定、Apply 输入、训练输入准备 | `maint/split-ml` |
| S2 | `services/knowledge_pipeline.py` 转为按阶段拆分的包 | `maint/split-knowledge` |
| T1 | UI 契约测试的字体降级、测试 DX | `maint/test-portability` |
| A1 | 只读审计：架构坏味道、文档漂移、工程化（报告未跟踪，结论摘入本 packet） | — |
| D1 | 文档漂移 B1–B6/B9、VS Code 跨平台、打包与环境自检说明 | `maint/docs` |
| X1 | 诊断包健壮性与日志覆盖、strict mypy 扩面、私有死代码 | `maint/dx` |

## 审计遗留（后续切片候选）

- 审计中心列表在切片前全量读取与投影（`limit=1` 投影 2,000 条），UI 每 2 秒刷新。
- Knowledge handler 直接改写调度 `JobRow`；恢复写入应收归 `JobScheduler`。
- 当前会话任务列表仍扫描全局 Knowledge 三表。
- Knowledge 派生/导入、LLM Conversation 的 pending 替换仍有直接 Session 操作（排除 storage/ 共 64 处）。
- 审计解读写入通过私有成员借用 `AuditQueryService` 的投影。
- 过期异步读取丢失内部异常，不进日志。

## 待决（需所有者判断，本轮不改语义）

- B7：任务中心「集中呈现日志」的承诺范围——当前只有 ML 日志，Knowledge 导入日志仍由 Knowledge Workspace 打开。
- B8：`audit.inspect` 查看对象是否应记为本会话引用（当前代码与测试保留该行为）。

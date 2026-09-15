# 工具依赖拓扑与边界审查

- **Objective**: 在注册与暴露解耦、参数解析失败可恢复的当前工作区上，审查工具的装配、发现、执行、会话持久化和 UI 投影是否具有合理且唯一的职责归属。
- **Guardrails**: 用户已授权四项修正，包括 tooling 拆分；保留已有修改，不添加自动化测试、不提交、不运行付费 benchmark。
- **Verification**: 已有服务测试、全量离线组合、静态检查、隔离桌面及打包 smoke；手工探针验证导入依赖、同回复资源读取、注册与 schema 投影独立，以及参数解析失败的反馈、持久化和修复。
- **Current Truth**: 已删除 Skill 读取前置条件、旧领域 Registry 执行入口与 Lazy 包装；tooling 拆为协议、schema 和执行模块，LLM 包导出不再预加载执行实现；所有调用方统一 typed 注册；15 项业务定义保持一致；25 项相关测试、303 项全量离线测试、静态检查、隔离桌面、Windows 打包及打包 smoke 全部通过，benchmark 仅收集未付费运行。
- **Next Step**: 等待用户审阅本轮实现；工作区未提交，既有不相关修改保持原样。

## Supporting Material

- [依赖拓扑、证据和建议](review.md)
- [Skill 资源读取离线探针结果](skill-resource-probe.json)
- [实现后拓扑与设计归属](../../docs/30-unit-tdd/agent-tools.md)
- [实现后手工探针](implementation-probe.json)
- [参数解析失败恢复复核](argument-json-recovery-probe.json)
- [未暴露工具调用与错误恢复复核](hidden-tool-recovery-probe.json)
- [命令、结果与源码摘要](verification.json)
- 审查基线：HEAD `d7bbe8dcd1789a582ec43cbb25e9034523a294ed` 加当前未提交修改；行号指向本轮检查时的工作区。

## 验证结果

- `pdm run test`：303 项通过，177.65 秒；324 条既有 NumPy/joblib 警告；现有相关测试仅迁移调用入口，没有新增或删除测试函数。
- `pdm run check`、`pdm run smoke --isolated` 和 benchmark 默认 4 项用例收集均通过。
- `pdm run package --dist-dir dist/tool-boundary-review` 与对应 `smoke-package` 均通过；包内确认收集新协议/schema/执行模块及 Conversation、Provider、messages，旧 tooling 模块不再存在。
- 手工探针验证了直接与同回复 reference/asset 读取、缺失资源失败后的修正、指导历史重载、消息/协议导入隔离、执行不依赖 schema 投影，以及 14 种普通/流式参数恢复场景；未暴露工具通过别名调用成功，未知工具和错误类型参数仍返回可修复的失败结果。
- 删除不再直接使用的 jsonschema 声明和 types-jsonschema 类型依赖，锁文件没有升级其他包；jsonschema 仍作为其他库的传递依赖保留。
- 证据界限：没有运行新一轮真实模型 benchmark，因此本次结果不代表所有业务用例已通过。

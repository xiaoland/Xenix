# 持久化整数业务身份

- **Objective**: Xenix 拥有的持久业务对象直接使用 SQLite 分配的整数 ID，服务、工具、会话、UI 和存储引用一致。
- **Guardrails**: 用户已授权实施；用户已明确授权提交；保留现有诊断文档和运行时数据；Provider 标识、模型键、内容指纹及临时文件名不属于业务主键；不新增回归测试或 benchmark 自动化测试；目标扩张、解释计算、工具和 Skill 上下文精简后续独立处理。
- **Verification**: `pdm run test -q` 307 项通过；收尾的 Conversation 空值边界修正后，`tests/agent tests/llm` 22 项通过；`pdm run check` 与 `pdm run smoke --isolated` 通过。Headless/Headed 默认题库分别收集 4 项，全目录收集 24 项，未调用付费 Provider。没有新增测试文件或 benchmark 自动化测试。
- **Current Truth**: 已实现全库整数序列，贯通 21 张业务表、服务、Tool 参数、Worker 请求、会话、UI 与 benchmark 消费边界。主键在 flush 时分配，需要提前发布的对象先提交预约；保留空号，删除不复用。Dataset derivation 复用 Dataset ID，分页结果复用 ToolCall ID。
- **Next Step**: 本批实现及验收完成，按用户指令整理提交；后续单独处理工具/Skill/系统提示词的上下文负担，任务目标扩张与解释计算另行讨论。

## 决策与影响

采用直接持久化整数身份，不引入短名、UUID 别名表或会话内映射。整数在一个 runtime 内唯一；不承诺多 runtime 合并后的全局唯一。Provider call ID、客户端提交键、模型/工具键、安装与运行诊断标识、内容指纹及临时文件名保持各自语义。

旧状态通过前向迁移更新关系、JSON、历史对话引用、Artifact URI、分页句柄与用量关联。ML task/model/apply 目录和 Knowledge canonical 包先复制再发布新数据库引用；原文件保留，不把文件复制误称为完整回滚。知识库 Unit 取得整数 ID，旧向量投影失效并由正常服务重建。外部复制的旧 UUID 链接不提供兼容别名。

排查旧模型时发现 Dataset snapshot 的 hash 参与分组抽样，因此保留历史 `sampling_fingerprint`，避免仅因身份改写而改变原评估划分；它不承担对象查找。旧文本模型的资源引用同步改成整数，保留词表、权重和历史准备指纹。

详细设计归属 [Unit TDD](../../docs/30-unit-tdd/persistent-identity.md)，跨单元契约和升级注意事项分别更新在 Storage/Artifact/Knowledge Product TDD 与 Deployment。

## 验证证据

[迁移证据](migration-evidence.json) 来自 `.runtime/dev` 的只读备份副本：69 个 Thread、2,459 条 Message、248 个 Dataset、269 个 Artifact、102 个 ML task 和 43 个模型记录全部保留，SQLite 完整性、外键和 ORM 读取通过；知识库 canonical 内容包身份通过，197 条历史用量记录与一份保存的训练抽样指纹保持衔接。原先存在的 42 个 Artifact 文件均仍可定位；其余历史文件缺失没有被伪装成迁移修复。原开发数据库仍为升级前版本，实验未改写它。

[身份与模型证据](identity-evidence.json) 来自一次性离线实验：8 个并发分配者取得 240 个互不重复的 ID；删除并重启后继续递增；含旧字符串资源引用的已训练文本模型完成转换并通过实际 `model.apply` adapter，预测不变，原模型文件字节未变。

本地日志位于 `build/integer-full-final.txt`、`build/integer-conversation-final.txt`、`build/integer-check-final.txt`、`build/integer-smoke-4.txt`、`build/integer-migration-final.txt` 和 `build/integer-identity-spike.txt`；一次性实验脚本留在忽略目录 `build/`，不成为 benchmark 或回归测试基建。

> 阶段归档（2026-09-15）：用户已结束 benchmark 优化及相关失败排查。以下为历史记录，旧 Next Step 不再代表待执行任务；当前工作见 [1.5.0 收尾](../minor-1-5-closeout/packet.md)。

# Harness benchmark 全题库测量

- **目标**：在 `81fb9bb` 的生产 Harness 与 benchmark 上完成全部 24 个现有节点及 4 个核心任务的 confirmation 变体，确认是否完整通过并定位未通过项。
- **授权与边界**：用户明确要求跑完整题库；本轮运行和诊断，不改生产代码、题面、oracle、配置或预算，不新增自动化测试。原始 4 月堂食数据使用用户已提供的本地文件。
- **形态**：单维护者的一次完整测量；按业务标准/对照 11 项、历史 13 项、confirmation 4 项分批管理 invocation 费用，不建立并行 Agent Track。
- **验证口径**：每项保存原报告、配置与版本身份、业务结果、Judge 结果、资源用量和失败原因。按报告策略解释结果，pytest 成功不代表业务通过；不把不同任务合并成能力得分，不把一次 headless 测量称为三次 headless 加一次 headed 的正式验收。
- **当前事实**：全部 28 项执行完成，原始业务判分 22 pass / 6 fail，没有跳过、超时或无法判分。分流 standard 与 confirmation 均通过，分别 14 / 25 轮；原 12 轮截断未再出现。源码和配置保持 `81fb9bb`，报告 dirty=true 仅反映新 packet。共 4,465,592 Subject tokens、187,204 Judge tokens，计量完整。
- **下一步**：用户随后授权的两处 oracle 修复已完成；聚类/商品相似推荐均通过离线原生回放和独立真实复跑，静态检查与题库收集通过，用户已授权提交。三项实际交付/解释问题另行分组诊断；详见 [修复记录](oracle-repair.md)。

运行输出保留在 `build/agent-harness-full-81fb9bb/`；本 packet 保存 [覆盖清单](manifest.json)、[验证结果](verification.md)、[结果索引](results.json) 和 [失败分流](findings.md)。用户已授权将本次记录与两项 oracle 修复整理提交。

## 后续授权：两项 oracle 修复

用户要求先修复聚类和商品相似推荐的误判，授权修改这两个用例及必要的共享交付读取，不改生产 Harness、题面、fixture、业务真值或其他失败项，不新增回归测试或 benchmark 自测；验证通过后已授权提交。开始状态的 28 项原始测量保持不变。

State diff：从“扫描所有 Dataset 并要求单一父链，然后对照 Artifact 元数据”改为“通过最终答复中的公开链接读取交付表，再检查原业务要求”；聚类必需列改为包含关系，额外说明列合法，原记录/特征/分群及推荐顺序要求继续生效。两个用例共用轻量的 `linked_tables`；失效链接不给交付，服务或表读取异常向上暴露，未交付的中间结果不能通过。

验证证据：[离线原生回放](oracle-repair-replay.json)、[真实复跑索引](oracle-repair-live.json)；两个真实用例均 pass，原报告另存 `build/agent-harness-oracle-repair/`，不覆盖先前报告。

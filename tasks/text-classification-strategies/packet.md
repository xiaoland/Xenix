# 文本策略、可复用执行与分组选型证据

- **Objective**: Agent 能选择词、字符片段或已分词文本策略，服务保存并复用该选择；新文本分类训练提供分组交叉验证证据，预测反馈明确词表覆盖不足。
- **Guardrails**: 用户已授权实现这两个问题并沉淀 Agent Tool 原则；不修改 AGENTS.md，不新增自动化回归测试，不改 benchmark 题库或阈值，不提交本轮工作；保留无关诊断改动。
- **Verification**: 三种策略的生产适配器训练、交叉验证、持久化与应用；旧 pickle 形状兼容、数字标签、无有效特征和验证不可用反馈；既有服务生命周期、完整离线测试、静态检查与隔离启动。真实 benchmark 分数独立记录。
- **Current Truth**: 实现与验证完成；三种策略手工验证及旧对象形状、验证不可用场景通过。旧单次留出生命周期测试已更新，删除不再使用的手写预处理/切分副本，原测试函数数量保留。完整离线测试 303 项通过，静态检查、隔离启动及 diff 检查通过；真实分流确认通过，实际交付预测 28/30 正确（93.33%）；Windows 打包与打包后 smoke 通过，新增评估模块存在于 PYZ 清单。
- **Next Step**: 等待用户决定是否提交；后续可讨论 11 次训练/37 轮的决策成本，两项英文错分仍保留为未解决证据。

## Decisions

- 单一 Agent 完成两个相互关联的能力改动，使用一个 packet 加手工证据，无额外任务树。
- 选择权属于 Agent；执行、训练分区内的学习和已声明配方的保存属于 ML 服务。data.transform 的业务清洗是显式前置数据，不自动变成模型内部配方。
- 新训练使用独立分组的折外预测；旧持久化策略仍按原留出语义读取。OOF 证据使用既有评估文件槽位，不引入 migration 或第二套任务生命周期。
- 无法完成的验证返回原因且不给成功子集汇总分数；无已知特征的预测仍保留在结果中并明确标记。
- 低置信度或词表覆盖率不等于准确率，交叉验证用于选型也不等于独立验收；不以新批次 oracle 反向挑选默认策略。

## Supporting Material

- [Agent Tool 设计原则](../../docs/30-unit-tdd/agent-tools.md)、[文本分类 Unit TDD](../../docs/30-unit-tdd/text-classification.md)。
- [三种策略验证](strategy-probes.json)、[兼容与验证不足反馈](compatibility-probes.json)。脚本只供手工执行，不加入自动化测试或 benchmark 题库。
- [发现与结果解释](findings.md)、[真实分流确认报告摘要](live-confirmation.json)。
- 初步原始诊断保留在 [前一诊断 packet](../harness-confirmation-diagnosis/packet.md)。

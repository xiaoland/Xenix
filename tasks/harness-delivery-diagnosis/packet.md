> 阶段归档（2026-09-15）：用户已结束 benchmark 优化及相关失败排查。以下为历史记录，旧 Next Step 不再代表待执行任务；当前工作见 [1.5.0 收尾](../minor-1-5-closeout/packet.md)。

# Harness 交付失败诊断

- **Objective**: 将完整题库中三项实际失败按机制分组，继续定位 system/skill、解释用事实与 Harness 信息接口的根本矛盾；评估业务对象全面使用整数序列的长期方向。
- **Guardrails**: 本轮授权为诊断、离线实验与任务材料；不改生产 Harness、工具、提示词或 benchmark 判分，不增加自动化测试；不将链接损坏或错误业务事实改判为通过。
- **Verification**: 以原始运行报告、源数据、当前代码和可复核的离线实验支撑结论；区分已证实的原因与尚需干预实验验证的改进假设。
- **Current Truth**: 前序两项 oracle 修复已提交为 `a94aa28`；初轮定位只证明了工具事实可见，不能据此把根因归于模型智力；本轮抓取真实请求，完成 6 次固定末端对照与 2 次完整生产路径测量，简单改 skill 首段或 5 份表格外壳未解决错误；主表由工具计算而额外定量解释和泛化业务判断仍被临时推导，是当前最有依据的干预机制；支持业务对象直接使用持久整数 sequence，替代短码映射方向，具体分配/历史转换方案尚待定稿。
- **Next Step**: 围绕明确交付目标与解释用计算事实设计 system/skill 和上下文精简方案；优先减少 skill 目录/activation 冗余，评估输入 schema 的可见性；整数主键需同时处理提前分配的 ToolCall/Dataset 及历史引用，尚未授权生产实现。

## 证据入口

- 完整运行与失败证据：[前序 packet](../harness-benchmark-full-run/packet.md)、[结果账本](../harness-benchmark-full-run/results.json)、[失败摘录](../harness-benchmark-full-run/failure-evidence.json)。
- 本轮只处理 `ml.forecast_validation_v1`、`business.revenue.v1.standard`、`business.revenue.v1.confirmation`；混合主题发现用例仍属单独的判分与产品质量混合问题。
- 诊断结论、优先级和前序判断更正：[findings.md](findings.md)；原生离线重放与独立事实核对：[offline-evidence.json](offline-evidence.json)。
- 本轮进一步定位：[context-findings.md](context-findings.md)、[实验声明](context-experiment.md)、[上下文组成](context-composition.json)、[六次受控采样](context-ablation-results.json)、[两次完整测量](context-live-results.json)。
- 对象 ID 设计判断：[integer-identity-direction.md](integer-identity-direction.md)。

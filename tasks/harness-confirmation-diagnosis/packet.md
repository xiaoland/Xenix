> 阶段归档（2026-09-15）：用户已结束 benchmark 优化及相关失败排查。以下为历史记录，旧 Next Step 不再代表待执行任务；当前工作见 [1.5.0 收尾](../minor-1-5-closeout/packet.md)。

# 补货超时与分流准确率诊断

- **Objective**: 解释完整题库中补货确认变体的 900 秒超时，以及分流确认变体 26/30 的真实交付错误，区分产品能力、Agent 决策与判分责任。
- **Guardrails**: 本轮授权为提交上一轮工作、调查与实验；不修改产品源码，不新增自动化测试，不改变用例、90% 标准或原始判分；独立诊断材料不混入上一轮提交。
- **Verification**: 用原始 trace、当时只读数据库观察、交付表及源码确定失效边界；分流离线重建要与原始切分、六组评估、30 条预测及四条错误概率相符；补货未复现时明确证据缺口。
- **Current Truth**: 上一轮已提交 22c1ccb。分流已复现，根因链为文本表征丢失信息、在同一小留出集上反复选型、交付阶段把低置信度复核当成满足整批准确率；补货已定位到失败 SQL 落库之后、下一次主采样 gateway 之前，但原始阻塞栈不可恢复，两次局部实验未复现挂起。
- **Next Step**: 讨论分流的文本表征与选型证据能力修正；补货下一次局部复现保留活动栈和中断快照，取得具体阻塞点后再修复，不以重跑成功宣称解决。

## Supporting Material

- [发现、因果边界与建议](findings.md)
- [分流原样重建](routing-replay.json)；[固定分组验证与文本表征对照](routing-representation-probes.json)
- [补货证据边界](restock-evidence.json)；[原运行数据库观察](restock-live-observations.json)；[同类 SQL 错误恢复实验](restock-error-replay.json)
- 诊断脚本仅供手工执行：设置 PYTHONPATH 为 src 与仓库根目录后使用项目 Python 运行本目录的 replay_routing.py、probe_routing_representation.py、replay_restock_failure.py；diagnose_restock_live.py 会调用真实 Provider，输出至 build/restock-confirmation-diagnosis/；collect_evidence.py 汇总已有本地证据。

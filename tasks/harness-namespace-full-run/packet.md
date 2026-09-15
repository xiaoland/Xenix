# 工具目录解耦后的完整 benchmark

- **目标**：重跑上次完整覆盖的 28 项，检查旧失败、成功项资源变化及新回归，判断命名空间工具激活后的实际交付表现。
- **授权与边界**：用户授权提交已完成改动、运行完整题库，并允许先处理有证据的高价值问题；既有改动已提交为 d7bbe8d。本轮另外将预处理 worker 的 Python 堆栈从错误正文移至异常附注，日志保留完整诊断；该小修复暂未提交。题面、oracle、Judge、Skill 正文、模型配置及预算保持不变，不新增自动化测试。
- **形态**：单维护者、一次完整测量；按历史一致的 business / legacy / confirmation 三个 invocation 组织费用，最多两个并行，不比较墙钟性能。使用清单、结果索引和必要的失败摘录作为本 packet 的证据，不建立额外 Track 或 Agent。
- **验证口径**：每项一次新会话，保存全部尝试；按正式报告策略判分，并复核失败与可疑通过的实际交付，不把 pytest 成功当作业务通过。与旧完整运行和最近四项生产测量分别比较，不混入 G0/G1 等消融 arm。一次 headless 运行不等于正式重复验收。
- **完成事实**：2026-09-14 13:06–14:01（Asia/Shanghai）执行全部 28 项，无跳过、无重复挑选；正式策略为 15 pass、12 fail、1 partial。运行前后源码和 case 指纹无变化。已有 25 项 Agent/LLM/UI 验证与 isolated smoke 通过；worker 小修复另经 17 项现有服务测试、check 和真实 DuckDB 错误投影核验。
- **诊断结论**：9 项失败被旧 oracle 整数 ID 问题挡住，未据此直接改判；另外分别发生未暴露工具导致会话中止、补货确认超时、分流确认准确率 86.7% 不足。图表 partial 有错误占比标签，收入/补货机器 pass 也出现 Judge 漏判。最近四项生产基线对比没有整体成本改善。
- **后续目标**：本轮测量与分流完成；新发现的修复尚未实施，先处理工具调用恢复边界与旧 oracle 的公开交付读取，再处理分组切分、批量训练反馈和清洗元数据。目标扩张及解释缺少计算支持仍按先前约定专项处理。

执行清单、配置和源文件指纹见 [manifest.json](manifest.json)。原始报告与日志在 build/agent-harness-namespace-d7bbe8d/；该目录的 settings 子目录包含私有配置，仅保存于忽略目录。所有运行使用生产 Harness 配额和 benchmark 既有外部预算。

全量历史基线为 81fb9bb，早于整数 ID、提示词与工具参数简化；即使配置与任务匹配，差异也只能解释为累计改进，不能全部归功于此次 namespace 激活。最近四个生产候选的结果另作更近的比较，逐项报告身份比较通过；完整覆盖、输入指纹和报告摘要核验见 [verification.json](verification.json)。

完整逐项结果见 [comparison.md](comparison.md)，具体证据、限制与下一轮优先级见 [findings.md](findings.md)。已观察 Subject tokens 5,776,793、Judge tokens 213,814；未暴露工具中止和超时使 Subject 用量不完整，不能视为完整费用。原始 pytest 汇总为 business 1 failed/10 passed、legacy 13 passed、confirmation 1 failed/3 passed；pytest 的成功是运行与存证成功，不能替代报告策略的业务判分。

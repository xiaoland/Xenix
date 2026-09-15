# 全题库运行结果（2026-09-13）

在 `81fb9bb` 上完成一次完整 headless 测量：24 个显式目录节点（4 个代表任务、7 个单条件对照、13 个历史题）加 4 个 confirmation，合计 28 项；每项仅执行一次，无重试选优、遗漏、跳过或追加付费测量。

原报告策略结果为 **22 pass、6 fail、0 partial、0 unscored**；28 项均 completed，全部报告成功持久化，无 wall timeout、invocation 停止或费用计量缺失。这里是题库执行计数，不是跨任务加权能力分数，也未完成三次 headless 加一次 headed 的正式验收。

Subject 为 `deepseek/deepseek-v4-flash`，Judge 为 `deepseek/deepseek-v4-pro`；运行前后显式 Subject、Embedding、Judge 配置文件哈希一致，28 份报告的 commit、runtime、effective settings 身份一致。报告 dirty=true 来自新建本任务 packet；生产源码、题面与 oracle 未改。

## 批次与资源

| 批次 | 项数 | 通过 | 未通过 | Subject tokens | pytest 执行结果 |
| --- | ---: | ---: | ---: | ---: | --- |
| business | 11 | 10 | 1 | 1,030,268 | 11 passed，1403.80 秒 |
| legacy | 13 | 9 | 4 | 2,060,059 | 13 passed / 11 deselected，1254.54 秒 |
| confirmation | 4 | 3 | 1 | 1,375,265 | 4 passed，761.86 秒 |

三批并发、各自使用隔离运行目录和原有每 invocation 4,000,000-token 门槛；每批实际消耗均未触及门槛，没有修改预算。共 245 轮、4,465,592 Subject tokens，Judge 另计 187,204 tokens；费用计量完整。pytest 的 passed 只代表执行完成，因此不能将三批 exit 0 解读为 28 项业务通过。

## 未通过项结论

| 用例 | 分流 | 已有证据 |
| --- | --- | --- |
| 双客群聚类 | 明确 oracle 误判 | 正确结果因两列补充诊断被精确列集合拒绝；原 SQL 离线重放证实。 |
| 商品相似推荐 | 明确 oracle 误判 | 正确的内联 apply 结果被单一数据集父链筛选排除；原生回放证实。 |
| 预测验证 | 实际交付失败 | 最终预测链接 ID 被改错一个字符，预测表与回测检查通过。 |
| 月结 standard | 实际解释矛盾 | 表格正确，解释把东西区退款比较说反；Judge 总判 fail，但分维度均为 2，需保留这一判分解释性问题。 |
| 月结 confirmation | 实际解释矛盾 | 取消订单区域/数量及整单退款表述与源记录不符。 |
| 主题发现 | 混合，需继续核对 | oracle 限定 LDA 格式；替代交付仅内联评估、未链接原生报告；两次分类训练被分组留出约束拒绝后改走检索。 |

详细依据、诊断局限与修复方向见 [失败分流](findings.md)。误判诊断没有改写原始 fail，也没有替代公开交付的重新验收。

## 分流修复的本版本证据

standard：两请求共 14 轮、321,108 tokens、139.975 秒，结构检查和 Judge 均 pass。confirmation：首请求 20 轮 / 780,463 tokens，第二请求 5 轮 / 358,246 tokens，合计 25 轮 / 1,138,709 tokens / 246.710 秒，新批正确率 28/30（93.33%），保存与复用检查及 Judge 全部通过。这证明先前共享十二轮的截断在这两次真实运行没有再发生；仍不是稳定性或正式重复验收结论。

## 各项原始结果

| case_id / 原报告 | 判分 | Judge | 轮次 | Subject tokens |
| --- | --- | --- | ---: | ---: |
| [business.campaign.v1.contact_interval](../../build/agent-harness-full-81fb9bb/business/business.campaign.v1.contact_interval-deepseek-deepseek-v4-flash-d2870d26ba2f4aafabf918323990d71e.json) | pass | pass | 6 | 63,565 |
| [business.campaign.v1.spending_threshold](../../build/agent-harness-full-81fb9bb/business/business.campaign.v1.spending_threshold-deepseek-deepseek-v4-flash-ae86cf812d2b469eb18ba5311cfd5f24.json) | pass | pass | 5 | 48,526 |
| [business.campaign.v1.standard](../../build/agent-harness-full-81fb9bb/business/business.campaign.v1.standard-deepseek-deepseek-v4-flash-e14d2bf8b79a4f33abf2a0768e255eee.json) | pass | pass | 6 | 55,825 |
| [business.restock.v1.arrival_earlier](../../build/agent-harness-full-81fb9bb/business/business.restock.v1.arrival_earlier-deepseek-deepseek-v4-flash-eb88e22a350044feaa897108b5d86748.json) | pass | pass | 6 | 59,843 |
| [business.restock.v1.budget_tight](../../build/agent-harness-full-81fb9bb/business/business.restock.v1.budget_tight-deepseek-deepseek-v4-flash-d23bbcfffa3a4faf8ff404f6c9fb10c4.json) | pass | pass | 7 | 96,371 |
| [business.restock.v1.margin_higher](../../build/agent-harness-full-81fb9bb/business/business.restock.v1.margin_higher-deepseek-deepseek-v4-flash-3ec6f30ef2d148ea88c8f78ed5582814.json) | pass | pass | 5 | 46,527 |
| [business.restock.v1.margin_lower](../../build/agent-harness-full-81fb9bb/business/business.restock.v1.margin_lower-deepseek-deepseek-v4-flash-ba8743e2c0f849c39153e40e99f639d2.json) | pass | pass | 5 | 50,880 |
| [business.restock.v1.no_purchase](../../build/agent-harness-full-81fb9bb/business/business.restock.v1.no_purchase-deepseek-deepseek-v4-flash-d6e7cea0afd443de99ff84704e4c96e8.json) | pass | pass | 4 | 27,190 |
| [business.restock.v1.standard](../../build/agent-harness-full-81fb9bb/business/business.restock.v1.standard-deepseek-deepseek-v4-flash-7f14e3d313084024adf79f7dc055b715.json) | pass | pass | 8 | 108,936 |
| [business.revenue.v1.standard](../../build/agent-harness-full-81fb9bb/business/business.revenue.v1.standard-deepseek-deepseek-v4-flash-f5c24ab1b83c4e3b8a16c71828887ddf.json) | fail | fail | 11 | 151,497 |
| [business.routing.v1.standard](../../build/agent-harness-full-81fb9bb/business/business.routing.v1.standard-deepseek-deepseek-v4-flash-fa174f6456c44e1095f950348290048b.json) | pass | pass | 14 | 321,108 |
| [business.campaign.v1.confirmation](../../build/agent-harness-full-81fb9bb/confirmation/business.campaign.v1.confirmation-deepseek-deepseek-v4-flash-69f8cd522863481691723d1b359e1357.json) | pass | pass | 5 | 53,241 |
| [business.restock.v1.confirmation](../../build/agent-harness-full-81fb9bb/confirmation/business.restock.v1.confirmation-deepseek-deepseek-v4-flash-d2debd471c954b8f921f86e6386c052d.json) | pass | pass | 6 | 63,970 |
| [business.revenue.v1.confirmation](../../build/agent-harness-full-81fb9bb/confirmation/business.revenue.v1.confirmation-deepseek-deepseek-v4-flash-12cb3d355e3e4299898a28b90e516917.json) | fail | fail | 9 | 119,345 |
| [business.routing.v1.confirmation](../../build/agent-harness-full-81fb9bb/confirmation/business.routing.v1.confirmation-deepseek-deepseek-v4-flash-bbfe4b759b8d4afaaf2e39c427bf3dd5.json) | pass | pass | 25 | 1,138,709 |
| [analysis.revenue_by_region_chart](../../build/agent-harness-full-81fb9bb/legacy/analysis.revenue_by_region_chart-deepseek-deepseek-v4-flash-51e6a8255abf41bcbbf211dcc2357d32.json) | pass | pass | 5 | 34,171 |
| [cleaning.april_dine_in_sales](../../build/agent-harness-full-81fb9bb/legacy/cleaning.april_dine_in_sales-deepseek-deepseek-v4-flash-a6e6af3ab62f4669a9aab604bc0111ef.json) | pass | not_requested | 8 | 125,221 |
| [knowledge.rainy_season_restock](../../build/agent-harness-full-81fb9bb/legacy/knowledge.rainy_season_restock-deepseek-deepseek-v4-flash-38dc544b12594e4dbf20ece48a2456fd.json) | pass | not_requested | 4 | 32,705 |
| [ml.cleaning_service_tickets](../../build/agent-harness-full-81fb9bb/legacy/ml.cleaning_service_tickets-deepseek-deepseek-v4-flash-f92c9348bff8439eb954f904700eef1c.json) | pass | not_requested | 7 | 68,637 |
| [ml.cluster_selection_v1](../../build/agent-harness-full-81fb9bb/legacy/ml.cluster_selection_v1-deepseek-deepseek-v4-flash-db3720ebbf844318a7bf63d8cabd44d8.json) | pass | pass | 10 | 150,185 |
| [ml.clustering_two_segments](../../build/agent-harness-full-81fb9bb/legacy/ml.clustering_two_segments-deepseek-deepseek-v4-flash-665017a6be6449e0bd6acac0a555a34b.json) | fail | not_requested | 5 | 44,099 |
| [ml.forecast_validation_v1](../../build/agent-harness-full-81fb9bb/legacy/ml.forecast_validation_v1-deepseek-deepseek-v4-flash-af055598eeec4be09bd426ed20cbf823.json) | fail | blocked | 16 | 315,972 |
| [ml.forecasting_seasonal_naive_transform](../../build/agent-harness-full-81fb9bb/legacy/ml.forecasting_seasonal_naive_transform-deepseek-deepseek-v4-flash-05cdf64aae15433eae5bebb75f05767a.json) | pass | not_requested | 9 | 113,562 |
| [ml.recommendation_item_similarity](../../build/agent-harness-full-81fb9bb/legacy/ml.recommendation_item_similarity-deepseek-deepseek-v4-flash-1b1865c5b9e2400396066ae98c47a6cc.json) | fail | not_requested | 8 | 79,957 |
| [ml.recommendation_ranking_v1](../../build/agent-harness-full-81fb9bb/legacy/ml.recommendation_ranking_v1-deepseek-deepseek-v4-flash-e6bea0f2f19b46dda474e20dca6a2594.json) | pass | pass | 12 | 182,092 |
| [ml.text_grouped_classification_v1](../../build/agent-harness-full-81fb9bb/legacy/ml.text_grouped_classification_v1-deepseek-deepseek-v4-flash-de77c0c12a13496daf1f8c9714bbb0e6.json) | pass | pass | 13 | 231,688 |
| [ml.text_keyword_frequency](../../build/agent-harness-full-81fb9bb/legacy/ml.text_keyword_frequency-deepseek-deepseek-v4-flash-8821e3fd139c410f8fbb05c3ebf57329.json) | pass | not_requested | 7 | 63,303 |
| [ml.text_topic_discovery_v1](../../build/agent-harness-full-81fb9bb/legacy/ml.text_topic_discovery_v1-deepseek-deepseek-v4-flash-e1fd7cd8069641a0881c0ff606f64184.json) | fail | blocked | 19 | 618,467 |

[机器可读结果索引](results.json) 保存每次报告路径、SHA256、身份、结构检查、Judge、预算与分请求用量；[覆盖清单](manifest.json) 保存具体节点和配置文件哈希。完整原报告及 CLI 日志在 `build/agent-harness-full-81fb9bb/`，未覆盖上轮单例验证。

本轮仅新增 task packet 与一次性诊断证据，没有新增 benchmark 自动化测试、回归测试或修改源码；未重新运行已在该实现通过且未受影响的服务测试。

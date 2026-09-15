# 完整 benchmark 比较

本文件保留正式报告策略的机器判分；人工发现的漏判和旧 oracle 阻塞见 [findings.md](findings.md)，不擅自覆盖为新的 pass。

覆盖 28 / 28 项，机器结果：15 pass，12 fail，1 partial。

已观察 Subject tokens 为 5,776,793，Judge tokens 为 213,814；未暴露工具中止与补货确认超时的 usage 不完整，Subject 完整总量未知。已记录 320 次采样轮次、31 次失败 ToolResult；Provider 提前中止没有形成 ToolResult，超时项也未保留完整调用结果，不能把这些计数当作无遗漏总量。

## 比较边界

每项一次 headless 样本，无重跑挑选；没有新增 benchmark 自动化测试。旧完整基线 81fb9bb 的原始 22/28 结果保持不变，随后修复的两群聚类和商品相似推荐另有通过记录，本次再次通过不能归为目录解耦带来的新能力。全量基线早于整数 ID、提示词和参数简化；差异只能作为累计变化观察。

Subject、Embedding、Judge 的配置摘要与旧完整运行相同。report policy 对逐项比较均允许解释，但不构成正式重复验收，也不证明统计上稳定的提升；不比较并发执行下的墙钟时间。tokens 包含缓存输入，不等于实际账单金额。

## 最近四项生产测量

基线仅取 implementation-results.json 指定的 layered 生产候选，不混入 G0/G1/G2 消融 arm。

| 标准题 | 机器结果 | 轮次（前 → 后） | Subject tokens（前 → 后） | 变化 | 工具错误（前 → 后） |
| --- | --- | ---: | ---: | ---: | ---: |
| 活动名单 | pass → pass | 5 → 6 | 34,753 → 45,502 | +30.9% | 0 → 0 |
| 补货 | pass → pass | 8 → 12 | 69,585 → 135,378 | +94.6% | 0 → 1 |
| 收入 | pass → pass | 10 → 10 | 109,824 → 107,276 | -2.3% | 1 → 0 |
| 分流 | pass → pass | 20 → 22 | 484,886 → 689,440 | +42.2% | 0 → 0 |

四题没有整体成本改善。收入只降低约 2.3%，且首答合计仍有 Judge 漏判；补货也存在解释漏判。分流的训练调用从 2 次增至 7 次，数据查询从 9 次增至 13 次，工具错误均为零，不能把增加的消耗统称为工具错误重试。

新目录在这四题的首轮输入均增加 886 tokens。该值是整个初始发现界面的净变化，不能全算作 Skill 正文，也不等于每轮固定多出同一数量；后续已激活工具会退出简目录。这是 discoverability 的实测成本，应与减少盲目查找/加载的收益一起比较，而不是把解耦本身当成 token 优化。

## 原完整基线中未通过的六项

| 用例 | 旧机器结果 | 当前机器结果 |
| --- | --- | --- |
| business.revenue.v1.standard | fail | pass |
| business.revenue.v1.confirmation | fail | pass |
| ml.clustering_two_segments | fail | pass |
| ml.forecast_validation_v1 | fail | fail |
| ml.recommendation_item_similarity | fail | pass |
| ml.text_topic_discovery_v1 | fail | fail |

当前失败的预测验证和主题发现先被旧整数父链判题挡住；预测存在整数公开链接不代表其全部内容已重新验收，主题发现另有隐藏输出格式和分组训练问题。收入的机器结果须结合逐轮人工复核，不能只根据 verdict 宣称旧问题全部消失。

## 逐项原始比较

| 用例 | 旧 → 新判分 | 轮次 | Subject tokens | token 变化 |
| --- | --- | ---: | ---: | ---: |
| business.campaign.v1.contact_interval | pass → pass | 6 → 6 | 63,565 → 44,255 | -30.4% |
| business.campaign.v1.spending_threshold | pass → pass | 5 → 5 | 48,526 → 34,717 | -28.5% |
| business.campaign.v1.standard | pass → pass | 6 → 6 | 55,825 → 45,502 | -18.5% |
| business.restock.v1.arrival_earlier | pass → pass | 6 → 5 | 59,843 → 37,032 | -38.1% |
| business.restock.v1.budget_tight | pass → pass | 7 → 9 | 96,371 → 89,291 | -7.3% |
| business.restock.v1.margin_higher | pass → fail | 5 → 1 | 46,527 → 未知 | 未知 |
| business.restock.v1.margin_lower | pass → pass | 5 → 12 | 50,880 → 170,675 | +235.4% |
| business.restock.v1.no_purchase | pass → pass | 4 → 10 | 27,190 → 106,617 | +292.1% |
| business.restock.v1.standard | pass → pass | 8 → 12 | 108,936 → 135,378 | +24.3% |
| business.revenue.v1.standard | fail → pass | 11 → 10 | 151,497 → 107,276 | -29.2% |
| business.routing.v1.standard | pass → pass | 14 → 22 | 321,108 → 689,440 | +114.7% |
| business.campaign.v1.confirmation | pass → pass | 5 → 6 | 53,241 → 51,954 | -2.4% |
| business.restock.v1.confirmation | pass → fail | 6 → 5 | 63,970 → 未知 | 未知 |
| business.revenue.v1.confirmation | fail → pass | 9 → 14 | 119,345 → 180,973 | +51.6% |
| business.routing.v1.confirmation | pass → fail | 25 → 23 | 1,138,709 → 559,133 | -50.9% |
| analysis.revenue_by_region_chart | pass → partial | 5 → 5 | 34,171 → 19,850 | -41.9% |
| cleaning.april_dine_in_sales | pass → fail | 8 → 23 | 125,221 → 777,435 | +520.9% |
| knowledge.rainy_season_restock | pass → pass | 4 → 4 | 32,705 → 13,825 | -57.7% |
| ml.cleaning_service_tickets | pass → fail | 7 → 10 | 68,637 → 107,886 | +57.2% |
| ml.cluster_selection_v1 | pass → fail | 10 → 17 | 150,185 → 391,837 | +160.9% |
| ml.clustering_two_segments | fail → pass | 5 → 12 | 44,099 → 98,393 | +123.1% |
| ml.forecast_validation_v1 | fail → fail | 16 → 20 | 315,972 → 379,351 | +20.1% |
| ml.forecasting_seasonal_naive_transform | pass → fail | 9 → 6 | 113,562 → 49,108 | -56.8% |
| ml.recommendation_item_similarity | fail → pass | 8 → 10 | 79,957 → 89,477 | +11.9% |
| ml.recommendation_ranking_v1 | pass → fail | 12 → 13 | 182,092 → 230,132 | +26.4% |
| ml.text_grouped_classification_v1 | pass → fail | 13 → 19 | 231,688 → 583,343 | +151.8% |
| ml.text_keyword_frequency | pass → fail | 7 → 7 | 63,303 → 29,075 | -54.1% |
| ml.text_topic_discovery_v1 | fail → fail | 19 → 28 | 618,467 → 729,018 | +17.9% |

旧新机器判分都为 pass 的 11 项中，7 项 tokens 降低、4 项增加；这只是按机器结果选出的描述统计，含已发现的 Judge 漏判，不作为质量等价或因果提升的证据。

原始路径、报告摘要、身份校验、Judge、budget 见 [results.json](results.json) 和 [comparisons.json](comparisons.json)；逐轮回答及失败调用见 [delivery-evidence.json](delivery-evidence.json)。

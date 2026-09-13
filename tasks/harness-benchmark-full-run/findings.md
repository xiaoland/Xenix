# 未通过项分流

本轮不改题面、oracle 或生产 Harness，也不重跑直至通过。下列诊断解释原始失败，结果索引仍保留报告策略给出的原判分；离线回放不是新增 Subject 样本，也不是自动化测试。

## 两个旧 oracle 的误判

- `ml.clustering_two_segments`：`_matches_expected` 要求列集合完全相等，实际 SQL 生成了正确的六条原始记录及 `cluster_id`，另加 `assignment_changed` 和 `normalized_distance_to_centroid`。精确重放报告中的 SQL：原 matcher 拒绝完整表，只选必需列后通过。题面只要求保留原记录并增加群组标签，没有禁止补充列。`public_artifact_linked` 因 dataset 为 None 提前返回，并不是独立证实链接无效。见 [聚类离线证据](clustering-oracle-evidence.json)。
- `ml.recommendation_item_similarity`：实际使用原生训练模型，对内联 `SKU-A` 输入执行 apply；返回的公开链接原样出现在最终答复。相同模型、角色、参数和输入的原生回放产生正确的 SKU-B / SKU-C 两行推荐，现有内容 matcher 通过。该结果的 `derived_from_dataset_id` 合理为 None，而 `ml_task_id` 能关联训练数据；旧 oracle 先要求沿数据集父节点回到原评分表，因此把它排除。FIT 的全商品推荐表又不满足两行条件，最终误报无交付。见 [推荐原生证据](recommendation-oracle-evidence.json)。

上述问题暴露了旧题仍按内部数据表示或生成路径找答案。修正方向应是从用户真正拿到的公开链接验证内容和必要来源，允许补充说明列及合法的内联 apply，不应为通过旧题而强迫 Harness 改用特定工具路径。旧题没有冻结完整导出文件，所以不能把离线回放冒称为已重新完成公开链接验收，也不在本轮覆盖原报告。

用户随后授权修复上述两项：已改为读取最终链接表格，原生离线回放与两个新的真实用例均通过；见 [后续修复记录](oracle-repair.md)。前述全量测量与原失败证据保留原貌。

## 已核实的实际问题

- `ml.forecast_validation_v1`：预测表和时间回测检查通过，`model.apply` 交付 URI 为 `artifact://59137ebae3ed4eb6ac3555e1a271187c`，最终答复写成 `artifact://59137ebae3ed4eb6ac5555e1a271187c`，仅一个字符不同。这是实际链接交付失败；不能通过模糊匹配 oracle 掩盖。Judge 因结构前提失败未执行，不能推断其余解释也通过。后续应从公开引用的生成和渲染接口检查可靠性，而非增加固定工具操作流程。
- `business.revenue.v1.confirmation`：两请求的净回款表和公开交付检查全部通过；Judge 对首请求解释给 0、修订解释给 2，结论 fail。独立查源确认首答称“东区有 2 笔 cancelled 订单”，但 O10 属东区、O20 属南区，东区仅一笔；后续又把 O04 的 11,000 元退款称作整单退款，原订单是 12,000 元。Judge 报告只保存分数和 reason code，没有指出具体句子，因此这些是独立验证到的矛盾，不能冒称是 Judge 的完整推理。见 [交付与解释证据](failure-evidence.json)。
- `business.revenue.v1.standard`：两请求数值和链接检查也全部通过，最终解释却称西区比东区“退款更多”，与其自己交付的 4,400.25 元对 8,600.50 元相反；又称单笔 7,000 / 2,000 元退款足以改变 7,850 元的区域差距。Judge 给 fail / incorrect_business_claim，但两个维度同时给 2，应保留这一分数与总判分不一致的观测，用于后续 rubric 解释性审查；不能仅凭维度满分否认已经核实的原文矛盾。

数值计算正确不保证自然语言说明可靠；这次月结失败没有工具失败证据，不应直接断言是某个 service 的实现缺陷。后续可从答复使用的事实粒度与交付摘要探索改善，保持真实业务矛盾可被判失败。

## 主题发现需要分开审查

`ml.text_topic_discovery_v1` 同时暴露旧 oracle 限制和交付评估缺口。题面要求运营主题、逐条标注、复用和质量评估，没有限定 LDA、概率列或报告 schema；oracle 却要求固定的 LDA 七列和专用评估报告。实际交付是业务命名的主题表与保留的近邻索引，因此不能直接把 assignment_missing 理解为没有标注。最终答复提供内联质量评估，但没有链接原生评估报告，Judge 被结构前提阻断；替代交付是否完整、可靠仍需专门核对，不在本次直接改判通过。

轨迹还显示两次监督分类训练因“每一类必须同时出现在分组后的训练集和留出集”被拒绝，第二次改变显式分组仍未成功；模型随后转用近邻检索并完成交付，合计 19 轮。它是值得追查的训练/评估边界线索，但这次运行没有单独证明样本不可训练，也不能仅根据模型自述断言该约束必需或完全不可满足。完整异常和实际交付摘要见 [失败证据](failure-evidence.json)。

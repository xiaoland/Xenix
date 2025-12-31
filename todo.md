# TODO of Xenix

## 原型功能

第一项功能肯定是：

- 给一组历史数据
- 分成训练组和测试组
- 微调出各个模型效果最佳的参数组合
- 对各个模型在其最佳参数下进行训练并对比效果
- 选择最好的模型，对数据进行批量预测

- [x] 不应该让 pipeline 操作数据库，否则就会硬编码 SQL 或者使用 Sqlalchemy 导致整个应用有两个 Source of Truth
- [ ] test_size: float = 0.2, random_state: int = 42, n_jobs: int = -1
- [x] 重命名“训练”为“调优”，可以自定义 ParamGrid（从 ParamGrid JSON Schema 自动生成表单）
- [ ] 提供 “训练” 操作，这时候可自定义模型参数进行训练，并取得指标（自动调优则是配置 ParamGrid，不再分列）
- [ ] 提供在线 Table 编辑，提供 Features ，可单独预测
- [x] 添加 Work / Project，保存 task （数组）（ Work -> task 链接，task不应该要求 Work ）
- [x] 没有 Upload 阶段，只有 Prepare Data 阶段，进行选择 Dataset -> Features , Target Columns -> 分割训练与测试数据集。
- [x] 对 business/ml 的 interface 还要来一场重构，还有 stdin, stdout 的规范化
- [x] WorkItem 还要记住启用的模型
- [ ] 移除上报 Train Metrics
- [ ] 将 Metrics 铺开，方便横向对比（inline scroll）
- [ ] 一键清除失败任务，删除任务
- [ ] 参数也是 popup 查看（结合 JSON Schema 渲染）
- [ ] 选择 taskId 则 model, params 都选好了，也就可以进入预测

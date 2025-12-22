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
- [ ] running 时显示进度条
- [ ] structured log，前端 deseralize
- [ ] 重命名“训练”为“调优”，可以自定义 ParamGrid（从 ParamGrid JSON Schema 自动生成表单）
- [ ] 提供 “训练” 操作，这时候可自定义模型参数进行训练，并取得指标
- [ ] 提供在线 Table 编辑，提供 Features ，可单独预测

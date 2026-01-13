# TODO of Xenix

## 原型功能

第一项功能肯定是：

- 给一组历史数据
- 分成训练组和测试组
- 微调出各个模型效果最佳的参数组合
- 对各个模型在其最佳参数下进行训练并对比效果
- 选择最好的模型，对数据进行批量预测

- [ ] test_size: float = 0.2, random_state: int = 42, n_jobs: int = -1
- [ ] 提供在线 Table 编辑，提供 Features ，可单独预测（predict_on_file, predict_on_json）
- [ ] 云端部署
  - [ ] 搞个服务器，目前要运行 Python 脚本
  - [ ] model_metadata 是 migration 的一部分，不要在运行时有操作
  - [x] PythonEnv 相关的管理可以移除了，因为云端部署
  - [ ] ModelTuningTable 的模型也应该从数据库获取
  - [ ] i18n 是远程资源，不要打包在里面，不然的话模型的翻译更新很麻烦
  - [x] 添加 users 表
  - [x] CSR
  - [ ] remove AVAILABLE_MODELS constant, use api
- [ ] 超级重构
  - [x] UploadDataset 要支持 Drag
  - [x] ColumnSelector 用回之前的样子
  - [ ] 我还要日志预览
  - [ ] 修复Dataset上传：Dataset upload error: TypeError: Content-Type was not one of "multipart/form-data" or "application/x-www-form-urlencoded"
  - [ ] 没有应用 RFC 7807 Problem Details for HTTP APIs
  - [ ] 增加更多的数据库约束（比如 work_items.dataset_id -> datasets.id)
  - [ ] 手动训练死翘翘
  - [ ] 自动训练又不能修改参数了
  - [ ] TuningStep 不要不停的 poll tasks
  - [ ] 移除对 redis 的依赖，使用 pgsql
- [ ] 计算阿里云Serverless方案的费用
  - 按照当前定价模型和用户画像，会付费的用户的使用频率、数据量是多少

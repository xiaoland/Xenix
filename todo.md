# TODO of Xenix

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
  - [ ] 没有应用 RFC 7807 Problem Details for HTTP APIs
  - [ ] 增加更多的数据库约束（比如 work_items.dataset_id -> datasets.id)
  - [ ] 手动训练死翘翘
  - [ ] 自动训练又不能修改参数了
  - [ ] TuningStep 不要不停的 poll tasks
  - [x] 移除对 redis, bullMQ，使用 pgsql tasks 表即可
- [ ] 计算阿里云Serverless方案的费用
  - 按照当前定价模型和用户画像，会付费的用户的使用频率、数据量是多少
- [ ] 统一日志<https://gemini.google.com/u/1/app/a3f5372ad3492fd2>
- [ ] Simplify API (especially train)
- [ ] schema to shared, frontend also uses Zod

## Frontend

- [ ] 在workItem级别选择 ml-backend deployment，前端默认带 workItem 的 deployment （未来可以允许 task 级别选择）
  - every user has a list of ml backends；完整列表就是官方的加上用户本地的，官方的backend需要计费（task会有字段）
- [ ] 如果是 local path，直接打开，不要下载
- [x] Inline predict 的结果展示不正确
  - targetColumn 不需要 predicted_ (这是 ml-backend 的锅)
  - 多了个 Prediction column
- [ ] Prediction History
- [ ] 橙色为主题色

## Backend

- [ ] 不要区分 fc build

## ML Backend

- [x] Add ml-backend
  - [x] ml-backend does not has adapter, it's pure python script only IO is stdio and file system.(Always save locally, but with base path)
  - [x] backend call ml-backend like local function with adapter
    - 异步调用，结果与状态更新怎么做？全部都存在 Filesystem 里面
- [x] 构建时产出 model_metadata.json 让 backend 读取并自动化推送到数据库
- [ ] 不要马上 Accepted，要先运行5s（如果在运行了就返回 202 Accepted），而且这样 backend 也就不用自己等待了
- [ ] 添加 Brearer 认证保护（ deployment 中配置 brearer column）（不着急，因为禁止了公网访问）
- [ ] Add fc handler 并开启异步任务

## Shared

- [x] 不要构建，直接引用源文件；backend、frontend打包的时候都带上

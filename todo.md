# TODOs of Xenix

## Infrastructure

- [ ] CD
  - [ ] 自动运行数据库迁移
  - [ ] 自动构建层（仅在必要时）
  - [ ] 自动构建应用并部署到 Aliyun FC
  - Fix 20260205
    - ml-backend 的打包结果过大
- [ ] 应用 RFC 7807 Problem Details for HTTP APIs
- [ ] 增加更多的数据库约束（比如 work_items.dataset_id -> datasets.id），配置正确的默认值
- [ ] 把所有的 schema 都移动到 shared 中
- [ ] 添加基于 Pino 的，backend, frontend 通用的可观测性支持（日志与链路追踪）
  - <https://gemini.google.com/u/1/app/a3f5372ad3492fd2>
- [ ] 为 work-item, project 添加基于 createdBy 的权限检查中间件

## Business

### Tasks

- [ ] 任务日志查看

### ML Operations

- [ ] 手动训练
- [ ] 自动训练可以修改 ParamGrid
- [ ] 特殊 http_proxy: frontend

### WorkItem

### Datasets

- [ ] 对于 OSS Dataset ，不显示路径
- [ ] 删除 Dataset 时 OSS 中的文件也要一并删除

## Others

- [ ] 橙色为主题色

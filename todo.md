# TODOs of Xenix

## Infrastructure

- [ ] CD
  - [ ] 自动运行数据库迁移（支持回滚，要备份）
  - [x] 自动构建层（仅在必要时）
  - [x] 自动构建应用并部署到 Aliyun FC
  - Fix
    - [x] ml-backend 的打包结果过大
    - [ ] 层清理不工作
- [ ] 应用 RFC 7807 Problem Details for HTTP APIs
- [ ] 增加更多的数据库约束（比如 work_items.dataset_id -> datasets.id），配置正确的默认值
- [ ] 把所有的 schema 都移动到 shared 中
- [ ] 添加基于 Pino 的，backend, frontend 通用的可观测性支持（日志与链路追踪）
  - <https://gemini.google.com/u/1/app/a3f5372ad3492fd2>
- [ ] 为 work-item, project 添加基于 createdBy 的权限检查中间件

## Business

### Tasks

- [ ] 流式任务日志
  - 可以的话不要再给 PostgreSQl 数据库负担了，考虑到成本问题？
  不过也还需要进一步确认 SLS 之类服务的价格。

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
- [ ] 一键反馈

## FIXMEs

- [ ] 翻译缺漏和错误

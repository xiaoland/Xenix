# Deploy to Aliyun Serverless

充分利用阿里云 Serverless 服务能力来部署 Xenix：

- ESA（边缘安全加速）：部署前端
- FC（函数计算）：部署后端
- OSS（对象存储）：存储上传与产出文件
- RDS PostgreSQL：数据库

## Backend（Aliyun FC）

当前后端部署策略：

- 运行时：`custom.debian12`（叠加官方 Node.js 22 层）
- 启动命令：`./fc-start.sh`
- 依赖来源：自定义 Node.js 依赖层 `xenix-backend-nodejs-deps`
- 函数代码包：仅最小产物（`dist/` + `fc-start.sh` + `s.yaml`）

说明：

- `fc-start.sh` 会在运行时执行 `ln -sf /opt/nodejs/node_modules ./node_modules`，用于让 ESM 入口从当前目录解析 layer 中依赖。
- CI 工作流会构建并发布 layer，再部署最小函数产物，避免将工作区多余文件（特别是 `node_modules`）打进函数代码。

详细流程见：[aliyun-fc.md](./aliyun-fc.md)。

## ML Backend

### 自定义层

目前所需的 [Python 依赖](../../pyproject.toml) ，[公共层](https://github.com/awesome-fc/awesome-layers/blob/main/README.md) 不能满足需求，需要打包自定义层。

运行来获得获得依赖层：

- `pdm export -f requirements --without-hashes -o tmp/requirements.txt`
- `pip install -r tmp/requirements.txt --target ./python --platform manylinux2014_x86_64 --only-binary=:all:`（注意因为 FC 环境是 Debian，在 Windows/MacOS 上构建时要加平台参数）
- `pnpm s cli fc layer publish --code ./my-layer-code --compatible-runtime java8,Java11,custom  --region cn-guangzhou --layer-name xenix-python-dep`

### 挂载 OSS

## Frontend（Aliyun ESA）

1. 添加：

    ```jsonc
    // esa.jsonc
    {
        "name": "xenix",
        "installCommand": "pnpm install",
        "buildCommand": "pnpm run --filter frontend build",
        "assets": {
            "directory": "./dist",
            "notFoundStrategy": "singlePageApplication"
        }
    }
    ```

2. 修改构建信息
    - 根目录：`/packages/frontend`
    - 环境变量
       - `VITE_API_URL`：填写 FC 给的访问地址

3. 添加站点
4. 绑定域名
5. 配置边缘证书

### 配置 OSS

需要在 OSS 的 CORS 策略中添加前端域名，否则会遭遇 `403 Forbidden`。

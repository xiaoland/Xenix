# Deploy to Aliyun Serverless

充分利用阿里云 Serverless 服务的能力来部署：

- ESA（边缘安全加速）：使用 Pages 部署前端
- FC（函数计算）：使用自定义运行时部署后端
- OSS（对象存储）：存储用户上传的、计算得到的数据文件
- RDS PostgreSQL：数据库

## FC

### 难点

- 需要 Node.js 运行时
- 文件上传（body大小的限制）与存放
  - 文件存储在阿里云 OSS 中
  - Python 需要执行的时候
- Python 的执行需要的依赖
- 数据库访问

### 配置层

目前所需的 [Python 依赖](../../pyproject.toml) ，[公共层](https://github.com/awesome-fc/awesome-layers/blob/main/README.md) 不能满足需求，需要打包自定义层。

运行来获得获得依赖层：

- `pdm export -f requirements --without-hashes -o tmp/requirements.txt`
- `pip install -r tmp/requirements.txt --target ./python --platform manylinux2014_x86_64 --only-binary=:all:` （注意因为 FC 环境是 Debian，在 Windows/MacOS 上构建时要加上平台参数）
- `pnpm s cli fc layer publish --code ./my-layer-code --compatible-runtime java8,Java11,custom  --region cn-guangzhou --layer-name xenix-python-dep`

## ESA

1. 添加：

    ```jsonc
    // esa.jsonc
    {
        "name": "xenix",
        "installCommand": "pnpm install",
        "buildCommand": "pnpm run build",
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

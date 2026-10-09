# 提示词自动迭代优化智能体 · 部署版

本目录为可独立运行的生产/演示部署包：**backend/app + 前端构建产物(static) + 启动脚本**。

## 目录结构

```
部署版code/
├── start_all.bat        # 一键启动（Windows）：装依赖→生成.env→启动服务
├── stop_all.bat         # 停止服务
├── nginx.conf           # 生产环境 Nginx 反代示例
└── backend/             # 后端源码 + 前端静态资源
    ├── app/             # FastAPI 应用
    ├── static/          # 前端构建产物（由 frontend/dist 复制而来）
    ├── tests/           # 后端测试
    ├── requirements.txt
    └── .env.example
```

## 快速启动（本地演示）

1. 确保已安装 Python 3.12+，并填写 LLM 密钥：
   - 运行 `start_all.bat`，首次会自动生成 `backend/.env`。
   - 编辑 `backend/.env`，填入 `LLM_BASE_URL`、`LLM_API_KEY`（OpenAI 兼容、国内直连）。
2. 浏览器访问 **http://localhost:8000**，注册账号后即可使用。
3. API 文档：http://localhost:8000/docs

> 单端口模式：前端静态页面由 FastAPI 统一托管（`app/core/static_host.py`），同时支持 SPA history 前端路由，无需额外起前端服务。

## 重新构建前端

若修改了前端代码，需重新构建并同步到 static：

```bat
cd ../01.code/prompt_optimizer/frontend
npm install
npm run build
xcopy dist ..\..\..\..\部署版code\backend\static /E /I /Y
```

构建后会生成 `dist/assets/*.js|css` 与 `index.html`，统一由后端 `/assets` 与 SPA fallback 提供。

## 生产部署（Nginx + HTTPS）

1. 服务器安装 Python 与 Nginx，上传本部署包。
2. 安装依赖与配置 `.env`（替换 JWT 密钥、填 LLM Key、数据库路径）。
3. 用 `nohup`/systemd 后台运行后端：`uvicorn app.main:app --host 127.0.0.1 --port 8000`（内网监听）。
4. 套用 `nginx.conf`，对外 80/443 + 证书，反代到 127.0.0.1:8000。

## 环境变量说明（backend/.env）

| 变量 | 说明 |
|------|------|
| `JWT_SECRET_KEY` | JWT 签名密钥，生产务必替换为随机长字符串 |
| `LLM_BASE_URL` | 大模型 API 地址（OpenAI 兼容） |
| `LLM_API_KEY` | 大模型 API 密钥 |
| `LLM_DEFAULT_MODEL` | 默认模型，如 qwen-plus |
| `DATABASE_URL` | 数据库连接，默认 `sqlite:///./prompt_optimizer.db` |

> 未配置 LLM 时，「登录/任务管理/用例管理」可用；「变体生成/任务执行/评审打分/迭代」类需 LLM 的功能会报错，填写密钥后重启即可。

## 注意事项

- 依据《互联网信息服务深度合成管理规定》，AI 生成内容已在界面显著标识；本系统建议本地化部署。
- 敏感数据（API 密钥）在 `.env`，请勿提交到版本库/公开仓库。
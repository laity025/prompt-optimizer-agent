# 提示词自动迭代优化智能体（Prompt Optimizer Agent）

> 一个基于智能体编排的**提示词自动迭代优化 WebApp**：用户设定优化目标、任务描述、测试用例集与初始提示词，
> 系统通过「**变体生成 → 任务执行 → 质量评估 → 择优迭代**」闭环自动优化提示词，
> 迭代至收敛后输出最优提示词、得分曲线与优化报告。

本项目为「AI 共创」模式下的教学实训案例，交付物包含**可运行代码 + 全套设计文档 + 实训指导书 + RAG 语料库**。

---

## 核心闭环

```
初始提示词
   │
   ├─► ① 变体生成   基于当前最优提示词 + 历史失败案例，生成多个候选变体
   ├─► ② 任务执行   在测试用例集上批量执行变体，支持并行与失败重试
   ├─► ③ 质量评估   自动指标（BLEU / ROUGE / 关键词命中 / 格式校验）+ LLM 评审打分（1–10 + 理由）
   ├─► ④ 择优迭代   加权合成得分，保留版本快照与评分理由，未收敛则回到 ①
   │
   └─► 输出：最优提示词 · 得分曲线 · 版本差异对比 · 优化建议报告
```

达到目标分 / 收敛 / 最大轮次即退出，全程留痕，支持人工冻结与版本回退。

## 功能模块

| 模块 | 关键能力 |
|------|---------|
| ① 优化任务管理 | 任务描述与优化目标、评分标准；用例集录入/导入；内置任务类型模板（文本生成 / 摘要 / 抽取 / 代码生成） |
| ② 变体生成与执行 | 多变体生成、批量执行、并行与重试、实时进度推送 |
| ③ 质量评估 | 自动指标 + 评审打分 + 加权合成，评测结果全程留痕 |
| ④ 迭代与报告 | 循环迭代直至收敛、得分曲线、版本 diff、报告一键导出与分享 |
| ⑤ 用户管理 | 注册 / 登录 / 角色权限，按用户隔离数据，历史可回溯复用 |

**量化目标**：综合得分较初始版本提升 ≥30%；自动评审与人工评分一致率 ≥80%；单轮迭代平均耗时 ≤60s；任务执行成功率 ≥98%。

## 技术栈

| 层次 | 选型 |
|------|------|
| 后端 | Python 3.12+ · FastAPI · SQLAlchemy 2.0 · SQLite |
| Agent 编排 | LangGraph（生成-执行-评估-择优循环） |
| 大模型 | OpenAI 兼容 LLM API（国内直连），用于变体生成 / 任务执行 / 评审打分 |
| 评估指标 | NLTK · rouge · 关键词命中 · 格式校验 |
| 数据处理 | pandas · NumPy |
| 前端 | React 18 · TypeScript · Vite · Ant Design · Zustand · ECharts · TailwindCSS |

## 目录结构

```
prompt-optimizer-agent/
├── 01.code/                      # 可运行源码（前后端分离）
│   └── prompt_optimizer/
│       ├── backend/              # FastAPI + LangGraph 后端
│       │   ├── app/              # api / core / db / llm / models / schemas / services
│       │   ├── tests/            # pytest 测试集
│       │   └── requirements.txt
│       └── frontend/             # React + Vite 前端
├── 02.data/                      # 测试用例集、评分标准、人工校准记录
├── 03.ppt/                       # 项目汇报 PPT、前端模块功能解析
├── 04.实训指导书/                  # 六段式实训教程 + AI 共创过程文档（PRD/UIUX/数据库/API/测试/部署）
├── 05.RAG语料/                    # 19 类 RAG 语料库 + RAG 助手提示词
├── 部署版code/                    # 一键部署包（后端源码 + 前端构建产物 + 启动脚本 + Nginx 配置）
├── score-quality-report/         # 评分质量可视化报告
├── 【规划】项目整体规划v1.0.md
├── 【参数】提示词自动迭代优化智能体v1.0.0.md
└── 提示词自动迭代优化智能体项目任务书V1.0.0.docx
```

> 命名约定：中文目录名 + 编号前缀，便于按顺序理解交付链路（代码 → 数据 → 汇报 → 教程 → 语料）。

## 快速开始

### 方式一：一键部署包（推荐，单端口开箱即用）

单端口模式——前端静态页面由 FastAPI 统一托管，无需另起前端服务。

```bat
cd 部署版code
start_all.bat
```

首次运行会自动安装依赖并从 `.env.example` 生成 `backend/.env`，随后编辑它填入 LLM 配置，重启即可：

```ini
LLM_BASE_URL=https://api.siliconflow.cn/v1
LLM_API_KEY=sk-你的密钥
LLM_DEFAULT_MODEL=deepseek-ai/DeepSeek-V4-Flash
```

访问 **http://localhost:8000**（API 文档 `/docs`）。

> 未配置 LLM 时，登录 / 任务管理 / 用例管理可用；变体生成、任务执行、评审打分、迭代等需 LLM 的功能会报错。

### 方式二：源码开发模式

**后端**

```bash
cd 01.code/prompt_optimizer/backend
pip install -r requirements.txt
cp .env.example .env    # 填入 LLM_BASE_URL / LLM_API_KEY
python -m uvicorn app.main:app --reload --port 8000
```

**前端**

```bash
cd 01.code/prompt_optimizer/frontend
npm install
npm run dev             # http://localhost:5173，/api 已代理到 127.0.0.1:8000
```

**测试**

```bash
cd 01.code/prompt_optimizer/backend && pytest          # 后端单测/集成测试
cd 01.code/prompt_optimizer/frontend && npm test       # 前端组件测试（vitest）
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `JWT_SECRET_KEY` | JWT 签名密钥，**生产环境务必替换为随机长字符串** |
| `LLM_BASE_URL` | 大模型 API 地址（OpenAI 兼容） |
| `LLM_API_KEY` | 大模型 API 密钥 |
| `LLM_DEFAULT_MODEL` | 默认模型名 |
| `DATABASE_URL` | 数据库连接，默认 `sqlite:///./prompt_optimizer.db` |
| `EMBED_MODEL` | 嵌入模型；留空则使用本地词法检索，填写如 `BAAI/bge-m3` 则启用向量检索 |
| `RAG_CORPUS_DIR` | 一键导入的示例语料库目录 |
| `RAG_EVAL_TOP_K` | 评测时默认注入的检索块数 |

## 文档与资料

- **实训教程**：`04.实训指导书/实训01~06 + 附录A/B`（产品需求 → UIUX → 开发任务 → 前端 → 后端 → 测试 → 密钥申请 → Nginx HTTPS）
- **AI 共创过程文档**：`04.实训指导书/AI共创过程文档/`（PRD、UI/UX、开发技术、数据库设计、API 接口、系统测试、部署运维）
- **RAG 语料库**：`05.RAG语料/`（19 类语料 + RAG 助手提示词，可直接用于检索增强问答）
- **评测基准**：`02.data/`（4 类任务用例集、评分标准、人工校准记录）

## 安全与合规

- **敏感配置不入库**：`.env`、`*.db` 已列入 `.gitignore`；仓库仅保留 `.env.example` 模板。请勿把真实密钥写入示例文件。
- **数据隔离**：SQLite 数据库文件含真实用户数据，不随仓库分发。
- **内容合规**：依据《互联网信息服务深度合成管理规定》，AI 生成内容在界面显著标识；系统支持本地化部署，敏感数据不出域。
- **部署建议**：生产环境通过 Nginx 反代 + HTTPS，后端仅监听内网 `127.0.0.1:8000`，配置示例见 `部署版code/nginx.conf`。

---

本项目为教学实训案例，用于演示「AI 共创」模式下的软件工程全流程实践。

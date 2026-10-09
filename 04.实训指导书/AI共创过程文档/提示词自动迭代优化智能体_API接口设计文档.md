# 提示词自动迭代优化智能体 —— API 接口设计文档

| 项目 | 内容 |
|------|------|
| 文档版本 | V2.0.0 |
| 基础路径 | `/api/v1` |
| 技术栈 | FastAPI + Pydantic |
| 配套 PRD | 《提示词自动迭代优化智能体_PRD文档.md》 |
| 配套数据库 | 《提示词自动迭代优化智能体_数据库设计文档.md》 |

---

## 一、通用约定

### 1.1 认证

- 除登录 / 注册 / 公开访问 / 在线调用外，所有接口需携带 `Authorization: Bearer <token>`。
- token 为 JWT，签发后有效期默认 24 小时；登录接口对「IP + 邮箱」实现失败计数与锁定（连续 5 次失败锁定 15 分钟），防止暴力破解。
- 鉴权失败的返回统一为：

```json
{ "code": 401, "message": "未登录或登录已过期", "data": null }
```

### 1.2 响应结构

所有接口统一返回：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

- `code=0` 表示成功；非 0 为业务错误码。
- `data` 为具体业务数据；无数据时可为 `null`。

### 1.3 错误码约定

| code | 含义 |
|------|------|
| 0 | 成功 |
| 1001 | 参数校验失败 |
| 1002 | 资源不存在 |
| 1003 | 无权限 / 数据越权 |
| 1004 | 状态不允许当前操作 |
| 1005 | 大模型调用失败 |
| 1006 | 内部错误 |
| 401 | 未登录 / 登录已过期 |
| 429 | 触发限流（登录锁定 / 在线端点按维度限流） |

### 1.4 分页约定

列表接口分页参数统一为 `page`（默认 1）与 `page_size`（默认 10，最大 100，且 `page ≥ 1`、`10 ≤ page_size ≤ 100`）；返回结构：

```json
{ "items": [], "total": 0, "page": 1, "page_size": 10 }
```

### 1.5 在线调用鉴权（特殊约定）

- 在线服务 `invoke` 接口**仅支持 POST**，使用 `X-Api-Key: sk-xxx` 请求头鉴权（HMAC 恒定时间比较），**不需要 JWT**，可被 curl / Postman / 程序代码直接调用。
- 在线调用按端点维度限流（默认 60 次/分钟），超限返回 HTTP 429。
- 公开报告读取（`/public/reports/*`）仅凭分享 token 访问，免登录、只读。

---

## 二、接口总览

| 模块 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 认证 | POST | /auth/register | 注册 |
| 认证 | POST | /auth/login | 登录（失败锁定） |
| 认证 | POST | /auth/logout | 退出登录 |
| 认证 | GET | /auth/me | 当前用户信息 |
| 任务 | POST | /tasks | 创建任务 |
| 任务 | GET | /tasks | 任务列表 |
| 任务 | GET | /tasks/{task_id} | 任务详情 |
| 任务 | GET | /tasks/{task_id}/best | 获取最优提示词 |
| 任务 | PUT | /tasks/{task_id} | 更新任务 |
| 任务 | DELETE | /tasks/{task_id} | 删除任务 |
| 用例 | POST | /tasks/{task_id}/cases | 添加用例 |
| 用例 | POST | /tasks/{task_id}/cases/import | 批量导入用例 |
| 用例 | GET | /tasks/{task_id}/cases | 用例列表 |
| 用例 | DELETE | /tasks/{task_id}/cases/{case_id} | 删除用例 |
| 迭代 | POST | /tasks/{task_id}/iterations/start | 开始迭代（异步 + 断点续跑） |
| 迭代 | POST | /tasks/{task_id}/iterations/stop | 停止迭代 |
| 迭代 | GET | /tasks/{task_id}/iterations/status | 迭代进度 |
| 迭代 | GET | /tasks/{task_id}/iterations/{round_no}/variants | 某轮变体列表 |
| 迭代 | GET | /tasks/{task_id}/iterations/{round_no}/scores | 得分曲线数据 |
| 迭代 | GET | /tasks/{task_id}/iterations/{round_no}/eval-results | 评估结果明细 |
| 迭代 | POST | /tasks/{task_id}/eval-results/{eval_id}/review | 人工抽检评分 |
| 版本 | GET | /tasks/{task_id}/versions | 版本历史 |
| 版本 | POST | /tasks/{task_id}/versions/{version_id}/freeze | 冻结 / 回退版本 |
| 模板 | GET | /task-templates | 任务类型模板 |
| 模型 | GET | /models | 可用模型列表 |
| 报告 | GET | /tasks/{task_id}/report | 获取优化报告 |
| 报告 | GET | /tasks/{task_id}/report/export | 导出报告（Markdown/JSON） |
| 知识库 | POST | /knowledge-bases | 创建知识库 |
| 知识库 | GET | /knowledge-bases | 我的知识库列表 |
| 知识库 | GET | /knowledge-bases/{kb_id} | 知识库详情 |
| 知识库 | DELETE | /knowledge-bases/{kb_id} | 删除知识库 |
| 知识库 | POST | /knowledge-bases/{kb_id}/docs | 上传/粘贴单篇语料 |
| 知识库 | POST | /knowledge-bases/{kb_id}/docs/bulk | 批量导入多篇语料 |
| 知识库 | POST | /knowledge-bases/{kb_id}/import-corpus | 一键导入示例语料库目录 |
| 知识库 | POST | /knowledge-bases/{kb_id}/retrieve | 检索预览（嵌入/词法双模式） |
| 知识库 | POST | /knowledge-bases/{kb_id}/evaluate | RAG 检索+生成评测（支撑度/忠实度） |
| 在线服务 | POST | /endpoints | 创建在线服务（生成密钥） |
| 在线服务 | GET | /endpoints | 我的在线服务列表 |
| 在线服务 | GET | /endpoints/{endpoint_id} | 在线服务详情（含密钥） |
| 在线服务 | PUT | /endpoints/{endpoint_id} | 更新在线服务（改名/描述/启停） |
| 在线服务 | POST | /endpoints/{endpoint_id}/rotate-key | 轮换密钥 |
| 在线服务 | DELETE | /endpoints/{endpoint_id} | 删除在线服务 |
| 在线服务 | GET | /endpoints/{endpoint_id}/logs | 调用日志 |
| 在线服务 | GET | /endpoints/{endpoint_id}/stats | 调用统计（SQL 聚合） |
| 在线服务 | POST | /endpoints/{endpoint_id}/invoke | 在线调用（X-Api-Key 鉴权，免 JWT，限流） |
| 评测 | POST | /tasks/{task_id}/benchmarks/start | 发起多模型对比评测 |
| 评测 | GET | /tasks/{task_id}/benchmarks | 评测历史列表 |
| 评测 | GET | /tasks/{task_id}/benchmarks/{run_id} | 评测结果详情（得分矩阵） |
| 评测 | GET | /tasks/{task_id}/benchmarks/{run_id}/report | 导出评测报告 |
| 评测 | GET | /benchmarks | 我的全部评测历史（跨任务） |
| 工作流 | POST | /tasks/{task_id}/workflows | 创建工作流（步骤模板 + 占位符） |
| 工作流 | GET | /tasks/{task_id}/workflows | 任务的工作流列表 |
| 工作流 | GET | /tasks/{task_id}/workflows/{wf_id} | 工作流详情（含步骤） |
| 工作流 | PUT | /tasks/{task_id}/workflows/{wf_id} | 更新工作流（可整体替换步骤） |
| 工作流 | DELETE | /tasks/{task_id}/workflows/{wf_id} | 删除工作流 |
| 工作流 | POST | /tasks/{task_id}/workflows/{wf_id}/run | 执行工作流并评测（异步） |
| 工作流 | GET | /tasks/{task_id}/workflows/{wf_id}/runs | 工作流运行历史 |
| 工作流 | GET | /tasks/{task_id}/workflows/{wf_id}/runs/{run_id} | 工作流运行报告 |
| 工作流 | POST | /tasks/{task_id}/workflows/{wf_id}/steps/{seq}/optimize | 优化工作流某步骤（异步） |
| 工作流 | GET | /tasks/{task_id}/workflows/{wf_id}/optimizations | 步骤优化历史 |
| 工作流 | GET | /tasks/{task_id}/workflows/{wf_id}/optimizations/{opt_id} | 步骤优化报告 |
| 分享 | POST | /reports/shares | 创建分享链接 |
| 分享 | GET | /reports/shares | 我的分享列表 |
| 分享 | DELETE | /reports/shares/{share_id} | 撤销分享 |
| 分享 | GET | /public/reports/{token} | 公开：链接元信息（免登录） |
| 分享 | GET | /public/reports/{token}/data | 公开：报告数据（免登录只读） |
| 仪表盘 | GET | /dashboard/overview | 资产总览（SQL 聚合） |
| 仪表盘 | GET | /dashboard/trend | 近 N 天活动趋势（含当天） |
| 仪表盘 | GET | /dashboard/tasks | 任务资产表 |
| 仪表盘 | GET | /dashboard/models | 模型统计（使用分布） |
| 仪表盘 | GET | /dashboard/versions | Prompt 版本库检索 |
| 管理 | GET | /admin/logs | 系统日志（管理员） |
| 管理 | GET | /admin/users | 用户列表（管理员） |
| 管理 | PUT | /admin/users/{user_id} | 修改用户角色 / 启停账号（管理员） |
| 系统 | GET | /health | 健康检查 |

---

## 三、接口详细定义

---

### 3.1 注册 / 登录

#### POST /auth/register

请求体：

```json
{
  "email": "user@example.com",
  "password": "password123",
  "full_name": "张三"
}
```

响应 `data`：

```json
{ "id": 1, "email": "user@example.com", "full_name": "张三", "role": "user" }
```

#### POST /auth/login

请求体：

```json
{ "email": "user@example.com", "password": "password123" }
```

响应 `data`：

```json
{ "token": "eyJhbGci...", "user": { "id": 1, "email": "...", "role": "user" } }
```

安全约束：登录失败按「IP + 邮箱」计数，连续 5 次失败锁定 15 分钟（锁定期间返回 429）；成功登录清零计数。

#### POST /auth/logout

清空登录态（前端同时清理本地用户信息与 HttpOnly cookie）。

#### GET /auth/me

响应 `data`：

```json
{ "id": 1, "email": "...", "full_name": "张三", "role": "user" }
```

---

### 3.2 任务管理

#### POST /tasks（创建任务）

请求体：

```json
{
  "name": "电商文案生成优化",
  "task_type": "text_gen",
  "description": "根据商品信息生成吸引人的电商文案",
  "objective": "提升点击率与转化意图",
  "criteria": "文案需包含卖点、使用场景、行动号召，语言简练有感染力",
  "execution_model": "qwen-plus",
  "judge_model": "qwen-plus",
  "auto_weight": 0.5,
  "judge_weight": 0.5,
  "initial_prompt": "你是一名电商文案专家……",
  "target_score": 85,
  "max_rounds": 5,
  "variants_per_round": 4,
  "concurrency": 2,
  "stagnant_rounds": 2,
  "kb_id": 3,
  "enable_rag": 1
}
```

- `kb_id`：绑定的知识库 id（可选）；`enable_rag=1` 时评测执行会自动检索知识库并注入上下文。
- 迭代终止条件：设置了 `target_score` 时以 `best_score >= target_score` 为准；未设置时按 `max_rounds` / `stagnant_rounds` 收敛判断（连续 stagnant_rounds 轮无提升即停止）。

响应 `data`：

```json
{ "id": 3, "name": "...", "task_type": "text_gen", "status": "pending", "current_round": 0 }
```

#### GET /tasks（任务列表）

查询参数：`page`、`page_size`、`status`（可选）、`keyword`（可选，匹配任务名）。

响应 `data`：

```json
{
  "items": [
    { "id": 3, "name": "电商文案生成优化", "task_type": "text_gen",
      "case_count": 12, "best_score": 82.5, "status": "running",
      "current_round": 3, "created_at": "2026-09-14T10:00:00" }
  ],
  "total": 5, "page": 1, "page_size": 10
}
```

#### GET /tasks/{task_id}（任务详情）

响应 `data` 包含任务全字段、最优提示词、各指标配置。

#### PUT /tasks/{task_id}（更新）

允许更新的字段：`name`、`description`、`objective`、`criteria`、`execution_model`、`judge_model`、`auto_weight`、`judge_weight`、`target_score`、`max_rounds`、`variants_per_round`、`concurrency`、`stagnant_rounds`、`kb_id`、`enable_rag`。其中运行中（`running`）任务禁止修改迭代相关参数，返回 `code=1004`。

#### DELETE /tasks/{task_id}

级联删除该任务下所有数据。运行中任务禁止删除，需先停止。

---

### 3.3 测试用例管理

#### POST /tasks/{task_id}/cases（添加单条用例）

请求体：

```json
{
  "input_text": "商品：无线蓝牙耳机，卖点：降噪、长续航24小时、防水",
  "reference_output": "可选",
  "keywords": ["降噪", "续航", "防水"],
  "run_test": "可选，JSON字符串：{\"inputs\":[[\"hello\"],[\"aba\"]],\"expected\":[false,true]}，用于代码生成类任务的单元测试通过率评估"
}
```

#### POST /tasks/{task_id}/cases/import（批量导入）

`multipart/form-data`，字段 `file`（.json / .csv）。

响应 `data`：

```json
{ "total": 20, "success": 18, "failed": 2, "errors": ["第3行缺少input_text"] }
```

#### GET /tasks/{task_id}/cases

分页返回用例列表。

#### DELETE /tasks/{task_id}/cases/{case_id}

删除指定用例。运行中任务禁止删除，返回 `code=1004`。

---

### 3.4 迭代执行

#### POST /tasks/{task_id}/iterations/start（开始迭代）

前提：任务状态为 `pending`、`stopped` 或 `completed`、存在至少 1 条用例。未填写初始提示词时，系统在首轮迭代前调用大模型按任务描述、优化目标与评分标准自动生成初始提示词。`stopped` 状态重启时从上次 `current_round` 的下一轮继续（断点续跑）；`completed` 状态重启则从第 1 轮重新开始。满足前提则返回成功，否则返回相应错误码。

返回 `data`：

```json
{ "task_id": 3, "task_status": "running", "total_rounds": 10,
  "start_round": 1, "resume": false }
```

接口立即返回，迭代由后端异步任务执行。

#### POST /tasks/{task_id}/iterations/stop（停止）

停止当前迭代循环，保留已产生结果。返回当前状态。

#### GET /tasks/{task_id}/iterations/status（进度查询）

前端每 1.5s 轮询。响应 `data`：

```json
{
  "task_id": 3, "task_status": "running", "current_round": 3, "max_rounds": 10,
  "current_best_score": 82.5,
  "variants_done": 3, "variants_total": 4,
  "cases_done": 10, "cases_total": 12, "cases_success": 10, "cases_failed": 0,
  "message": null
}
```

---

### 3.5 得分曲线与版本

#### GET /tasks/{task_id}/iterations/{round}/variants（某轮变体）

响应 `data`：变体列表，每项含 `variant_no`、`prompt_text`、`strategy_tag`、`score`、`status`。

#### GET /tasks/{task_id}/iterations/{round}/scores（得分曲线）

响应 `data`：

```json
{
  "rounds": [
    { "round": 1, "best_score": 55.0 },
    { "round": 2, "best_score": 63.2 },
    { "round": 3, "best_score": 70.8 }
  ],
  "target_score": 85
}
```

#### GET /tasks/{task_id}/versions（版本历史）

响应 `data`：版本列表（version_no、score、is_best、frozen、created_at）。

#### POST /tasks/{task_id}/versions/{version_id}/freeze（冻结 / 回退）

query 参数 `action`：`freeze`（冻结，不参与择优）或 `revert`（回退：以该版本作为新基准重新开始）。回退前提：任务已停止或已完成。调用示例：`POST /tasks/{task_id}/versions/{version_id}/freeze?action=revert`。

#### GET /tasks/{task_id}/iterations/{round}/eval-results（评估结果明细）

按变体×用例返回该轮的评估明细。响应 `data`：

```json
{
  "items": [
    { "variant_no": 1, "test_case_id": 5, "model_output": "...",
      "bleu": 62.0, "rouge": 70.5, "keyword_hit": 100.0, "format_ok": 1,
      "judge_score": 8, "judge_reason": "卖点清晰……", "total_score": 78.0,
      "manual_score": null, "manual_checked": 0 }
  ],
  "total": 20
}
```

manual_score 为 null 表示该条未抽检。

#### POST /tasks/{task_id}/eval-results/{eval_id}/review（人工抽检评分）

请求体：

```json
{ "manual_score": 9, "manual_note": "人工复核：文案感染力强" }
```

将人工评分写入对应评估记录，置 `manual_checked=1`。用于支撑「自动评审与人工评分一致率」指标的采集与校准。

---

### 3.6 任务类型模板

#### GET /task-templates

响应 `data`：预置模板列表，每项含 `task_type`、`name`、`description_template`、`criteria_template`、`recommended_metrics`、`example_cases`。

---

### 3.7 报告

#### GET /tasks/{task_id}/report（获取报告）

响应 `data` 结构：

```json
{
  "task_id": 3, "task_name": "电商文案生成优化",
  "best_prompt": "最终最优提示词全文",
  "initial_prompt": "初始提示词全文",
  "score_curve": [ { "round": 1, "best_score": 55.0 } ],
  "version_diffs": [ { "from_no": 0, "to_no": 3, "added": "...", "removed": "...", "changed": "..." } ],
  "judge_summary": [ { "round": 3, "best_score": 82.5, "reason": "该版本……" } ],
  "suggestions": ["建议补充更多失败用例", "建议调整评分标准表述"]
}
```

#### GET /tasks/{task_id}/report/export?format=markdown|json

返回对应格式的报告文件下载（`Content-Type: text/markdown` 或 `application/json`），文件名如 `report_task_3_20260914.md`。

---

### 3.8 其他

#### GET /models（可用模型列表）

响应 `data`：模型 id、名称、能力描述。用于前端任务创建时选择执行/评审模型。

#### GET /admin/logs（管理员）

查询参数：`page`、`page_size`、`user_id`（可选）、`result`（可选）。权限不足返回 `code=1003`。

#### GET /admin/users（管理员）

分页返回全部用户（不含密码哈希），每项含 `id`、`email`、`full_name`、`role`、`is_active`、`created_at`。

#### PUT /admin/users/{user_id}（管理员）

请求体：

```json
{ "role": "admin", "is_active": 1 }
```

`role` 与 `is_active` 至少传一项。用于角色管理与账号启停。不能对自身执行禁用操作。权限不足返回 `code=1003`。

---

### 3.9 知识库（RAG）

#### POST /knowledge-bases（创建知识库）

请求体：

```json
{
  "name": "产品手册语料库",
  "description": "用于产品问答的检索语料",
  "embed_model": ""
}
```

- `embed_model` 为空表示本地词法检索（无需外部依赖）；传入嵌入模型名则启用向量检索。

响应 `data`：

```json
{ "id": 1, "name": "产品手册语料库", "embed_model": "", "doc_count": 0, "chunk_count": 0 }
```

#### GET /knowledge-bases（我的知识库列表）

返回知识库列表，每项含 `id`、`name`、`description`、`embed_model`、`doc_count`、`chunk_count`、`created_at`。

#### GET /knowledge-bases/{kb_id}（详情）

返回知识库详情 + 文档列表（`title`、`chunk_count`、`status`、`error`）。

#### DELETE /knowledge-bases/{kb_id}

删除知识库。若存在任务绑定该库，先自动解除任务引用（`kb_id=null, enable_rag=0`）再删除，避免悬空外键。

#### POST /knowledge-bases/{kb_id}/docs（上传单篇语料）

请求体：

```json
{ "title": "使用手册.md", "content": "文档全文……" }
```

响应 `data`：新建文档 `id`、切分后的 `chunk_count`；`doc_count`/`chunk_count` 通过 SQL 原子自增更新。

#### POST /knowledge-bases/{kb_id}/docs/bulk（批量导入）

请求体：`{ "docs": [ { "title": "...", "content": "..." }, ... ] }`。返回导入成功数 / 失败明细。

#### POST /knowledge-bases/{kb_id}/import-corpus（一键导入示例语料）

仅允许从服务端配置目录 `RAG_CORPUS_DIR` 导入预置语料（不接受任意用户路径，防止任意文件读取）。返回导入文档数与块数。

#### POST /knowledge-bases/{kb_id}/retrieve（检索预览）

请求体：

```json
{ "query": "如何配置环境变量？", "top_k": 5 }
```

响应 `data`：命中知识块列表，每项含 `chunk_id`、`doc_title`、`text`、`score`。查询侧嵌入失败时返回空列表（不返回全 0 得分命中，避免注入错误上下文）。

#### POST /knowledge-bases/{kb_id}/evaluate（RAG 评测）

请求体：

```json
{ "cases": [ { "input_text": "...", "reference_output": "..." } ], "top_k": 5 }
```

响应 `data`：每条的检索命中来源列表 + 答案 + 两项 0-100 评分：`support_score`（来源支撑度）、`faithfulness_score`（忠实度）。

---

### 3.10 在线服务

#### POST /endpoints（创建在线服务）

请求体：

```json
{
  "task_id": 3,
  "name": "电商文案-生产端点",
  "description": "对外发布的最优提示词调用",
  "prompt_mode": "best"
}
```

- `prompt_mode`：best=任务最优提示词快照 / initial=初始提示词 / custom=自定义提示词。
- 响应 `data` 含端点信息与 `api_key`（`sk-` 前缀，明文仅本次返回，后续仅展示脱敏末四位）。

#### GET /endpoints / GET /endpoints/{endpoint_id}

端点列表 / 详情（含密钥脱敏、`call_count`、`active`）。

#### PUT /endpoints/{endpoint_id}

更新名称、描述、启停状态（`active` 0/1）。不可修改提示词快照与密钥（轮换走专门接口）。

#### POST /endpoints/{endpoint_id}/rotate-key（轮换密钥）

生成新 `sk-` 密钥（urllib-safe 随机），旧密钥立即失效，历史调用日志保留。响应返回新密钥明文一次。

#### DELETE /endpoints/{endpoint_id}

删除端点及其调用日志。

#### GET /endpoints/{endpoint_id}/logs（调用日志）

分页返回日志（时间、输入、输出、状态、耗时），支持按 `status` 筛选。

#### GET /endpoints/{endpoint_id}/stats（调用统计）

返回 SQL 聚合统计：`total_calls`、`today_calls`、`success_calls`、`failed_calls`、`avg_latency_ms`。

#### POST /endpoints/{endpoint_id}/invoke（在线调用）

**免 JWT**，使用 `X-Api-Key: sk-xxx` 请求头鉴权（HMAC 恒定时间比较）。请求体：

```json
{ "input": "商品：无线蓝牙耳机……" }
```

- 端点停用 / 密钥错误返回 401；触发限流（默认 60 次/分钟）返回 429。
- 响应 `data`：`{ "output": "模型生成结果", "model": "...", "latency_ms": 123 }`。
- 每次调用写 `endpoint_call_logs`，并原子更新 `call_count`。

调用示例（curl）：

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/endpoints/5/invoke" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: sk-xxxxxxxx" \
  -d '{"input": "商品：无线蓝牙耳机……"}'
```

---

### 3.11 模型评测平台

#### POST /tasks/{task_id}/benchmarks/start（发起评测）

请求体：

```json
{
  "name": "四模型横向对比",
  "prompt_mode": "best",
  "models": ["qwen-plus", "deepseek-v3", "glm-4", "kimi"],
  "case_ids": [5, 6, 7],
  "criteria": "评测标准……",
  "sample_rounds": 1
}
```

接口立即返回，评测由后台异步执行；`GET /benchmarks` 可轮询进度。

#### GET /tasks/{task_id}/benchmarks（历史列表）

返回该任务全部评测运行（`status`、`best_model`、`best_score`、`created_at`）。

#### GET /tasks/{task_id}/benchmarks/{run_id}（结果详情）

响应 `data` 结构：

```json
{
  "run_id": 1, "status": "completed", "best_model": "deepseek-v3",
  "models": ["qwen-plus", "deepseek-v3"],
  "matrix": {
    "qwen-plus":   { "avg": 78.2, "per_case": [75.0, 81.4], "judge_reason": "..." },
    "deepseek-v3": { "avg": 84.5, "per_case": [82.0, 87.0], "judge_reason": "..." }
  },
  "recommended_model": "deepseek-v3"
}
```

`matrix` 为「模型 × 用例」得分矩阵，`recommended_model` 为平均分最高的模型。

#### GET /tasks/{task_id}/benchmarks/{run_id}/report（导出报告）

导出评测报告（Markdown / JSON），含矩阵、推荐结论与各模型评语。

#### GET /benchmarks（我的全部评测历史）

跨任务返回当前用户的全部评测运行。

---

### 3.12 多步骤工作流

#### POST /tasks/{task_id}/workflows（创建工作流）

请求体：

```json
{
  "name": "信息抽取-问答两步流",
  "description": "先抽取实体，再基于实体回答",
  "steps": [
    { "seq": 1, "name": "实体抽取", "prompt_template": "从以下文本抽取所有实体：\n{{input}}", "model": "" },
    { "seq": 2, "name": "生成回答", "prompt_template": "基于实体 {{step1.out}} 回答：{{input}}", "model": "" }
  ]
}
```

- 步骤模板支持 `{{input}}`（用例原始输入）与 `{{stepN.out}}`（第 N 步输出）。
- 步骤列表不可为空模板 / 空列表（与前端校验一致），否则返回 `code=1001`。

#### GET /tasks/{task_id}/workflows / GET /tasks/{task_id}/workflows/{wf_id}

工作流列表 / 详情（含步骤）。

#### PUT /tasks/{task_id}/workflows/{wf_id}

更新名称、描述与步骤（可整体替换步骤列表）。

#### DELETE /tasks/{task_id}/workflows/{wf_id}

删除工作流及其运行 / 优化记录。

#### POST /tasks/{task_id}/workflows/{wf_id}/run（执行工作流）

请求体：

```json
{ "run_baseline": 1 }
```

- 异步执行：对任务全部用例做链式执行（占位符逐级解析），`run_baseline=1` 时同时跑单 prompt 基线对照。
- 同一工作流并发发起由后端工作流粒度锁串行化，防止重复运行。
- 返回 `{ "run_id": 3, "status": "running" }`。

#### GET /tasks/{task_id}/workflows/{wf_id}/runs / runs/{run_id}

运行历史 / 运行报告（`avg_score`、`baseline_avg_score`、每用例 `final_output`、`step_trace`、`baseline_score`）。

#### POST /tasks/{task_id}/workflows/{wf_id}/steps/{seq}/optimize（步骤优化）

请求体：

```json
{ "max_rounds": 3 }
```

- 对指定步骤指令做多轮贪心迭代优化（轮次可配置 1/2/3/5），每轮生成变体→整链评测→择优，连续两轮无提升提前终止。
- 优化完成后回写该步骤 `prompt_template`。返回 `{ "optimization_id": 1, "status": "running" }`。

#### GET /tasks/{task_id}/workflows/{wf_id}/optimizations / optimizations/{opt_id}

步骤优化历史 / 优化报告（`base_prompt`、`best_prompt`、`base_score`、`best_score`、`improved`、每轮变体得分）。

---

### 3.13 报告分享

#### POST /reports/shares（创建分享链接）

请求体：

```json
{ "report_type": "benchmark", "target_id": 1, "expires_hours": 168 }
```

- `report_type`：`benchmark`=模型评测 / `optimization`=工作流步骤优化 / `task`=任务迭代。
- `expires_hours`：0 或缺省=永久；否则为有效期小时数。
- 响应 `data`：`{ "id": 1, "token": "a1b2...", "expires_at": "...", "share_url": "/share/a1b2..." }`。

#### GET /reports/shares（我的分享列表）

返回全部分享记录（类型、标题、`token`、`status`、`expires_at`、`view_count`、`created_at`）。

#### DELETE /reports/shares/{share_id}（撤销分享）

撤销后公开访问立即失效（`status=revoked`）。

#### GET /public/reports/{token}（公开元信息，免登录）

返回分享元信息（类型、标题、是否有效、是否过期）。

#### GET /public/reports/{token}/data（公开报告数据，免登录只读）

返回对应类型的只读报告载荷（评测矩阵 / 优化轮次曲线与指令对比 / 任务最优提示词与版本对比）；仅统计 `view_count`，不提供任何编辑能力。token 无效、已撤销或已过期返回 `code=1002`。

---

### 3.14 仪表盘

#### GET /dashboard/overview（资产总览）

响应 `data`：

```json
{
  "tasks": 12, "cases": 268, "iterations": 34,
  "kbs": 3, "endpoints": 5, "workflows": 4, "shares": 6,
  "total_calls": 1820
}
```

统计使用 SQL 聚合函数（`COUNT`/`SUM`），不使用内存计算。

#### GET /dashboard/trend（近 N 天趋势）

查询参数：`days`（默认 7，包含当天）。返回每日活动计数（新建任务、用例、迭代、调用等维度）。

#### GET /dashboard/tasks（任务资产表）

返回最近任务列表（名称、状态、得分、用例数、更新时间）。

#### GET /dashboard/models（模型统计）

返回模型使用分布（各模型执行/评审调用次数与占比）。

#### GET /dashboard/versions（版本库检索）

查询参数：`keyword`（可选）。返回任务最优提示词版本库检索结果（`total` 为实际匹配计数）。

---

## 四、鉴权与数据隔离

- 任务、用例、版本、迭代、报告、人工抽检相关接口，服务端依据 token 解析出的 `user_id` 校验资源属主，非属主访问一律返回 `code=1003`（人工抽检需校验评估记录所属任务的 user_id；版本冻结/回退同样校验任务归属）。
- 知识库、端点、评测、工作流、分享等扩展接口同样以 `user_id` 强校验属主；工作流运行与步骤优化数据必须通过 `workflow_id` 关联过滤用户（`Workflow.user_id`），防止跨租户泄露。
- 管理员接口（`/admin/*`）仅 `role=admin` 可访问；管理员不能对自身执行禁用操作。
- 在线调用（`/endpoints/{id}/invoke`）仅用 `X-Api-Key` 鉴权，不校验 JWT；密钥比对使用 HMAC 恒定时间比较。
- 公开报告（`/public/reports/*`）仅凭 token 访问，且只读；token 无效 / 撤销 / 过期返回 `code=1002`。
- token 过期 / 非法返回 `code=401`。

---

## 五、与前端交互时序

### 5.1 迭代运行

```
前端 POST /iterations/start        → 后端异步启动 LangGraph 循环，立即返回
前端 GET  /iterations/status (每1.5s) → 后端返回实时进度
每轮结束 → 更新 tasks.best_prompt / best_score、写入 prompt_versions
迭代结束（达标/收敛/最大轮次）→ tasks.status=completed
前端 GET /report 显示报告 → GET /report/export 导出 → POST /reports/shares 分享
```

后端异步任务内部流程（Single Responsibility）：变体生成（LLM）→ 批量执行用例（LLM，并发+重试）→ 自动指标（本地 NLTK/rouge）→ 评审打分（LLM）→ 加权合成 → 择优更新 → 终止判断。

### 5.2 知识库 / 在线服务 / 评测 / 工作流 / 分享

```
知识库：POST /knowledge-bases → POST /{kb_id}/docs(/bulk|import-corpus) → POST /{kb_id}/retrieve 预览 → POST /{kb_id}/evaluate 评测
在线服务：POST /endpoints → 外部 POST /endpoints/{id}/invoke（X-Api-Key）→ GET /{id}/logs|stats 观测 → POST /{id}/rotate-key 轮换
评测：POST /tasks/{id}/benchmarks/start（异步）→ GET /{task_id}/benchmarks/{run_id} 轮询矩阵 → GET /report 导出
工作流：POST /tasks/{id}/workflows（步骤模板）→ POST /{wf_id}/run（异步链式执行）→ POST /steps/{seq}/optimize（步骤优化）
分享：POST /reports/shares → 分享 /share/{token} → 免登录 GET /public/reports/{token}/data → DELETE /reports/shares/{id} 撤销
```
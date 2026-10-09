# API接口使用语料库

**主题：** 提示词自动迭代优化智能体 API 接口使用
**适用范围：** 前端开发、后端开发、测试人员、学习者
**版本：** v1.0

---

## Q: 本系统 API 的基础约定是什么？

**A:** API 基础路径为 /api/v1，采用 RESTful 风格；除登录/注册外均需携带 Authorization: Bearer token（JWT，默认 24 小时）；响应统一为 结构 `{code, message, data}`，code=0 表示成功；列表接口分页参数为 page 与 page_size。

**标签：** API约定, RESTful, JWT, 响应结构, 分页

---

## Q: 系统的错误码有哪些？

**A:** 错误码约定：0 成功、1001 参数校验失败、1002 资源不存在、1003 无权限/越权、1004 状态不允许当前操作、1005 大模型调用失败、1006 内部错误。401 表示未登录或登录过期。

**标签：** 错误码, 参数错误, 无权限, 状态不允许, 模型失败

---

## Q: 认证相关的接口有哪些？

**A:** 认证接口包括：POST /auth/register（注册）、POST /auth/login（登录，返回 token 与用户信息）、GET /auth/me（获取当前用户信息）。

**标签：** 认证接口, 注册, 登录, 当前用户

---

## Q: 任务管理相关的接口有哪些？

**A:** 包括：POST /tasks（创建任务）、GET /tasks（任务列表，支持状态与关键词筛选）、GET /tasks/{id}（任务详情）、PUT /tasks/{id}（更新任务）、DELETE /tasks/{id}（删除任务）。

**标签：** 任务接口, 创建, 列表, 详情, 更新, 删除

---

## Q: 测试用例相关的接口有哪些？

**A:** 包括：POST /tasks/{id}/cases（添加单条用例）、POST /tasks/{id}/cases/import（JSON/CSV 批量导入）、GET /tasks/{id}/cases（用例列表）、DELETE /tasks/{id}/cases/{case_id}（删除用例）。

**标签：** 用例接口, 添加, 导入, 列表, 删除

---

## Q: 迭代执行相关的接口有哪些？

**A:** 包括：POST /tasks/{id}/iterations/start（开始迭代，立即返回）、POST /tasks/{id}/iterations/stop（停止迭代）、GET /tasks/{id}/iterations/status（进度查询，前端轮询）、GET /tasks/{id}/iterations/{round}/variants（某轮变体列表）。

**标签：** 迭代接口, 开始, 停止, 进度, 变体

---

## Q: 开始迭代的前提条件是什么？

**A:** 任务状态为 pending/stopped/completed、存在至少 1 条用例；未填初始提示词时首轮前由大模型按任务描述、目标与评分标准自动生成；stopped 重启从上次轮次下轮继续（断点续跑），completed 重启从第 1 轮重来。

**标签：** 迭代前提, 用例条件, 初始提示词, 断点续跑

---

## Q: 迭代进度接口返回哪些数据？

**A:** 返回任务状态、当前轮次、最大轮次、当前最优得分、已完成/总数变体数、已完成/总用例数、成功/失败用例数与消息；前端据此更新进度条与成败计数。

**标签：** 进度接口, 当前轮次, 最优得分, 成败计数

---

## Q: 得分曲线与版本接口有哪些？

**A:** 包括：GET /tasks/{id}/iterations/{round}/scores（各轮最优得分曲线）、GET /tasks/{id}/iterations/{round}/eval-results（评估结果明细）、GET /tasks/{id}/versions（版本历史）、POST /tasks/{id}/versions/{version_id}/freeze（冻结/回退）。

**标签：** 得分曲线, 评估明细, 版本历史, 冻结回退

---

## Q: 人工抽检接口如何使用？

**A:** POST /tasks/{id}/eval-results/{eval_id}/review，请求体传入 manual_score（1-10）与 manual_note；将人工评分写入该评估记录并标记已抽检，用于支撑一致率指标采集与校准。

**标签：** 人工抽检, 人工评分, 一致率, 复核

---

## Q: 报告相关的接口有哪些？

**A:** 包括：GET /tasks/{id}/report（获取优化报告，含最优提示词、得分曲线、版本差异、评分理由汇总、优化建议）、GET /tasks/{id}/report/export?format=markdown|json（导出报告文件）。

**标签：** 报告接口, 优化报告, 导出, Markdown, JSON

---

## Q: 管理相关的接口有哪些？

**A:** 管理员接口包括：GET /admin/logs（系统日志）、GET /admin/users（用户列表）、PUT /admin/users/{user_id}（调整角色/启停账号）；仅 role=admin 可访问，权限不足返回 code=1003。

**标签：** 管理接口, 日志, 用户管理, 权限

---

## Q: 系统如何保证 API 的数据隔离？

**A:** 业务接口经 get_current_user 注入当前用户，服务层依据 token 解析的 user_id 校验资源属主，非属主访问返回 code=1003；管理员接口额外校验 role=admin。

**标签：** 数据隔离, user_id, 属主校验, 权限

---

## Q: API 与前端如何交互？

**A:** 前端调用迭代开始接口立即返回后，通过轮询进度接口获取实时进度；迭代由后端异步任务执行，前端每 1.5 秒查询一次；报告与得分曲线接口读取落库数据，前端据此渲染图表与报告。

**标签：** 前后端交互, 轮询, 异步任务, 数据渲染